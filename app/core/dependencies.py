from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from app.core.logging_config import logger
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
# O GerenciadorVetorial é instanciado uma única vez ao subir o servidor (padrão Singleton).
# Internamente, ele carrega o modelo de embedding 'all-MiniLM-L6-v2' (centenas de MB)
# e conecta ao Pinecone. Recriar isso a cada requisição seria proibitivo em tempo e memória.
#
# O bloco try/except garante que uma falha de inicialização produza um log CRITICAL claro
# (com o motivo do erro) antes de o processo encerrar. Sem ele, uma API key ausente ou
# o Pinecone fora do ar gerariam uma exceção genérica sem contexto durante o import.
try:
    logger.info("Inicializando GerenciadorVetorial (modelo de embedding + Pinecone)...")
    gerenciador = GerenciadorVetorial()
    logger.info("GerenciadorVetorial inicializado com sucesso.")
except Exception as e:
    logger.critical(
        "Falha CRÍTICA ao inicializar GerenciadorVetorial. "
        "Verifique se PINECONE_API_KEY está definida e se há conectividade de rede. "
        "Erro: %s", e
    )
    raise


# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DE MODELOS DE LINGUAGEM (LLM)
# -----------------------------------------------------------------------------
def retornar_cliente_llm(model_name: str = "groq:llama-3.3-70b-versatile", config_params: dict | None = None):
    """
    Resumo Principal: Criar e retornar uma instância do cliente LLM inicializada.

    COMO FUNCIONA:
    1. Resolução dos Parâmetros: Garante que `config_params` seja um dict válido, mesmo quando
       o chamador não passa o argumento. Evita o bug clássico de argumento mutável padrão em Python:
       usar `dict = {}` como padrão faz com que o MESMO objeto de dicionário seja compartilhado
       por todas as chamadas, o que pode causar efeitos colaterais inesperados se o dict for
       modificado internamente. Usar `None` como sentinela e criar o dict no corpo é a solução correta.
    2. Instanciação do Modelo: Usa a fábrica `init_chat_model` do LangChain para
       construir um modelo padronizado, especificando a Groq e a variante do Llama.
    3. Resolução de Credenciais: Delega ao LangChain a leitura automática das chaves
       disponíveis no ambiente (injetadas via dotenv no início deste módulo).

    Args:
        model_name (str): Identificador do modelo no formato 'provider:modelo'.
                          Padrão: 'groq:llama-3.3-70b-versatile'.
        config_params (dict | None): Parâmetros opcionais de configuração do modelo
                                     (ex: {'temperature': 0.1, 'max_tokens': 4096}).
                                     Se None, usa um dicionário vazio (configuração padrão do modelo).

    Returns:
        BaseChatModel: Objeto de modelo agnóstico do LangChain, já configurado e
        autenticado para conversar com o provedor Groq.

    Raises:
        ValueError: Disparado internamente caso o framework perceba a falta das
                    variáveis de ambiente obrigatórias (ex: GROQ_API_KEY ausente).
    """
    # --- 1. Resolução dos Parâmetros ---
    # Sentinela None: cada chamada recebe seu próprio dict, independente das demais.
    config_params = config_params or {}

    # --- 2. Instanciação do Modelo e 3. Resolução de Credenciais ---
    # Ao passar a URN "groq:llama-3.3-70b-versatile", o LangChain identifica
    # o provider e busca as chaves necessárias nas variáveis de ambiente correspondente.
    return init_chat_model(model_name, **config_params)