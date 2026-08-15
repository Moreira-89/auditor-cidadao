"""
Coração do agente: run_agent() orquestra um turno de conversa de ponta a ponta e
devolve a resposta em streaming (SSE).

Fluxo completo, buffer-then-commit e o tratamento de histórico interrompido:
docs/arquitetura/visao_geral.md.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from app.core.logging_config import logger
from app.core.prompt import PROMPT_DINAMICO, PROMPT_EXTRATOR, TOOL_STATUS_MAP
from app.models.laudo import RespostaLaudo
from app.services.build_graph import get_graph
from app.services.lifespan import get_extrator


def escape_xml(texto: str) -> str:
    """Escapa < e > para o usuário não quebrar as tags XML do prompt (ex.: `</METADADOS>`)."""
    return texto.replace("<", "&lt;").replace(">", "&gt;")


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


async def run_agent(
    pergunta_usuario: str,
    lista_cnpj: list[str],
    estado: str,
    municipio: str,
    thread_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Executa o agente de auditoria e retorna a resposta da LLM via streaming de eventos."""

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

    conversa_iniciada = len(state.values.get("messages", [])) > 0

    if conversa_iniciada:
        # O checkpointer restaura o histórico — só a nova pergunta precisa ser enviada
        texto_protegido = f"<PERGUNTA>{pergunta_usuario}</PERGUNTA>"
        mensagens_entrada = [HumanMessage(content=texto_protegido)]
    else:
        # Primeiro turno: envia o envelope com CNPJs/estado/município/pergunta. O
        # SYSTEM_PROMPT não é injetado aqui — create_agent (build_graph.py) já o
        # prepõe automaticamente a cada chamada ao modelo via system_prompt=. O
        # contexto do edital também não é pré-injetado — o agente busca sob demanda
        # via a tool buscar_contexto_edital.
        cnpjs_formatados = escape_xml(
            ", ".join(lista_cnpj)
            if lista_cnpj
            else "Nenhum CNPJ encontrado no documento."
        )
        data_hoje = datetime.now(UTC).date().strftime("%Y%m%d")
        human_message = HumanMessage(
            content=PROMPT_DINAMICO.format(
                pergunta_usuario=pergunta_usuario,
                cnpjs_formatados=cnpjs_formatados,
                municipio=municipio,
                estado=estado,
                data_hoje=data_hoje,
            )
        )
        mensagens_entrada = [human_message]

    try:
        # estado/municipio são repassados em todo turno — o checkpointer não persiste
        # chaves arbitrárias, e o ToolRuntime das tools precisa lê-los do estado ativo.
        laudo_completo = ""
        buffer_temporario = ""  # buffer-then-commit, ver docs/arquitetura/visao_geral.md
        async for evento in grafo.astream_events(
            input={
                "messages": mensagens_entrada,
                "estado": estado,
                "municipio": municipio,
            },
            config={**config, "recursion_limit": 50},
            version="v2",
        ):
            tipo_evento = evento["event"]

            if tipo_evento == "on_chat_model_start":
                buffer_temporario = ""  # nova mensagem do LLM começando

            elif tipo_evento == "on_chat_model_stream":
                # getattr com default: chunks intermediários podem não ter o atributo tool_calls
                chunk = evento["data"].get("chunk")
                if (
                    chunk is not None
                    and chunk.content
                    and not getattr(chunk, "tool_calls", None)
                ):
                    buffer_temporario += chunk.content
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

            elif tipo_evento == "on_chat_model_end":
                mensagem_final = evento["data"].get("output")
                if not getattr(mensagem_final, "tool_calls", None):
                    laudo_completo += buffer_temporario
                # Se tinha tool_calls, o buffer é descartado (era decisão intermediária)

            elif tipo_evento == "on_tool_start":
                tool_name = evento["name"]
                mensagem = TOOL_STATUS_MAP.get(tool_name, "Analisando...")
                yield f"data: {json.dumps({'type': 'status', 'content': mensagem})}\n\n"

        # try/except isolado: uma falha na extração não deve derrubar o "done" — o
        # Markdown do laudo já foi entregue ao frontend com sucesso.
        try:
            extrator_estruturado = get_extrator().with_structured_output(RespostaLaudo)
            resultado = await extrator_estruturado.ainvoke(
                [
                    SystemMessage(content=PROMPT_EXTRATOR),
                    HumanMessage(content=laudo_completo),
                ]
            )
            if resultado.laudo is not None:
                yield f"data: {json.dumps({'type': 'laudo_estruturado', 'content': resultado.laudo.model_dump()})}\n\n"
        except Exception:  # noqa: BLE001
            logger.exception("Erro ao extrair laudo estruturado | thread=%s", thread_id)
            yield f"data: {json.dumps({'type': 'laudo_estruturado_erro', 'content': 'Não foi possível gerar a versão estruturada do laudo.'})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception:  # noqa: BLE001
        logger.exception("Erro durante o streaming do agente | thread=%s", thread_id)
        yield f"data: {json.dumps({'type': 'error', 'content': 'Ocorreu um erro ao processar sua pergunta. Tente novamente.'})}\n\n"
