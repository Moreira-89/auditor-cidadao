import app.agents.graph as graph_mod
from app.agents.conversa import run_agent
from app.agents.eventos import ErroNoTurno, TokenGerado
from app.agents.graph import get_graph, initialize_graph
from app.agents.prompt import PROMPT_RELATORIO_INICIAL
from app.agents.tools.registry import TOOLS_NATIVAS
from app.config.logging import logger
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from evaluation.indexacao import EditalIndexado


class ToolChamada(BaseModel):
    tool: str
    argumentos: dict

class ResultadoExecucao(BaseModel):
    caso_id: str
    texto_laudo: str
    tools_chamadas: list[ToolChamada]
    saidas_ferramentas: list[str]
    contexto_edital_recuperado: str | None

def preparar_ambiente() -> None:
    """Monta o grafo fora do lifespan do FastAPI — ver docs/ia/avaliacao.md."""
    graph_mod.LLM_TEMPERATURE = 0.0  # reprodutível; produção usa 0.1
    initialize_graph(tools=TOOLS_NATIVAS, checkpointer=InMemorySaver())
    logger.info("Grafo de avaliação inicializado | tools=%d | temperature=0", len(TOOLS_NATIVAS))

async def executar_caso(edital: EditalIndexado) -> ResultadoExecucao:
    """Roda o edital indexado pelo mesmo run_agent() da produção — ver docs/ia/avaliacao.md."""
    thread_id = edital.edital_id  # filtro do RAG usa isso, ver contexto_edital.py
    texto: list[str] = []
    async for evento in run_agent(
        pergunta_usuario=PROMPT_RELATORIO_INICIAL,
        lista_cnpj=edital.lista_cnpj,
        estado=edital.estado,
        municipio=edital.municipio,
        thread_id=thread_id,
    ):
        if isinstance(evento, TokenGerado):
            texto.append(evento.texto)
        elif isinstance(evento, ErroNoTurno):
            # run_agent só loga a exceção original (conversa.py) — não há como recuperar
            # a causa raiz aqui, só apontar pro log.
            raise RuntimeError(  # noqa: TRY004 — não é erro de tipo, é falha do turno
                f"run_agent falhou | caso={edital.caso_id} — ver logs do backend"
            )
    texto_laudo = "".join(texto)

    # run_agent só emite o NOME da tool (FerramentaIniciada) — os argumentos e o
    # resultado de cada chamada só ficam disponíveis no checkpoint.
    snapshot = await get_graph().aget_state({"configurable": {"thread_id": thread_id}})
    mensagens = snapshot.values["messages"]

    tools_chamadas: list[ToolChamada] = []
    saidas_ferramentas: list[str] = []
    contextos_edital: list[str] = []
    for msg in mensagens:
        for tc in getattr(msg, "tool_calls", None) or []:
            tools_chamadas.append(ToolChamada(tool=tc["name"], argumentos=tc["args"]))
        if isinstance(msg, ToolMessage):
            saidas_ferramentas.append(f"[{msg.name}] {msg.content}")
            if msg.name == "buscar_contexto_edital":
                contextos_edital.append(str(msg.content))

    logger.info(
        "Caso executado | caso=%s | tools=%s | chars_laudo=%d",
        edital.caso_id,
        [t.tool for t in tools_chamadas],
        len(texto_laudo),
    )

    return ResultadoExecucao(
        caso_id=edital.caso_id,
        texto_laudo=texto_laudo,
        tools_chamadas=tools_chamadas,
        saidas_ferramentas=saidas_ferramentas,
        contexto_edital_recuperado="\n\n".join(contextos_edital) or None,
    )
