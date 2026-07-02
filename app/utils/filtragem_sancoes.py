"""
Consulta e normaliza sanções de empresas nos cadastros do Portal da Transparência:
CEIS (Cadastro de Empresas Inidôneas e Suspensas) e CNEP (Cadastro Nacional de
Empresas Punidas).
"""

import httpx

URL_CEIS = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
URL_CNEP = "https://api.portaldatransparencia.gov.br/api-de-dados/cnep"


async def consultar_sancao_async(url_base: str, cnpj: str, headers: dict) -> list | None:
    """
    Consulta um cadastro de sanções (CEIS ou CNEP) do Portal da Transparência
    para um CNPJ específico. `codigoSancionado` é o parâmetro correto da API
    para filtrar por CNPJ — `cnpjSancionado` é aceito silenciosamente mas
    ignorado, retornando a listagem padrão sem filtro nenhum.

    Retorna `None` (nunca `[]`) quando a consulta falha, para distinguir
    "fonte indisponível, não verificado" de "fonte consultada, sem sanções" —
    distinção exigida pela Anomalia H do SYSTEM_PROMPT (score mínimo MÉDIO
    quando CEIS/CNEP não puderem ser verificados).
    """
    params = {"codigoSancionado": cnpj, "pagina": 1}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url_base, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        # Falha isolada nesta fonte não deve derrubar a chamada da outra dentro do gather
        return None


def _achatar_sancao(registro: dict, fonte_cadastro: str) -> dict:
    """
    Extrai os campos relevantes de um registro bruto de sanção (CEIS ou CNEP),
    achatando a estrutura aninhada da API do Portal da Transparência em um
    dict plano, e marca de qual cadastro o registro veio.
    """
    return {
        "dataInicioSancao": registro["dataInicioSancao"],
        "dataFimSancao": registro["dataFimSancao"],
        "tipoSancao": registro["tipoSancao"]["descricaoResumida"],
        "orgaoSancionadorNome": registro["orgaoSancionador"]["nome"],
        "orgaoSancionadorUf": registro["orgaoSancionador"]["siglaUf"],
        "orgaoSancionadorPoder": registro["orgaoSancionador"]["poder"],
        "orgaoSancionadorEsfera": registro["orgaoSancionador"]["esfera"],
        "sancionadoNome": registro["sancionado"]["nome"],
        "sancionadoCnpj": registro["pessoa"]["cnpjFormatado"],
        "numeroProcesso": registro["numeroProcesso"],
        # .get() só aqui: registros do CEIS não trazem valorMulta, diferente do CNEP.
        # Os demais campos usam acesso direto de propósito — se sumirem, é sinal de
        # mudança no shape da API e queremos que quebre visível (KeyError), não silencioso.
        "valorMulta": registro.get("valorMulta"),
        "fonte_cadastro": fonte_cadastro,
        "tipo_registro": "sancao",
    }


def processar_sancoes(resultados_ceis: list, resultados_cnep: list) -> list[dict]:
    """
    Orquestra o achatamento dos registros de sanção vindos do CEIS e do CNEP,
    marcando a origem de cada um, e retorna uma única lista combinada.
    """
    sancoes_ceis = [_achatar_sancao(r, "CEIS") for r in resultados_ceis]
    sancoes_cnep = [_achatar_sancao(r, "CNEP") for r in resultados_cnep]
    return sancoes_ceis + sancoes_cnep
