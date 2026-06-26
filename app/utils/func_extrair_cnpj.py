import re

from validate_docbr import CNPJ as ValidadorCNPJ

# -----------------------------------------------------------------------------
# EXTRAÇÃO DE DADOS
# -----------------------------------------------------------------------------


def extrair_cnpj(texto: str) -> list[str]:
    """
    Objetivo: Extrair, normalizar e validar CNPJs de um texto usando Expressões Regulares.

    COMO FUNCIONA:
    1. Busca Formatada: Encontra CNPJs com pontuação (XX.XXX.XXX/XXXX-XX).
    2. Busca Limpa: Encontra sequências de exatamente 14 dígitos contíguos.
    3. Normalização: Soma os resultados e remove a formatação de pontuação de todos os matches.
    4. Validação: Filtra apenas os CNPJs matematicamente válidos (verifica os dígitos
       verificadores com o algoritmo oficial da Receita Federal) para descartar falsos positivos,
       como timestamps, valores monetários ou IDs de 14 dígitos que possam aparecer no edital.
    5. Deduplicação: Retorna a lista final sem duplicatas, preservando a ordem de ocorrência.

    Args:
        texto (str): O texto bruto onde a busca será executada (ex: texto do edital).

    Returns:
        list[str]: Lista contendo CNPJs únicos encontrados, limpos (apenas números) e validados.
    """
    # --- 1. Busca Formatada ---
    # Encontra todas as ocorrências de um CNPJ que possua pontos, barras e traço.
    # Este padrão já é estruturalmente específico, minimizando falsos positivos.
    cnpjs_formatados = re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", texto)

    # --- 2. Busca Limpa ---
    # Encontra ocorrências que consistem de exatamente 14 dígitos sequenciais.
    # Atenção: este padrão pode capturar outros números de 14 dígitos (timestamps, IDs).
    # A validação no passo 4 descarta esses falsos positivos.
    cnpjs_limpos = re.findall(r"\b\d{14}\b", texto)

    # Une ambas as listas
    todos = cnpjs_formatados + cnpjs_limpos

    # --- 3. Normalização ---
    # Aplica regex de substituição para remover quaisquer pontuações residuais dos matches,
    # padronizando todos os CNPJs como sequências de 14 dígitos numéricos.
    normalizados = [re.sub(r"[./-]", "", c) for c in todos]

    # --- 4. Validação ---
    # Instanciamos o validador da biblioteca `validate-docbr`, que implementa o algoritmo
    # oficial da Receita Federal para verificar os dois dígitos verificadores do CNPJ.
    # Isso descarta números de 14 dígitos que não são CNPJs reais (ex: datas, valores).
    validador = ValidadorCNPJ()
    validados = [c for c in normalizados if validador.validate(c)]

    # --- 5. Deduplicação ---
    # `dict.fromkeys` elimina duplicatas enquanto a ordem de inserção original é preservada.
    # Isso é importante pois um mesmo CNPJ pode aparecer formatado e não-formatado no edital.
    return list(dict.fromkeys(validados))
