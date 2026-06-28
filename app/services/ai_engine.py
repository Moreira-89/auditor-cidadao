import json
import uuid
from datetime import date
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.prompt import PROMPT_DINAMICO, SYSTEM_PROMPT, TOOL_STATUS_MAP
from app.services.build_graph import get_graph


async def run_agent(
    pergunta_usuario: str,
    lista_cnpj: list[str],
    user_name: str,
    estado: str,
    municipio: str,
    thread_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Executa o agente de auditoria e retorna a resposta da LLM via streaming de eventos."""

    # Escapa < e > para evitar que o usuário quebre o isolamento estrutural do prompt com tags XML
    pergunta_usuario = pergunta_usuario.replace("<", "&lt;").replace(">", "&gt;")

    # Garante que exista um thread_id válido; gera UUID se nenhum for fornecido
    if not thread_id:
        thread_id = str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}

    # Consulta o grafo SINGLETON para verificar se esta thread já tem histórico salvo no InMemorySaver
    state = get_graph().get_state(config)
    conversa_iniciada = len(state.values.get("messages", [])) > 0

    if conversa_iniciada:
        # Turnos subsequentes: envia só a nova pergunta; o checkpointer restaura o histórico automaticamente
        texto_protegido = f"<PERGUNTA>{pergunta_usuario}</PERGUNTA>"
        mensagens_entrada = [HumanMessage(content=texto_protegido)]
    else:
        # Primeiro turno: injeta o SystemMessage com as regras do agente e o HumanMessage com contexto da sessão
        # O contexto do edital NÃO é pré-injetado — o agente o busca via a tool buscar_contexto_edital
        cnpjs_formatados = (
            ", ".join(lista_cnpj)
            if lista_cnpj
            else "Nenhum CNPJ encontrado no documento."
        )
        system_message = SystemMessage(
            content=SYSTEM_PROMPT.format(user_name=user_name)
        )
        data_hoje = date.today().strftime("%Y%m%d")
        human_message = HumanMessage(
            content=PROMPT_DINAMICO.format(
                pergunta_usuario=pergunta_usuario,
                cnpjs_formatados=cnpjs_formatados,
                municipio=municipio,
                estado=estado,
                data_hoje=data_hoje,
            )
        )
        mensagens_entrada = [system_message, human_message]

    # `estado` e `municipio` são repassados em TODOS os turnos porque o InMemorySaver não persiste
    # chaves arbitrárias entre invocações — o InjectedState da tool precisa lê-los do estado ativo
    async for evento in get_graph().astream_events(
        input={"messages": mensagens_entrada, "estado": estado, "municipio": municipio},
        config={**config, "recursion_limit": 50},
        version="v2",
    ):
        tipo_evento = evento["event"]

        # Emite cada fragmento de texto gerado pela LLM; ignora chunks que são apenas tool_calls
        if tipo_evento == "on_chat_model_stream":
            chunk = evento["data"]["chunk"]
            if chunk.content and not chunk.tool_calls:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

        # Emite mensagem de status legível ao usuário quando uma tool é acionada
        elif tipo_evento == "on_tool_start":
            tool_name = evento["name"]
            mensagem = TOOL_STATUS_MAP.get(tool_name, "Processando...")
            yield f"data: {json.dumps({'type': 'status', 'content': mensagem})}\n\n"
