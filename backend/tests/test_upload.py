"""
O /upload/ virou um stream SSE (`progress`/`heartbeat`/`done`/`error`) para o request
não ficar minutos ocioso e o navegador não derrubar a conexão. Estes testes fixam o
contrato de fio de `_stream_indexacao` e o comportamento do heartbeat.
"""

import asyncio
import json

import pytest
from app.api.endpoints import upload as upload_mod
from app.api.endpoints.upload import _com_heartbeat, _stream_indexacao
from app.ingestion.pdf import ErroExtracaoPDF
from app.ingestion.pdf_hierarquico import EditalExtraido


def _eventos(linhas: list[str]) -> list[dict]:
    payloads = []
    for linha in linhas:
        assert linha.startswith("data: ") and linha.endswith("\n\n")
        payloads.append(json.loads(linha[len("data: ") : -2]))
    return payloads


async def _coletar(gen) -> list[dict]:
    return _eventos([linha async for linha in gen])


def _edital_fake() -> EditalExtraido:
    return EditalExtraido(
        secoes=[{"ordem": 0, "nivel": 1, "titulo": "X", "caminho": "X", "texto_completo": "t\n"}],
        filhos_brutos=[{"secao_ordem": 0, "tipo": "TextItem", "texto": "t"}],
        texto="texto do edital 11.222.333/0001-81",
        num_paginas=3,
    )


@pytest.fixture
def _patch(monkeypatch):
    """Neutraliza as etapas pesadas — o teste é do fluxo de eventos, não do Docling."""
    monkeypatch.setattr(upload_mod, "documento_tem_texto_nativo", lambda *a, **k: True)
    monkeypatch.setattr(upload_mod, "extrair_estrutura_pdf", lambda *a, **k: _edital_fake())
    monkeypatch.setattr(upload_mod, "_indexar_hierarquico", lambda *a, **k: None)
    monkeypatch.setattr(upload_mod, "extrair_cnpj", lambda _: ["11222333000181"])


def test_fluxo_feliz_emite_progress_e_done_com_cnpjs(_patch):
    eventos = asyncio.run(
        _coletar(
            _stream_indexacao(
                b"%PDF-fake", "edital.pdf",
                thread_id="t1", estado="MA", municipio="São Luís",
            )
        )
    )
    tipos = [e["type"] for e in eventos]
    assert tipos[0] == "progress"
    assert "progress" in tipos
    assert tipos[-1] == "done"
    assert "error" not in tipos
    assert eventos[-1]["cnpjs"] == ["11222333000181"]


def test_falha_na_extracao_vira_evento_error_sem_done(_patch, monkeypatch):
    def _explode(*a, **k):
        raise ErroExtracaoPDF("edital.pdf")

    monkeypatch.setattr(upload_mod, "extrair_estrutura_pdf", _explode)

    eventos = asyncio.run(
        _coletar(
            _stream_indexacao(
                b"x", "edital.pdf", thread_id="t1", estado="MA", municipio="X"
            )
        )
    )
    assert eventos[-1]["type"] == "error"
    assert "PDF" in eventos[-1]["content"]
    assert not any(e["type"] == "done" for e in eventos)


def test_falha_na_indexacao_vira_evento_error(_patch, monkeypatch):
    def _explode(*a, **k):
        raise RuntimeError("mongo fora do ar")

    monkeypatch.setattr(upload_mod, "_indexar_hierarquico", _explode)

    eventos = asyncio.run(
        _coletar(
            _stream_indexacao(
                b"x", "edital.pdf", thread_id="t1", estado="MA", municipio="X"
            )
        )
    )
    assert eventos[-1]["type"] == "error"
    assert not any(e["type"] == "done" for e in eventos)


def test_heartbeat_enquanto_a_tarefa_nao_termina(monkeypatch):
    monkeypatch.setattr(upload_mod, "_HEARTBEAT_SEGUNDOS", 0.05)

    async def _cenario():
        async def _lenta():
            await asyncio.sleep(0.17)
            return "ok"

        tarefa = asyncio.create_task(_lenta())
        linhas = [linha async for linha in _com_heartbeat(tarefa, "Extraindo…", 35)]
        return _eventos(linhas), tarefa.result()

    eventos, resultado = asyncio.run(_cenario())
    assert resultado == "ok"
    assert eventos[0] == {"type": "progress", "content": "Extraindo…", "pct": 35}
    assert [e["type"] for e in eventos[1:]] == ["heartbeat"] * (len(eventos) - 1)
    assert len(eventos) >= 2  # pelo menos um heartbeat


def test_heartbeat_nao_engole_excecao_da_tarefa(monkeypatch):
    monkeypatch.setattr(upload_mod, "_HEARTBEAT_SEGUNDOS", 0.05)

    async def _cenario():
        async def _falha():
            await asyncio.sleep(0.02)
            raise RuntimeError("boom")

        tarefa = asyncio.create_task(_falha())
        async for _ in _com_heartbeat(tarefa, "x", 1):
            pass
        tarefa.result()  # deve re-levantar

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(_cenario())
