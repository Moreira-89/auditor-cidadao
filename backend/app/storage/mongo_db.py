from app.config.logging import logger
from app.config.settings import (
    MONGODB_COLECAO_CHUNKS,
    MONGODB_DATABASE,
    MONGODB_INDICE_VETORIAL,
    MONGODB_URI,
)
from pymongo import MongoClient
from pymongo.database import Database

# Singleton preguiçoso: a conexão só abre na primeira chamada, não no import.
_database: Database | None = None

NOME_BANCO = MONGODB_DATABASE

# Chunks (parágrafos/tabelas) do edital, cada um rotulado com o caminho da sua
# seção. Ver docs/ia/rag_dados.md.
COLECAO_CHUNKS = MONGODB_COLECAO_CHUNKS
NOME_INDICE_VETORIAL = MONGODB_INDICE_VETORIAL


def get_database() -> Database:
    """Devolve o banco Mongo compartilhado, conectando na primeira chamada."""
    global _database
    if _database is None:
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI não definida no ambiente.")
        logger.info("Conectando ao MongoDB...")
        cliente = MongoClient(MONGODB_URI)
        cliente.admin.command("ping")
        _database = cliente[NOME_BANCO]
        logger.info("MongoDB conectado.")
    return _database
