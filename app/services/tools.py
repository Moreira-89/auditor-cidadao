"""
Resumo: Ferramentas (Tools) disponíveis para o Agente de IA consultar dados externos em tempo real.

COMO FUNCIONA:
1. Contrato com o Agente: As funções deste arquivo são "doadas" ao LLM como ferramentas invocáveis.
   Quando o modelo detecta um CNPJ, ele requisita a execução de `consultar_receita_federal`. O código
   Python faz a chamada HTTP real, e o JSON de retorno volta para o modelo continuar a análise.
2. Validação Defensiva: Antes de qualquer chamada à rede, o CNPJ é validado estruturalmente e pelos
   seus dígitos verificadores. Isso evita que o agente desperdice iterações (e tempo do usuário)
   consultando CNPJs claramente inválidos que o próprio modelo pode ter gerado mal-formados.
3. Tratamento de Erros: Todos os erros retornam um dicionário com a chave "error", não uma exceção.
   O agente consegue ler esse erro e comunicar ao usuário o que aconteceu de forma amigável.
"""

import re

import requests


def validar_digitos_cnpj(cnpj: str) -> bool:
    """
    Objetivo: Validar os dois dígitos verificadores de um CNPJ usando o algoritmo oficial da Receita Federal.

    COMO FUNCIONA:
    1. Limpeza e Checagem Básica: Remove pontuações e valida se são exatamente 14 dígitos numéricos.
    2. Rejeição de Sequências Triviais: CNPJs com todos os dígitos iguais (ex: 11111111111111)
       são matematicamente válidos pelo algoritmo, mas são sabidamente inválidos e usados como
       "CNPJs nulos" em sistemas legados — rejeitamos aqui.
    3. Cálculo do 1º Dígito Verificador: Multiplica os 12 primeiros dígitos por pesos decrescentes
       [5,4,3,2,9,8,7,6,5,4,3,2], soma os produtos, tira o resto da divisão por 11 e aplica a regra:
       se o resto < 2, o dígito é 0; caso contrário, é 11 - resto.
    4. Cálculo do 2º Dígito Verificador: Repete o processo com os 13 primeiros dígitos e pesos
       [6,5,4,3,2,9,8,7,6,5,4,3,2].
    5. Comparação Final: Verifica se os dígitos calculados batem com os dois últimos do CNPJ original.

    Args:
        cnpj (str): CNPJ a ser validado. Pode conter pontuações (elas serão removidas internamente).

    Returns:
        bool: True se o CNPJ passar em todas as validações, False caso contrário.
    """
    # --- 1. Limpeza e Checagem Básica ---
    cnpj = re.sub(r"[./-]", "", cnpj)
    if len(cnpj) != 14 or not cnpj.isdigit():
        return False

    # --- 2. Rejeição de Sequências Triviais ---
    # set(cnpj) retorna o conjunto de caracteres únicos — se tiver só 1 elemento,
    # todos os dígitos são iguais (ex: "00000000000000"), o que é um CNPJ nulo.
    if len(set(cnpj)) == 1:
        return False

    # --- 3. Cálculo do 1º Dígito Verificador ---
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto1 = soma1 % 11
    digito1 = 0 if resto1 < 2 else 11 - resto1

    # --- 4. Cálculo do 2º Dígito Verificador ---
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma2 = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto2 = soma2 % 11
    digito2 = 0 if resto2 < 2 else 11 - resto2

    # --- 5. Comparação Final ---
    return int(cnpj[12]) == digito1 and int(cnpj[13]) == digito2


