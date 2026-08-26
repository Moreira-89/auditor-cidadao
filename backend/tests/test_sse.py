"""
A tradução de evento de domínio para o protocolo SSE. O frontend (frontend/js/chat.js)
faz JSON.parse de cada linha `data: ` e despacha por `type`, então estes testes fixam o
contrato de fio entre backend e navegador.
"""

import json

from app.agents.eventos import ErroNoTurno, FerramentaIniciada, TokenGerado, TurnoConcluido
from app.api.endpoints.chat import _para_sse, _stream_sse


def _payload(linha: str) -> dict:
    assert linha.startswith("data: ") and linha.endswith("\n\n")
    return json.loads(linha[len("data: ") : -2])


def test_token_vira_evento_token():
    assert _payload(_para_sse(TokenGerado("A empresa"))) == {
        "type": "token", "content": "A empresa",
    }


def test_ferramenta_vira_status_com_a_mensagem_do_mapa():
    payload = _payload(_para_sse(FerramentaIniciada("buscar_contexto_edital")))
    assert payload["type"] == "status"
    assert "edital" in payload["content"].lower()


def test_ferramenta_desconhecida_cai_no_texto_generico():
    payload = _payload(_para_sse(FerramentaIniciada("tool_que_nao_existe")))
    assert payload == {"type": "status", "content": "Analisando..."}


def test_conclusao_nao_carrega_content():
    assert _payload(_para_sse(TurnoConcluido())) == {"type": "done"}


def test_erro_nao_vaza_detalhe_interno():
    payload = _payload(_para_sse(ErroNoTurno()))
    assert payload["type"] == "error"
    assert "Tente novamente" in payload["content"]


def test_toda_linha_termina_com_linha_em_branco():
    # O separador \n\n é o que delimita um evento no protocolo SSE.
    for evento in (TokenGerado("x"), FerramentaIniciada("y"), TurnoConcluido(), ErroNoTurno()):
        assert _para_sse(evento).endswith("\n\n")


async def test_stream_traduz_a_sequencia_inteira():
    async def eventos():
        yield FerramentaIniciada("buscar_contexto_edital")
        yield TokenGerado("ok")
        yield TurnoConcluido()

    tipos = [_payload(linha)["type"] async for linha in _stream_sse(eventos())]
    assert tipos == ["status", "token", "done"]
