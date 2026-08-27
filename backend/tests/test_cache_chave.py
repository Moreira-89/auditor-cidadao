"""
A chave de cache é calculada a partir dos argumentos crus que o LLM envia. Estes testes
cobrem os dois normalizadores que existem para que isso não gere chave errada — o
segundo nasceu de um TypeError que derrubava duas tools em produção.
"""

from types import SimpleNamespace

import pytest

from app.agents.tools.cache import _gerar_chave
from app.agents.tools.registry import CACHE_KEY_NORMALIZERS


def test_cnpj_formatado_e_so_digitos_geram_a_mesma_chave():
    formatado = _gerar_chave(
        "consultar_receita_federal", {"cnpj": "11.222.333/0001-81"}, CACHE_KEY_NORMALIZERS
    )
    digitos = _gerar_chave(
        "consultar_receita_federal", {"cnpj": "11222333000181"}, CACHE_KEY_NORMALIZERS
    )
    assert formatado == digitos


def test_cnpjs_diferentes_geram_chaves_diferentes():
    a = _gerar_chave("consultar_receita_federal", {"cnpj": "11222333000181"}, CACHE_KEY_NORMALIZERS)
    b = _gerar_chave("consultar_receita_federal", {"cnpj": "11444777000161"}, CACHE_KEY_NORMALIZERS)
    assert a != b


def _runtime(estado: str, municipio: str):
    """Imita o ToolRuntime: o que importa aqui é ele NÃO ser serializável em JSON."""
    return SimpleNamespace(state={"estado": estado, "municipio": municipio})


def test_toolruntime_sem_normalizador_quebra_a_chave():
    # Regressão: sem o normalizador, calcular a chave levantava
    # "TypeError: Object of type ... is not JSON serializable" em TODA chamada
    # de buscar_contexto_edital e buscar_informacao_web.
    with pytest.raises(TypeError):
        _gerar_chave("buscar_contexto_edital", {"pergunta": "prazo", "runtime": _runtime("PA", "Belém")})


def test_toolruntime_com_normalizador_gera_chave():
    chave = _gerar_chave(
        "buscar_contexto_edital",
        {"pergunta": "prazo", "runtime": _runtime("PA", "Belém")},
        CACHE_KEY_NORMALIZERS,
    )
    assert chave.startswith("mcp_cache:buscar_contexto_edital_")


def test_mesma_pergunta_em_municipios_diferentes_nao_compartilha_cache():
    # A correção do TypeError não pode ter custado a separação por município:
    # reaproveitar o contexto de outro edital seria um erro de auditoria.
    belem = _gerar_chave(
        "buscar_contexto_edital",
        {"pergunta": "prazo", "runtime": _runtime("PA", "Belém")},
        CACHE_KEY_NORMALIZERS,
    )
    macapa = _gerar_chave(
        "buscar_contexto_edital",
        {"pergunta": "prazo", "runtime": _runtime("AP", "Macapá")},
        CACHE_KEY_NORMALIZERS,
    )
    assert belem != macapa


def test_ordem_dos_argumentos_nao_muda_a_chave():
    a = _gerar_chave("t", {"x": 1, "y": 2})
    b = _gerar_chave("t", {"y": 2, "x": 1})
    assert a == b
