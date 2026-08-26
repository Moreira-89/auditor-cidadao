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
