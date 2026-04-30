import re

def extrair_cnpj(texto: str) -> list[str]:
    """
    Função auxiliar para extração de CNPJs do texto do edital.

    COMO FUNCIONA:
    Recebe um bloco de texto (uma string inteira, que pode ser todo o edital) e
    utiliza uma Expressão Regular (Regex) para varrer o texto em busca de padrões
    específicos que se pareçam com um CNPJ formatado (XX.XXX.XXX/XXXX-XX).
    
    A regex `\b\d{2}\.\d{3}\.\d{3}\/\d{4}\-\d{2}\b` significa:
    - `\b`: Limite de palavra (garante que não é um número gigantesco com o CNPJ no meio)
    - `\d{2}`: Dois dígitos, seguido de um ponto `\.`
    - `\d{3}`: Três dígitos, seguido de um ponto `\.`
    - `\d{3}`: Três dígitos, seguido de uma barra `\/`
    - `\d{4}`: Quatro dígitos (geralmente a filial), seguido de um traço `\-`
    - `\d{2}`: Dois dígitos finais (verificadores)

    Args:
        texto (str): O texto extraído do PDF do edital.

    Returns:
        list[str]: Uma lista contendo todas as strings que deram "match" com o formato do CNPJ.
    """
    # Encontra todas as ocorrências do padrão no texto e retorna como lista
    cnpjs = re.findall(r"\b\d{2}\.\d{3}\.\d{3}\/\d{4}\-\d{2}\b", texto)
    return cnpjs