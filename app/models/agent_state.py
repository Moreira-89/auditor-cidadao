from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


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
