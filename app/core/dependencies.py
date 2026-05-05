"""
Resumo: Arquivo para gerenciar dependências globais do projeto.

COMO FUNCIONA:
1. Inicialização: Instancia objetos que precisam ser mantidos em memória durante todo o ciclo de vida da aplicação.
2. Injeção: Disponibiliza essas instâncias (como o gerenciador vetorial) para que outras partes do sistema usem, evitando recarregar recursos e modelos de machine learning.
"""

from app.services.gerenciadorvetorial import GerenciadorVetorial

# -----------------------------------------------------------------------------
# DEPENDÊNCIAS GLOBAIS
# -----------------------------------------------------------------------------

# --- 1. Inicialização ---
# Instanciamos o GerenciadorVetorial de forma global para a aplicação.
# --- 2. Injeção ---
# Assim como no upload, isso evita a recriação de conexões com o Pinecone
# e a recarga de modelos de embeddings a cada nova pergunta do usuário.
gerenciador = GerenciadorVetorial()
