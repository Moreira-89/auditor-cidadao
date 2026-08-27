import re
from typing import Annotated

import httpx
from langchain.tools import tool
from pydantic import Field
from validate_docbr import CNPJ

URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"


async def _consultar_cnpj(cnpj_limpo: str) -> dict:
    """Busca o cadastro na BrasilAPI. Recebe o CNPJ só com dígitos e já validado."""
    url = URL_BRASILAPI_CNPJ.format(cnpj=cnpj_limpo)

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
    response.raise_for_status()

    data = response.json()
    # Devolve só os campos usados na auditoria e descarta o resto da resposta da BrasilAPI
    # (telefone, quadro de sócios/QSA, capital social, CNAEs secundários...). Isso enxuga o
    # que chega ao LLM. Obs.: alguns desses campos descartados são candidatos a reforçar o
    # catálogo de anomalias numa versão futura (ver "Backlog V2" no roadmap).
    return {
        "razao_social": data.get("razao_social"),
        "nome_fantasia": data.get("nome_fantasia"),
        "descricao_situacao_cadastral": data.get("descricao_situacao_cadastral"),
        "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao"),
        "data_inicio_atividade": data.get("data_inicio_atividade"),
        "logradouro": data.get("logradouro"),
        "numero": data.get("numero"),
        "bairro": data.get("bairro"),
        "municipio": data.get("municipio"),
        "uf": data.get("uf"),
        "cep": data.get("cep"),
    }


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
        return await _consultar_cnpj(cnpj_limpo)
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
