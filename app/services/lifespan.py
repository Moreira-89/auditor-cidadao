"""
"Lifespan" do FastAPI: código que roda UMA vez no startup do servidor (antes do primeiro
request) e uma vez no shutdown. É onde concentramos a inicialização pesada, para não pagar
esse custo de novo a cada requisição.

O que acontece no startup, em ordem:
1. Garante que o Node.js/npx está acessível (o MCP roda como um processo Node).
2. Conecta ao MCP LiciNexus e obtém as ferramentas de PNCP. (MCP = Model Context Protocol,
   um padrão para expor ferramentas a um agente; aqui é um pacote npm que fala com o PNCP.)
3. Filtra só as ferramentas MCP desejadas, ajusta os schemas delas (mcp_utils) e envolve
   tudo em cache com validade de 24h (cache_mcp) — inclusive as ferramentas nativas.
4. Constrói o grafo do agente (com todas as ferramentas) e o modelo extrator, guardando
   ambos como singletons usados pela aplicação inteira.
"""

import os
import shutil
import sys
from contextlib import asynccontextmanager
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from fastapi import FastAPI

from app.core.dependencies import (
    DB_URI,
    EXTRATOR_MODEL,
    EXTRATOR_TEMPERATURE,
    retornar_cliente_llm,
)
from app.core.logging_config import logger
from app.services.build_graph import initialize_graph
from app.services.tools import TOOLS
from app.utils.cache_mcp import aplicar_cache
from app.utils.mcp_utils import patch_mcp_tools

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

    try:
        mcp_tools_todas = await mcp_client.get_tools()
    except Exception as e:
        # Falha aqui derruba o startup do servidor de propósito (fail-fast) — mas sem
        # contexto, o traceback bruto do subprocess Node.js não deixa claro se o problema
        # é o MCP em si ou a inicialização do npx/PATH feita acima.
        logger.exception("Falha ao conectar ao MCP LiciNexus durante o startup.")
        raise RuntimeError(
            "Não foi possível obter as ferramentas do MCP LiciNexus. "
            "Verifique se o pacote @licinexusbr/mcp está acessível e se o npx foi localizado corretamente."
        ) from e

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

    # Instancia o modelo extrator (temperatura 0 para saída determinística),
    # usado no processo de extração de informações.
    global _extrator_instance
    _extrator_instance = retornar_cliente_llm(
        model_name=EXTRATOR_MODEL,
        config_params={"temperature": EXTRATOR_TEMPERATURE},
    )
    logger.info("Modelo extrator inicializado com sucesso.")

    # A conexão com o Redis só existe dentro deste "with" — por isso o grafo (que guarda o
    # checkpointer) só pode ser construído aqui dentro, e o app também só pode rodar (yield)
    # aqui dentro. Quando o "with" fecha (shutdown), a conexão é encerrada automaticamente.
    async with AsyncRedisSaver.from_conn_string(DB_URI) as checkpointer:
        # Constrói e armazena o grafo com todas as tools combinadas
        initialize_graph(tools=todas_as_tools, checkpointer=checkpointer)
        logger.info(
            "Grafo inicializado com sucesso (checkpointer Redis). Servidor pronto para receber requests."
        )

        # O yield separa startup do shutdown — o app roda aqui, ainda dentro do "with".
        yield

        # Nenhum cleanup explícito de mcp_client é necessário: como cada chamada MCP já
        # abre e fecha sua própria sessão/subprocess internamente, não há recurso persistente
        # para liberar aqui.
        logger.info("Servidor encerrado com sucesso.")
