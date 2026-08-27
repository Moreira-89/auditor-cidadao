import re

from validate_docbr import CNPJ as ValidadorCNPJ


def extrair_cnpj(texto: str) -> list[str]:
    """
    Extrai, normaliza e valida todos os CNPJs encontrados em um texto.
    Combina busca por formato pontuado e por 14 dígitos contíguos, descarta
    falsos positivos via dígitos verificadores e retorna a lista deduplicada.
    """
    # Padrão pontuado é estruturalmente específico — minimiza falsos positivos por si só
    cnpjs_formatados = re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", texto)

    # Padrão de 14 dígitos pode capturar timestamps e IDs — a validação posterior descarta esses casos
    cnpjs_limpos = re.findall(r"\b\d{14}\b", texto)

    todos = cnpjs_formatados + cnpjs_limpos

    # Remove pontuação de todos os matches para padronizar como sequência de 14 dígitos
    normalizados = [re.sub(r"[./-]", "", c) for c in todos]

    # Descarta números que não passam no algoritmo oficial da Receita Federal (dígitos verificadores)
    validador = ValidadorCNPJ()
    validados = [c for c in normalizados if validador.validate(c)]

    # `dict.fromkeys` elimina duplicatas preservando a ordem de ocorrência
    return list(dict.fromkeys(validados))
