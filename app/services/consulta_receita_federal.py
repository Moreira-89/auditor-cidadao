"""
Integração com a BrasilAPI para consulta de dados cadastrais de empresas
brasileiras na Receita Federal a partir do CNPJ.

Separado de app/services/tools.py para manter a tool (@tool) enxuta: aqui mora
a chamada HTTP e a extração dos campos relevantes; validação de formato do
CNPJ e o texto de erro voltado ao LLM ficam no wrapper em tools.py.
"""

import httpx

URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"


async def consultar_cnpj(cnpj_limpo: str) -> dict:
    """
    Consulta os dados cadastrais de uma empresa na Receita Federal via BrasilAPI.

    Recebe o CNPJ já limpo (só dígitos) e validado — essa função não repete a
    validação, é responsabilidade do chamador (ver consultar_receita_federal em
    app/services/tools.py).

    Levanta as exceções nativas do httpx (TimeoutException, HTTPStatusError,
    RequestError) em caso de falha, em vez de mascará-las — o chamador decide
    como traduzir cada uma em uma mensagem de erro para o LLM.
    """
    url = URL_BRASILAPI_CNPJ.format(cnpj=cnpj_limpo)

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
    response.raise_for_status()

    data = response.json()
    # Devolve só os campos usados na auditoria e descarta o resto da resposta da BrasilAPI
    # (telefone, quadro de sócios/QSA, capital social, CNAEs secundários...). Isso enxuga o
    # que chega ao LLM. Obs.: alguns desses campos descartados são candidatos a reforçar o
    # catálogo de anomalias numa versão futura (ver "Backlog V2" no roadmap).
    return {
        "razao_social": data.get("razao_social"),
        "nome_fantasia": data.get("nome_fantasia"),
        "descricao_situacao_cadastral": data.get("descricao_situacao_cadastral"),
        "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao"),
        "data_inicio_atividade": data.get("data_inicio_atividade"),
        "logradouro": data.get("logradouro"),
        "numero": data.get("numero"),
        "bairro": data.get("bairro"),
        "municipio": data.get("municipio"),
        "uf": data.get("uf"),
        "cep": data.get("cep"),
    }
