from typing import Annotated

from langchain.tools import ToolRuntime, tool
from langchain_tavily import TavilySearch
from pydantic import Field

# Páginas com menos texto que isso normalmente são erro de acesso, paywall ou lixo
_TAMANHO_MINIMO_CONTEUDO = 200
# Limite por resultado para não estourar o contexto do LLM com várias buscas por turno
_TAMANHO_MAXIMO_CONTEUDO = 2000


def processar_resultados_busca(resultados: list[dict]) -> list[dict]:
    """
    Filtra os resultados brutos da Tavily: descarta conteúdos curtos demais,
    trunca os longos demais e mantém só os campos que interessam ao LLM
    (url, title, content), descartando score/raw_content.

    Função pura, separada da chamada de rede de propósito: é testável sem
    Tavily nenhuma, só passando uma lista de dicts.
    """
    return [
        {
            "url": r["url"],
            "title": r["title"],
            "content": r["content"][:_TAMANHO_MAXIMO_CONTEUDO],
        }
        for r in resultados
        if len(r["content"]) >= _TAMANHO_MINIMO_CONTEUDO
    ]


async def _buscar_na_web(assunto_busca: str, estado: str, municipio: str) -> list[dict]:
    """Busca na Tavily, complementando a query com município/estado, e filtra o resultado."""
    # search_depth="advanced" prioriza qualidade do conteúdo sobre velocidade da busca
    tavily = TavilySearch(max_results=3, search_depth="advanced")
    resultado = await tavily.ainvoke({"query": f"{assunto_busca} {municipio} {estado}"})
    return processar_resultados_busca(resultado.get("results", []))


@tool
async def buscar_informacao_web(
    assunto_busca: Annotated[
        str,
        Field(
            description="Termo ou frase curta de pesquisa. Seja específico. NÃO inclua cidade, estado ou país.",
            min_length=5,
        ),
    ],
    runtime: ToolRuntime,
) -> dict:
    """
    Busca informações atualizadas na internet sobre um tema específico.

    Use esta ferramenta sempre que precisar de contexto adicional, notícias recentes,
    ou informações complementares sobre um assunto relacionado ao edital ou à licitação.
    A busca é feita em fontes confiáveis e relevantes para garantir a qualidade da informação.

    Args:
        assunto_busca: Termo ou frase curta de pesquisa. Seja específico. NÃO inclua cidade, estado ou país.

    Returns:
        Em sucesso: dicionário com a chave "results", contendo os trechos mais relevantes encontrados na web.
        Em falha: dicionário com a chave "error" descrevendo o problema encontrado.
    """
    try:
        resultados = await _buscar_na_web(
            assunto_busca, runtime.state["estado"], runtime.state["municipio"]
        )
    except Exception as e:  # noqa: BLE001
        # A lib da Tavily não expõe uma hierarquia de exceções específica e documentada
        # (indisponibilidade da API, cota excedida, chave ausente/inválida caem todas aqui)
        return {"error": f"Falha ao buscar informações na web: {e!s}"}

    return {"results": resultados}
