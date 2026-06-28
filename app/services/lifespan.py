import logging
import os
import shutil
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.services.build_graph import initialize_graph
from app.services.tools import TOOLS
from app.utils.mcp_utils import patch_mcp_tools

logger = logging.getLogger(__name__)


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

    # O cliente é instanciado diretamente e mantido em escopo até após o yield,
    # garantindo que o subprocess Node.js permaneça vivo enquanto o servidor estiver rodando.
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
    mcp_tools = patch_mcp_tools(mcp_tools)

    # Combina as tools nativas do projeto com as tools do MCP
    todas_as_tools = TOOLS + mcp_tools
    logger.info(
        "Total de ferramentas disponíveis para o agente: %d", len(todas_as_tools)
    )

    # Constrói e armazena o grafo com todas as tools combinadas
    initialize_graph(todas_as_tools)
    logger.info("Grafo inicializado com sucesso. Servidor pronto para receber requests.")

    # O yield separa startup do shutdown.
    # mcp_client permanece em escopo aqui — o subprocess Node.js fica vivo enquanto o servidor roda.
    yield

    # -------------------------------------------------------------------------
    # SHUTDOWN
    # -------------------------------------------------------------------------
    # Ao sair do escopo do lifespan, o GC do Python encerra o subprocess Node.js.
    # Nota: o cleanup explícito via __aexit__ não está disponível nesta versão da lib.
    logger.info("Servidor encerrado com sucesso.")