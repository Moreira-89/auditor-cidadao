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
# SINGLETON DO CLIENTE LLM
# -----------------------------------------------------------------------------
# O modelo e o binding de ferramentas são criados UMA ÚNICA VEZ no import do módulo.
# Isso evita que 'call_llm' recrie o cliente a cada invocação do nó.
# Em um único request HTTP, o nó 'call_llm' pode ser executado várias vezes (se o agente
# precisar chamar ferramentas em sequência), tornando a recriação do cliente custosa e desnecessária.
_modelo_llm = retornar_cliente_llm(
    model_name="groq:llama-3.3-70b-versatile",
    config_params={"temperature": 0.1}
)
# O `bind_tools` vincula ao modelo a lista de ferramentas disponíveis para o agente.
# Isso instrui o LLM sobre quais funções ele pode chamar e como estruturar os argumentos.
_modelo_com_ferramentas = _modelo_llm.bind_tools(TOOLS)


# -----------------------------------------------------------------------------
# NÓS DO GRAFO (FUNÇÕES DE PROCESSAMENTO)
# -----------------------------------------------------------------------------
def call_llm(state: AgentState) -> AgentState:
    """
    Resumo Principal: Invoca o modelo LLM passando o histórico atual de mensagens do estado.

    COMO FUNCIONA:
    1. Invocação do Modelo: Pega a lista completa de mensagens atual do estado (`state["messages"]`)
       e a passa para o modelo de linguagem (singleton de módulo, já vinculado às ferramentas)
       gerar a próxima resposta ou decidir chamar uma ferramenta.
    2. Atualização do Estado: Retorna um dicionário contendo a nova mensagem gerada empacotada em
       uma lista. Devido à anotação `add_messages` na TypedDict do AgentState, a mensagem será
       adicionada ao final do histórico (e não substituída).

    Args:
        state (AgentState): O estado atual da execução do agente, contendo o histórico de interações.

    Returns:
        AgentState: Um fragmento de estado (dict) contendo a nova resposta do LLM, que o LangGraph
        mesclará automaticamente no estado global da run.
    """
    # --- 1. Invocação do Modelo ---
    # Usamos o singleton '_modelo_com_ferramentas' criado no nível do módulo.
    # Ao passar a sequência inteira de BaseMessage, mantemos o modelo ciente
    # de todo o contexto conversacional pregresso (histórico completo da thread).
    response = _modelo_com_ferramentas.invoke(state["messages"])

    # --- 2. Atualização do Estado ---
    # Retornar apenas a chave que foi modificada é a melhor prática no LangGraph.
    # O framework fará o merge dessa modificação no state global da run.
    return {"messages": [response]}


def tool_node(state: AgentState) -> AgentState:
    """
    Resumo Principal: Executa a ferramenta solicitada pelo LLM e devolve o resultado ao estado.

    COMO FUNCIONA:
    1. Inspeção da Última Mensagem: Verifica se a última mensagem do estado é uma AIMessage
       com chamadas de ferramentas pendentes. Se não for, retorna o estado sem modificações
       (mecanismo de segurança para evitar erros de fluxo inesperado no grafo).
    2. Extração da Chamada: Lê o nome, os argumentos e o ID único da última tool_call pendente.
    3. Execução da Ferramenta: Localiza a ferramenta pelo nome no dicionário TOOLS_BY_NAME
       e a invoca com os argumentos fornecidos pelo LLM. Erros são capturados e devolvidos
       como mensagem de texto (em vez de propagar a exceção e travar o grafo inteiro).
    4. Empacotamento da Resposta: Envolve o resultado em um ToolMessage vinculado ao ID
       da chamada original, para que o LLM saiba exatamente a qual requisição a resposta pertence.

    Args:
        state (AgentState): O estado atual do agente com as mensagens acumuladas.

    Returns:
        AgentState: Fragmento de estado com o ToolMessage resultante da execução da ferramenta.
    """
    # --- 1. Inspeção da Última Mensagem ---
    # Verificamos se realmente existe uma tool_call para processar.
    # Este guard previne erros caso o nó seja acionado em uma situação inesperada pelo grafo.
    llm_response = state["messages"][-1]
    if not isinstance(llm_response, AIMessage) or not getattr(
        llm_response, "tool_calls", None
    ):
        return state

    # --- 2. Extração e Execução de Todas as Chamadas ---
    # O LLM pode gerar MÚltiplas tool_calls em uma única AIMessage (ex: um CNPJ por chamada).
    # O protocolo LangChain/Groq EXIGE que cada tool_call_id presente na AIMessage possua
    # um ToolMessage correspondente. Processar apenas a útima (tool_calls[-1]) causa dois
    # problemas: as ferramentas dos outros CNPJs não são executadas, e o modelo recebe
    # uma resposta incompleta, encerrando o agente antes de terminar a tarefa.
    tool_messages = []
    for call in llm_response.tool_calls:
        name, args, id_ = call["name"], call["args"], call["id"]

        # --- 3. Execução da Ferramenta ---
        # Capturamos erros de forma granular para não travar o grafo.
        # O erro é devolvido ao LLM como conteúdo de texto para que ele possa se recuperar
        # e informar o usuário sobre o problema (ex: "CNPJ inválido").
        try:
            content = TOOLS_BY_NAME[name].invoke(args)
        except (KeyError, IndexError, TypeError, ValidationError, ValueError) as error:
            content = f"Erro ao executar tool {name}: {error}"

        # --- 4. Empacotamento da Resposta ---
        # O `tool_call_id` é o vínculo entre a requisição do LLM e a resposta da ferramenta.
        # Sem ele, o protocolo de mensagens do LangChain/Groq ficaria desalinhado.
        tool_messages.append(ToolMessage(content=str(content), tool_call_id=id_))

    return {"messages": tool_messages}


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
def build_graph() -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
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
    # --- 1. Definição da Estrutura ---
    builder = StateGraph(
        state_schema=AgentState,
        context_schema=None,
        input_schema=AgentState,
        output_schema=AgentState,
    )

    # --- 2. Registro dos Nós ---
    builder.add_node("call_llm", call_llm)
    builder.add_node("tool_node", tool_node)

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


# -----------------------------------------------------------------------------
# SINGLETON DO GRAFO COMPILADO
# -----------------------------------------------------------------------------
# O grafo é instanciado UMA ÚNICA VEZ no nível do módulo, ao ser importado pela primeira vez.
#
# Por que isso é CRÍTICO para o funcionamento do sistema:
# O InMemorySaver criado dentro de 'build_graph()' é um objeto em memória RAM.
# Se 'build_graph()' fosse chamado dentro de cada requisição HTTP, um InMemorySaver
# NOVO seria criado a cada request — destruindo o histórico da conversa anterior.
# Com o singleton, o MESMO InMemorySaver (e portanto o MESMO histórico por thread_id)
# é compartilhado por todas as requisições enquanto o servidor estiver no ar.
graph = build_graph()
