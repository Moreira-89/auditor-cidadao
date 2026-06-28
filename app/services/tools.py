import asyncio
import re

import httpx
from langchain.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState
from typing_extensions import Annotated
from validate_docbr import CNPJ

from app.core.dependencies import gerenciador
from app.models.consulta_cnpj import ConsultaCNPJ


@tool(args_schema=ConsultaCNPJ)
async def consultar_receita_federal(cnpj: str) -> dict:
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


# Lista de tools nativas do projeto — combinada com as MCP tools no startup pelo lifespan
TOOLS: list[BaseTool] = [consultar_receita_federal, buscar_contexto_edital]
