"""
As 4 tools nativas ATIVAS do projeto, passadas ao agente junto com as tools MCP
do PNCP (ver app/services/lifespan.py): consulta cadastral (Receita Federal),
busca semântica no edital indexado (Pinecone), busca web (Tavily) e verificação
de sanções (CEIS/CNEP do Portal da Transparência).

Cada tool aqui é intencionalmente um wrapper fino: valida e normaliza os
argumentos vindos do LLM, delega a chamada externa de verdade para um módulo
de serviço dedicado (app/services/consulta_*.py, busca_web.py) e traduz o
resultado (ou a exceção) em algo que o LLM consegue interpretar. Isso mantém
este arquivo legível conforme o número de tools cresce, e permite reusar a
lógica de integração fora do contexto de agente (scripts, testes, endpoints).

NOTA — buscar_contratos_fornecedor_pncp (histórico de contratos entre um
fornecedor e um órgão no PNCP) está definida abaixo mas DESATIVADA de propósito:
removida de TOOLS e do SYSTEM_PROMPT porque a varredura de todas as modalidades
de um órgão pode levar vários minutos sob o rate limit do PNCP (ver
app/services/consulta_pncp.py), o que arrisca derrubar o streaming SSE em
produção antes de terminar. O código fica pronto para ser reativado depois que
esse ponto for resolvido (ex.: heartbeats periódicos no SSE, ou escopo mais
restrito de varredura) — só voltar a incluí-la na lista TOOLS e na seção
CAPACIDADES DISPONÍVEIS do SYSTEM_PROMPT.
"""

import asyncio
import os
import re

import httpx
from dotenv import load_dotenv
from langchain.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState
from pydantic import Field
from typing_extensions import Annotated
from validate_docbr import CNPJ

from app.core.dependencies import gerenciador
from app.services.busca_web import buscar_na_web
from app.services.consulta_pncp import buscar_contratos_por_fornecedor
from app.services.consulta_receita_federal import consultar_cnpj
from app.services.consulta_sancoes import consultar_sancoes

load_dotenv()


