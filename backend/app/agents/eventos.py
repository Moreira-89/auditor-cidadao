from dataclasses import dataclass


@dataclass(frozen=True)
class TokenGerado:
    """Um fragmento de texto da resposta, conforme o modelo o produz."""

    texto: str


@dataclass(frozen=True)
class FerramentaIniciada:
    """O agente começou a executar uma ferramenta. `nome` é o nome técnico da tool."""

    nome: str


@dataclass(frozen=True)
class TurnoConcluido:
    """O agente terminou de responder, sem erro."""


@dataclass(frozen=True)
class ErroNoTurno:
    """A execução falhou. A causa já foi registrada no log, com o thread_id."""


EventoDoTurno = TokenGerado | FerramentaIniciada | TurnoConcluido | ErroNoTurno
