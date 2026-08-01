"""
Configuração e recursos compartilhados, carregados UMA vez no import do módulo:

- Os parâmetros dos modelos (agente principal, extrator e avaliador) lidos do .env, com
  defaults seguros para o servidor não quebrar no boot se alguma env var faltar.
- Um único GerenciadorVetorial (embeddings + conexão com o Pinecone), reutilizado por todo
  o app — abrir essa conexão é caro demais para refazer a cada requisição (padrão singleton).
"""

import os
import secrets

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
REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")


# Minutos de INATIVIDADE até um checkpoint (histórico de conversa) expirar no Redis
# — não é um TTL fixo desde a criação: cada leitura renova a contagem (ver
# refresh_on_read em app/services/lifespan.py), então uma conversa em uso nunca
# expira no meio, só threads abandonadas são limpas. Default 1440 min = 24h.
TTL_CHECKPOINT_MINUTOS = int(os.getenv("TTL_CHECKPOINT_MINUTOS", "1440"))

# Diferencia ambiente de produção (Railway, servido via HTTPS) de desenvolvimento
# local (uvicorn em http://localhost, sem TLS). Hoje o único uso é decidir a flag
# `secure` do cookie de sessão (ver app/api/dependencies_http.py) — um cookie
# `Secure=True` só é reenviado pelo navegador em conexões HTTPS, então usá-lo fixo
# faria o cookie nunca persistir em dev local, quebrando o rate limiter em silêncio
# (cada requisição pareceria vir de um cliente novo).
#
# Comparação por string (não bool(os.getenv(...))) porque bool("False") é True em
# Python — qualquer string não-vazia é "verdadeira". O default é "True" de propósito:
# se a env var faltar (ex.: esquecida no deploy), o comportamento seguro (HTTPS
# obrigatório) é o padrão, não o inseguro.
AMBIENTE_PRODUCAO = os.getenv("AMBIENTE_PRODUCAO", "True").strip().lower() == "true"

# Chave secreta usada para ASSINAR os cookies de identificação de sessão (ver
# app/utils/cookie_manager.py). Só quem conhece essa chave consegue gerar uma
# assinatura válida — é o que impede um cliente de forjar ou adulterar o cookie.
#
# Se a env var não estiver definida, geramos uma chave aleatória em memória no boot.
# Isso evita o servidor quebrar em ambiente de desenvolvimento, mas tem um efeito
# colateral importante: a cada reinício do processo (ou em cada worker, se rodar
# múltiplos), a chave muda e os cookies emitidos antes viram inválidos. Por isso,
# em produção, SEMPRE defina COOKIE_SECRET_KEY no ambiente.
_COOKIE_SECRET_KEY_ENV = os.getenv("COOKIE_SECRET_KEY")
if not _COOKIE_SECRET_KEY_ENV:
    logger.warning(
        "COOKIE_SECRET_KEY não definida no ambiente — usando uma chave aleatória "
        "gerada em memória. Os cookies emitidos não sobrevivem a um restart do "
        "servidor. Defina essa env var em produção."
    )
COOKIE_SECRET_KEY = _COOKIE_SECRET_KEY_ENV or secrets.token_hex(32)


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
