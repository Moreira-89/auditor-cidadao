import app.agents.graph as graph_mod
import app.agents.tools.contexto_edital as contexto_edital_mod
from app.agents.graph import get_graph, initialize_graph
from app.agents.relatorio import gerar_relatorio_inicial
from app.agents.tools.registry import TOOLS_NATIVAS
from app.config.logging import logger
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from evaluation.indexacao import EditalIndexado


class ToolChamada(BaseModel):
    tool: str
    argumentos: dict

class ResultadoExecucao(BaseModel):
    caso_id: str
    texto_laudo: str
    laudo: dict | None
    sugestoes_perguntas: list[str]
    tools_chamadas: list[ToolChamada]
    saidas_ferramentas: list[str]
    contexto_edital_recuperado: str | None

def preparar_ambiente() -> None:
    """
    Monta o grafo uma vez, fora do lifespan do FastAPI: só as 4 tools nativas,
    sem MCP e sem a camada aplicar_cache. Checkpointer em memória — a avaliação
    não precisa de Redis. Chamar uma vez antes do primeiro executar_caso.
    """
    # Avaliação precisa ser reprodutível: zera a temperatura do agente (produção usa 0.1).
    graph_mod.LLM_TEMPERATURE = 0.0
    initialize_graph(tools=TOOLS_NATIVAS, checkpointer=InMemorySaver())
    logger.info("Grafo de avaliação inicializado | tools=%d | temperature=0", len(TOOLS_NATIVAS))

async def executar_caso(edital: EditalIndexado) -> ResultadoExecucao:
    """
    Roda o relatório automático de produção contra o edital já indexado e
    coleta o que as métricas precisam: laudo, tools chamadas, saídas das tools
    e o contexto que o RAG recuperou.
    """
    # buscar_contexto_edital lê PINECONE_NAMESPACE do módulo em tempo de chamada —
    # redireciona a busca pro namespace isolado deste caso.
    contexto_edital_mod.PINECONE_NAMESPACE = edital.namespace

    thread_id = f"eval-{edital.caso_id}"
    resultado = await gerar_relatorio_inicial(
        thread_id=thread_id,
        lista_cnpj=edital.lista_cnpj,
        estado=edital.estado,
        municipio=edital.municipio,
    )
    if resultado is None:
        raise RuntimeError(f"gerar_relatorio_inicial devolveu None | caso={edital.caso_id}")

    # gerar_relatorio_inicial não devolve as mensagens; lê do checkpoint.
    snapshot = await get_graph().aget_state({"configurable": {"thread_id": thread_id}})
    mensagens = snapshot.values["messages"]

    tools_chamadas: list[ToolChamada] = []
    saidas_ferramentas: list[str] = []
    contextos_edital: list[str] = []
    for msg in mensagens:
        for tc in getattr(msg, "tool_calls", None) or []:
            tools_chamadas.append(ToolChamada(tool=tc["name"], argumentos=tc["args"]))
        if msg.__class__.__name__ == "ToolMessage":
            saidas_ferramentas.append(f"[{msg.name}] {msg.content}")
            if msg.name == "buscar_contexto_edital":
                contextos_edital.append(str(msg.content))

    logger.info(
        "Caso executado | caso=%s | tools=%s | anomalias=%s",
        edital.caso_id,
        [t.tool for t in tools_chamadas],
        [a.get("codigo") for a in (resultado["laudo"] or {}).get("anomalias", [])],
    )

    return ResultadoExecucao(
        caso_id=edital.caso_id,
        texto_laudo=resultado["texto"],
        laudo=resultado["laudo"],
        sugestoes_perguntas=resultado["sugestoes_perguntas"],
        tools_chamadas=tools_chamadas,
        saidas_ferramentas=saidas_ferramentas,
        contexto_edital_recuperado="\n\n".join(contextos_edital) or None,
    )