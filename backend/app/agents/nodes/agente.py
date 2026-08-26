from app.agents.prompt import SYSTEM_PROMPT
from app.agents.state import AgentState
from langchain_core.messages import SystemMessage


def criar_no_agente(modelo):
    """
    Devolve o nó que chama o LLM — único ponto do projeto onde o modelo principal
    é invocado. Recebe o modelo já com bind_tools aplicado (ver graph.py).

    O SYSTEM_PROMPT é preposto a cada chamada em vez de ficar no histórico: assim
    ele não é persistido pelo checkpointer nem duplicado a cada turno, e mudanças
    no prompt valem imediatamente para conversas já em andamento.
    """

    async def no_agente(state: AgentState) -> dict:
        resposta = await modelo.ainvoke(
            [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        )
        return {"messages": [resposta]}

    return no_agente
