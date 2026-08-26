import json
import uuid
from collections.abc import AsyncGenerator

from app.agents.envelope import escape_xml, montar_primeiro_turno
from app.agents.graph import get_graph
from app.config.logging import logger
from app.config.tool_status_map import TOOL_STATUS_MAP
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot


async def _curar_tool_calls_pendentes(
    grafo: CompiledStateGraph,
    state: StateSnapshot,
    config: RunnableConfig,
    thread_id: str,
) -> None:
    """
    Corrige o histórico se um turno anterior foi interrompido no meio de tool_calls
    (ex.: usuário parou a geração) — sem isso a OpenAI rejeita o próximo turno com 400,
    porque toda tool_call precisa de uma tool message de resposta logo em seguida.
    Detalhes: docs/arquitetura/visao_geral.md#historico-interrompido-no-meio-de-uma-tool_call.
    """
    mensagens = state.values.get("messages", [])
    if not mensagens:
        return

    ultima_mensagem = mensagens[-1]
    tool_calls = getattr(ultima_mensagem, "tool_calls", None)
    if not isinstance(ultima_mensagem, AIMessage) or not tool_calls:
        return

    ids_respondidos = {m.tool_call_id for m in mensagens if isinstance(m, ToolMessage)}
    pendentes = [tc for tc in tool_calls if tc["id"] not in ids_respondidos]
    if not pendentes:
        return

    logger.warning(
        "Turno anterior interrompido com tool_calls sem resposta | thread=%s | pendentes=%d — corrigindo histórico.",
        thread_id,
        len(pendentes),
    )
    respostas_sinteticas = [
        ToolMessage(
            content="Chamada cancelada: a geração anterior foi interrompida antes da execução desta ferramenta.",
            tool_call_id=tc["id"],
        )
        for tc in pendentes
    ]
    await grafo.aupdate_state(config, {"messages": respostas_sinteticas})


def _sse(tipo: str, content: str | None = None) -> str:
    """Formata um evento no protocolo Server-Sent Events consumido pelo frontend."""
    payload = {"type": tipo} if content is None else {"type": tipo, "content": content}
    return f"data: {json.dumps(payload)}\n\n"


async def run_agent(
    pergunta_usuario: str,
    lista_cnpj: list[str],
    estado: str,
    municipio: str,
    thread_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Executa um turno de conversa e devolve a resposta do agente em streaming (SSE)."""

    # Escapa todos os campos que entram no prompt, não só a pergunta — qualquer um deles
    # pode carregar tags XML maliciosas vindas do cliente.
    pergunta_usuario = escape_xml(pergunta_usuario)
    estado = escape_xml(estado)
    municipio = escape_xml(municipio)

    if not thread_id:
        thread_id = str(uuid.uuid4())

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    grafo = get_graph()
    state = await grafo.aget_state(config)

    await _curar_tool_calls_pendentes(grafo, state, config, thread_id)

    if state.values.get("messages"):
        # O checkpointer restaura o histórico — só a nova pergunta precisa ser enviada
        mensagens_entrada = [
            HumanMessage(content=f"<PERGUNTA>{pergunta_usuario}</PERGUNTA>")
        ]
    else:
        # Primeiro turno: envia o envelope com CNPJs/estado/município/pergunta. O
        # SYSTEM_PROMPT não é injetado aqui — create_agent (graph.py) já o prepõe a cada
        # chamada ao modelo. O contexto do edital também não é pré-injetado: o agente
        # busca sob demanda via a tool buscar_contexto_edital.
        mensagens_entrada = [
            montar_primeiro_turno(pergunta_usuario, lista_cnpj, estado, municipio)
        ]

    try:
        # estado/municipio são repassados em todo turno — o checkpointer não persiste
        # chaves arbitrárias, e o ToolRuntime das tools precisa lê-los do estado ativo.
        async for evento in grafo.astream_events(
            input={
                "messages": mensagens_entrada,
                "estado": estado,
                "municipio": municipio,
            },
            config={**config, "recursion_limit": 50},
            version="v2",
        ):
            if evento["event"] == "on_chat_model_stream":
                # getattr com default: chunks intermediários podem não ter o atributo tool_calls
                chunk = evento["data"].get("chunk")
                if (
                    chunk is not None
                    and chunk.content
                    and not getattr(chunk, "tool_calls", None)
                ):
                    yield _sse("token", chunk.content)

            elif evento["event"] == "on_tool_start":
                yield _sse(
                    "status", TOOL_STATUS_MAP.get(evento["name"], "Analisando...")
                )

        yield _sse("done")

    except Exception:  # noqa: BLE001
        logger.exception("Erro durante o streaming do agente | thread=%s", thread_id)
        yield _sse(
            "error", "Ocorreu um erro ao processar sua pergunta. Tente novamente."
        )
