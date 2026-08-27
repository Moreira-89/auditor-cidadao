"""
Variáveis de ambiente da aplicação, lidas uma única vez no import deste módulo.

Este arquivo é só configuração: lê env vars, aplica defaults e valida o formato.
Ele não abre conexão, não instancia cliente e não importa nenhum outro módulo do
`app` além do logger — de propósito. Importar `app.config.settings` tem que ser
barato e livre de efeito colateral, senão nada abaixo dele fica testável sem rede.

Referência completa de cada env var (default, obrigatoriedade, o "porquê" de cada
uma): docs/operacional/variaveis_ambiente.md. Os comentários abaixo cobrem só o que
não está lá — decisões específicas do código Python.
"""

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

# Extrator roda no mesmo turno, depois do streaming (ver ai_engine.py) — reusa os
# limites do agente principal em vez de expor env vars próprias sem necessidade.
EXTRATOR_MODEL = os.getenv("EXTRATOR_MODEL", "openai:gpt-4o-mini")
EXTRATOR_TEMPERATURE = float(os.getenv("EXTRATOR_TEMPERATURE", "0.0"))
EXTRATOR_TIMEOUT_SEGUNDOS = LLM_TIMEOUT_SEGUNDOS
EXTRATOR_MAX_RETRIES = LLM_MAX_RETRIES

# Namespace e top-k da busca vetorial no Pinecone (ver app/agents/tools/contexto_edital.py).
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "production")
TOP_K_EDITAL = int(os.getenv("TOP_K_EDITAL", "3"))

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
# por vírgula se houver mais de uma (ex.: preview + produção). Vazio por padrão:
# sem essa env var definida, nenhuma origem cross-site é liberada e a API só
# responde a chamadas same-origin (ex.: dev local, onde o backend também serve
# o frontend — ver main.py).
CORS_ORIGINS = [
    origem.strip()
    for origem in os.getenv("CORS_ORIGINS", "").split(",")
    if origem.strip()
]
