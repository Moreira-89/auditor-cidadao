import requests


def consultar_receita_federal(cnpj: str) -> dict:
    """
    Consulta os dados cadastrais de uma empresa brasileira na Receita Federal a partir do seu CNPJ.

    COMO FUNCIONA:
    Este arquivo atua como uma "Ferramenta" (Tool) para a Inteligência Artificial. 
    Lembre-se que o LLM (Llama 3) é um modelo de linguagem treinado até uma data 
    específica e não tem acesso direto à internet para checar dados em tempo real.
    
    Portanto, nós construímos esta função Python tradicional e "damos" ela para o LLM. 
    Quando o modelo descobre um CNPJ, ele pede para executar essa função. Nós (o sistema)
    executamos o request HTTP na BrasilAPI, pegamos os dados reais e devolvemos
    como um JSON para a IA ler e incluir na sua resposta final.

    Casos de uso:
    - Confirmar se a razão social declarada no documento corresponde ao CNPJ informado.
    - Verificar se a empresa está com situação cadastral ATIVA.
    - Identificar o ramo de atividade (CNAE) e cruzar com o objeto do contrato.

    Args:
        cnpj (str): CNPJ da empresa. Pode vir formatado ("12.345.678/0001-99") ou 
                    só em números. A BrasilAPI resolve os dois.

    Returns:
        dict: Dicionário contendo os dados mastigados da empresa (razão social, status, etc) 
              ou um dicionário com a chave "error" em caso de falha.
    """
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

    try:
        # timeout=10 evita que a função trave para sempre caso o servidor não responda
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            dados_filtrados = {
                "razao_social": data.get("razao_social"),
                "nome_fantasia": data.get("nome_fantasia"),
                "descricao_situacao_cadastral": data.get(
                    "descricao_situacao_cadastral"
                ),
                "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao"),
                "data_inicio_atividade": data.get("data_inicio_atividade"),
            }
            return dados_filtrados
        else:
            # Erros HTTP conhecidos: 404 (CNPJ não encontrado), 429 (rate limit), etc.
            return {
                "error": f"Receita Federal retornou status {response.status_code} para o CNPJ {cnpj}"
            }

    except requests.exceptions.Timeout:
        # O servidor demorou mais de 5s para responder (lentidão ou instabilidade)
        return {
            "error": f"Timeout ao consultar o CNPJ {cnpj}: o servidor da BrasilAPI não respondeu a tempo"
        }

    except requests.exceptions.ConnectionError:
        # Sem internet, DNS falhou ou o servidor da BrasilAPI está fora do ar
        return {
            "error": f"Falha de conexão ao consultar o CNPJ {cnpj}: verifique a conectividade com a internet"
        }

    except requests.exceptions.RequestException as e:
        # Captura qualquer outro erro inesperado da biblioteca requests
        return {"error": f"Erro inesperado ao consultar o CNPJ {cnpj}: {str(e)}"}
