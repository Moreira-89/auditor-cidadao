import logging
import os
import shutil
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.services.build_graph import initialize_graph
from app.utils.mcp_utils import patch_mcp_tools_para_groq
from app.services.tools import TOOLS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # -------------------------------------------------------------------------
    # STARTUP
    # -------------------------------------------------------------------------
    logger.info("Iniciando servidor — carregando ferramentas e grafo...")

    # Resolve o PATH do Node.js no Windows, onde subprocessos não herdam
    # automaticamente o PATH do shell. No Linux/Docker, o shutil.which
    # já encontra o npx normalmente sem essa injeção.
    if sys.platform == "win32":
        os.environ["PATH"] = (
            r"C:\Program Files\nodejs" + os.pathsep + os.environ.get("PATH", "")
        )

    npx_cmd = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx_cmd:
        raise RuntimeError(
            "npx não encontrado no PATH. Node.js está instalado e no PATH do sistema?"
        )

    logger.info("npx encontrado em: %s", npx_cmd)

    # Importação aqui dentro evita dependência circular no nível do módulo
    from langchain_mcp_adapters.client import MultiServerMCPClient

    mcp_client = MultiServerMCPClient(
        {
            "licinexus": {
                "command": npx_cmd,
                "args": ["-y", "@licinexusbr/mcp"],
                "transport": "stdio",
            }
        }
    )

    TOOLS_MCP_SELECIONADAS = {
        "search_licitacoes",
        "get_licitacao",
        "list_licitacao_itens",
        "list_licitacao_resultados",
        "get_fornecedor_contratos",
        "search_atas_rp",
        "compare_periodos",
    }

    mcp_tools_todas = await mcp_client.get_tools()
    mcp_tools = [t for t in mcp_tools_todas if t.name in TOOLS_MCP_SELECIONADAS]
    logger.info(
        "MCP conectado — %d/%d ferramentas selecionadas para o agente.",
        len(mcp_tools), len(mcp_tools_todas)
    )
    mcp_tools = patch_mcp_tools_para_groq(mcp_tools)

    # Combina as tools nativas do projeto com as tools do MCP
    todas_as_tools = TOOLS + mcp_tools
    logger.info(
        "Total de ferramentas disponíveis para o agente: %d", len(todas_as_tools)
    )

    # Constrói e armazena o grafo com todas as tools combinadas
    initialize_graph(todas_as_tools)
    logger.info("Grafo inicializado com sucesso. Servidor pronto para receber requests.")

    # O yield separa startup do shutdown.
    # O mcp_client permanece vivo aqui — enquanto essa variável existir no escopo,
    # o subprocess Node.js continua rodando e as tool calls funcionam.
    yield

    # -------------------------------------------------------------------------
    # SHUTDOWN
    # -------------------------------------------------------------------------
    logger.info("Encerrando servidor — liberando recursos do MCP...")
    # O mcp_client sai de escopo aqui. O garbage collector do Python
    # encerra o subprocess Node.js automaticamente.
    logger.info("Servidor encerrado com sucesso.")