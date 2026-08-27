import hashlib
import json
from collections.abc import Callable
from typing import Any

from app.config.logging import logger
from langchain_core.tools import StructuredTool
from redis.asyncio import Redis

# tool_name -> {arg_nome: função de normalização}, aplicado só ao calcular a chave. O
# normalizador recebe o valor bruto do argumento (string do LLM OU objeto injetado, ex.:
# ToolRuntime) e deve devolver algo serializável em JSON — necessário sempre que o
# argumento não for uma string simples, ver nota sobre ToolRuntime abaixo.
NormalizadoresChave = dict[str, dict[str, Callable[[Any], Any]]]


def _gerar_chave(
    tool_name: str, kwargs: dict, normalizadores: NormalizadoresChave | None = None
) -> str:
    """Chave de cache = nome da tool + MD5 dos argumentos (normalizados, se houver normalizador)."""
    kwargs_para_chave = kwargs
    normalizadores_da_tool = (normalizadores or {}).get(tool_name)
    if normalizadores_da_tool:
        kwargs_para_chave = dict(kwargs)
        for arg_nome, normalizar in normalizadores_da_tool.items():
            if arg_nome in kwargs_para_chave:
                kwargs_para_chave[arg_nome] = normalizar(kwargs_para_chave[arg_nome])

    # sort_keys=True: mesma chamada com dict em ordens diferentes não deve gerar chaves diferentes
    kwargs_serialized = json.dumps(kwargs_para_chave, sort_keys=True)
    hash_object = hashlib.md5(kwargs_serialized.encode())
    return f"mcp_cache:{tool_name}_{hash_object.hexdigest()}"


def _serializar(resultado) -> str:
    """Marca o tipo original antes de virar JSON — tools MCP devolvem tupla, e json.loads
    nunca reconstrói uma tupla sozinho (sempre vira lista)."""
    if isinstance(resultado, tuple):
        return json.dumps({"__tipo__": "tupla", "valor": list(resultado)})
    return json.dumps({"__tipo__": "bruto", "valor": resultado})


def _desserializar(dado_json: str):
    """Desfaz o empacotamento de `_serializar`, restaurando o tipo original marcado na escrita."""
    dado = json.loads(dado_json)
    if dado["__tipo__"] == "tupla":
        return tuple(dado["valor"])
    return dado["valor"]


def _wrap_com_cache(
    original_coroutine,
    tool_name: str,
    redis_client: Redis,
    ttl_segundos: int,
    normalizadores: NormalizadoresChave | None = None,
):
    """Retorna uma coroutine que intercepta a chamada da tool original com cache Redis (TTL)."""

    async def coroutine_com_cache(**kwargs):
        cache_key = _gerar_chave(tool_name, kwargs, normalizadores)

        try:
            cache_hit = await redis_client.get(cache_key)
        except Exception:  # noqa: BLE001 — Redis fora do ar não deve derrubar a tool
            logger.exception(
                "Falha ao ler do Redis | tool=%s | chave=%s — seguindo sem cache.",
                tool_name,
                cache_key,
            )
            return await original_coroutine(**kwargs)

        if cache_hit is not None:
            logger.info("Cache HIT (Redis) | tool=%s | chave=%s", tool_name, cache_key)
            return _desserializar(cache_hit)

        logger.info("Cache MISS (Redis) | tool=%s | chave=%s", tool_name, cache_key)
        result = await original_coroutine(**kwargs)

        try:
            await redis_client.set(cache_key, _serializar(result), ex=ttl_segundos)
            logger.debug(
                "Resultado gravado no Redis | tool=%s | chave=%s | ttl=%ds",
                tool_name,
                cache_key,
                ttl_segundos,
            )
        except Exception:  # noqa: BLE001 — tool já tem resultado válido, só não fica em cache
            logger.exception(
                "Falha ao gravar no Redis | tool=%s | chave=%s — resultado não foi cacheado.",
                tool_name,
                cache_key,
            )

        return result

    return coroutine_com_cache


def aplicar_cache(
    tools: list,
    redis_client: Redis,
    ttl_segundos: int = 86400,
    normalizadores: NormalizadoresChave | None = None,
) -> list:
    """Envolve cada tool com cache no Redis e retorna a lista modificada."""
    resultado = []

    for tool in tools:
        nova_coroutine = _wrap_com_cache(
            tool.coroutine, tool.name, redis_client, ttl_segundos, normalizadores
        )

        # StructuredTool é imutável — reconstrói o objeto inteiro trocando só a coroutine.
        tool_com_cache = StructuredTool(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            coroutine=nova_coroutine,
            func=getattr(tool, "func", None),
            return_direct=getattr(tool, "return_direct", False),
        )
        resultado.append(tool_com_cache)

    logger.info(
        "Cache Redis aplicado a %d ferramenta(s): %s",
        len(resultado),
        ", ".join(t.name for t in resultado),
    )

    return resultado
