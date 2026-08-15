"""
As 4 ferramentas nativas do projeto (Receita Federal, RAG do edital, sanções CEIS/CNEP,
busca web) — combinadas com as tools de PNCP do MCP em app/services/lifespan.py. Cada
tool é uma casca fina sobre um módulo de serviço dedicado (consulta_*.py, busca_web.py).

Lista completa de ferramentas e a tool desativada (buscar_contratos_fornecedor_pncp):
docs/arquitetura/visao_geral.md#ferramentas-disponiveis-ao-agente.
"""

import asyncio
import os
import re
from typing import Annotated

import httpx
from dotenv import load_dotenv
from langchain.tools import BaseTool, ToolRuntime, tool
from pydantic import Field
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
    cnpj_limpo = re.sub(r"[./-]", "", cnpj)

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
        return {"error": f"Falha de conexão ao consultar o CNPJ {cnpj_limpo}: {e!s}"}


@tool
async def buscar_contexto_edital(
    pergunta: str,
    runtime: ToolRuntime,
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
    # Lido em tempo de chamada (não de import): evaluation/pipeline_avaliacao.py sobrescreve
    # PINECONE_NAMESPACE para isolar o namespace de teste sem afetar o agente em produção.
    namespace_busca = os.getenv("PINECONE_NAMESPACE", "production")
    top_k = int(os.getenv("TOP_K_EDITAL", "3"))

    return await asyncio.to_thread(  # busca ao Pinecone é síncrona; to_thread não bloqueia o event loop
        gerenciador.buscar_contexto,
        pergunta=pergunta,
        estado=runtime.state["estado"],
        municipio=runtime.state["municipio"],
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
        resultados = await buscar_na_web(
            assunto_busca, runtime.state["estado"], runtime.state["municipio"]
        )
    except Exception as e:  # noqa: BLE001
        # A lib da Tavily não expõe uma hierarquia de exceções específica e documentada
        # (indisponibilidade da API, cota excedida, chave ausente/inválida caem todas aqui)
        return {"error": f"Falha ao buscar informações na web: {e!s}"}

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
    cnpj_limpo = re.sub(r"[./-]", "", cnpj)

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
        return {"error": f"Falha de conexão ao consultar o PNCP: {e!s}"}

    return {"resultados": resultados}


# Usado por aplicar_cache (app/utils/cache_mcp.py) para a chave de cache usar o CNPJ já
# normalizado — ver docs/arquitetura/protocolo_mcp.md#cache-das-ferramentas-aplicar_cache.
def _normalizar_cnpj_para_cache(v: str) -> str:
    return re.sub(r"[./-]", "", v)


# ToolRuntime não é serializável em JSON — sem isso, aplicar_cache quebra com TypeError
# ao tentar calcular a chave. Extrai só estado/municipio (que PRECISAM continuar na chave:
# a mesma pergunta em municípios diferentes tem que gerar cache MISS, não reusar o
# resultado de outro edital) — ver docs/arquitetura/protocolo_mcp.md#cache-das-ferramentas-aplicar_cache.
def _extrair_estado_municipio_para_cache(runtime: ToolRuntime) -> dict:
    return {"estado": runtime.state["estado"], "municipio": runtime.state["municipio"]}


CACHE_KEY_NORMALIZERS = {
    "consultar_receita_federal": {"cnpj": _normalizar_cnpj_para_cache},
    "consultar_sancoes_empresa": {"cnpj": _normalizar_cnpj_para_cache},
    "buscar_contratos_fornecedor_pncp": {
        "cnpj_orgao": _normalizar_cnpj_para_cache,
        "cnpj_fornecedor": _normalizar_cnpj_para_cache,
    },
    "buscar_contexto_edital": {"runtime": _extrair_estado_municipio_para_cache},
    "buscar_informacao_web": {"runtime": _extrair_estado_municipio_para_cache},
}

TOOLS: list[BaseTool] = [
    consultar_receita_federal,
    buscar_contexto_edital,
    buscar_informacao_web,
    consultar_sancoes_empresa,
]
