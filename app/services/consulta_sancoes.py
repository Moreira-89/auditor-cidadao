"""
Consulta e combina sanções de uma empresa nos cadastros CEIS (Cadastro de
Empresas Inidôneas e Suspensas) e CNEP (Cadastro Nacional de Empresas
Punidas) do Portal da Transparência (CGU), a partir do CNPJ.
"""

import asyncio
import os

import httpx

URL_CEIS = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
URL_CNEP = "https://api.portaldatransparencia.gov.br/api-de-dados/cnep"


async def _consultar_sancao_async(url_base: str, cnpj: str, headers: dict) -> list | None:
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


def _processar_sancoes(resultados_ceis: list, resultados_cnep: list) -> list[dict]:
    """
    Orquestra o achatamento dos registros de sanção vindos do CEIS e do CNEP,
    marcando a origem de cada um, e retorna uma única lista combinada.
    """
    sancoes_ceis = [_achatar_sancao(r, "CEIS") for r in resultados_ceis]
    sancoes_cnep = [_achatar_sancao(r, "CNEP") for r in resultados_cnep]
    return sancoes_ceis + sancoes_cnep


async def consultar_sancoes(cnpj_limpo: str) -> list[dict]:
    """
    Consulta CEIS e CNEP em paralelo para o CNPJ informado (já limpo e validado
    pelo chamador) e retorna a lista combinada de sanções.

    Nunca lança exceção: cada fonte é isolada dentro de _consultar_sancao_async,
    que retorna None em caso de falha. Quando isso acontece, um item
    `{"tipo_registro": "aviso", ...}` é incluído no resultado para sinalizar
    explicitamente ao LLM que aquela base específica não pôde ser verificada —
    distinção importante da Anomalia H do SYSTEM_PROMPT (nunca tratar "não
    verificado" como "sem sanções").
    """
    # Chave da API do Portal da Transparência (CGU), exigida no header em vez de query param
    CGU_API_KEY = os.getenv("CGU_API_KEY")

    # Sem a chave não há como consultar. Tratamos isso como "não verificado" (dois avisos,
    # um por base), no mesmo formato que a Anomalia H espera — em vez de deixar o httpx
    # estourar. Motivo técnico: um header com valor None levanta TypeError, que NÃO é um
    # httpx.HTTPError e por isso escaparia do try/except de _consultar_sancao_async,
    # virando um erro cru e confuso para o LLM em vez de um aviso claro.
    if not CGU_API_KEY:
        aviso = "CGU_API_KEY não configurada no ambiente — sanções não verificadas."
        return [
            {"tipo_registro": "aviso", "error": f"CEIS indisponível: {aviso}"},
            {"tipo_registro": "aviso", "error": f"CNEP indisponível: {aviso}"},
        ]

    headers = {"chave-api-dados": CGU_API_KEY, "Accept": "application/json"}

    # Consulta CEIS e CNEP em paralelo, já que são endpoints independentes;
    # falha em uma fonte não derruba a outra (tratado dentro de _consultar_sancao_async)
    resultados_ceis, resultados_cnep = await asyncio.gather(
        _consultar_sancao_async(URL_CEIS, cnpj_limpo, headers),
        _consultar_sancao_async(URL_CNEP, cnpj_limpo, headers),
    )

    # None sinaliza falha na fonte (distinto de [] = fonte consultada, sem sanções)
    avisos = []
    if resultados_ceis is None:
        avisos.append(
            {
                "tipo_registro": "aviso",
                "error": f"CEIS indisponível: não foi possível verificar sanções do CNPJ {cnpj_limpo} nesta base.",
            }
        )
        resultados_ceis = []
    if resultados_cnep is None:
        avisos.append(
            {
                "tipo_registro": "aviso",
                "error": f"CNEP indisponível: não foi possível verificar sanções do CNPJ {cnpj_limpo} nesta base.",
            }
        )
        resultados_cnep = []

    return avisos + _processar_sancoes(resultados_ceis, resultados_cnep)
