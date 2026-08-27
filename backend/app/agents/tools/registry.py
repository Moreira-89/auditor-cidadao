import os
import re
import shutil
import sys

from app.agents.tools.busca_web import buscar_informacao_web
from app.agents.tools.cache import aplicar_cache
from app.agents.tools.contexto_edital import buscar_contexto_edital
from app.agents.tools.mcp import patch_mcp_tools
from app.agents.tools.receita_federal import consultar_receita_federal
from app.agents.tools.sancoes import consultar_sancoes_empresa
from app.config.logging import logger
from app.config.tool_status_map import TOOL_STATUS_MAP
from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool
from redis.asyncio import Redis

TTL_CACHE_TOOLS_SEGUNDOS = 86400

TOOLS_NATIVAS: list[BaseTool] = [
    consultar_receita_federal,
    buscar_contexto_edital,
    buscar_informacao_web,
    consultar_sancoes_empresa,
]

# Subconjunto das tools que o MCP LiciNexus expõe. É uma decisão de produto sobre o que
# o agente sabe fazer, não de infraestrutura — por isso mora aqui e não no lifespan.
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


def _normalizar_cnpj_para_cache(v: str) -> str:
    return re.sub(r"[./-]", "", v)


def _extrair_estado_municipio_para_cache(runtime: ToolRuntime) -> dict:
    # ToolRuntime não é serializável em JSON e quebraria _gerar_chave com TypeError.
    # estado/municipio PRECISAM continuar na chave: a mesma pergunta em municípios
    # diferentes tem que dar cache MISS, não reusar o resultado de outro edital.
    return {"estado": runtime.state["estado"], "municipio": runtime.state["municipio"]}


# Aplicado só ao calcular a chave de cache, para o mesmo CNPJ formatado e só-dígitos
# caírem na mesma entrada — ver docs/arquitetura/protocolo_mcp.md.
CACHE_KEY_NORMALIZERS = {
    "consultar_receita_federal": {"cnpj": _normalizar_cnpj_para_cache},
    "consultar_sancoes_empresa": {"cnpj": _normalizar_cnpj_para_cache},
    "buscar_contexto_edital": {"runtime": _extrair_estado_municipio_para_cache},
    "buscar_informacao_web": {"runtime": _extrair_estado_municipio_para_cache},
}


def _localizar_npx() -> str:
    """Encontra o executável do npx, que roda o servidor MCP como subprocesso."""
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
    return npx_cmd


async def _obter_tools_mcp() -> list[BaseTool]:
    """Conecta ao MCP LiciNexus e devolve só as tools de TOOLS_MCP_SELECIONADAS, já patchadas."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    mcp_client = MultiServerMCPClient(
        {
            "licinexus": {
                "command": _localizar_npx(),
                "args": ["-y", "@licinexusbr/mcp"],
                "transport": "stdio",
            }
        }
    )

    try:
        todas = await mcp_client.get_tools()
    except Exception as e:
        # Fail-fast de propósito — mas com contexto, já que o traceback bruto do
        # subprocess Node.js não deixa claro se o problema é o MCP ou o npx/PATH.
        logger.exception("Falha ao conectar ao MCP LiciNexus durante o startup.")
        raise RuntimeError(
            "Não foi possível obter as ferramentas do MCP LiciNexus. "
            "Verifique se o pacote @licinexusbr/mcp está acessível e se o npx foi localizado corretamente."
        ) from e

    selecionadas = [t for t in todas if t.name in TOOLS_MCP_SELECIONADAS]
    logger.info(
        "MCP conectado — %d/%d ferramentas selecionadas para o agente.",
        len(selecionadas),
        len(todas),
    )

    ausentes = TOOLS_MCP_SELECIONADAS - {t.name for t in selecionadas}
    if ausentes:
        logger.warning(
            "Tools pedidas em TOOLS_MCP_SELECIONADAS que o MCP não expôs: %s — "
            "nome mudou no servidor ou a seleção está desatualizada.",
            ", ".join(sorted(ausentes)),
        )

    return patch_mcp_tools(tools=selecionadas)


def _conferir_mensagens_de_status(tools: list[BaseTool]) -> None:
    """
    Avisa se alguma tool ficou sem entrada no TOOL_STATUS_MAP.

    Sem isso a divergência é invisível: a tool cai no fallback "Analisando..." do
    streaming e ninguém percebe que a mensagem específica sumiu.
    """
    sem_mensagem = sorted({t.name for t in tools} - TOOL_STATUS_MAP.keys())
    if sem_mensagem:
        logger.warning(
            "Tools sem mensagem em TOOL_STATUS_MAP (vão exibir 'Analisando...'): %s",
            ", ".join(sem_mensagem),
        )

    orfas = sorted(TOOL_STATUS_MAP.keys() - {t.name for t in tools})
    if orfas:
        logger.warning(
            "Entradas de TOOL_STATUS_MAP sem tool correspondente: %s", ", ".join(orfas)
        )


async def montar_tools(redis_client: Redis) -> list[BaseTool]:
    """
    Monta a lista final de tools entregue ao grafo: nativas + MCP, todas com cache Redis.

    É esta lista que o agente executa — não as funções dos arquivos vizinhos, que
    aqui passam por aplicar_cache() e viram wrappers.
    """
    tools_mcp = await _obter_tools_mcp()

    tools = aplicar_cache(
        tools=TOOLS_NATIVAS,
        redis_client=redis_client,
        ttl_segundos=TTL_CACHE_TOOLS_SEGUNDOS,
        normalizadores=CACHE_KEY_NORMALIZERS,
    ) + aplicar_cache(
        tools=tools_mcp,
        redis_client=redis_client,
        ttl_segundos=TTL_CACHE_TOOLS_SEGUNDOS,
    )

    _conferir_mensagens_de_status(tools)
    logger.info("Total de ferramentas disponíveis para o agente: %d", len(tools))
    return tools
