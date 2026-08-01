"""
Job standalone de limpeza do banco vetorial (Pinecone).

Apaga do índice apenas os registros indexados via upload de usuário
("origem": "upload_usuario") cujo timestamp_indexacao seja mais antigo que o
prazo de retenção configurado — preserva registros de outras origens (ex.:
futura tool "agente_busca") e qualquer registro ainda dentro do prazo.

Pensado para rodar como cron job isolado (ex.: no Railway), por isso não
depende do GerenciadorVetorial nem de nenhum outro módulo da API: só carrega
o .env e fala direto com o Pinecone, no mesmo espírito de
testes_locais/limpar_banco.py.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pinecone import Pinecone

# Carrega as variáveis de ambiente (como PINECONE_API_KEY) do arquivo .env
load_dotenv()

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "auditor-cidadao")
NAMESPACE = os.getenv("PINECONE_NAMESPACE", "production")


def limpar_registros_expirados() -> None:
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("❌ PINECONE_API_KEY não encontrada no .env")
        sys.exit(1)

    # Quantos dias um registro de upload de usuário pode ficar indexado antes
    # de ser considerado expirado. Default de 7 dias cobre o caso comum de
    # análise de um edital dentro de uma mesma semana.
    dias_retencao = int(os.getenv("PINECONE_RETENCAO_DIAS", "2"))
    cutoff = int(
        (datetime.now(timezone.utc) - timedelta(days=dias_retencao)).timestamp()
    )

    print("-> Conectando ao Pinecone...")
    pc = Pinecone(api_key=api_key)

    try:
        index = pc.Index(INDEX_NAME)

        filtro = {
            "timestamp_indexacao": {"$lte": cutoff},
            "origem": {"$eq": "upload_usuario"},
        }

        print(
            f"🗑️ Apagando registros de upload_usuario com timestamp_indexacao <= {cutoff} "
            f"(retenção de {dias_retencao} dias) do namespace '{NAMESPACE}' do índice '{INDEX_NAME}'..."
        )
        # O Pinecone não retorna quantos registros foram afetados por um delete
        # com filtro (só confirma se a chamada foi aceita) — por isso o log
        # abaixo é de confirmação de execução, não de contagem.
        index.delete(namespace=NAMESPACE, filter=filtro)

        print("✅ Limpeza concluída sem erros.")
    except Exception as e:
        print(f"❌ Erro ao limpar o banco: {e}")
        sys.exit(1)


if __name__ == "__main__":
    limpar_registros_expirados()