def consultar_receita_federal(cnpj: str) -> dict:
    """
    Objetivo: Consultar os dados cadastrais de uma empresa brasileira na Receita Federal a partir do CNPJ.

    COMO FUNCIONA:
    1. Limpeza do CNPJ: Remove pontuações para garantir um input padronizado antes da validação.
    2. Validação Estrutural: Checa se o CNPJ tem exatamente 14 dígitos numéricos.
    3. Validação dos Dígitos Verificadores: Executa o algoritmo oficial para confirmar que o CNPJ
       é matematicamente legítimo — evitando chamadas HTTP desnecessárias para CNPJs inválidos.
    4. Requisição à BrasilAPI: Faz o GET para a API pública e aguarda a resposta (timeout de 5s).
    5. Tratamento da Resposta: Em caso de sucesso (200), filtra e retorna apenas os campos úteis
       para a análise de auditoria. Para qualquer erro HTTP ou de rede, retorna um dict com "error".

    Args:
        cnpj (str): CNPJ enviado pelo agente de IA. Pode vir formatado ("12.345.678/0001-99")
                    ou apenas numérico ("12345678000199"). A limpeza é feita internamente.

    Returns:
        dict: Em sucesso, retorna campos da empresa (razão social, situação cadastral, CNAE, etc).
              Em falha, retorna {"error": "<descrição do problema>"} para o agente tratar.
    """
    # --- 1. Limpeza do CNPJ ---
    # Removemos qualquer pontuação antes de validar, pois o modelo pode enviar
    # o CNPJ em diferentes formatos dependendo de como o leu no documento.
    cnpj_limpo = re.sub(r"[./-]", "", cnpj)

    # --- 2. Validação Estrutural ---
    # Garantia mínima: deve ser composto apenas de dígitos e ter exatamente 14 caracteres.
    if not cnpj_limpo.isdigit() or len(cnpj_limpo) != 14:
        return {"error": f"CNPJ inválido: '{cnpj}'. Deve conter exatamente 14 dígitos numéricos."}

    # --- 3. Validação dos Dígitos Verificadores ---
    # Checagem matemática pelo algoritmo oficial. Evita chamadas HTTP para CNPJs
    # tecnicamente bem formados mas logicamente impossíveis (ex: 00.000.000/0000-00).
    if not validar_digitos_cnpj(cnpj_limpo):
        return {"error": f"CNPJ inválido: '{cnpj}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal."}

    # --- 4. Requisição à BrasilAPI ---
    # Usamos o CNPJ já limpo (só números) na URL — é o formato esperado pela API.
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"

    try:
        # timeout=5 evita que a função trave indefinidamente caso o servidor não responda.
        # O agente ficaria preso esperando e esgotaria o MAX_ITERACOES sem resposta útil.
        response = requests.get(url, timeout=5)

        # --- 5. Tratamento da Resposta ---
        if response.status_code == 200:
            data = response.json()

            # Filtramos apenas os campos relevantes para auditoria de editais.
            # Devolver o JSON inteiro seria redundante e aumentaria o consumo de tokens.
            dados_filtrados = {
                "razao_social": data.get("razao_social"),
                "nome_fantasia": data.get("nome_fantasia"),
                "descricao_situacao_cadastral": data.get("descricao_situacao_cadastral"),
                "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao"),
                "data_inicio_atividade": data.get("data_inicio_atividade"),
            }
            return dados_filtrados
        else:
            # Erros HTTP conhecidos: 404 (CNPJ não encontrado na base), 429 (rate limit), etc.
            return {
                "error": f"Receita Federal retornou status {response.status_code} para o CNPJ {cnpj_limpo}"
            }

    except requests.exceptions.Timeout:
        # O servidor demorou mais de 5s — pode ser lentidão pontual ou instabilidade da BrasilAPI.
        return {
            "error": f"Timeout ao consultar o CNPJ {cnpj_limpo}: o servidor da BrasilAPI não respondeu a tempo."
        }

    except requests.exceptions.ConnectionError:
        # Sem internet, DNS falhou ou o servidor da BrasilAPI está fora do ar.
        return {
            "error": f"Falha de conexão ao consultar o CNPJ {cnpj_limpo}: verifique a conectividade com a internet."
        }

    except requests.exceptions.RequestException as e:
        # Captura qualquer outro erro inesperado da biblioteca requests (ex: SSL, redirect loop).
        return {"error": f"Erro inesperado ao consultar o CNPJ {cnpj_limpo}: {str(e)}"}
