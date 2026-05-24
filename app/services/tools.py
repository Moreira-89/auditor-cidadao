import re
import requests
from langchain.tools import BaseTool, tool
from validate_docbr import CNPJ
from app.core.dependencies import gerenciador
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState


# -----------------------------------------------------------------------------
# FERRAMENTAS DO AGENTE (TOOLS)
# -----------------------------------------------------------------------------
@tool
def consultar_receita_federal(cnpj: str) -> dict:
    """
    Objetivo: Consultar os dados cadastrais de uma empresa brasileira na Receita Federal a partir do CNPJ.

    COMO FUNCIONA:
    1. Limpeza do CNPJ: Remove pontuações e hífens para padronizar o input em um formato numérico limpo.
    2. Validação Estrutural e de Dígitos: Utiliza a biblioteca especializada `validate-docbr` para conferir
       se o CNPJ é matematicamente autêntico, prevenindo requisições HTTP desnecessárias para números inválidos.
    3. Requisição à BrasilAPI: Faz uma chamada HTTP GET para a API pública com um timeout de 5 segundos.
    4. Tratamento da Resposta: Se a consulta for bem-sucedida (200), filtra e retorna os campos de interesse.
       Caso contrário ou em falha de conexão/timeout, retorna um dicionário informando o erro.

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

    # --- 2. Validação Estrutural e de Dígitos ---
    # Usamos a biblioteca especializada do ecossistema brasileiro para certificar
    # que o documento é real e matematicamente correto antes de fazermos a consulta de rede.
    if not CNPJ().validate(cnpj_limpo):
        return {"error": f"CNPJ inválido: '{cnpj}'. Os dígitos verificadores não conferem com o algoritmo oficial da Receita Federal."}

    # --- 3. Requisição à BrasilAPI ---
    # Usamos o CNPJ já limpo (só números) na URL — é o formato esperado pela API.
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"

    try:
        # timeout=5 evita que a função trave indefinidamente caso o servidor não responda.
        # O agente ficaria preso esperando e esgotaria o MAX_ITERACOES sem resposta útil.
        response = requests.get(url, timeout=5)

        # --- 4. Tratamento da Resposta ---
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

@tool
def buscar_contexto_edital(
    pergunta: str,
    # O InjectedState avisa o LangGraph para puxar o valor direto da chave "estado" do AgentState
    estado: Annotated[str, InjectedState("estado")],
    # O mesmo para o município
    municipio: Annotated[str, InjectedState("municipio")]
) -> str:
    """
    Realiza uma busca semântica avançada dentro do edital ativo indexado no banco vetorial.
    Deve ser usada sempre que precisares de encontrar regras, cláusulas, multas ou exigências do edital.
    
    Args:
        pergunta: O termo ou dúvida específica que desejas pesquisar no texto do edital.
    """
    
    # Dentro da ferramenta, simplesmente delegas o trabalho para o método
    # do teu GerenciadorVetorial que já faz o similarity_search perfeitamente!
    contexto = gerenciador.buscar_contexto(
        pergunta=pergunta,
        estado=estado,
        municipio=municipio
    )
    
    return contexto

TOOLS: list[BaseTool] = [consultar_receita_federal, buscar_contexto_edital]
TOOLS_BY_NAME: dict[str, BaseTool] = {t.name: t for t in TOOLS}