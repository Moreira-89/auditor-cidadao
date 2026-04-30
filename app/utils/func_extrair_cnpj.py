import re


def extrair_cnpj(texto: str) -> list[str]:
    """
    Função auxiliar para extração de CNPJs do texto do edital.
    Utiliza expressão regular para encontrar CNPJs no formato.

    Args:
        texto (str): Texto do edital.

    Returns:
        list[str]: Lista de CNPJs encontrados no texto.
    """
    cnpjs = re.findall(r"\b\d{2}\.\d{3}\.\d{3}\/\d{4}\-\d{2}\b", texto)
    return cnpjs