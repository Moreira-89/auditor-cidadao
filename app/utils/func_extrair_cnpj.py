"""
Resumo: Utilitário para extração de CNPJs a partir de textos brutos.

COMO FUNCIONA:
1. Varrer Texto: A função recebe um texto extraído (ex: edital) e aplica expressões regulares.
2. Extração: Identifica tanto padrões formatados quanto numéricos puros que representem um CNPJ.
3. Normalização: Garante que os retornos sejam formatados uniformemente, removendo pontuações e duplicatas.
"""

import re

# -----------------------------------------------------------------------------
# EXTRAÇÃO DE DADOS
# -----------------------------------------------------------------------------

def extrair_cnpj(texto: str) -> list[str]:
    """
    Objetivo: Extrair e normalizar CNPJs de um texto usando Expressões Regulares.

    COMO FUNCIONA:
    1. Busca Formatada: Encontra CNPJs com pontuação (XX.XXX.XXX/XXXX-XX).
    2. Busca Limpa: Encontra CNPJs puramente numéricos (14 dígitos).
    3. Normalização: Soma os resultados, remove a formatação e exclui as redundâncias mantendo a ordem.

    Args:
        texto (str): O texto bruto onde a busca será executada (ex: texto do edital).

    Returns:
        list[str]: Uma lista contendo todas as strings de CNPJs únicos encontrados e limpos (apenas números).
    """
    # --- 1. Busca Formatada ---
    # Encontra todas as ocorrências de um CNPJ que possua pontos, barras e traço.
    cnpjs_formatados = re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", texto)
    
    # --- 2. Busca Limpa ---
    # Encontra ocorrências que consistem de exatamente 14 dígitos sequenciais.
    cnpjs_limpos = re.findall(r"\b\d{14}\b", texto)

    # Une ambas as listas
    todos = cnpjs_formatados + cnpjs_limpos

    # --- 3. Normalização ---
    # Aplica regex de substituição para remover quaisquer pontuações residuais dos matches.
    normalizados = [re.sub(r"[./-]", "", c) for c in todos]

    # Retorna usando dict.fromkeys para eliminar duplicatas enquanto a ordem original é preservada.
    return list(dict.fromkeys(normalizados))