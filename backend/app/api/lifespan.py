import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.agents.graph import initialize_graph
from app.agents.tools.registry import montar_tools
from app.api.rate_limiter import inicializar_rate_limiter
from app.config.logging import logger
from app.ingestion.pdf_hierarquico import inicializar_converters
from app.storage.checkpointer import abrir_checkpointer
from app.storage.mongo_db import get_database
from app.storage.redis import abrir_client_redis
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Monta os recursos da aplicação no startup e os libera no shutdown."""
    logger.info("Iniciando servidor — carregando ferramentas e grafo...")

    async with abrir_client_redis() as redis_client:
        tools = await montar_tools(redis_client)
        inicializar_rate_limiter(redis_client)

        # Pré-aquece os dois converters do Docling (com e sem OCR). Bloqueante e
        # pesado (carga de modelo de layout/tabela/OCR) — vai pra thread pra não
        # travar o event loop no startup.
        logger.info("Pré-aquecendo converters do Docling...")
        await asyncio.to_thread(inicializar_converters)

        # Abre a conexão com o MongoDB (cliente síncrono)
        # já no startup — o ping dentro de get_database falha rápido se a URI/rede
        # estiver ruim, em vez de só na primeira escrita de seção.
        logger.info("Conectando ao MongoDB...")
        await asyncio.to_thread(get_database)

        async with abrir_checkpointer() as checkpointer:
            initialize_graph(tools=tools, checkpointer=checkpointer)
            logger.info("Servidor pronto para receber requests.")

            yield

    logger.info("Servidor encerrado com sucesso.")
