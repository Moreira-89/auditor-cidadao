import asyncio
import re

import httpx
from langchain.tools import BaseTool, tool
from validate_docbr import CNPJ
from app.core.dependencies import gerenciador
from app.models.consulta_cnpj import ConsultaCNPJ
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState


# -----------------------------------------------------------------------------
# FERRAMENTAS DO AGENTE (TOOLS)
# -----------------------------------------------------------------------------
@tool(args_schema=ConsultaCNPJ)
async def consultar_receita_federal(cnpj: str) -> dict:
    """
    Objetivo: Consultar os dados cadastrais de uma empresa brasileira na Receita Federal a partir do CNPJ.

    COMO FUNCIONA:
    1. Limpeza do CNPJ: Remove pontuações e hífens para padronizar o input em um formato numérico limpo.
    2. Validação Estrutural e de Dígitos: Utiliza a biblioteca especializada `validate-docbr` para conferir
       se o CNPJ é matematicamente autêntico, prevenindo requisições HTTP desnecessárias para números inválidos.
    3. Requisição assíncrona à BrasilAPI: Faz uma chamada HTTP GET com httpx.AsyncClient e timeout de 5s.
    4. Tratamento da Resposta: Se a consulta for bem-sucedida (200), filtra e retorna os campos de interesse.
       Caso contrário ou em falha de conexão/timeout, retorna um dicionário informando o erro.

    Args:
        cnpj (str): CNPJ enviado pelo agente de IA. Pode vir formatado ("12.345.678/0001-99")
                    ou apenas numérico ("12345678000199"). A limpeza é feita internamente.

    Returns:
        dict: Em sucesso, retorna campos da empresa (razão social, situação cadastral, CNAE, etc).
              Em falha, retorna {"error": "<descrição do problema>"} para o agente tratar.
    """
    # --- 1. Limpeza do CNPJ ---
    cnpj_limpo = re.sub(r"[./-]", "", cnpj)

    # --- 2. Validação Estrutural e de Dígitos ---
    if not CNPJ().validate(cnpj_limpo):
        return {"error": f"CNPJ inválido: '{cnpj}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal."}

    # --- 3. Requisição Assíncrona à BrasilAPI ---
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)

        # --- 4. Tratamento da Resposta ---
        if response.status_code == 200:
            data = response.json()
            return {
                "razao_social": data.get("razao_social"),
                "nome_fantasia": data.get("nome_fantasia"),
                "descricao_situacao_cadastral": data.get("descricao_situacao_cadastral"),
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
    # O InjectedState avisa o LangGraph para puxar o valor direto da chave "estado" do AgentState
    estado: Annotated[str, InjectedState("estado")],
    # O mesmo para o município
    municipio: Annotated[str, InjectedState("municipio")]
) -> str:
    """
    Realiza uma busca semântica avançada dentro do edital ativo indexado no banco vetorial.
    Deve ser usada sempre que precisares de encontrar regras, cláusulas, multas ou exigências do edital.

    Args:
        pergunta: O termo ou dúvida específica que desejas pesquisar no texto do edital.
    """
    # asyncio.to_thread garante que a query síncrona ao Pinecone não bloqueie o event loop.
    return await asyncio.to_thread(
        gerenciador.buscar_contexto,
        pergunta=pergunta,
        estado=estado,
        municipio=municipio
    )

TOOLS: list[BaseTool] = [consultar_receita_federal, buscar_contexto_edital]
TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in TOOLS}