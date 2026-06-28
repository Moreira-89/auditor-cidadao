import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from app.core.logging_config import logger
from app.services.gerenciadorvetorial import GerenciadorVetorial

load_dotenv()

# Parâmetros do LLM lidos do .env para facilitar troca de modelo sem alterar código
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS"))


# GerenciadorVetorial instanciado uma única vez no import (Singleton):
# carrega o modelo de embedding e conecta ao Pinecone — custoso demais para recriar por requisição.
# O try/except garante log CRITICAL com contexto claro antes de encerrar o processo em caso de falha.
try:
    logger.info("Inicializando GerenciadorVetorial (modelo de embedding + Pinecone)...")
    gerenciador = GerenciadorVetorial()
    logger.info("GerenciadorVetorial inicializado com sucesso.")
except Exception as e:
    logger.critical(
        "Falha CRÍTICA ao inicializar GerenciadorVetorial. "
        "Verifique se PINECONE_API_KEY está definida e se há conectividade de rede. "
        "Erro: %s",
        e,
    )
    raise


def retornar_cliente_llm(model_name: str, config_params: dict | None = None):
    """
    Cria e retorna uma instância do cliente LLM configurada via LangChain.
    Usa None como sentinela para config_params a fim de evitar o bug de argumento mutável padrão em Python.
    """
    # Sentinela None: cada chamada recebe seu próprio dict, independente das demais
    config_params = config_params or {}

    # init_chat_model identifica o provider pelo prefixo do model_name e lê as credenciais do ambiente
    return init_chat_model(model_name, **config_params)
