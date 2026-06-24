from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START
from langgraph.graph.state import CompiledStateGraph, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.dependencies import LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE, retornar_cliente_llm
from app.models.agent_state import AgentState

# -----------------------------------------------------------------------------
# O modelo e o binding de ferramentas são criados UMA ÚNICA VEZ no import do módulo.
# Isso evita que 'call_llm' recrie o cliente a cada invocação do nó.
# Em um único request HTTP, o nó 'call_llm' pode ser executado várias vezes (se o agente
# precisar chamar ferramentas em sequência), tornando a recriação do cliente custosa e desnecessária.


def router(state: AgentState) -> Literal["tool_node", "__end__"]:
    """
    Resumo Principal: Decide qual é o próximo nó do grafo com base na última mensagem do LLM.

    COMO FUNCIONA:
    1. Inspeção de Tool Calls: Verifica se a última mensagem do estado contém chamadas
       de ferramentas pendentes (atributo `tool_calls` não vazio).
       - Se sim: retorna "tool_node" para que o grafo execute a ferramenta solicitada.
       - Se não: retorna "__end__" para finalizar o ciclo e devolver a resposta ao chamador.

    Args:
        state (AgentState): O estado atual do agente com as mensagens acumuladas.

    Returns:
        Literal["tool_node", "__end__"]: O nome do próximo nó a ser executado pelo grafo.
    """
    # --- 1. Inspeção de Tool Calls ---
    # `getattr` com default None é usado com segurança para inspecionar o atributo sem
    # lançar AttributeError caso a mensagem não seja uma AIMessage (ex: HumanMessage).
    llm_response = state["messages"][-1]
    if getattr(llm_response, "tool_calls", None):
        return "tool_node"
    return "__end__"


# -----------------------------------------------------------------------------
# CONSTRUÇÃO DO GRAFO
# -----------------------------------------------------------------------------
def build_graph(tools: list) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """
    Resumo Principal: Constrói e compila o StateGraph do agente com checkpointer de memória.

    COMO FUNCIONA:
    1. Definição da Estrutura: Cria o StateGraph com o schema de estado (AgentState).
    2. Registro dos Nós: Adiciona os nós de processamento ao grafo (call_llm e tool_node).
    3. Definição das Arestas: Conecta os nós com as transições de controle de fluxo —
       o 'router' decide dinamicamente se o agente deve usar uma ferramenta ou encerrar.
    4. Compilação: Finaliza o grafo com o InMemorySaver como checkpointer, habilitando
       a persistência do histórico de mensagens segmentada por thread_id.

    Returns:
        CompiledStateGraph: O grafo compilado e pronto para ser invocado via `.invoke()`.

    Raises:
        ValueError: Se a estrutura do grafo for inválida (ex: nó sem arestas conectadas).
    """

    _modelo_llm = retornar_cliente_llm(
        model_name=LLM_MODEL,
        config_params={
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
        }
    )
    # O `bind_tools` vincula ao modelo a lista de ferramentas disponíveis para o agente.
    # Isso instrui o LLM sobre quais funções ele pode chamar e como estruturar os argumentos.
    _modelo_com_ferramentas = _modelo_llm.bind_tools(tools)    

    # --- 1. Definição da Estrutura ---
    builder = StateGraph(
        state_schema=AgentState,
        context_schema=None,
        input_schema=AgentState,
        output_schema=AgentState,
    )

    # --- 1. Registro dos Nós ---
    async def call_llm(state: AgentState) -> AgentState:
        response = await _modelo_com_ferramentas.ainvoke(state["messages"])
        return {"messages": [response]}

    builder.add_node("call_llm", call_llm)
    # ToolNode nativo do LangGraph: gerencia execução paralela de tool_calls,
    # injeta automaticamente os parâmetros InjectedState, trata erros e formata ToolMessages.
    builder.add_node("tool_node", ToolNode(tools))

    # --- 3. Definição das Arestas ---
    # START → call_llm: o ponto de entrada sempre começa pelo LLM.
    # call_llm → router → [tool_node | __end__]: o roteador decide o próximo passo.
    # tool_node → call_llm: após executar a ferramenta, o LLM recebe o resultado e formula a resposta.
    builder.add_edge(START, "call_llm")
    builder.add_conditional_edges("call_llm", router, ["tool_node", "__end__"])
    builder.add_edge("tool_node", "call_llm")

    # --- 4. Compilação ---
    # O InMemorySaver guarda o estado de cada thread (conversa) na RAM do servidor.
    # ATENÇÃO: ao reiniciar o servidor, TODO o histórico de conversas é perdido.
    # Para produção com necessidade de persistência, use PostgresSaver ou RedisSaver.
    return builder.compile(checkpointer=InMemorySaver())

_graph_instance = None

def get_graph():
    """Retorna o grafo inicializado. Levanta erro se lifespan não rodou ainda."""
    if _graph_instance is None:
        raise RuntimeError("Grafo não inicializado. O lifespan do FastAPI foi executado?")
    return _graph_instance

def initialize_graph(tools: list) -> None:
    """Chamado UMA VEZ pelo lifespan. Constrói e armazena o grafo com todas as tools."""
    global _graph_instance
    _graph_instance = build_graph(tools=tools)