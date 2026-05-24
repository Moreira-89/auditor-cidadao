from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.checkpoint.memory import InMemorySaver


from app.core.dependencies import retornar_cliente_llm

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO DE DEPENDÊNCIAS DO AGENTE
# -----------------------------------------------------------------------------
# --- 1. Instanciação do Modelo LLM ---
# Inicializamos o modelo de linguagem de forma global no escopo deste módulo.
# O objetivo técnico é reaproveitar a mesma instância do LLM em todas as 
# invocações do grafo, evitando o custo e a lentidão de recriá-lo repetidas vezes.
model = retornar_cliente_llm(
    model_name="groq:llama-3.3-70b-versatile",
    config_params={
        "temperature": 0.1
    }
)


# -----------------------------------------------------------------------------
# DEFINIÇÃO DO ESTADO GLOBAL DO GRAFO
# -----------------------------------------------------------------------------
class AgentState(TypedDict):
    """
    Resumo Principal: Define a estrutura de dados (estado) mantida e transacionada ao longo do fluxo do LangGraph.

    COMO FUNCIONA:
    1. Armazenamento de Mensagens: Utiliza a chave `messages` para armazenar o histórico da conversa.
    2. Redução de Mensagens: A anotação `add_messages` atua como um "reducer", garantindo que novas
       mensagens retornadas pelos nós sejam concatenadas ao histórico existente, em vez de sobrescrevê-lo.

    OBSERVAÇÃO ARQUITETURAL:
        Quando quiser atualizar algo durante o processamento (ex: adicionar uma lista de CNPJs ou
        o nome do usuário), basta adicionar uma nova chave nesta TypedDict.
    """
    # --- 1. Armazenamento de Mensagens e 2. Redução de Mensagens ---
    # `add_messages` é crucial no LangGraph. Ele avisa o motor interno de que se um nó 
    # retornar algo na chave "messages", esse conteúdo deve sofrer um 'append' (anexar) 
    # e não uma simples substituição da variável.
    messages: Annotated[Sequence[BaseMessage], add_messages]


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
    response = model.invoke(state["messages"])
    
    # --- 2. Atualização do Estado ---
    # Retornar apenas a chave que foi modificada é a melhor prática no LangGraph.
    # O framework fará o merge dessa modificação no state global da run.
    return {"messages": [response]}


# -----------------------------------------------------------------------------
# CONSTRUÇÃO E COMPILAÇÃO DO FLUXO
# -----------------------------------------------------------------------------
def create_graph():
    """
    Resumo Principal: Constrói a máquina de estados (StateGraph) que define o fluxo de execução do agente.

    COMO FUNCIONA:
    1. Inicialização do Grafo: Cria o objeto `StateGraph` ancorado no esquema `AgentState`, 
       para garantir a tipagem correta dos dados que trafegam pelo fluxo.
    2. Adição de Nós e Arestas: Registra a função `call_llm` como um nó executável. Em seguida, 
       define o caminho lógico: o sistema começa no `START`, segue para `call_llm` e termina em `END`.
    3. Persistência em Memória: Configura um "checkpointer" em memória RAM para reter o histórico
       do estado entre os turnos conversacionais de um mesmo usuário/sessão.

    Args:
        Nenhum.

    Returns:
        CompiledGraph: O grafo executável compilado. É o objeto que será chamado usando 
        `.invoke()` para iniciar o fluxo.
    """
    # --- 1. Inicialização do Grafo ---
    # Definimos os schemas de input, output e o geral. Isso ajuda a prevenir 
    # erros silenciosos caso um nó tente retornar uma chave que não existe no estado.
    builder = StateGraph(
        state_schema=AgentState,
        context_schema=None,
        input_schema=AgentState,
        output_schema=AgentState
    )

    # --- 2. Adição de Nós e Arestas ---
    # As edges (arestas) definem as transições de um estado para o outro.
    # O START sinaliza o primeiro nó a ser engatilhado quando o grafo é invocado.
    # O END sinaliza a conclusão natural da pipeline.
    builder.add_node("call_llm", call_llm)
    builder.add_edge(START, "call_llm")
    builder.add_edge("call_llm", END)

    # --- 3. Persistência em Memória ---
    # O InMemorySaver é ótimo para manter o estado conversacional durante o ciclo
    # de vida do processo na memória (ideal para testes ou singletons do servidor).
    # O método `.compile` trava o grafo e o otimiza para execução.
    checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
