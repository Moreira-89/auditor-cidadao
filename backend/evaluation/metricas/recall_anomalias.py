import re

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

# Formato exigido pelo prompt (app/agents/prompt.py) — ver docs/ia/avaliacao.md.
_PADRAO_ACHADO = re.compile(
    r"\*\*\[ESTADO:\s*(CONFIRMADO|INDÍCIO)\]\s*"
    r"\[NÍVEL DE RISCO:\s*(?:BAIXO|MÉDIO|ALTO|CRÍTICO)\]\s*"
    r"[—-]\s*([A-I])\."
)

def extrair_anomalias(texto_laudo: str) -> list[tuple[str, str]]:
    """Devolve [(codigo, estado), ...] achados no laudo."""
    return [(m.group(2), m.group(1)) for m in _PADRAO_ACHADO.finditer(texto_laudo)]


class RecallAnomaliasMetric(BaseMetric):
    """F1 de anomalias detectadas vs. esperadas, sem LLM — ver docs/ia/avaliacao.md."""

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        esperadas = sorted(set((test_case.metadata or {}).get("anomalias_esperadas", [])))
        detectadas = sorted(
            {codigo for codigo, _ in extrair_anomalias(test_case.actual_output or "")}
        )

        if not esperadas:
            acertou = not detectadas
            self.score = 1.0 if acertou else 0.0
            self.reason = (
                "Caso-controle sem anomalias — nenhum código apontado, como esperado."
                if acertou
                else f"Caso-controle sem anomalias, mas o laudo apontou: {detectadas}."
            )
        else:
            faltantes = [c for c in esperadas if c not in detectadas]
            verdadeiros = len(esperadas) - len(faltantes)
            recall = verdadeiros / len(esperadas)
            precisao = verdadeiros / len(detectadas) if detectadas else 0.0
            soma = precisao + recall
            self.score = 2 * precisao * recall / soma if soma else 0.0
            self.reason = (
                f"Esperadas={esperadas} | Detectadas={detectadas} | "
                f"precisão={precisao:.2f} recall={recall:.2f}"
            )

        score = self.score
        self.success = score >= (self.threshold or 0.0)
        return score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case, *args, **kwargs)

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "Recall de Anomalias"
