import json
import uuid
from datetime import date
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.logging_config import logger
from app.core.prompt import (
    PROMPT_DINAMICO,
    PROMPT_EXTRATOR,
    SYSTEM_PROMPT,
    TOOL_STATUS_MAP,
)
from app.models.laudo import RespostaLaudo
from app.services.build_graph import get_graph
from app.services.lifespan import get_extrator


def escape_xml(texto: str) -> str:
    """Escapa < e > para evitar que um campo controlado pelo usuário quebre o isolamento
    estrutural das tags XML do prompt (ex.: injetar `</METADADOS><PERGUNTA>...`)."""
    return texto.replace("<", "&lt;").replace(">", "&gt;")


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
        cnpjs_formatados = escape_xml(
            ", ".join(lista_cnpj)
            if lista_cnpj
            else "Nenhum CNPJ encontrado no documento."
        )
        system_message = SystemMessage(content=SYSTEM_PROMPT)
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

    try:
        # `estado` e `municipio` são repassados em TODOS os turnos porque o InMemorySaver não persiste
        # chaves arbitrárias entre invocações — o InjectedState da tool precisa lê-los do estado ativo
        laudo_completo = ""
        # Acumula os chunks da mensagem do LLM em andamento; só é somado a laudo_completo em
        # on_chat_model_end, quando dá pra confirmar que a mensagem não tinha tool_calls. Isso evita
        # contaminar laudo_completo com texto de uma rodada de decisão de tool que emitiu conteúdo
        # parcial antes do tool_calls aparecer completo no stream.
        buffer_temporario = ""
        async for evento in get_graph().astream_events(
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
                # Nova mensagem do LLM começando — reseta o buffer da rodada anterior
                buffer_temporario = ""

            # Emite cada fragmento de texto gerado pela LLM; ignora chunks que são apenas tool_calls.
            # getattr com default None evita AttributeError em chunks intermediários que, dependendo da versão do langchain-core, podem não expor o atributo`tool_calls`.
            elif tipo_evento == "on_chat_model_stream":
                chunk = evento["data"]["chunk"]
                if chunk.content and not getattr(chunk, "tool_calls", None):
                    buffer_temporario += chunk.content
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

            elif tipo_evento == "on_chat_model_end":
                # Mensagem completa — agora sabemos com certeza se ela tinha tool_calls
                mensagem_final = evento["data"]["output"]
                if not getattr(mensagem_final, "tool_calls", None):
                    # Não tinha tool_calls → era resposta final de verdade, confirma no acumulador real
                    laudo_completo += buffer_temporario
                # Se tinha tool_calls, o buffer é descartado (não soma em laudo_completo)

            # Emite mensagem de status legível ao usuário quando uma tool é acionada
            elif tipo_evento == "on_tool_start":
                tool_name = evento["name"]
                mensagem = TOOL_STATUS_MAP.get(tool_name, "Analisando...")
                yield f"data: {json.dumps({'type': 'status', 'content': mensagem})}\n\n"

        # Após o streaming de texto terminar, extrai a versão estruturada do laudo (JSON)
        # a partir do Markdown completo já enviado ao frontend. Isolado em try/except próprio:
        # uma falha aqui não deve derrubar o "done" nem reaproveitar a mensagem de erro genérica
        # do streaming, já que o texto do laudo já foi entregue com sucesso.
        try:
            extrator_estruturado = get_extrator().with_structured_output(RespostaLaudo)
            resultado = await extrator_estruturado.ainvoke(
                [SystemMessage(content=PROMPT_EXTRATOR), HumanMessage(content=laudo_completo)]
            )
            if resultado.laudo is not None:
                yield f"data: {json.dumps({'type': 'laudo_estruturado', 'content': resultado.laudo.model_dump()})}\n\n"
        except Exception:
            logger.exception(
                "Erro ao extrair laudo estruturado | thread=%s", thread_id
            )
            yield f"data: {json.dumps({'type': 'laudo_estruturado_erro', 'content': 'Não foi possível gerar a versão estruturada do laudo.'})}\n\n"

        # Sinaliza ao frontend que o streaming terminou normalmente
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception:
        # Sem isso, uma exceção aqui dentro derruba o generator sem avisar o frontend,
        # que ficaria esperando tokens indefinidamente.
        logger.exception("Erro durante o streaming do agente | thread=%s", thread_id)
        yield f"data: {json.dumps({'type': 'error', 'content': 'Ocorreu um erro ao processar sua pergunta. Tente novamente.'})}\n\n"
