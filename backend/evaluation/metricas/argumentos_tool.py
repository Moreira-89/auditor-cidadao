from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


def _somente_digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


def _normalizar(args: dict) -> dict:
    return {
        chave: _somente_digitos(valor) if chave == "cnpj" and isinstance(valor, str) else valor
        for chave, valor in args.items()
    }


class ArgumentosToolMetric(BaseMetric):
    """Complementa o ToolCorrectnessMetric nativo — ver docs/ia/avaliacao.md."""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        esperadas_com_args = [
            t for t in (test_case.expected_tools or []) if t.input_parameters
        ]
        chamadas = test_case.tools_called or []

        if not esperadas_com_args:
            self.score = 1.0
            self.reason = "Nenhuma tool esperada exige argumento específico."
            self.success = True
            return self.score

        faltantes = []
        for esperada in esperadas_com_args:
            alvo = _normalizar(esperada.input_parameters or {})
            casou = any(
                c.name == esperada.name
                and all(_normalizar(c.input_parameters or {}).get(k) == v for k, v in alvo.items())
                for c in chamadas
            )
            if not casou:
                faltantes.append(f"{esperada.name}{esperada.input_parameters}")

        score = 1.0 - len(faltantes) / len(esperadas_com_args)
        self.score = score
        self.reason = f"Faltantes: {faltantes}" if faltantes else "Todos os argumentos esperados batem."
        self.success = score >= (self.threshold or 0.0)
        return score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case, *args, **kwargs)

    @property
    def __name__(self) -> str:  # type: ignore[override]
        return "Argumentos da Tool"
