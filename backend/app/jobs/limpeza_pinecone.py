import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pinecone import Pinecone
from pinecone.exceptions import NotFoundException, PineconeException

# Carrega as variáveis de ambiente (como PINECONE_API_KEY) do arquivo .env
load_dotenv()

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "auditor-cidadao")
NAMESPACE = os.getenv("PINECONE_NAMESPACE", "production")


def limpar_registros_expirados() -> None:
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("Erro: PINECONE_API_KEY não encontrada no .env.")
        sys.exit(1)

    # Quantos dias um registro de upload de usuário pode ficar indexado antes
    # de ser considerado expirado. Default de 2 dias cobre o caso comum de
    # análise de um edital dentro de uma mesma semana.
    dias_retencao = int(os.getenv("PINECONE_RETENCAO_DIAS", "2"))
    cutoff = int(
        (datetime.now(timezone.utc) - timedelta(days=dias_retencao)).timestamp()
    )

    print(f"Conectando ao Pinecone (índice '{INDEX_NAME}', namespace '{NAMESPACE}')...")
    pc = Pinecone(api_key=api_key)

    try:
        index = pc.Index(INDEX_NAME)

        filtro = {
            "timestamp_indexacao": {"$lte": cutoff},
            "origem": {"$eq": "upload_usuario"},
        }

        print(
            "Apagando registros de origem 'upload_usuario' indexados há mais de "
            f"{dias_retencao} dias (timestamp_indexacao <= {cutoff})..."
        )
        # O Pinecone não retorna quantos registros foram afetados por um delete
        # com filtro (só confirma se a chamada foi aceita) — por isso o log
        # abaixo é de confirmação de execução, não de contagem.
        try:
            index.delete(namespace=NAMESPACE, filter=filtro)
        except NotFoundException:
            # O Pinecone cria namespaces só na primeira indexação; se ainda
            # não há nenhum registro em NAMESPACE, o delete retorna 404 em
            # vez de "0 registros apagados". Não há nada a limpar, então
            # trata como sucesso em vez de derrubar o job.
            print(
                f"Namespace '{NAMESPACE}' ainda não existe — nenhum registro a limpar."
            )

        print("Limpeza concluída.")
    except PineconeException as e:
        print(f"Erro ao limpar o índice '{INDEX_NAME}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    limpar_registros_expirados()
