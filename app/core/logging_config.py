"""
Módulo de Configuração Central de Logging da Aplicação.

COMO FUNCIONA:
1. Definição do Logger Raiz: Cria um logger nomeado "auditor_cidadao" que serve como
   ponto central de registro para todos os módulos do projeto.
2. Exportação: O objeto `logger` é importado pelos demais módulos que precisam registrar
   eventos, garantindo que toda a aplicação compartilhe o mesmo canal de saída e formato.

PADRÃO DE USO:
    from app.core.logging_config import logger

    logger.info("Operação concluída com sucesso.")
    logger.warning("Arquivo não encontrado, usando fallback.")
    logger.error("Falha crítica: %s", str(e))

SOBRE OS NÍVEIS DE LOG:
    - DEBUG   → Detalhes internos úteis apenas durante desenvolvimento.
    - INFO    → Eventos esperados do fluxo normal (indexação, avaliação iniciada, etc.).
    - WARNING → Algo inesperado, mas que não interrompeu a execução (ex: PDF real pulado).
    - ERROR   → Falha em uma operação específica que foi contornada (ex: PDF não encontrado).
    - CRITICAL→ Falha que pode encerrar a aplicação (ex: chave de API ausente).

NOTA ARQUITETURAL:
    O `basicConfig` (que define o handler de saída e o formato) NÃO é chamado aqui.
    Isso é proposital: quem configura o handler é o ponto de entrada da aplicação
    (o `main()` em `evaluation/pipeline_avaliacao.py` para o script CLI, ou o próprio
    uvicorn para a API). Assim, bibliotecas que importam este módulo não "sequestram"
    o logging do chamador.
"""

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
# ponto de entrada da aplicação (main() em evaluation/pipeline_avaliacao.py ou o uvicorn na API).
logger.addHandler(logging.NullHandler())
