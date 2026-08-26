from app.agents.envelope import escape_xml, montar_primeiro_turno
from app.agents.graph import get_graph
from app.agents.prompt import PROMPT_EXTRATOR_INICIAL, PROMPT_RELATORIO_INICIAL
from app.config.logging import logger
from app.config.settings import (
    EXTRATOR_MAX_RETRIES,
    EXTRATOR_MODEL,
    EXTRATOR_TEMPERATURE,
    EXTRATOR_TIMEOUT_SEGUNDOS,
)
from app.llm import retornar_cliente_llm
from app.api.schemas.laudo import RelatorioInicial
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

_extrator = None


def get_extrator():
    """Cliente LLM que estrutura o laudo em JSON, criado na primeira chamada."""
    global _extrator
    if _extrator is None:
        _extrator = retornar_cliente_llm(
            model_name=EXTRATOR_MODEL,
            config_params={
                "temperature": EXTRATOR_TEMPERATURE,
                "timeout": EXTRATOR_TIMEOUT_SEGUNDOS,
                "max_retries": EXTRATOR_MAX_RETRIES,
            },
        )
    return _extrator


async def gerar_relatorio_inicial(
    thread_id: str,
    lista_cnpj: list[str],
    estado: str,
    municipio: str,
) -> dict | None:
    """
    Gera o relatório automático pós-indexação: assim que o upload termina de indexar o
    edital, roda um primeiro turno sintético — sem esperar o usuário perguntar nada —
    pedindo um laudo completo, e extrai dele um resumo estruturado mais sugestões de
    perguntas de acompanhamento.

    Roda como o PRIMEIRO turno da thread (mesmo `thread_id` que o frontend vai usar no
    chat): perguntas seguintes continuam essa mesma conversa no checkpointer, em vez de
    começar do zero. Por isso deve ser chamado uma única vez por thread, antes de
    qualquer run_agent() no mesmo thread_id.

    Não levanta exceção: qualquer falha (LLM, extração, timeout) é logada e vira None —
    o upload não pode falhar por causa do relatório automático, que é um "bônus" de UX,
    não um requisito do fluxo de indexação.
    """
    try:
        estado = escape_xml(estado)
        municipio = escape_xml(municipio)

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        grafo = get_graph()

        mensagem_inicial = montar_primeiro_turno(
            PROMPT_RELATORIO_INICIAL, lista_cnpj, estado, municipio
        )

        # Sem streaming aqui — o relatório faz parte da resposta síncrona do upload, não
        # do canal SSE de conversa (ver docs/arquitetura para o trade-off de latência).
        resultado_agente = await grafo.ainvoke(
            {
                "messages": [mensagem_inicial],
                "estado": estado,
                "municipio": municipio,
            },
            config={**config, "recursion_limit": 50},
        )
        mensagem_final = resultado_agente["messages"][-1]
        texto_relatorio = (
            mensagem_final.content if isinstance(mensagem_final, AIMessage) else ""
        )

        extrator_estruturado = get_extrator().with_structured_output(RelatorioInicial)
        resultado = await extrator_estruturado.ainvoke(
            [
                SystemMessage(content=PROMPT_EXTRATOR_INICIAL),
                HumanMessage(content=texto_relatorio),
            ]
        )

        return {
            "texto": texto_relatorio,
            "laudo": resultado.laudo.model_dump() if resultado.laudo else None,
            "sugestoes_perguntas": resultado.sugestoes_perguntas,
        }
    except Exception:  # noqa: BLE001
        logger.exception(
            "Erro ao gerar relatório automático pós-indexação | thread=%s", thread_id
        )
        return None
