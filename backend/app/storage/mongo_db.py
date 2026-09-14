from app.config.logging import logger
from app.config.settings import MONGODB_URI
from pymongo import MongoClient
from pymongo.database import Database

# Singleton preguiçoso: a conexão só abre na primeira chamada, não no import.
_database: Database | None = None

NOME_BANCO = "auditor_cidadao"

# Chunks (parágrafos/tabelas) do edital, cada um rotulado com o caminho da sua
# seção. Ver docs/ia/rag_dados.md.
COLECAO_CHUNKS = "chunks_edital"
NOME_INDICE_VETORIAL = "idx_chunks_vetor"


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
