"""
Configuração e recursos compartilhados, carregados UMA vez no import do módulo:

- Os parâmetros dos modelos (agente principal, extrator e avaliador) lidos do .env, com
  defaults seguros para o servidor não quebrar no boot se alguma env var faltar.
- Um único GerenciadorVetorial (embeddings + conexão com o Pinecone), reutilizado por todo
  o app — abrir essa conexão é caro demais para refazer a cada requisição (padrão singleton).
"""

import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from app.core.logging_config import logger
from app.services.gerenciadorvetorial import GerenciadorVetorial

load_dotenv()

# Parâmetros do LLM lidos do .env para facilitar troca de modelo sem alterar código.
# Defaults abaixo evitam TypeError no boot (ex.: Railway) caso a env var não esteja configurada.
LLM_MODEL = os.getenv("LLM_MODEL", "openai:gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# Modelo usado no processo de extração de informações — separado do LLM_MODEL do agente
# principal para permitir trocar um sem afetar o outro.
EXTRATOR_MODEL = os.getenv("EXTRATOR_MODEL", "openai:gpt-4o-mini")
# Temperatura 0 por padrão: saída determinística é o comportamento esperado para extração.
EXTRATOR_TEMPERATURE = float(os.getenv("EXTRATOR_TEMPERATURE", "0.0"))

# Modelo usado pelo RAGAS (evaluation/pipeline_avaliacao.py) para julgar as métricas —
# separado do LLM_MODEL do agente principal para permitir trocar um sem afetar o outro.
AVALIADOR_MODEL = os.getenv("AVALIADOR_MODEL", "openai:gpt-4o-mini")
# Temperatura 0 por padrão: saída determinística é o comportamento esperado para avaliação.
AVALIADOR_TEMPERATURE = float(os.getenv("AVALIADOR_TEMPERATURE", "0.0"))

# URI de conexão do Redis, usado pelo AsyncRedisSaver como checkpointer do grafo — guarda o
# histórico de conversa por thread_id de forma persistente e compartilhada entre workers.
DB_URI = os.getenv("DB_URI", "redis://localhost:6379")


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
