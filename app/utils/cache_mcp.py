import hashlib
import json
from collections.abc import Callable

from langchain_core.tools import StructuredTool
from redis.asyncio import Redis

from app.core.logging_config import logger

# Para uma tool específica, mapeia nome do argumento -> função que normaliza o valor
# ANTES de gerar a chave de cache (nunca antes de chamar a tool de verdade). Ex.:
# {"consultar_receita_federal": {"cnpj": lambda v: re.sub(r"[./-]", "", v)}}.
NormalizadoresChave = dict[str, dict[str, Callable[[str], str]]]

# =============================================================================
# CONTEXTO GERAL DO MÓDULO
#
# Cada chamada a uma tool MCP dispara uma requisição ao servidor Node.js (que fala
# com o PNCP). Como esses dados de licitações/contratos/atas mudam pouco ao longo do
# dia, repetir a mesma chamada com os mesmos argumentos só desperdiça tempo e tokens
# de contexto — o resultado seria idêntico.
#
# Este módulo evita isso guardando os resultados no Redis com "prazo de validade"
# (TTL, time-to-live): o próprio Redis descarta sozinho as chaves vencidas via
# `ex=ttl_segundos` no SET (não precisamos checar horário na mão nem limitar
# tamanho manualmente — diferente do antigo TTLCache em memória, o Redis não some
# quando o processo do servidor reinicia, e pode ser compartilhado entre múltiplas
# instâncias do servidor rodando ao mesmo tempo).
#
# Validade padrão: 86400 segundos (24 horas).
# =============================================================================


def _gerar_chave(
    tool_name: str, kwargs: dict, normalizadores: NormalizadoresChave | None = None
) -> str:
    """
    Gera uma chave de cache única combinando o nome da tool e um hash dos argumentos.
    Usa MD5 apenas por velocidade e determinismo — não há requisito de segurança aqui.

    `normalizadores` existe porque a chave é gerada a partir dos argumentos EXATOS que
    o LLM decide enviar — mas algumas tools normalizam esses argumentos por dentro
    (ex.: `consultar_receita_federal` tira pontuação do CNPJ em `tools.py` antes de
    consultar). Sem isso, "11.222.333/0001-81" e "11222333000181" — a mesma consulta —
    geram chaves diferentes, e o cache nunca dá HIT entre uma formatação e outra. Aplicar
    o mesmo normalizador aqui, só para o cálculo da chave, resolve isso sem duplicar a
    lógica de negócio da tool nem alterar o valor que de fato chega até ela.
    """
    kwargs_para_chave = kwargs
    normalizadores_da_tool = (normalizadores or {}).get(tool_name)
    if normalizadores_da_tool:
        kwargs_para_chave = dict(kwargs)
        for arg_nome, normalizar in normalizadores_da_tool.items():
            valor = kwargs_para_chave.get(arg_nome)
            if isinstance(valor, str):
                kwargs_para_chave[arg_nome] = normalizar(valor)

    # sort_keys=True garante que {"a":1,"b":2} e {"b":2,"a":1} produzam exatamente o mesmo hash.
    # Sem isso, a mesma chamada com dicts em ordens diferentes criaria entradas duplicadas no cache.
    kwargs_serialized = json.dumps(kwargs_para_chave, sort_keys=True)
    hash_object = hashlib.md5(kwargs_serialized.encode())
    # Prefixo com o nome da tool evita colisão entre tools diferentes que recebam os mesmos args
    return f"mcp_cache:{tool_name}_{hash_object.hexdigest()}"


def _serializar(resultado) -> str:
    """
    Empacota o resultado com uma marca explícita do tipo original antes de virar texto.

    Por quê: o retorno das tools não é sempre dict/list/str. As tools MCP (via
    langchain-mcp-adapters, response_format="content_and_artifact") devolvem uma
    TUPLA `(conteudo, artefato)` — e `json.loads` nunca reconstrói uma tupla, sempre
    devolve uma lista. Se a leitura tentasse "adivinhar" o tipo pela estrutura (ex.:
    "lista de 2 itens = era tupla"), uma tool nativa que por coincidência devolvesse
    uma lista de 2 elementos de verdade ficaria ambígua. Marcando o tipo na escrita,
    a leitura nunca precisa adivinhar — funciona para dict, list, str e tuple (e
    qualquer combinação futura) sem a função precisar saber de qual tool o
    resultado veio.
    """
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
    """
    Retorna uma nova coroutine que intercepta chamadas à tool original e aplica cache
    no Redis com TTL. O client Redis é compartilhado por referência entre todas as
    tools — uma única conexão guarda os resultados de todas as tools registradas em
    `aplicar_cache`.
    """

    async def coroutine_com_cache(**kwargs):
        cache_key = _gerar_chave(tool_name, kwargs, normalizadores)

        try:
            cache_hit = await redis_client.get(cache_key)
        except Exception:  # noqa: BLE001 — captura ampla proposital: Redis fora do
            # ar não pode derrubar a tool — só significa que essa chamada específica
            # não terá cache, e vai direto na tool original.
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
            # ex=ttl_segundos faz o próprio Redis expirar a chave sozinho — equivalente
            # ao TTL automático que o TTLCache fazia em memória.
            await redis_client.set(cache_key, _serializar(result), ex=ttl_segundos)
            logger.debug(
                "Resultado gravado no Redis | tool=%s | chave=%s | ttl=%ds",
                tool_name,
                cache_key,
                ttl_segundos,
            )
        except Exception:  # noqa: BLE001 — mesma lógica do GET: se o Redis falhar na
            # escrita, a tool já rodou e tem resultado válido — só não fica em cache
            # dessa vez.
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
    """
    Envolve cada tool com cache no Redis (compartilhado entre todas as tools passadas
    aqui) e retorna a lista modificada. Evita chamadas repetidas para os mesmos
    argumentos dentro do TTL.

    `normalizadores` é opcional e não afeta tools que não aparecem nele — só existe
    para os casos em que argumentos formatados de jeitos diferentes (ex.: CNPJ com ou
    sem pontuação) representam a mesma consulta, ver `_gerar_chave`.
    """
    resultado = []

    for tool in tools:
        nova_coroutine = _wrap_com_cache(
            tool.coroutine, tool.name, redis_client, ttl_segundos, normalizadores
        )

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

    logger.info(
        "Cache Redis aplicado a %d ferramenta(s): %s",
        len(resultado),
        ", ".join(t.name for t in resultado),
    )

    return resultado
