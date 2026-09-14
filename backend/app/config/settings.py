# Lê env vars e aplica defaults. Referência de cada variável:
# docs/operacional/variaveis_ambiente.md.

import os
import secrets

from app.config.logging import logger
from dotenv import load_dotenv

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "openai:gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TIMEOUT_SEGUNDOS = int(os.getenv("LLM_TIMEOUT_SEGUNDOS", "60"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# Busca vetorial do RAG de editais (ver app/storage/vetorial.py).
TOP_K_EDITAL = int(os.getenv("TOP_K_EDITAL", "5"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

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

# Origens autorizadas a chamar a API via CORS — a URL pública do serviço de
# frontend no Railway (ex.: "https://auditorcidadao.up.railway.app"), separadas
# por vírgula se houver mais de uma (ex.: preview + produção).
CORS_ORIGINS = [
    origem.strip()
    for origem in os.getenv("CORS_ORIGINS", "").split(",")
    if origem.strip()
]

# Libera o Vite automaticamente em dev — ver CORS_ORIGINS em
# docs/operacional/variaveis_ambiente.md.
if not AMBIENTE_PRODUCAO:
    CORS_ORIGINS += [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",  # vite preview
    ]

# Conexão com MongoDB Atlas — armazena e busca os chunks do edital (RAG hierárquico).
MONGODB_URI = os.getenv("MONGODB_URI")

# Juiz LLM da métrica de Fidelidade (G-Eval), ver backend/evaluation/metricas/fidelidade.py.
# Só OpenAI é suportado como juiz hoje; removemos o prefixo "openai:" se vier
# (mesmo formato "provider:model" do LLM_MODEL, mas aqui só um provider existe).
AVALIADOR_MODEL = os.getenv("AVALIADOR_MODEL", "gpt-4o").removeprefix("openai:")
AVALIADOR_TEMPERATURE = float(os.getenv("AVALIADOR_TEMPERATURE", "0.0"))
