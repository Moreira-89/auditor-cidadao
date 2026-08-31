import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.config.logging import logger

from evaluation.aprovacao import MetricasDoCaso, avaliar_aprovacao, formatar_relatorio
from evaluation.dataset.schema import Caso, carregar_casos
from evaluation.execucao import executar_caso, preparar_ambiente
from evaluation.indexacao import indexar_caso, limpar_namespace
from evaluation.metricas.aderencia_tools import avaliar_aderencia
from evaluation.metricas.ragas import avaliar_ragas
from evaluation.metricas.recall_anomalias import avaliar_recall_anomalias

RESULTADOS_DIR = Path(__file__).parent / "resultados"

async def _avaliar_caso(caso: Caso) -> dict:
    edital = indexar_caso(caso)
    try:
        execucao = await executar_caso(edital)
        aderencia = avaliar_aderencia(caso.tools_esperadas, execucao.tools_chamadas)
        recall = avaliar_recall_anomalias(caso.anomalias_esperadas, execucao.laudo)
        ragas = await avaliar_ragas(caso, execucao)
    finally:
        # Sempre limpa, mesmo se a execução ou o RAGAS estourarem no meio.
        limpar_namespace(edital.namespace)

    return {
        "caso_id": caso.id,
        "descricao": caso.descricao,
        "laudo": execucao.laudo,
        "texto_laudo": execucao.texto_laudo,
        "saidas_ferramentas": execucao.saidas_ferramentas,
        "contexto_edital_recuperado": execucao.contexto_edital_recuperado,
        "tools_chamadas": [t.model_dump() for t in execucao.tools_chamadas],
        "aderencia_tools": aderencia.model_dump(),
        "recall_anomalias": recall.model_dump(),
        "ragas": ragas.model_dump(),
    }

async def _rodar(ids: list[str] | None) -> None:
    casos = carregar_casos()
    if ids:
        casos = [c for c in casos if c.id in ids]
    if not casos:
        raise SystemExit(f"Nenhum caso encontrado para: {ids}")

    logger.info("Iniciando avaliação | casos=%s", [c.id for c in casos])
    preparar_ambiente()

    # Sequencial de propósito: namespaces do Pinecone, rate limit dos LLMs e logs legíveis.
    detalhes = [await _avaliar_caso(caso) for caso in casos]

    metricas_por_caso = [
        MetricasDoCaso(
            caso_id=d["caso_id"],
            aderencia_tools=d["aderencia_tools"]["score"],
            recall_anomalias=d["recall_anomalias"]["score"],
            faithfulness=d["ragas"]["faithfulness"],
            context_recall=d["ragas"]["context_recall"],
        )
        for d in detalhes
    ]
    aprovacao = avaliar_aprovacao(metricas_por_caso)

    RESULTADOS_DIR.mkdir(exist_ok=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = RESULTADOS_DIR / f"avaliacao_{carimbo}.json"
    destino.write_text(
        json.dumps(
            {"aprovacao": aprovacao.model_dump(), "casos": detalhes},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(formatar_relatorio(aprovacao))
    print(f"\nRelatório completo: {destino}")

if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    asyncio.run(_rodar(sys.argv[1:] or None))