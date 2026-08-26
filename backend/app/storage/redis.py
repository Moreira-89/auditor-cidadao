from contextlib import asynccontextmanager

from app.config.logging import logger
from app.config.settings import REDIS_URI
from redis.asyncio import Redis


@asynccontextmanager
async def abrir_client_redis():
    """
    Client Redis compartilhado entre o rate limiter e o cache de ferramentas.

    É uma conexão separada da do checkpointer (app/storage/checkpointer.py): esta é
    um client comum, aquela exige o asetup() do AsyncRedisSaver para criar os índices
    de checkpoint. Fecha sozinha ao sair do contexto.
    """
    client = Redis.from_url(REDIS_URI)
    logger.info("Client Redis (rate limiter + cache de ferramentas) conectado.")
    try:
        yield client
    finally:
        await client.aclose()
        logger.info("Client Redis (rate limiter + cache de ferramentas) encerrado.")
