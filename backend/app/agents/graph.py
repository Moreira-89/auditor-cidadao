from app.agents.nodes.agente import criar_no_agente
from app.agents.state import AgentState
from app.config.settings import (
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SEGUNDOS,
)
from app.llm import retornar_cliente_llm
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

# Criado uma vez no startup pelo lifespan e reutilizado em todos os requests —
# compilar o grafo a cada pergunta seria caro e recriaria a conexão do checkpointer.
_grafo: CompiledStateGraph | None = None


def build_graph(tools: list, checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """
    Monta o ciclo ReAct: o agente decide, as ferramentas executam, o agente lê o
    resultado e decide de novo, até responder sem pedir ferramenta nenhuma.

        START → agente ─(pediu tool?)→ ferramentas → agente
                      └─(não)────────→ END
    """
    modelo = retornar_cliente_llm(
        model_name=LLM_MODEL,
        config_params={
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
            "timeout": LLM_TIMEOUT_SEGUNDOS,
            "max_retries": LLM_MAX_RETRIES,
        },
    ).bind_tools(tools)

    grafo = StateGraph(AgentState)
    grafo.add_node("agente", criar_no_agente(modelo))
    # ToolNode executa a tool pedida e é quem injeta o ToolRuntime nas que o declaram.
    grafo.add_node("ferramentas", ToolNode(tools))

    grafo.add_edge(START, "agente")
    # tools_condition devolve "tools" quando a última AIMessage traz tool_calls; o dict
    # traduz esse retorno para o nome que o nó tem aqui.
    grafo.add_conditional_edges(
        "agente", tools_condition, {"tools": "ferramentas", END: END}
    )
    grafo.add_edge("ferramentas", "agente")

    return grafo.compile(checkpointer=checkpointer)


def initialize_graph(tools: list, checkpointer: BaseCheckpointSaver) -> None:
    """Chamado uma única vez pelo lifespan para construir e guardar o grafo."""
    global _grafo
    _grafo = build_graph(tools=tools, checkpointer=checkpointer)


def get_graph() -> CompiledStateGraph:
    """Devolve o grafo compilado. Lança RuntimeError se o lifespan ainda não rodou."""
    if _grafo is None:
        raise RuntimeError(
            "Grafo não inicializado. O lifespan do FastAPI foi executado?"
        )
    return _grafo
