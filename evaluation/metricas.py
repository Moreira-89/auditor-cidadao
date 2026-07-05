"""
Métricas de avaliação do agente de auditoria contra o golden dataset: comparam o
que o agente efetivamente fez durante a execução (tools_chamadas, capturado em
pipeline_avaliacao.py) com o que cada caso espera (tools_esperadas).
"""

import re


def calcular_aderencia_tools(caso: dict, tools_chamadas: list) -> float:
    """
    Mede a fração de caso["tools_esperadas"] que o agente efetivamente cobriu.

    Para cada tool esperada: MISS se nenhuma chamada em tools_chamadas tem o mesmo
    nome; HIT se o nome bate e argumentos_esperados é None (nome já basta, ex.:
    buscar_contexto_edital, buscar_informacao_web); senão HIT só se algum item de
    tools_chamadas com esse nome tiver, no seu input, todos os valores de
    argumentos_esperados (ex.: o cnpj esperado).

    O loop percorre apenas tools_esperadas, nunca tools_chamadas — chamadas extras
    (tools que o agente chamou mas não eram esperadas) nunca entram no numerador
    nem no denominador, ou seja, não penalizam a aderência.
    """
    tools_esperadas = caso.get("tools_esperadas", [])
    if not tools_esperadas:
        return 1.0

    hits = 0
    for tool_esperada in tools_esperadas:
        nome_esperado = tool_esperada["tool"]
        argumentos_esperados = tool_esperada.get("argumentos_esperados")

        chamadas_mesmo_nome = [
            chamada
            for chamada in tools_chamadas
            if chamada.get("tool") == nome_esperado
        ]

        if not chamadas_mesmo_nome:
            continue  # MISS — tool esperada nem foi chamada

        if argumentos_esperados is None:
            hits += 1  # HIT — nome já basta
            continue

        # HIT só se alguma chamada com esse nome contém todos os argumentos esperados no input.
        # Remove pontuação (., /, -) dos dois lados antes de comparar: o LLM pode formatar o
        # CNPJ ("38.504.819/0001-69"), e a normalização real só acontece dentro da tool,
        # depois que on_tool_start já capturou o argumento cru.
        bateu = any(
            all(
                re.sub(r"[./-]", "", str(valor_esperado))
                in re.sub(r"[./-]", "", str(chamada.get("input")))
                for valor_esperado in argumentos_esperados.values()
            )
            for chamada in chamadas_mesmo_nome
        )
        if bateu:
            hits += 1

    return hits / len(tools_esperadas)