@tool
async def consultar_receita_federal(
    cnpj: Annotated[
        str,
        Field(
            description='CNPJ da empresa encontrado no texto. Aceita formatado ("12.345.678/0001-99") ou apenas numérico ("12345678000199").',
            min_length=14,
            max_length=18,
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
        Em sucesso: dicionário com razão social, nome fantasia, situação cadastral, CNAE,
        data de início de atividade e endereço (logradouro, número, bairro, município, UF, CEP).
        Em falha: dicionário com a chave "error" descrevendo o problema encontrado.
    """
    # Remove pontuação e hífens para padronizar o CNPJ antes de validar e consultar
    cnpj_limpo = re.sub(r"[./-]", "", cnpj)

    # Valida matematicamente os dígitos verificadores antes de fazer a requisição HTTP
    if not CNPJ().validate(cnpj_limpo):
        return {
            "error": f"CNPJ inválido: '{cnpj}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal."
        }

    try:
        return await consultar_cnpj(cnpj_limpo)
    except httpx.TimeoutException:
        return {
            "error": f"Timeout ao consultar o CNPJ {cnpj_limpo}: o servidor da BrasilAPI não respondeu a tempo."
        }
    except httpx.HTTPStatusError as e:
        return {
            "error": f"Receita Federal retornou status {e.response.status_code} para o CNPJ {cnpj_limpo}"
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
    # Lido em tempo de chamada (não de import) para que evaluation/pipeline_avaliacao.py
    # possa apontar para o namespace "avaliacao" via env var sem afetar o agente em produção,
    # que continua usando o default "production" do GerenciadorVetorial.
    namespace_busca = os.getenv("PINECONE_NAMESPACE", "production")
    top_k = int(os.getenv("TOP_K_EDITAL", "3"))

    # asyncio.to_thread garante que a query síncrona ao Pinecone não bloqueie o event loop
    return await asyncio.to_thread(
        gerenciador.buscar_contexto,
        pergunta=pergunta,
        estado=estado,
        municipio=municipio,
        namespace=namespace_busca,
        top_k=top_k,
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
    try:
        resultados = await buscar_na_web(assunto_busca, estado, municipio)
    except Exception as e:
        # A lib da Tavily não expõe uma hierarquia de exceções específica e documentada
        # (indisponibilidade da API, cota excedida, chave ausente/inválida caem todas aqui)
        return {"error": f"Falha ao buscar informações na web: {str(e)}"}

    return {"results": resultados}


@tool
async def consultar_sancoes_empresa(
    cnpj: Annotated[
        str,
        Field(
            description='CNPJ da empresa encontrado no texto. Aceita formatado ("12.345.678/0001-99") ou apenas numérico ("12345678000199").',
            min_length=14,
            max_length=18,
        ),
    ],
) -> list:
    """
    Consulta se uma empresa brasileira possui sanções ativas nos cadastros CEIS
    e CNEP do Portal da Transparência a partir do CNPJ.

    Use esta ferramenta sempre que precisar verificar se uma empresa mencionada
    no edital ou nos resultados de licitação está impedida ou suspensa de
    contratar com a administração pública. Aceita o CNPJ formatado
    ("12.345.678/0001-99") ou apenas numérico ("12345678000199").

    Args:
        cnpj: O CNPJ da empresa a ser consultada.

    Returns:
        Lista de dicionários, um por sanção encontrada (pode ser vazia se a empresa
        não tiver sanções). Cada item tem "tipo_registro": "sancao" (dado real) ou
        "aviso" (CNPJ inválido ou CEIS/CNEP indisponível na consulta) — trate "aviso"
        como "não verificado", nunca como "empresa sem sanções".
    """
    # Remove pontuação e hífens para padronizar o CNPJ antes de validar e consultar
    cnpj_limpo = re.sub(r"[./-]", "", cnpj)

    # Valida matematicamente os dígitos verificadores antes de fazer a requisição HTTP
    if not CNPJ().validate(cnpj_limpo):
        return [
            {
                "tipo_registro": "aviso",
                "error": f"CNPJ inválido: '{cnpj}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal.",
            }
        ]

    return await consultar_sancoes(cnpj_limpo)


@tool
async def buscar_contratos_fornecedor_pncp(
    cnpj_orgao: Annotated[
        str,
        Field(
            description='CNPJ do órgão contratante (prefeitura/município), normalmente encontrado no cabeçalho do edital. Aceita formatado ("12.345.678/0001-99") ou apenas numérico ("12345678000199").',
            min_length=14,
            max_length=18,
        ),
    ],
    cnpj_fornecedor: Annotated[
        str,
        Field(
            description='CNPJ da empresa a verificar, encontrado no texto do edital. Aceita formatado ("12.345.678/0001-99") ou apenas numérico ("12345678000199").',
            min_length=14,
            max_length=18,
        ),
    ],
    ano: Annotated[
        int,
        Field(
            description="Ano de referência das compras a considerar — normalmente o ano de publicação do edital em análise."
        ),
    ],
) -> dict:
    """
    Verifica, no Portal Nacional de Contratações Públicas (PNCP), se um fornecedor
    específico já venceu (foi homologado) em contratações anteriores junto ao mesmo
    órgão contratante, dentro de um ano de referência.

    Use esta ferramenta sempre que precisar checar o histórico de relacionamento entre
    uma empresa mencionada no edital e o órgão contratante (prefeitura) — por exemplo,
    para investigar Reincidência Suspeita (Anomalia G) ou Fracionamento Irregular
    (Anomalia C) ao longo do tempo. Diferente de `consultar_receita_federal`, que traz
    dados cadastrais gerais da empresa, esta ferramenta cruza especificamente o par
    órgão + fornecedor no PNCP.

    Args:
        cnpj_orgao: CNPJ do órgão contratante (prefeitura), apenas dígitos.
        cnpj_fornecedor: CNPJ da empresa a verificar, apenas dígitos.
        ano: Ano de referência das compras a considerar.

    Returns:
        Em sucesso: dicionário com a chave "resultados", lista de contratos em que o
        fornecedor venceu junto a esse órgão naquele ano — cada item com
        "numeroControlePNCP", "objeto", "valor", "situacao" e "dataResultado". Lista
        vazia significa que a consulta funcionou, mas não encontrou nenhum contrato
        do fornecedor com esse órgão naquele ano.
        Em falha: dicionário com a chave "error" descrevendo o problema encontrado.

    Nota: por causa de limites de requisição impostos pelo PNCP, esta consulta varre
    todas as modalidades de contratação do órgão no ano e pode levar alguns minutos
    em órgãos com muitas compras — isso é esperado, não um erro.
    """
    # Remove pontuação e hífens para padronizar os CNPJs antes de validar e consultar
    cnpj_orgao_limpo = re.sub(r"[./-]", "", cnpj_orgao)
    cnpj_fornecedor_limpo = re.sub(r"[./-]", "", cnpj_fornecedor)

    if not CNPJ().validate(cnpj_orgao_limpo):
        return {
            "error": f"CNPJ do órgão inválido: '{cnpj_orgao}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal."
        }
    if not CNPJ().validate(cnpj_fornecedor_limpo):
        return {
            "error": f"CNPJ do fornecedor inválido: '{cnpj_fornecedor}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal."
        }

    try:
        resultados = await buscar_contratos_por_fornecedor(cnpj_orgao_limpo, cnpj_fornecedor_limpo, ano)
    except httpx.TimeoutException:
        return {"error": f"Timeout ao consultar o PNCP para o órgão {cnpj_orgao_limpo}."}
    except httpx.HTTPStatusError as e:
        return {
            "error": f"PNCP retornou status {e.response.status_code} para o órgão {cnpj_orgao_limpo}."
        }
    except httpx.RequestError as e:
        return {"error": f"Falha de conexão ao consultar o PNCP: {str(e)}"}

    return {"resultados": resultados}


# Lista de tools nativas do projeto — combinada com as MCP tools no startup pelo lifespan
TOOLS: list[BaseTool] = [
    consultar_receita_federal,
    buscar_contexto_edital,
    buscar_informacao_web,
    consultar_sancoes_empresa,
]
