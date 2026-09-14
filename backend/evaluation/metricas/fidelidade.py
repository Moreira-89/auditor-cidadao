from deepeval.metrics import GEval
from deepeval.metrics.g_eval import Rubric
from deepeval.test_case import SingleTurnParams

from evaluation.juiz import construir_juiz


def metrica_fidelidade(modelo_juiz: str, temperatura: float = 0.0, threshold: float = 0.6) -> GEval:
    """G-Eval de Fidelidade — rubric e racional completos em docs/ia/avaliacao.md."""
    return GEval(
        name="Fidelidade",
        evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.CONTEXT],
        evaluation_steps=[
            (
                "Liste cada afirmação factual do laudo em ACTUAL_OUTPUT — valores, datas, "
                "CNPJs, situação cadastral, cláusulas citadas, nível de risco de cada achado. "
                "Ignore conectivo e juízo de valor."
            ),
            (
                "Para cada afirmação, procure em CONTEXT um trecho que a sustente literalmente "
                "ou por paráfrase direta (mesmo dado, palavras diferentes)."
            ),
            (
                "Marque cada afirmação como SUSTENTADA ou NÃO SUSTENTADA. Uma afirmação que "
                "EXTRAPOLA o dado da fonte (ex.: fonte diz '3 sanções', laudo diz 'sanções "
                "recorrentes e graves') conta como NÃO SUSTENTADA, mesmo sem inventar dado novo."
            ),
            "Conte quantas afirmações ficaram NÃO SUSTENTADAS antes de aplicar o rubric.",
        ],
        rubric=[
            Rubric(
                score_range=(5, 5), expected_outcome="Todas as afirmações sustentadas."
            ),
            Rubric(
                score_range=(4, 4),
                expected_outcome="1 não sustentada, detalhe menor que não muda o achado.",
            ),
            Rubric(
                score_range=(3, 3),
                expected_outcome="1 não sustentada que afeta a evidência de um achado.",
            ),
            Rubric(
                score_range=(2, 2),
                expected_outcome="2+ não sustentadas, ou 1 que inventa dado central "
                "(CNPJ, valor, sanção, cláusula) sem base em nenhuma fonte.",
            ),
            Rubric(
                score_range=(1, 1),
                expected_outcome="Achado (CONFIRMADO/INDÍCIO) cuja evidência central "
                "não existe em nenhuma fonte consultada.",
            ),
        ],
        threshold=threshold,
        model=construir_juiz(modelo_juiz, temperatura),
    )
