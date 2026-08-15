"""
Configuração e recursos compartilhados, carregados uma vez no import do módulo.

Referência completa de cada env var (default, obrigatoriedade, o "porquê" de cada
uma): docs/operacional/variaveis_ambiente.md. Comentários abaixo só cobrem o que
não está lá — decisões específicas do código Python.
"""

import os
import secrets

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from app.core.logging_config import logger
from app.services.gerenciadorvetorial import GerenciadorVetorial

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "openai:gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TIMEOUT_SEGUNDOS = int(os.getenv("LLM_TIMEOUT_SEGUNDOS", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# Extrator roda no mesmo turno, depois do streaming (ver ai_engine.py) — reusa os
# limites do agente principal em vez de expor env vars próprias sem necessidade.
EXTRATOR_MODEL = os.getenv("EXTRATOR_MODEL", "openai:gpt-4o-mini")
EXTRATOR_TEMPERATURE = float(os.getenv("EXTRATOR_TEMPERATURE", "0.0"))
EXTRATOR_TIMEOUT_SEGUNDOS = LLM_TIMEOUT_SEGUNDOS
EXTRATOR_MAX_RETRIES = LLM_MAX_RETRIES

AVALIADOR_MODEL = os.getenv("AVALIADOR_MODEL", "openai:gpt-4o-mini")
AVALIADOR_TEMPERATURE = float(os.getenv("AVALIADOR_TEMPERATURE", "0.0"))

REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")
TTL_CHECKPOINT_MINUTOS = int(os.getenv("TTL_CHECKPOINT_MINUTOS", "1440"))

# bool(os.getenv(...)) não serve aqui: bool("False") é True em Python (string não-vazia).
# Default "True" de propósito — env var esquecida no deploy cai no lado seguro (HTTPS).
AMBIENTE_PRODUCAO = os.getenv("AMBIENTE_PRODUCAO", "True").strip().lower() == "true"

# Sem COOKIE_SECRET_KEY definida, cai numa chave aleatória em memória — não quebra o
# boot em dev, mas invalida cookies emitidos a cada restart. Sempre definir em produção.
_COOKIE_SECRET_KEY_ENV = os.getenv("COOKIE_SECRET_KEY")
if not _COOKIE_SECRET_KEY_ENV:
    logger.warning(
        "COOKIE_SECRET_KEY não definida no ambiente — usando uma chave aleatória "
        "gerada em memória. Os cookies emitidos não sobrevivem a um restart do "
        "servidor. Defina essa env var em produção."
    )
COOKIE_SECRET_KEY = _COOKIE_SECRET_KEY_ENV or secrets.token_hex(32)


# Singleton: uma única conexão Pinecone/embedding para todo o app.
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
    """Cria um cliente LLM via init_chat_model (provider identificado pelo prefixo de model_name)."""
    config_params = config_params or {}  # sentinela: evita default mutável compartilhado
    return init_chat_model(model_name, **config_params)
