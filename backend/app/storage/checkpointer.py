from contextlib import asynccontextmanager

from app.config.logging import logger
from app.config.settings import REDIS_URI, TTL_CHECKPOINT_MINUTOS
from langgraph.checkpoint.redis.aio import AsyncRedisSaver


@asynccontextmanager
async def abrir_checkpointer():
    """
    Checkpointer do LangGraph no Redis — é ele que faz a conversa sobreviver entre
    requisições e entre restarts do servidor.

    O grafo só pode ser compilado (e o app só pode rodar) dentro deste contexto: é
    aqui que a conexão existe. Por isso o lifespan mantém o `async with` aberto pelo
    tempo de vida inteiro da aplicação.
    """
    # refresh_on_read=True: cada leitura renova o TTL, então só threads abandonadas expiram.
    ttl_config = {"default_ttl": TTL_CHECKPOINT_MINUTOS, "refresh_on_read": True}

    async with AsyncRedisSaver.from_conn_string(
        redis_url=REDIS_URI, ttl=ttl_config
    ) as checkpointer:
        await checkpointer.asetup()
        logger.info("Checkpointer Redis pronto (TTL=%d min).", TTL_CHECKPOINT_MINUTOS)
        yield checkpointer
