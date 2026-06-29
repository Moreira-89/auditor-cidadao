import hashlib
import json
import time

from langchain_core.tools import StructuredTool

# =============================================================================
# CONTEXTO GERAL DO MÓDULO
#
# Cada chamada a uma tool MCP dispara uma requisição ao servidor Node.js via
# subprocess. Para consultas idempotentes ao PNCP (licitações, contratos, atas),
# os dados mudam com pouca frequência — chamar o mesmo endpoint com os mesmos
# argumentos várias vezes no mesmo dia desperdiça latência e tokens de contexto.
#
# Este módulo resolve isso com um cache em memória com TTL:
#   1. Na primeira chamada, executa a tool normalmente e armazena o resultado.
#   2. Nas chamadas seguintes com os mesmos argumentos, retorna o resultado
#      armazenado sem acionar o MCP server, desde que dentro do TTL.
#
# O cache é por processo (RAM) e não persiste entre reinicializações do servidor.
# TTL padrão: 86400 segundos (24 horas).
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


def _wrap_com_cache(original_coroutine, tool_name: str, cache: dict, ttl_segundos: int):
    """
    Retorna uma nova coroutine que intercepta chamadas à tool original e aplica cache com TTL.
    O dict `cache` é compartilhado por referência entre todas as tools — uma única estrutura
    em memória guarda os resultados de todas as tools registradas em `aplicar_cache`.
    """

    async def coroutine_com_cache(**kwargs):
        cache_key = _gerar_chave(tool_name, kwargs)

        if cache_key in cache:
            cached_entry = cache[cache_key]
            # Verifica se o resultado ainda está dentro do prazo de validade.
            # timestamp + ttl define o momento de expiração; compara com o instante atual.
            if (cached_entry["timestamp"] + ttl_segundos) > time.time():
                return cached_entry["result"]
            # Se expirou, deixa cair e chama a tool novamente abaixo

        result = await original_coroutine(**kwargs)

        # Registra o resultado junto com o timestamp da execução para controle de TTL.
        # Sobrescreve silenciosamente uma entrada expirada, se houver.
        cache[cache_key] = {"result": result, "timestamp": time.time()}
        return result

    return coroutine_com_cache


def aplicar_cache(tools: list, ttl_segundos: int = 86400) -> list:
    """
    Envolve cada tool MCP com cache em memória compartilhado e retorna a lista modificada.
    Evita chamadas repetidas ao servidor MCP para os mesmos argumentos dentro do TTL.
    O cache é único por chamada a esta função — tools de listas diferentes não compartilham cache.
    """
    # Um único dict de cache é compartilhado entre todas as tools da lista.
    # A separação por tool acontece dentro da chave (prefixo com tool_name), não em dicts separados.
    cache = {}
    resultado = []

    for tool in tools:
        nova_coroutine = _wrap_com_cache(tool.coroutine, tool.name, cache, ttl_segundos)

        # O StructuredTool é imutável após a criação — não é possível trocar apenas a coroutine.
        # Por isso reconstruímos o objeto inteiro, copiando todos os atributos originais da tool MCP
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
