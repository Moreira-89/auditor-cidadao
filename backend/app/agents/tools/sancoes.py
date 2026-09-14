import asyncio
import os
import re
from datetime import UTC, date, datetime
from typing import Annotated

import httpx
from langchain.tools import tool
from pydantic import Field
from validate_docbr import CNPJ

URL_CEIS = "https://api.portaldatransparencia.gov.br/api-de-dados/ceis"
URL_CNEP = "https://api.portaldatransparencia.gov.br/api-de-dados/cnep"


def _parse_data_br(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        dia, mes, ano = (int(parte) for parte in valor.split("/"))
        return date(ano, mes, dia)
    except (ValueError, TypeError):
        return None


def _sancao_vigente(data_inicio: str | None, data_fim: str | None) -> bool | None:
    """Diz se a sanção está vigente hoje, a partir das datas 'DD/MM/AAAA' da fonte.
    Calculado aqui para o agente não errar comparação de datas. None quando uma data
    foi informada mas não pôde ser interpretada."""
    hoje = datetime.now(UTC).date()
    inicio, fim = _parse_data_br(data_inicio), _parse_data_br(data_fim)
    if (data_inicio and inicio is None) or (data_fim and fim is None):
        return None
    if inicio and hoje < inicio:
        return False
    return not (fim and hoje > fim)


async def _consultar_cadastro(url_base: str, cnpj: str, headers: dict) -> list | None:
    """
    Consulta um cadastro (CEIS ou CNEP) para um CNPJ. `codigoSancionado` é o
    parâmetro correto da API para filtrar por CNPJ — `cnpjSancionado` é aceito
    silenciosamente mas ignorado, retornando a listagem padrão sem filtro nenhum.

    Retorna `None` (nunca `[]`) quando a consulta falha, para o chamador poder
    distinguir "fonte indisponível" de "fonte consultada, sem sanções".
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
    """Achata um registro bruto do Portal da Transparência e marca de qual cadastro veio."""
    return {
        "dataInicioSancao": registro["dataInicioSancao"],
        "dataFimSancao": registro["dataFimSancao"],
        "vigente": _sancao_vigente(
            registro["dataInicioSancao"], registro["dataFimSancao"]
        ),
        "tipoSancao": registro["tipoSancao"]["descricaoResumida"],
        "orgaoSancionadorNome": registro["orgaoSancionador"]["nome"],
        "orgaoSancionadorUf": registro["orgaoSancionador"]["siglaUf"],
        "orgaoSancionadorPoder": registro["orgaoSancionador"]["poder"],
        "orgaoSancionadorEsfera": registro["orgaoSancionador"]["esfera"],
        "sancionadoNome": registro["sancionado"]["nome"],
        "sancionadoCnpj": registro["pessoa"]["cnpjFormatado"],
        "numeroProcesso": registro["numeroProcesso"],
        "valorMulta": registro.get("valorMulta"),
        "fonte_cadastro": fonte_cadastro,
        "tipo_registro": "sancao",
    }


async def _consultar_sancoes(cnpj_limpo: str) -> list[dict]:
    """Consulta CEIS e CNEP em paralelo. Nunca levanta exceção: falha vira item de aviso."""
    # Chave da API do Portal da Transparência (CGU), exigida no header em vez de query param
    CGU_API_KEY = os.getenv("CGU_API_KEY")

    # Sem a chave não há como consultar. Tratamos isso como "não verificado" (dois avisos,
    # um por base) em vez de deixar o httpx estourar. Motivo técnico: um header com valor
    # None levanta TypeError, que NÃO é um httpx.HTTPError e por isso escaparia do
    # try/except de _consultar_cadastro, virando um erro cru e confuso para o LLM.
    if not CGU_API_KEY:
        aviso = "CGU_API_KEY não configurada no ambiente — sanções não verificadas."
        return [
            {"tipo_registro": "aviso", "error": f"CEIS indisponível: {aviso}"},
            {"tipo_registro": "aviso", "error": f"CNEP indisponível: {aviso}"},
        ]

    headers = {"chave-api-dados": CGU_API_KEY, "Accept": "application/json"}

    # Endpoints independentes, consultados em paralelo; falha em um não derruba o outro
    resultados_ceis, resultados_cnep = await asyncio.gather(
        _consultar_cadastro(URL_CEIS, cnpj_limpo, headers),
        _consultar_cadastro(URL_CNEP, cnpj_limpo, headers),
    )

    avisos = []
    for nome_base, resultados in (("CEIS", resultados_ceis), ("CNEP", resultados_cnep)):
        if resultados is None:
            avisos.append(
                {
                    "tipo_registro": "aviso",
                    "error": f"{nome_base} indisponível: não foi possível verificar sanções do CNPJ {cnpj_limpo} nesta base.",
                }
            )

    sancoes = [
        _achatar_sancao(registro, nome_base)
        for nome_base, resultados in (
            ("CEIS", resultados_ceis),
            ("CNEP", resultados_cnep),
        )
        for registro in (resultados or [])
    ]
    return avisos + sancoes


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
        como "não verificado", nunca como "empresa sem sanções". Registros de sanção
        trazem "vigente" (true/false já calculado contra a data de hoje; null se as
        datas não puderam ser interpretadas) — use este campo direto, não recompare datas.
    """
    cnpj_limpo = re.sub(r"[./-]", "", cnpj)

    if not CNPJ().validate(cnpj_limpo):
        return [
            {
                "tipo_registro": "aviso",
                "error": f"CNPJ inválido: '{cnpj}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal.",
            }
        ]

    return await _consultar_sancoes(cnpj_limpo)
