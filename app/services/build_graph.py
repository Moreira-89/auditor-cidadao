"""
Monta o grafo LangGraph do agente.

O fluxo é um ciclo ReAct simples: o LLM pensa e decide se precisa de uma ferramenta
(nó call_llm); se precisar, o grafo executa a ferramenta (nó tool_node) e devolve o
resultado ao LLM; isso se repete até o LLM responder sem pedir mais nenhuma ferramenta.

O checkpointer (hoje AsyncRedisSaver, ver lifespan.py) guarda o histórico de cada
conversa por thread_id. É exposto como singleton (initialize_graph/get_graph) porque
construir o grafo é caro e ele é idêntico — mesmas tools — para todas as requisições
do processo.
"""

from typing import Literal

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import START
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.dependencies import (
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    retornar_cliente_llm,
)
from app.models.agent_state import AgentState


def router(state: AgentState) -> Literal["tool_node", "__end__"]:
    """
    Decide o próximo nó do grafo com base na última mensagem do LLM.
    Se a mensagem contém tool_calls pendentes, direciona para 'tool_node'.
    Caso contrário, encerra o ciclo com '__end__'.
    """
    # `getattr` com default None evita AttributeError caso a mensagem não seja uma AIMessage
    llm_response = state["messages"][-1]
    if getattr(llm_response, "tool_calls", None):
        return "tool_node"
    return "__end__"


def build_graph(
    tools: list,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """
    Constrói e compila o StateGraph do agente com memória persistida por thread.
    Registra os nós 'call_llm' e 'tool_node', conecta as arestas e compila
    com o checkpointer recebido para manter o histórico por thread_id.
    """
    _modelo_llm = retornar_cliente_llm(
        model_name=LLM_MODEL,
        config_params={
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
        },
    )
    # `bind_tools` informa ao LLM quais ferramentas estão disponíveis e como estruturar os argumentos
    _modelo_com_ferramentas = _modelo_llm.bind_tools(tools)

    builder = StateGraph(
        state_schema=AgentState,
        context_schema=None,
        input_schema=AgentState,
        output_schema=AgentState,
    )

    async def call_llm(state: AgentState) -> dict[str, list[BaseMessage]]:
        response = await _modelo_com_ferramentas.ainvoke(state["messages"])
        return {"messages": [response]}

    builder.add_node("call_llm", call_llm)
    # ToolNode gerencia execução paralela de tool_calls, injeta InjectedState e formata ToolMessages
    builder.add_node("tool_node", ToolNode(tools))

    # START → call_llm: entrada sempre pelo LLM
    # call_llm → router → [tool_node | __end__]: roteador decide o próximo passo
    # tool_node → call_llm: após executar a ferramenta, o LLM recebe o resultado e formula a resposta
    builder.add_edge(START, "call_llm")
    builder.add_conditional_edges("call_llm", router, ["tool_node", "__end__"])
    builder.add_edge("tool_node", "call_llm")

    return builder.compile(checkpointer=checkpointer)


# Instância singleton do grafo — criada uma única vez no startup e reutilizada em todos os requests
_graph_instance: CompiledStateGraph | None = None


def get_graph():
    """Retorna a instância do grafo. Lança RuntimeError se o lifespan ainda não inicializou."""
    if _graph_instance is None:
        raise RuntimeError(
            "Grafo não inicializado. O lifespan do FastAPI foi executado?"
        )
    return _graph_instance


def initialize_graph(tools: list, checkpointer: BaseCheckpointSaver) -> None:
    """Chamado uma única vez pelo lifespan para construir e armazenar o grafo com todas as tools."""
    global _graph_instance
    _graph_instance = build_graph(tools=tools, checkpointer=checkpointer)
