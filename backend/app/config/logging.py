import logging

# -----------------------------------------------------------------------------
# LOGGER CENTRAL DA APLICAÇÃO
# -----------------------------------------------------------------------------

# Criamos um logger com nome específico ao invés de usar o logger raiz (root logger).
# O nome "auditor_cidadao" permite que outros projetos ou testes isolem os logs
# desta aplicação sem interferir com outros pacotes que também usam o módulo logging.
logger = logging.getLogger("auditor_cidadao")

# Adicionamos um NullHandler como handler padrão do logger.
# Esta é a prática recomendada pelo Python (PEP 328 / docs oficiais) para módulos
# que são importados por outros projetos: o NullHandler "absorve" os logs silenciosamente
# quando o chamador não configurou nenhum handler, evitando o aviso
# "No handlers could be found for logger 'auditor_cidadao'".
# O handler real (StreamHandler, FileHandler, etc.) é sempre configurado pelo
# ponto de entrada da aplicação (main.py, ou o uvicorn em produção).
logger.addHandler(logging.NullHandler())
