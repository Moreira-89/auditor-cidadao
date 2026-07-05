"""
Métricas de avaliação do agente de auditoria contra o golden dataset: comparam o
que o agente efetivamente fez durante a execução (tools_chamadas, capturado em
pipeline_avaliacao.py) com o que cada caso espera (tools_esperadas).
"""

import re


def _normalizar(valor) -> str:
    """Remove pontuação (., /, -) e converte para string, pra comparar valores
    sem depender de como o LLM formatou o argumento (ex.: CNPJ com ou sem máscara)."""
    return re.sub(r"[./-]", "", str(valor))


# =============================================================================
# CONTEXTO GERAL DO MÓDULO
#
# calcular_aderencia_tools mede se o agente chamou as tools certas para um caso
# do golden dataset — não avalia a qualidade da resposta final, só se as
# ferramentas esperadas (tools_esperadas) foram de fato acionadas.
#
# A regra chave de design está no sentido do loop: ele percorre tools_esperadas,
# nunca tools_chamadas. Isso significa que uma tool extra que o agente chamou
# mas que não constava em tools_esperadas simplesmente não aparece em lugar
# nenhum do cálculo — nem ajuda, nem atrapalha a nota. Só o que era esperado
# entra na conta.
# =============================================================================


def calcular_aderencia_tools(caso: dict, tools_chamadas: list) -> float:
    """
    Mede a fração de caso["tools_esperadas"] que o agente efetivamente cobriu.

    Para cada tool esperada, ela é considerada COBERTA quando:
    - existe pelo menos uma chamada em tools_chamadas com o mesmo nome, E
    - se argumentos_esperados for None, o nome já basta (ex.: buscar_contexto_edital,
      buscar_informacao_web — tools onde só importa ter sido chamada, não com quê);
    - se argumentos_esperados tiver valores (ex.: {"cnpj": "..."}), pelo menos uma
      dessas chamadas precisa ter todos esses valores presentes no seu input.

    Caso contrário, ela é considerada NÃO COBERTA (a tool esperada nem foi chamada,
    ou foi chamada mas com os argumentos errados).

    O retorno é: quantidade_cobertas / total de tools_esperadas.
    """
    tools_esperadas = caso.get("tools_esperadas", [])
    if not tools_esperadas:
        return 1.0

    quantidade_cobertas = 0

    for tool_esperada in tools_esperadas:
        nome_esperado = tool_esperada["tool"]
        argumentos_esperados = tool_esperada.get("argumentos_esperados")

        # Isola, dentre todas as chamadas que o agente fez, só as que têm o
        # mesmo nome da tool esperada — as demais não são candidatas a cobrir
        # esta tool_esperada específica.
        chamadas_mesmo_nome = [
            chamada
            for chamada in tools_chamadas
            if chamada.get("tool") == nome_esperado
        ]

        if not chamadas_mesmo_nome:
            continue  # NÃO COBERTA — a tool esperada nem foi chamada

        if argumentos_esperados is None:
            # NÃO exige verificar o input: para estas tools, só chamar já basta
            quantidade_cobertas += 1
            continue

        # A partir daqui, precisamos confirmar que os argumentos batem — não
        # basta o nome da tool ter sido chamado.
        #
        # coberta_por_alguma_chamada vira True assim que UMA chamada (entre as
        # de mesmo nome) contiver TODOS os valores esperados no seu input.
        # Os dois `break` abaixo replicam o short-circuit que any()/all() fariam
        # sozinhos — sem eles o resultado final seria o mesmo, só que com
        # iterações desnecessárias depois de a resposta já estar decidida:
        #   - o break de dentro para assim que UM argumento não bate (não
        #     adianta checar os outros argumentos dessa mesma chamada);
        #   - o break de fora para assim que UMA chamada já bateu tudo (não
        #     precisa testar as chamadas seguintes, a tool já está coberta).
        coberta_por_alguma_chamada = False
        for chamada in chamadas_mesmo_nome:
            todos_argumentos_bateram = True
            for chave_esperada, valor_esperado in argumentos_esperados.items():
                # Busca a chave certa no input da chamada (ex.: "cnpj"), em vez de
                # procurar o valor esperado em qualquer lugar do dict inteiro
                # serializado — isso evita falso-positivo se o mesmo valor aparecer
                # por acaso em outro campo do input.
                valor_recebido = (chamada.get("input") or {}).get(chave_esperada)

                # Normaliza (remove pontuação, ex.: "." "/" "-") os dois lados antes de
                # comparar: o LLM pode formatar o CNPJ ("38.504.819/0001-69"), e a
                # normalização real só acontece dentro da tool, depois que
                # on_tool_start já capturou o argumento cru.
                if _normalizar(valor_esperado) != _normalizar(valor_recebido):
                    todos_argumentos_bateram = False
                    break

            if todos_argumentos_bateram:
                coberta_por_alguma_chamada = True
                break

        if coberta_por_alguma_chamada:
            quantidade_cobertas += 1

    return quantidade_cobertas / len(tools_esperadas)
