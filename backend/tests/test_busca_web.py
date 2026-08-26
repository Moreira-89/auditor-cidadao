from app.agents.tools.busca_web import processar_resultados_busca


def _resultado(conteudo: str, url="https://exemplo.gov.br", titulo="Título"):
    return {"url": url, "title": titulo, "content": conteudo, "score": 0.9, "raw_content": "..."}


def test_descarta_conteudo_curto_demais():
    assert processar_resultados_busca([_resultado("erro 403")]) == []


def test_mantem_conteudo_no_limite_minimo():
    assert len(processar_resultados_busca([_resultado("x" * 200)])) == 1


def test_trunca_conteudo_longo_demais():
    [saida] = processar_resultados_busca([_resultado("x" * 5000)])
    assert len(saida["content"]) == 2000


def test_descarta_campos_irrelevantes_ao_llm():
    [saida] = processar_resultados_busca([_resultado("x" * 300)])
    assert set(saida) == {"url", "title", "content"}


def test_lista_vazia_nao_quebra():
    assert processar_resultados_busca([]) == []
