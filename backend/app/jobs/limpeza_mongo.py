import os
import sys
from datetime import datetime, timedelta, timezone

from app.storage.mongo_db import COLECAO_CHUNKS, NOME_BANCO
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Carrega as variáveis de ambiente (como MONGODB_URI) do arquivo .env
load_dotenv()


def limpar_secoes_expiradas() -> None:
    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("Erro: MONGODB_URI não encontrada no .env.")
        sys.exit(1)

    # Quantos dias um chunk de upload de usuário pode ficar guardado antes de
    # ser considerado expirado. Default de 2 dias cobre a análise dentro de uma semana.
    dias_retencao = int(os.getenv("MONGO_RETENCAO_DIAS", "2"))
    cutoff = int(
        (datetime.now(timezone.utc) - timedelta(days=dias_retencao)).timestamp()
    )

    print(f"Conectando ao MongoDB (banco '{NOME_BANCO}', coleção '{COLECAO_CHUNKS}')...")
    try:
        cliente = MongoClient(uri)
        cliente.admin.command("ping")
        colecao = cliente[NOME_BANCO][COLECAO_CHUNKS]

        # Só chunks de upload manual expiram — outras origens (ex.: futura
        # indexação automática via PNCP) podem ter regra de retenção diferente.
        filtro = {
            "timestamp_indexacao": {"$lte": cutoff},
            "origem": "upload_usuario",
        }
        print(
            "Apagando chunks de origem 'upload_usuario' indexados há mais de "
            f"{dias_retencao} dias (timestamp_indexacao <= {cutoff})..."
        )
        resultado = colecao.delete_many(filtro)
        print(f"Limpeza concluída — {resultado.deleted_count} chunk(s) removido(s).")
    except PyMongoError as e:
        print(f"Erro ao limpar a coleção '{COLECAO_CHUNKS}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    limpar_secoes_expiradas()
