import operator
from typing import Annotated

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Estado compartilhado entre os nós do grafo durante um turno de conversa."""

    # MessagesState já traz `messages`, com o reducer add_messages que acumula o
    # histórico em vez de sobrescrever.

    # Filtro geográfico do RAG. Não é lido pelo LLM: as tools o alcançam pelo
    # ToolRuntime (ver app/agents/tools/), que injeta o estado ativo na chamada.
    # Precisa ser reenviado a cada turno — o checkpointer só persiste as chaves
    # que o schema declara, e quem chama o grafo é quem sabe estado/município.
    estado: str
    municipio: str

    # Id do edital em análise. A thread é 1:1 com o edital, então é o próprio
    # thread_id; as tools de RAG o usam para filtrar a busca no banco vetorial
    # pelo edital certo. Reenviado a cada turno, pelo mesmo motivo de estado/município.
    thread_id: str

    # secao_ordem de cada seção já devolvida por buscar_contexto_edital nesta thread
    # (não o título — títulos podem se repetir no edital, ver contexto_edital.py).
    # Reducer de união, não sobrescreve.
    secoes_vistas: Annotated[set[int], operator.or_]
