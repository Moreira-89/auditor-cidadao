TAMANHO_MINIMO_CONTEUDO = 200
TAMANHO_MAXIMO_CONTEUDO = 2000


def _filtrar_por_tamanho(
    resultados: list[dict], minimo: int = TAMANHO_MINIMO_CONTEUDO
) -> list[dict]:
    """
    Mantém apenas os resultados cujo conteúdo tenha ao menos `minimo` caracteres,
    descartando páginas com pouco texto útil (ex: paywalls, erros de acesso).
    """
    return [
        resultado for resultado in resultados if len(resultado["content"]) >= minimo
    ]


def _truncar_conteudo(
    resultados: list[dict], maximo: int = TAMANHO_MAXIMO_CONTEUDO
) -> list[dict]:
    """
    Trunca o campo "content" de cada resultado para no máximo `maximo` caracteres,
    para limitar o tamanho do contexto enviado ao LLM.
    """
    # Copia cada dict via **resultado e sobrescreve só o campo "content", preservando os demais
    return [
        {**resultado, "content": resultado["content"][:maximo]} for resultado in resultados
    ]


def _manter_campos_relevantes(resultados: list[dict]) -> list[dict]:
    """
    Mantém apenas os campos relevantes para o LLM (url, title e content),
    descartando metadados desnecessários como score e raw_content.
    """
    return [
        {"url": r["url"], "title": r["title"], "content": r["content"]}
        for r in resultados
    ]


def processar_resultados_busca(resultados: list[dict]) -> list[dict]:
    """
    Orquestra o pipeline de filtragem sobre os resultados brutos da Tavily:
    descarta conteúdos muito curtos, trunca os muito longos e mantém
    apenas os campos relevantes para o LLM. Única função deste módulo
    que deve ser importada de fora — as demais são detalhe de implementação.
    """
    resultados = _filtrar_por_tamanho(resultados)
    resultados = _truncar_conteudo(resultados)
    resultados = _manter_campos_relevantes(resultados)
    return resultados
