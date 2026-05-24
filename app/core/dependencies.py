from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from app.services.gerenciadorvetorial import GerenciadorVetorial

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO DO AMBIENTE
# -----------------------------------------------------------------------------
# --- 1. CARREGAR VARIÁVEIS DE AMBIENTE ---
# Lemos as configurações do arquivo .env e as injetamos na memória do sistema operativo.
# O motivo técnico desta chamada precoce é garantir que todos os drivers de banco de dados,
# serviços vetoriais e clientes LLM consigam ler as credenciais corretas desde a partida.
load_dotenv()


# -----------------------------------------------------------------------------
# DEPENDÊNCIAS E CLIENTES GLOBAIS
# -----------------------------------------------------------------------------
# Instanciamos o GerenciadorVetorial uma única vez ao subir o servidor.
# Internamente, ele carrega o modelo de embedding 'all-MiniLM-L6-v2' (centenas de MB)
# e conecta ao Pinecone. Recriar isso a cada requisição seria proibitivo em tempo e memória.
gerenciador = GerenciadorVetorial()


# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DE MODELOS DE LINGUAGEM (LLM)
# -----------------------------------------------------------------------------
def retornar_cliente_llm(model_name: str = "groq:llama-3.3-70b-versatile", config_params:dict={}):
    """
    Resumo Principal: Criar e retornar uma instância do cliente LLM inicializada.

    COMO FUNCIONA:
    1. Instanciação do Modelo: Usa a fábrica `init_chat_model` do LangChain para
       construir um modelo padronizado, especificando a Groq e a variante do Llama.
    2. Resolução de Credenciais: Delega ao LangChain a leitura automática das chaves
       disponíveis no ambiente (injetadas via dotenv).

    Returns:
        BaseChatModel: Objeto de modelo agnóstico do LangChain, já configurado e 
        autenticado para conversar com o provedor Groq.

    Raises:
        ValueError: Disparado internamente caso o framework perceba a falta das
                    variáveis de ambiente obrigatórias.
    """
    # --- 1. Instanciação do Modelo e 2. Resolução de Credenciais ---
    # Ao passar a URN "groq:llama-3.3-70b-versatile", o LangChain identifica
    # o provider e busca as chaves necessárias nas variáveis de ambiente correspondente.
    return init_chat_model(model_name, **config_params)