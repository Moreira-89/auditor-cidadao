# pyright: reportMissingImports=false, reportCallIssue=false
# ragas 0.3.9 não publica type stubs — pyright não resolve as classes; runtime ok.
import os
import re

from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from ragas import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, LLMContextRecall

from evaluation.dataset.schema import Caso
from evaluation.execucao import ResultadoExecucao

# Juiz do RAGAS: gpt-4o por padrão (o gpt-4o-mini dá nota instável para o mesmo
# contexto). Configurável por AVALIADOR_MODEL / AVALIADOR_TEMPERATURE no .env.
MODELO_JUIZ = os.getenv("AVALIADOR_MODEL", "openai:gpt-4o").removeprefix("openai:")
TEMPERATURA_JUIZ = float(os.getenv("AVALIADOR_TEMPERATURE", "0.0"))
PERGUNTA_LAUDO = (
    "Faça o laudo de auditoria do edital e das empresas vencedoras, apontando anomalias."
)

# Corta o laudo no início das seções de "Verificações ..." — o faithfulness mede se
# os ACHADOS estão fundamentados, não a prosa de "o que não deu para verificar", que
# é meta-raciocínio sem valor literal de ferramenta para o juiz ancorar.
_CORTE_ACHADOS = re.compile(r"\n#+\s*Verifica[cç][oõ]es\b", re.IGNORECASE)


def _resumo_e_achados(texto_laudo: str) -> str:
    corte = _CORTE_ACHADOS.search(texto_laudo)
    return texto_laudo[: corte.start()].strip() if corte else texto_laudo

class ResultadoRagas(BaseModel):
    faithfulness: float | None
    context_recall: float | None


def _juiz():
    return LangchainLLMWrapper(
        ChatOpenAI(model=MODELO_JUIZ, temperature=TEMPERATURA_JUIZ)
    )

async def avaliar_ragas(caso: Caso, resultado: ResultadoExecucao) -> ResultadoRagas:
    juiz = _juiz()

    faithfulness_score: float | None = None
    resumo_e_achados = _resumo_e_achados(resultado.texto_laudo)
    if resultado.saidas_ferramentas and resumo_e_achados:
        amostra = SingleTurnSample(
            user_input=PERGUNTA_LAUDO,
            retrieved_contexts=resultado.saidas_ferramentas,
            response=resumo_e_achados,
        )
        faithfulness_score = float(
            await Faithfulness(llm=juiz).single_turn_ascore(amostra)
        )

    context_recall_score: float | None = None
    if caso.contexto_edital_esperado:
        amostra = SingleTurnSample(
            user_input=PERGUNTA_LAUDO,
            retrieved_contexts=[resultado.contexto_edital_recuperado or ""],
            response=resultado.texto_laudo,
            reference=caso.contexto_edital_esperado,
        )
        context_recall_score = float(
            await LLMContextRecall(llm=juiz).single_turn_ascore(amostra)
        )

    return ResultadoRagas(
        faithfulness=faithfulness_score,
        context_recall=context_recall_score,
    )