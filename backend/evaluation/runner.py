import asyncio
import sys
from pathlib import Path

from app.config.logging import logger
from app.config.settings import AVALIADOR_MODEL, AVALIADOR_TEMPERATURE
from deepeval import evaluate
from deepeval.evaluate.configs import DisplayConfig
from deepeval.metrics import ContextualRecallMetric, ToolCorrectnessMetric
from deepeval.models import OpenAIModel
from deepeval.test_case import LLMTestCase, ToolCall

from evaluation.dataset.schema import Caso, carregar_casos
from evaluation.execucao import ToolChamada, executar_caso, preparar_ambiente
from evaluation.indexacao import indexar_caso, limpar_edital
from evaluation.metricas.argumentos_tool import ArgumentosToolMetric
from evaluation.metricas.fidelidade import metrica_fidelidade
from evaluation.metricas.recall_anomalias import RecallAnomaliasMetric

RESULTADOS_DIR = Path(__file__).parent / "resultados"


def _tool_call(tool: str, argumentos: dict) -> ToolCall:
    return ToolCall(name=tool, input_parameters=argumentos or None)


def _chamadas_tool(tools_chamadas: list[ToolChamada]) -> list[ToolCall]:
    return [_tool_call(t.tool, t.argumentos) for t in tools_chamadas]


def _tools_esperadas(caso: Caso) -> list[ToolCall]:
    return [_tool_call(t.tool, t.argumentos_esperados) for t in caso.tools_esperadas]


async def _montar_test_case(caso: Caso) -> LLMTestCase:
    """Indexa o edital do caso, roda o agente (caminho real de produção) e monta o
    LLMTestCase pronto pro deepeval. Limpa o Mongo mesmo se a execução falhar."""
    edital = indexar_caso(caso)
    try:
        execucao = await executar_caso(edital)
    finally:
        limpar_edital(edital.edital_id)

    return LLMTestCase(
        input=caso.descricao,
        actual_output=execucao.texto_laudo,
        context=execucao.saidas_ferramentas,
        retrieval_context=[execucao.contexto_edital_recuperado or ""],
        expected_output=caso.contexto_edital_esperado,
        tools_called=_chamadas_tool(execucao.tools_chamadas),
        expected_tools=_tools_esperadas(caso),
        metadata={"anomalias_esperadas": caso.anomalias_esperadas},
        name=caso.id,
    )


# Comuns aos dois lotes (tool certa + argumento certo). O que muda por `tipo` é só o
# que cada suíte cobra como gabarito de conteúdo — ver docs/ia/avaliacao.md.

def _metricas_por_tipo(juiz: OpenAIModel) -> dict[str, list]:
    return {
        "real": [
            ToolCorrectnessMetric(),
            ArgumentosToolMetric(),
            ContextualRecallMetric(threshold=0.7, model=juiz),
            metrica_fidelidade(AVALIADOR_MODEL, AVALIADOR_TEMPERATURE),
        ],
        "sintetico": [
            ToolCorrectnessMetric(),
            ArgumentosToolMetric(),
            RecallAnomaliasMetric(),
            metrica_fidelidade(AVALIADOR_MODEL, AVALIADOR_TEMPERATURE),
        ],
    }


async def _rodar(ids: list[str] | None) -> None:
    casos = carregar_casos()
    if ids:
        casos = [c for c in casos if c.id in ids]
    if not casos:
        raise SystemExit(f"Nenhum caso encontrado para: {ids}")

    logger.info("Iniciando avaliação | casos=%s", [c.id for c in casos])
    preparar_ambiente()

    # Sequencial de propósito: rate limit dos LLMs e logs legíveis.
    pares = [(caso, await _montar_test_case(caso)) for caso in casos]

    juiz = OpenAIModel(model=AVALIADOR_MODEL, temperature=AVALIADOR_TEMPERATURE)
    metricas_por_tipo = _metricas_por_tipo(juiz)

    RESULTADOS_DIR.mkdir(exist_ok=True)
    aprovado_geral = True
    # Um evaluate() por tipo: real e sintético cobram métricas diferentes, e o
    # deepeval só aceita uma lista de métricas global por chamada.
    for tipo, metricas in metricas_por_tipo.items():
        test_cases = [tc for caso, tc in pares if caso.tipo == tipo]
        if not test_cases:
            continue
        resultado = evaluate(
            test_cases=test_cases,
            metrics=metricas,
            display_config=DisplayConfig(
                # inspect_after_run abre um prompt interativo (questionary) no fim da
                # rodada — trava um script não-interativo esperando input que nunca chega.
                inspect_after_run=False,
                results_folder=str(RESULTADOS_DIR),  # grava test_run_<timestamp>.json
            ),
        )
        aprovado_geral &= all(r.success for r in resultado.test_results)

    if not aprovado_geral:
        sys.exit(1)


if __name__ == "__main__":
    import logging
    import os
    import subprocess
    from datetime import datetime, timezone

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Duplica tudo que sai no terminal (logs + as tabelas do deepeval) também
    # pro arquivo, igual a `| tee` — inclusive o que não passa por `logging`.
    # Guarda uma cópia dos fds originais: sem isso, o `tee` nunca vê EOF no
    # stdin dele (o fd 1/2 duplicado continua aberto) e trava no tee.wait().
    RESULTADOS_DIR.mkdir(exist_ok=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = RESULTADOS_DIR / f"log_{carimbo}.txt"
    stdout_original = os.dup(1)
    stderr_original = os.dup(2)
    tee = subprocess.Popen(["tee", str(log_path)], stdin=subprocess.PIPE)
    assert tee.stdin is not None
    os.dup2(tee.stdin.fileno(), 1)
    os.dup2(tee.stdin.fileno(), 2)
    tee.stdin.close()

    try:
        asyncio.run(_rodar(sys.argv[1:] or None))
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(stdout_original, 1)
        os.dup2(stderr_original, 2)
        os.close(stdout_original)
        os.close(stderr_original)
        tee.wait()
