from langchain.agents import AgentState as _BaseAgentState


class AgentState(_BaseAgentState):
    """
    Estado do grafo: o que os nós do LangGraph carregam entre si durante uma conversa.
    Estende o AgentState de langchain.agents (messages, jump_to, structured_response) — é
    o schema que build_graph.py passa como state_schema= ao create_agent. Detalhes (reducer,
    ToolRuntime, plano de evolução): docs/arquitetura/visao_geral.md.
    """

    # Filtro geográfico do RAG — lido nas tools via um parâmetro runtime: ToolRuntime.
    estado: str
    municipio: str
