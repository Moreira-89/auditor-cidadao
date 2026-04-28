import requests

def consultar_receita_federal(cnpj: str) -> dict:
    """
    Consulta os dados cadastrais de uma empresa brasileira na Receita Federal a partir do seu CNPJ.

    Use esta função sempre que precisar verificar ou enriquecer informações sobre uma empresa
    mencionada em um edital, contrato ou documento público. Ela é especialmente útil para:
    - Confirmar se a razão social declarada no documento corresponde ao CNPJ informado.
    - Verificar se a empresa está com situação cadastral ATIVA perante a Receita Federal.
    - Identificar o ramo de atividade (CNAE) e cruzar com o objeto do contrato.

    Args:
        cnpj (str): CNPJ da empresa a ser consultada. Pode ser enviado com ou sem formatação
                    (ex: "12.345.678/0001-99" ou "12345678000199"). A API aceita ambos os formatos.

    Returns:
        dict: Em caso de sucesso, retorna um dicionário com os seguintes campos:
            - razao_social (str): Nome jurídico oficial da empresa registrado na Receita Federal.
            - nome_fantasia (str | None): Nome comercial da empresa, se houver.
            - descricao_situacao_cadastral (str): Situação atual da empresa (ex: "ATIVA", "BAIXADA", "SUSPENSA").
            - cnae_fiscal_descricao (str): Descrição da atividade econômica principal da empresa.
            - data_inicio_atividade (str): Data de abertura da empresa no formato "AAAA-MM-DD".

              Em caso de falha (API indisponível, CNPJ inexistente, erro de rede), retorna:
            - error (str): Mensagem descrevendo o motivo da falha. Informe este erro ao usuário
                           e prossiga a análise apenas com os dados disponíveis no documento.
    """
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

    try:
        # timeout=10 evita que a função trave para sempre caso o servidor não responda
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            
            dados_filtrados = {"razao_social": data.get("razao_social"),
                                "nome_fantasia": data.get("nome_fantasia"),
                                "descricao_situacao_cadastral": data.get("descricao_situacao_cadastral"),
                                "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao"),
                                "data_inicio_atividade": data.get("data_inicio_atividade")
                                }
            return dados_filtrados
        else:
            # Erros HTTP conhecidos: 404 (CNPJ não encontrado), 429 (rate limit), etc.
            return {"error": f"Receita Federal retornou status {response.status_code} para o CNPJ {cnpj}"}

    except requests.exceptions.Timeout:
        # O servidor demorou mais de 5s para responder (lentidão ou instabilidade)
        return {"error": f"Timeout ao consultar o CNPJ {cnpj}: o servidor da BrasilAPI não respondeu a tempo"}

    except requests.exceptions.ConnectionError:
        # Sem internet, DNS falhou ou o servidor da BrasilAPI está fora do ar
        return {"error": f"Falha de conexão ao consultar o CNPJ {cnpj}: verifique a conectividade com a internet"}

    except requests.exceptions.RequestException as e:
        # Captura qualquer outro erro inesperado da biblioteca requests
        return {"error": f"Erro inesperado ao consultar o CNPJ {cnpj}: {str(e)}"}