"""
"Lifespan" do FastAPI: roda uma vez no startup (antes do primeiro request) e uma vez
no shutdown — é onde fica a inicialização pesada (MCP, cache, grafo).

Passo a passo e diagrama: docs/arquitetura/protocolo_mcp.md.
"""

import os
import shutil
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis

from app.core.dependencies import (
    EXTRATOR_MAX_RETRIES,
    EXTRATOR_MODEL,
    EXTRATOR_TEMPERATURE,
    EXTRATOR_TIMEOUT_SEGUNDOS,
    REDIS_URI,
    TTL_CHECKPOINT_MINUTOS,
    retornar_cliente_llm,
)
from app.core.logging_config import logger
from app.services.build_graph import initialize_graph
from app.services.rate_limiter import inicializar_rate_limiter
from app.services.tools import CACHE_KEY_NORMALIZERS, TOOLS
from app.utils.cache_mcp import aplicar_cache
from app.utils.mcp_utils import patch_mcp_tools

# Singleton do modelo extrator, criado no startup e recuperado via get_extrator().
_extrator_instance = None


def get_extrator():
    """Retorna a instância do modelo extrator. Lança RuntimeError se o lifespan ainda não inicializou."""
    if _extrator_instance is None:
        raise RuntimeError(
            "Modelo extrator não inicializado. O lifespan do FastAPI foi executado?"
        )
    return _extrator_instance


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gerencia o ciclo de vida da aplicação: inicializa o MCP e o grafo no startup e libera recursos no shutdown."""

    logger.info("Iniciando servidor — carregando ferramentas e grafo...")

    # Subprocessos no Windows não herdam o PATH do shell automaticamente
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

    # Client Redis compartilhado entre rate limiter e cache de ferramentas — independente
    # da conexão do checkpointer (não precisa do asetup() que o AsyncRedisSaver exige).
    redis_client = Redis.from_url(REDIS_URI)
    logger.info("Client Redis (rate limiter + cache de ferramentas) conectado.")

    # Import adiado: evita dependência circular no nível do módulo
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

    try:
        mcp_tools_todas = await mcp_client.get_tools()
    except Exception as e:
        # Fail-fast de propósito — mas com contexto, já que o traceback bruto do
        # subprocess Node.js não deixa claro se o problema é o MCP ou o npx/PATH.
        logger.exception("Falha ao conectar ao MCP LiciNexus durante o startup.")
        raise RuntimeError(
            "Não foi possível obter as ferramentas do MCP LiciNexus. "
            "Verifique se o pacote @licinexusbr/mcp está acessível e se o npx foi localizado corretamente."
        ) from e

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

    mcp_tools = patch_mcp_tools(tools=mcp_tools)

    # Cache Redis TTL 24h — normalizadores=CACHE_KEY_NORMALIZERS unifica a chave de cache
    # entre CNPJ formatado e só-dígitos (ver docs/arquitetura/protocolo_mcp.md).
    mcp_tools = aplicar_cache(
        tools=mcp_tools, redis_client=redis_client, ttl_segundos=86400
    )
    tools_nativas = aplicar_cache(
        tools=TOOLS,
        redis_client=redis_client,
        ttl_segundos=86400,
        normalizadores=CACHE_KEY_NORMALIZERS,
    )

    todas_as_tools = tools_nativas + mcp_tools
    logger.info(
        "Total de ferramentas disponíveis para o agente: %d", len(todas_as_tools)
    )

    global _extrator_instance
    _extrator_instance = retornar_cliente_llm(
        model_name=EXTRATOR_MODEL,
        config_params={
            "temperature": EXTRATOR_TEMPERATURE,
            "timeout": EXTRATOR_TIMEOUT_SEGUNDOS,
            "max_retries": EXTRATOR_MAX_RETRIES,
        },
    )
    logger.info("Modelo extrator inicializado com sucesso.")

    inicializar_rate_limiter(redis_client)
    logger.info("Rate limiter inicializado com o client Redis compartilhado.")

    # refresh_on_read=True: cada leitura renova o TTL, então só threads abandonadas expiram.
    ttl_config = {"default_ttl": TTL_CHECKPOINT_MINUTOS, "refresh_on_read": True}

    # O grafo só pode ser construído (e o app só pode rodar) dentro deste "with" — é
    # aqui que a conexão do checkpointer com o Redis existe.
    async with AsyncRedisSaver.from_conn_string(
        redis_url=REDIS_URI, ttl=ttl_config
    ) as checkpointer:
        await checkpointer.asetup()

        initialize_graph(tools=todas_as_tools, checkpointer=checkpointer)
        logger.info(
            "Grafo inicializado com sucesso (checkpointer Redis). Servidor pronto para receber requests."
        )

        yield

        logger.info("Servidor encerrado com sucesso.")

    await redis_client.aclose()
    logger.info("Client Redis (rate limiter + cache de ferramentas) encerrado.")
