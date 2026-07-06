import hashlib
import json

from cachetools import TTLCache
from langchain_core.tools import StructuredTool

# =============================================================================
# CONTEXTO GERAL DO MÓDULO
#
# Cada chamada a uma tool MCP dispara uma requisição ao servidor Node.js (que fala
# com o PNCP). Como esses dados de licitações/contratos/atas mudam pouco ao longo do
# dia, repetir a mesma chamada com os mesmos argumentos só desperdiça tempo e tokens
# de contexto — o resultado seria idêntico.
#
# Este módulo evita isso guardando os resultados num cache em memória com "prazo de
# validade" (TTL, time-to-live), via `cachetools.TTLCache`: a própria lib descarta
# sozinha as entradas vencidas (não precisamos checar horário na mão), e o `maxsize`
# impede o cache de crescer sem limite num servidor que fica dias no ar (ex.: Railway,
# 512 MB de RAM).
#
# O cache vive na RAM do processo e some quando o servidor reinicia.
# Validade padrão: 86400 segundos (24 horas).
# =============================================================================


def _gerar_chave(tool_name: str, kwargs: dict) -> str:
    """
    Gera uma chave de cache única combinando o nome da tool e um hash dos argumentos.
    Usa MD5 apenas por velocidade e determinismo — não há requisito de segurança aqui.
    """
    # sort_keys=True garante que {"a":1,"b":2} e {"b":2,"a":1} produzam exatamente o mesmo hash.
    # Sem isso, a mesma chamada com dicts em ordens diferentes criaria entradas duplicadas no cache.
    kwargs_serialized = json.dumps(kwargs, sort_keys=True)
    hash_object = hashlib.md5(kwargs_serialized.encode())
    # Prefixo com o nome da tool evita colisão entre tools diferentes que recebam os mesmos args
    return f"{tool_name}_{hash_object.hexdigest()}"


def _wrap_com_cache(original_coroutine, tool_name: str, cache: TTLCache):
    """
    Retorna uma nova coroutine que intercepta chamadas à tool original e aplica cache com TTL.
    O `TTLCache` é compartilhado por referência entre todas as tools — uma única estrutura
    em memória guarda os resultados de todas as tools registradas em `aplicar_cache`.
    """

    async def coroutine_com_cache(**kwargs):
        cache_key = _gerar_chave(tool_name, kwargs)

        # TTLCache já descarta sozinho entradas expiradas — só precisamos checar se ainda está lá.
        if cache_key in cache:
            return cache[cache_key]

        result = await original_coroutine(**kwargs)
        cache[cache_key] = result
        return result

    return coroutine_com_cache


def aplicar_cache(
    tools: list, ttl_segundos: int = 86400, maxsize: int = 1000
) -> list:
    """
    Envolve cada tool com cache em memória compartilhado e retorna a lista modificada.
    Evita chamadas repetidas para os mesmos argumentos dentro do TTL.
    `maxsize` limita a quantidade de entradas simultâneas — quando o limite é atingido,
    o `TTLCache` descarta a entrada menos recentemente usada antes de aceitar uma nova.
    O cache é único por chamada a esta função — tools de listas diferentes não compartilham cache.
    """
    # Um único TTLCache é compartilhado entre todas as tools da lista.
    # A separação por tool acontece dentro da chave (prefixo com tool_name), não em caches separados.
    cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl_segundos)
    resultado = []

    for tool in tools:
        nova_coroutine = _wrap_com_cache(tool.coroutine, tool.name, cache)

        # O StructuredTool é imutável após a criação — não é possível trocar apenas a coroutine.
        # Por isso reconstruímos o objeto inteiro, copiando todos os atributos originais da tool
        # e substituindo somente a coroutine pela versão com cache.
        tool_com_cache = StructuredTool(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            coroutine=nova_coroutine,
            func=getattr(tool, "func", None),
            return_direct=getattr(tool, "return_direct", False),
        )
        resultado.append(tool_com_cache)

    return resultado
