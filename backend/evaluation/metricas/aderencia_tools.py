from pydantic import BaseModel

from evaluation.dataset.schema import ToolEsperada
from evaluation.execucao import ToolChamada


class ResultadoAderencia(BaseModel):
    score: float
    esperadas: list[str]
    chamadas: list[str]
    faltantes: list[str]

def _somente_digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


def _normalizar_args(args: dict) -> dict:
    # CNPJ pode chegar "47.417.848/0001-84" da IA e "47417848000184" do gabarito.
    return {
        chave: _somente_digitos(valor) if chave == "cnpj" and isinstance(valor, str) else valor
        for chave, valor in args.items()
    }

def _casa(esperada: ToolEsperada, chamada: ToolChamada) -> bool:
    if esperada.tool != chamada.tool:
        return False
    esperados = _normalizar_args(esperada.argumentos_esperados)
    reais = _normalizar_args(chamada.argumentos)
    return all(reais.get(chave) == valor for chave, valor in esperados.items())

def avaliar_aderencia(
    tools_esperadas: list[ToolEsperada],
    tools_chamadas: list[ToolChamada],
) -> ResultadoAderencia:
    nomes_chamados = [c.tool for c in tools_chamadas]
    if not tools_esperadas:
        return ResultadoAderencia(score=1.0, esperadas=[], chamadas=nomes_chamados, faltantes=[])

    faltantes = [
        e.tool for e in tools_esperadas if not any(_casa(e, c) for c in tools_chamadas)
    ]
    return ResultadoAderencia(
        score=1.0 - len(faltantes) / len(tools_esperadas),
        esperadas=[e.tool for e in tools_esperadas],
        chamadas=nomes_chamados,
        faltantes=faltantes,
    )