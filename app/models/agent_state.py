from collections.abc import Sequence
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


# -----------------------------------------------------------------------------
# DEFINIÇÃO DO ESTADO GLOBAL DO GRAFO
# -----------------------------------------------------------------------------
class AgentState(TypedDict):
    """
    O "estado" do agente: a caixa de dados que o LangGraph carrega de um nó para o outro
    durante uma conversa. Tudo o que os nós do grafo precisam ler ou atualizar mora aqui.

    O que guarda:
    1. `messages` — o histórico da conversa (perguntas do usuário, respostas do LLM e
       resultados das ferramentas).
    2. `estado` e `municipio` — o contexto geográfico do edital em análise.

    Dois detalhes importantes:
    - `add_messages` (anotação sobre `messages`) é um "reducer": quando um nó devolve algo
      em `messages`, o LangGraph ANEXA ao histórico existente em vez de sobrescrever. Sem
      isso, cada passo apagaria a conversa anterior.
    - `estado` e `municipio` precisam estar declarados aqui para o LangGraph conseguir
      injetá-los automaticamente na ferramenta `buscar_contexto_edital` (via `InjectedState`).
      Se não estiverem no TypedDict, o framework não encontra esses valores no estado do grafo.

    Para estender: precisa carregar um dado novo pelo fluxo (ex.: um score parcial de risco)?
    Basta adicionar uma nova chave neste TypedDict.
    """

    # --- 1. Armazenamento de Mensagens e 2. Redução de Mensagens ---
    # `add_messages` é crucial no LangGraph. Ele avisa o motor interno de que se um nó
    # retornar algo na chave "messages", esse conteúdo deve sofrer um 'append' (anexar)
    # e não uma simples substituição da variável.
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # --- 3. Contexto Geográfico ---
    # Usados como filtros na busca semântica do Pinecone para recuperar apenas os chunks
    # do edital correto. São injetados automaticamente pelo LangGraph nas ferramentas que
    # declaram `InjectedState("estado")` e `InjectedState("municipio")` em sua assinatura.
    estado: str
    municipio: str
