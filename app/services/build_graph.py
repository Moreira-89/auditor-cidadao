"""
Monta o agente via create_agent (langchain.agents) — ciclo ReAct padrão da lib
(nós "model" e "tools"), no lugar do StateGraph manual anterior.

Detalhes de arquitetura (por que o ciclo é assim, o AgentState, o checkpointer):
ver docs/arquitetura/visao_geral.md.
"""

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from app.core.dependencies import (
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SEGUNDOS,
    retornar_cliente_llm,
)
from app.core.prompt import SYSTEM_PROMPT
from app.models.agent_state import AgentState


def build_graph(
    tools: list,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    """Constrói o agente com o checkpointer recebido."""
    modelo_llm = retornar_cliente_llm(
        model_name=LLM_MODEL,
        config_params={
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
            "timeout": LLM_TIMEOUT_SEGUNDOS,
            "max_retries": LLM_MAX_RETRIES,
        },
    )

    # create_agent faz o bind_tools internamente — não repetir aqui.
    return create_agent(
        model=modelo_llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        state_schema=AgentState,
        checkpointer=checkpointer,
    )


# Singleton: criado uma vez no startup, reutilizado em todos os requests.
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
