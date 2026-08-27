from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.agents.graph import initialize_graph
from app.agents.tools.registry import montar_tools
from app.api.rate_limiter import inicializar_rate_limiter
from app.config.logging import logger
from app.storage.checkpointer import abrir_checkpointer
from app.storage.redis import abrir_client_redis
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Monta os recursos da aplicação no startup e os libera no shutdown."""
    logger.info("Iniciando servidor — carregando ferramentas e grafo...")

    async with abrir_client_redis() as redis_client:
        tools = await montar_tools(redis_client)
        inicializar_rate_limiter(redis_client)

        async with abrir_checkpointer() as checkpointer:
            initialize_graph(tools=tools, checkpointer=checkpointer)
            logger.info("Servidor pronto para receber requests.")

            yield

    logger.info("Servidor encerrado com sucesso.")
