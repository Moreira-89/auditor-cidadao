import asyncio
import re

import httpx
from dotenv import load_dotenv
from langchain.tools import BaseTool, tool
from langchain_tavily import TavilySearch
from langgraph.prebuilt import InjectedState
from pydantic import Field
from typing_extensions import Annotated
from validate_docbr import CNPJ

from app.core.dependencies import gerenciador
from app.utils.filtragem_resultados_web import processar_resultados_busca

load_dotenv()


@tool
async def consultar_receita_federal(
    cnpj: Annotated[
        str,
        Field(
            description='CNPJ da empresa encontrado no texto. Retorne APENAS os 14 dígitos numéricos, sem pontos, barras ou traços.',
            min_length=14,
            max_length=14,
        ),
    ],
) -> dict:
    """
    Consulta os dados cadastrais de uma empresa brasileira na Receita Federal a partir do CNPJ.

    Use esta ferramenta sempre que precisar verificar a situação cadastral, razão social,
    CNAE ou data de início de atividade de uma empresa mencionada no edital ou nos resultados
    de licitação. Aceita o CNPJ formatado ("12.345.678/0001-99") ou apenas numérico ("12345678000199").

    Args:
        cnpj: O CNPJ da empresa a ser consultada.

    Returns:
        Em sucesso: dicionário com razão social, nome fantasia, situação cadastral, CNAE e data de início.
        Em falha: dicionário com a chave "error" descrevendo o problema encontrado.
    """
    # Remove pontuação e hífens para padronizar o CNPJ antes de validar e consultar
    cnpj_limpo = re.sub(r"[./-]", "", cnpj)

    # Valida matematicamente os dígitos verificadores antes de fazer a requisição HTTP
    if not CNPJ().validate(cnpj_limpo):
        return {
            "error": f"CNPJ inválido: '{cnpj}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal."
        }

    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)

        if response.status_code == 200:
            data = response.json()
            # Retorna apenas os campos relevantes para auditoria, descartando dados de endereço e telefone
            return {
                "razao_social": data.get("razao_social"),
                "nome_fantasia": data.get("nome_fantasia"),
                "descricao_situacao_cadastral": data.get(
                    "descricao_situacao_cadastral"
                ),
                "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao"),
                "data_inicio_atividade": data.get("data_inicio_atividade"),
            }
        return {
            "error": f"Receita Federal retornou status {response.status_code} para o CNPJ {cnpj_limpo}"
        }

    except httpx.TimeoutException:
        return {
            "error": f"Timeout ao consultar o CNPJ {cnpj_limpo}: o servidor da BrasilAPI não respondeu a tempo."
        }

    except httpx.RequestError as e:
        # Captura erros de conexão, DNS, SSL, redirect loop, etc.
        return {"error": f"Falha de conexão ao consultar o CNPJ {cnpj_limpo}: {str(e)}"}


@tool
async def buscar_contexto_edital(
    pergunta: str,
    # InjectedState puxa o valor direto do AgentState, invisível para o LLM e para o schema da tool
    estado: Annotated[str, InjectedState("estado")],
    municipio: Annotated[str, InjectedState("municipio")],
) -> str:
    """
    Busca trechos relevantes do edital ativo no banco vetorial com base em uma pergunta.

    Use esta ferramenta sempre que precisar encontrar regras, prazos, exigências, penalidades,
    critérios de julgamento ou qualquer cláusula específica do edital em análise. A busca é
    semântica — não é necessário usar as palavras exatas do edital, basta descrever o que procura.

    Args:
        pergunta: A dúvida ou termo específico a ser pesquisado no texto do edital.

    Returns:
        Trechos do edital mais relevantes para a pergunta, prontos para análise.
        Se nenhum trecho for encontrado, retorna uma mensagem informando que o edital pode não estar indexado.
    """
    # asyncio.to_thread garante que a query síncrona ao Pinecone não bloqueie o event loop
    return await asyncio.to_thread(
        gerenciador.buscar_contexto,
        pergunta=pergunta,
        estado=estado,
        municipio=municipio,
    )


@tool
async def buscar_informacao_web(
    assunto_busca: Annotated[
        str,
        Field(
            description="Termo ou frase curta de pesquisa. Seja específico. NÃO inclua cidade, estado ou país.",
            min_length=5,
        ),
    ],
    # InjectedState puxa o valor direto do AgentState, invisível para o LLM e para o schema da tool
    estado: Annotated[str, InjectedState("estado")],
    municipio: Annotated[str, InjectedState("municipio")],
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

    # search_depth="advanced" prioriza qualidade do conteúdo sobre velocidade da busca
    tavily_tool = TavilySearch(max_results=3, search_depth="advanced")

    # Concatena estado e município para dar contexto geográfico à busca, já que o LLM é instruído a não incluí-los em assunto_busca
    query = f"{assunto_busca} {municipio} {estado}"

    try:
        result = await tavily_tool.ainvoke({"query": query})
    except Exception as e:
        # A lib da Tavily não expõe uma hierarquia de exceções específica e documentada
        # (indisponibilidade da API, cota excedida, chave ausente/inválida caem todas aqui)
        return {"error": f"Falha ao buscar informações na web: {str(e)}"}

    return {"results": processar_resultados_busca(result.get("results", []))}


# Lista de tools nativas do projeto — combinada com as MCP tools no startup pelo lifespan
TOOLS: list[BaseTool] = [
    consultar_receita_federal,
    buscar_contexto_edital,
    buscar_informacao_web,
]
