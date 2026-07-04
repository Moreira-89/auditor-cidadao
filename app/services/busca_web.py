"""
Integração com a Tavily para busca de informações complementares na web:
monta a query com contexto geográfico (estado/município) e filtra/normaliza
os resultados brutos antes de repassá-los ao LLM.
"""

from langchain_tavily import TavilySearch

# Páginas com menos texto que isso normalmente são erro de acesso, paywall ou lixo
_TAMANHO_MINIMO_CONTEUDO = 200
# Limite por resultado para não estourar o contexto do LLM com várias buscas por turno
_TAMANHO_MAXIMO_CONTEUDO = 2000


def _filtrar_por_tamanho(resultados: list[dict], minimo: int = _TAMANHO_MINIMO_CONTEUDO) -> list[dict]:
    """Mantém apenas resultados cujo conteúdo tenha ao menos `minimo` caracteres."""
    return [resultado for resultado in resultados if len(resultado["content"]) >= minimo]


def _truncar_conteudo(resultados: list[dict], maximo: int = _TAMANHO_MAXIMO_CONTEUDO) -> list[dict]:
    """Trunca o campo "content" de cada resultado para no máximo `maximo` caracteres."""
    # Copia cada dict via **resultado e sobrescreve só o campo "content", preservando os demais
    return [{**resultado, "content": resultado["content"][:maximo]} for resultado in resultados]


def _manter_campos_relevantes(resultados: list[dict]) -> list[dict]:
    """Mantém só os campos relevantes ao LLM (url, title, content), descartando score/raw_content."""
    return [{"url": r["url"], "title": r["title"], "content": r["content"]} for r in resultados]


def processar_resultados_busca(resultados: list[dict]) -> list[dict]:
    """
    Orquestra o pipeline de filtragem sobre os resultados brutos da Tavily:
    descarta conteúdos muito curtos, trunca os muito longos e mantém
    apenas os campos relevantes para o LLM. Exposto separadamente de
    `buscar_na_web` para permitir testar o pipeline de filtragem isolado,
    sem precisar de uma busca real na Tavily (ver testes_locais/).
    """
    resultados = _filtrar_por_tamanho(resultados)
    resultados = _truncar_conteudo(resultados)
    resultados = _manter_campos_relevantes(resultados)
    return resultados


async def buscar_na_web(assunto_busca: str, estado: str, municipio: str) -> list[dict]:
    """
    Busca `assunto_busca` na web, complementando a query com município/estado
    para dar contexto geográfico (o LLM é instruído a não incluí-los sozinho em
    assunto_busca), e retorna os resultados já filtrados/processados.

    A lib da Tavily não expõe uma hierarquia de exceções específica e
    documentada — o chamador deve capturar Exception de forma genérica.
    """
    # search_depth="advanced" prioriza qualidade do conteúdo sobre velocidade da busca
    tavily_tool = TavilySearch(max_results=3, search_depth="advanced")
    query = f"{assunto_busca} {municipio} {estado}"

    result = await tavily_tool.ainvoke({"query": query})
    return processar_resultados_busca(result.get("results", []))
