"""
Montagem do grafo e o ciclo ReAct, sem rede: um modelo falso no lugar do LLM.

O teste do ToolRuntime é o mais importante do arquivo — a injeção acontece dentro do
ToolNode, e se ela parar de funcionar as tools de RAG e de busca web passam a receber
`runtime=None` sem erro explícito.
"""

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

import app.agents.graph as graph_mod


class ModeloFalso:
    """Pede uma tool no primeiro turno e responde no segundo, forçando o ciclo completo."""

    def __init__(self, nome_tool: str):
        self.nome_tool = nome_tool
        self.chamadas = 0
        self.mensagens_recebidas = []

    def bind_tools(self, tools):
        self.tools_ligadas = tools
        return self

    async def ainvoke(self, messages):
        self.chamadas += 1
        self.mensagens_recebidas.append(messages)
        if self.chamadas == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": self.nome_tool, "args": {"pergunta": "p"}, "id": "c1"}],
            )
        return AIMessage(content="resposta final")


@tool
async def tool_espia(pergunta: str, runtime: ToolRuntime) -> str:
    """Devolve o contexto geográfico que recebeu, para o teste conferir a injeção."""
    return f"{runtime.state['estado']}/{runtime.state['municipio']}"


def _montar(monkeypatch):
    modelo = ModeloFalso("tool_espia")
    monkeypatch.setattr(graph_mod, "retornar_cliente_llm", lambda **kw: modelo)
    grafo = graph_mod.build_graph(tools=[tool_espia], checkpointer=InMemorySaver())
    return grafo, modelo


ENTRADA = {
    "messages": [HumanMessage(content="qual o prazo?")],
    "estado": "PA",
    "municipio": "Belém",
}
CONFIG = {"configurable": {"thread_id": "t-teste"}}


def test_grafo_tem_os_dois_nos_esperados(monkeypatch):
    grafo, _ = _montar(monkeypatch)
    assert {"agente", "ferramentas"} <= set(grafo.get_graph().nodes)


async def test_ciclo_react_completo(monkeypatch):
    grafo, modelo = _montar(monkeypatch)
    resultado = await grafo.ainvoke(ENTRADA, config=CONFIG)

    tipos = [type(m).__name__ for m in resultado["messages"]]
    assert tipos == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    assert modelo.chamadas == 2, "o agente precisa ser chamado de novo após a ferramenta"
    assert resultado["messages"][-1].content == "resposta final"


async def test_system_prompt_e_preposto_a_cada_chamada(monkeypatch):
    grafo, modelo = _montar(monkeypatch)
    await grafo.ainvoke(ENTRADA, config=CONFIG)

    # As duas chamadas ao modelo precisam começar com a SystemMessage — o prompt não
    # fica no histórico, é preposto toda vez.
    assert all(msgs[0].type == "system" for msgs in modelo.mensagens_recebidas)
    assert len(modelo.mensagens_recebidas) == 2


async def test_toolruntime_recebe_o_contexto_geografico_do_estado(monkeypatch):
    grafo, _ = _montar(monkeypatch)
    resultado = await grafo.ainvoke(ENTRADA, config=CONFIG)

    [tool_message] = [m for m in resultado["messages"] if isinstance(m, ToolMessage)]
    assert tool_message.content == "PA/Belém"


async def test_estado_e_municipio_sobrevivem_ao_turno(monkeypatch):
    grafo, _ = _montar(monkeypatch)
    resultado = await grafo.ainvoke(ENTRADA, config=CONFIG)
    assert (resultado["estado"], resultado["municipio"]) == ("PA", "Belém")


async def test_checkpointer_preserva_o_historico_entre_turnos(monkeypatch):
    grafo, modelo = _montar(monkeypatch)
    await grafo.ainvoke(ENTRADA, config=CONFIG)

    modelo.chamadas = 1  # já respondeu; agora só devolve texto
    await grafo.ainvoke(
        {"messages": [HumanMessage(content="e o valor?")], "estado": "PA", "municipio": "Belém"},
        config=CONFIG,
    )
    estado = await grafo.aget_state(CONFIG)
    conteudos = [m.content for m in estado.values["messages"]]
    assert "qual o prazo?" in conteudos and "e o valor?" in conteudos
