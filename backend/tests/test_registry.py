"""
A verificação de mensagens de status existe para tornar visível uma divergência que,
sem ela, só apareceria como um "Analisando..." genérico na tela do usuário.
"""

import logging
from types import SimpleNamespace

from app.agents.tools import registry
from app.config.tool_status_map import TOOL_STATUS_MAP


def _tool(nome: str):
    return SimpleNamespace(name=nome)


def test_avisa_quando_uma_tool_nao_tem_mensagem(caplog):
    with caplog.at_level(logging.WARNING, logger="auditor_cidadao"):
        registry._conferir_mensagens_de_status([_tool("consultar_receita_federal"), _tool("tool_nova")])
    assert "tool_nova" in caplog.text
    assert "Analisando" in caplog.text


def test_avisa_quando_o_mapa_tem_entrada_orfa(caplog):
    with caplog.at_level(logging.WARNING, logger="auditor_cidadao"):
        registry._conferir_mensagens_de_status([_tool("consultar_receita_federal")])
    assert "sem tool correspondente" in caplog.text


def test_silencioso_quando_tudo_bate(caplog):
    tools = [_tool(nome) for nome in TOOL_STATUS_MAP]
    with caplog.at_level(logging.WARNING, logger="auditor_cidadao"):
        registry._conferir_mensagens_de_status(tools)
    assert caplog.text == ""


def test_todas_as_tools_nativas_tem_mensagem_de_status():
    # Guarda o caso mais provável: alguém adiciona uma tool nativa e esquece o mapa.
    sem_mensagem = {t.name for t in registry.TOOLS_NATIVAS} - TOOL_STATUS_MAP.keys()
    assert not sem_mensagem, f"tools nativas sem mensagem: {sem_mensagem}"


def test_todas_as_tools_mcp_selecionadas_tem_mensagem_de_status():
    sem_mensagem = registry.TOOLS_MCP_SELECIONADAS - TOOL_STATUS_MAP.keys()
    assert not sem_mensagem, f"tools MCP sem mensagem: {sem_mensagem}"


def test_normalizadores_de_cache_cobrem_toda_tool_nativa_que_precisa():
    # Toda tool nativa que recebe CNPJ ou ToolRuntime precisa de normalizador,
    # senão a chave de cache fica errada (CNPJ) ou quebra (ToolRuntime).
    nomes_nativos = {t.name for t in registry.TOOLS_NATIVAS}
    assert set(registry.CACHE_KEY_NORMALIZERS) <= nomes_nativos
