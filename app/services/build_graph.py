from typing import Literal

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START
from langgraph.graph.state import CompiledStateGraph, StateGraph
from pydantic import ValidationError

from app.core.dependencies import retornar_cliente_llm
from app.models.agent_state import AgentState
from app.services.tools import TOOLS, TOOLS_BY_NAME


# -----------------------------------------------------------------------------
# NÓS DO GRAFO (FUNÇÕES DE PROCESSAMENTO)
# -----------------------------------------------------------------------------
def call_llm(state: AgentState) -> AgentState:
    """
    Resumo Principal: Invoca o modelo LLM passando o histórico atual de mensagens do estado.

    COMO FUNCIONA:
    1. Invocação do Modelo: Pega a lista completa de mensagens atual do estado (`state["messages"]`)
       e a passa para o modelo de linguagem gerar a próxima resposta.
    2. Atualização do Estado: Retorna um dicionário contendo a nova mensagem gerada empacotada em uma lista.
       Devido à anotação `add_messages` na TypedDict, a mensagem será adicionada ao final do histórico.

    Args:
        state (AgentState): O estado atual da execução do agente, contendo o histórico de interações.

    Returns:
        AgentState: Um fragmento de estado (dict) contendo a nova resposta do LLM, que o LangGraph
        mesclará automaticamente no estado global.
    """
    # --- 1. Invocação do Modelo ---
    # Ao passar a sequência inteira de `BaseMessage`, mantemos o modelo ciente
    # de todo o contexto conversacional pregresso.
    model = retornar_cliente_llm(
        model_name="groq:llama-3.3-70b-versatile", config_params={"temperature": 0.1}
    )
    model_with_tools = model.bind_tools(TOOLS)

    response = model_with_tools.invoke(state["messages"])

    # --- 2. Atualização do Estado ---
    # Retornar apenas a chave que foi modificada é a melhor prática no LangGraph.
    # O framework fará o merge dessa modificação no state global da run.
    return {"messages": [response]}


def tool_node(state: AgentState) -> AgentState:

    llm_response = state["messages"][-1]

    if not isinstance(llm_response, AIMessage) or not getattr(
        llm_response, "tool_calls", None
    ):
        return state

    call = llm_response.tool_calls[-1]
    name, args, id_ = call["name"], call["args"], call["id"]

    try:
        content = TOOLS_BY_NAME[name].invoke(args)
    except (KeyError, IndexError, TypeError, ValidationError, ValueError) as error:
        content = f"Erro ao executar tool {name}: {error}"

    tool_message = ToolMessage(content=content, tool_call_id=id_)

    return {"messages": [tool_message]}


def router(state: AgentState) -> Literal["tool_node", "__end__"]:
    llm_response = state["messages"][-1]

    if getattr(llm_response, "tool_calls", None):
        return "tool_node"
    return "__end__"


def build_graph() -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    builder = StateGraph(
        state_schema=AgentState,
        context_schema=None,
        input_schema=AgentState,
        output_schema=AgentState,
    )

    builder.add_node("call_llm", call_llm)
    builder.add_node("tool_node", tool_node)

    builder.add_edge(START, "call_llm")
    builder.add_conditional_edges("call_llm", router, ["tool_node", "__end__"])
    builder.add_edge("tool_node", "call_llm")

    return builder.compile(checkpointer=InMemorySaver())
