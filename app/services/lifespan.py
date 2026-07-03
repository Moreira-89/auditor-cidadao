import logging
import os
import shutil
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.dependencies import EXTRATOR_MODEL, EXTRATOR_TEMPERATURE, retornar_cliente_llm
from app.services.build_graph import initialize_graph
from app.services.tools import TOOLS
from app.utils.cache_mcp import aplicar_cache
from app.utils.mcp_utils import patch_mcp_tools

logger = logging.getLogger(__name__)

# Instância singleton do modelo usado no processo de extração de informações (temperatura 0
# para respostas determinísticas). Criada no startup do lifespan e recuperada via get_extrator().
_extrator_instance = None


def get_extrator():
    """Retorna a instância do modelo extrator. Lança RuntimeError se o lifespan ainda não inicializou."""
    if _extrator_instance is None:
        raise RuntimeError(
            "Modelo extrator não inicializado. O lifespan do FastAPI foi executado?"
        )
    return _extrator_instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação: inicializa o MCP e o grafo no startup e libera recursos no shutdown."""

    logger.info("Iniciando servidor — carregando ferramentas e grafo...")

    # No Windows, subprocessos não herdam o PATH do shell automaticamente — injeta o Node.js manualmente
    if sys.platform == "win32":
        os.environ["PATH"] = (
            r"C:\Program Files\nodejs" + os.pathsep + os.environ.get("PATH", "")
        )

    # Localiza o executável npx no PATH; usa npx.cmd no Windows e npx no Linux/Docker
    npx_cmd = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx_cmd:
        raise RuntimeError(
            "npx não encontrado no PATH. Node.js está instalado e no PATH do sistema?"
        )

    logger.info("npx encontrado em: %s", npx_cmd)

    # Importação adiada para evitar dependência circular no nível do módulo
    from langchain_mcp_adapters.client import MultiServerMCPClient

    # Nesta versão do langchain-mcp-adapters (0.3.0), o MultiServerMCPClient não mantém
    # um subprocess Node.js persistente: get_tools() e cada chamada de tool abrem e fecham
    # sua própria sessão (via "async with" internamente), então não há um processo de longa
    # duração para encerrar explicitamente no shutdown do lifespan.
    mcp_client = MultiServerMCPClient(
        {
            "licinexus": {
                "command": npx_cmd,
                "args": ["-y", "@licinexusbr/mcp"],
                "transport": "stdio",
            }
        }
    )

    mcp_tools_todas = await mcp_client.get_tools()

    # Filtra apenas as tools necessárias para o agente, descartando as demais do MCP
    TOOLS_MCP_SELECIONADAS = {
        "search_licitacoes",
        "search_contratos",
        "get_contrato",
        "list_contrato_termos",
        "list_licitacao_arquivos",
        "aggregate_licitacoes_por_periodo",
        "get_licitacao",
        "list_licitacao_itens",
        "list_licitacao_resultados",
        "get_fornecedor_contratos",
        "search_atas_rp",
        "compare_periodos",
    }

    mcp_tools = [t for t in mcp_tools_todas if t.name in TOOLS_MCP_SELECIONADAS]
    logger.info(
        "MCP conectado — %d/%d ferramentas selecionadas para o agente.",
        len(mcp_tools),
        len(mcp_tools_todas),
    )

    # Aplica o patch de tipos permissivos para compatibilidade entre LLM e MCP server
    mcp_tools = patch_mcp_tools(tools=mcp_tools)

    # Envolve cada tool MCP com cache em memória (TTL 24h) para evitar chamadas repetidas ao subprocess
    mcp_tools = aplicar_cache(tools=mcp_tools, ttl_segundos=86400)

    # Envolve também as tools nativas do projeto (Receita Federal, busca no edital) com o mesmo cache —
    # antes só as tools MCP eram cacheadas, mas essas duas fazem chamada HTTP/Pinecone e se beneficiam igual
    tools_nativas = aplicar_cache(tools=TOOLS, ttl_segundos=86400)

    # Combina as tools nativas do projeto com as tools do MCP
    todas_as_tools = tools_nativas + mcp_tools
    logger.info(
        "Total de ferramentas disponíveis para o agente: %d", len(todas_as_tools)
    )

    # Constrói e armazena o grafo com todas as tools combinadas
    initialize_graph(todas_as_tools)
    logger.info(
        "Grafo inicializado com sucesso. Servidor pronto para receber requests."
    )

    # Instancia o modelo extrator (temperatura 0 para saída determinística),
    # usado no processo de extração de informações.
    global _extrator_instance
    _extrator_instance = retornar_cliente_llm(
        model_name=EXTRATOR_MODEL,
        config_params={"temperature": EXTRATOR_TEMPERATURE},
    )
    logger.info("Modelo extrator inicializado com sucesso.")

    # O yield separa startup do shutdown.
    yield

    # Nenhum cleanup explícito de mcp_client é necessário: como cada chamada MCP já
    # abre e fecha sua própria sessão/subprocess internamente, não há recurso persistente
    # para liberar aqui.
    logger.info("Servidor encerrado com sucesso.")
