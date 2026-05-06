import os


from dotenv import load_dotenv
from groq import Groq

from app.services.gerenciadorvetorial import GerenciadorVetorial

# Garante que as variáveis do arquivo .env sejam carregadas antes de ler as chaves de API.
# É importante chamar `load_dotenv()` antes de qualquer `os.getenv()` para que os valores
# estejam disponíveis no momento em que os clientes são instanciados abaixo.
load_dotenv()


# -----------------------------------------------------------------------------
# DEPENDÊNCIAS GLOBAIS
# -----------------------------------------------------------------------------

# --- 1. Gerenciador Vetorial (Singleton) ---
# Instanciamos o GerenciadorVetorial uma única vez ao subir o servidor.
# Internamente, ele carrega o modelo de embedding 'all-MiniLM-L6-v2' (centenas de MB)
# e conecta ao Pinecone. Recriar isso a cada requisição seria proibitivo em tempo e memória.
gerenciador = GerenciadorVetorial()

# --- 2. Cliente Groq (Singleton) ---
# Da mesma forma, o cliente da API da Groq é instanciado aqui uma única vez.
# A alternativa (chamar retornar_cliente_groq() dentro de cada request) criava um novo
# objeto de conexão HTTP por requisição — desnecessário, pois o cliente é stateless
# e pode ser reutilizado com segurança entre chamadas concorrentes.
# A verificação da chave garante um erro claro na inicialização, antes de qualquer
# requisição chegar, facilitando o diagnóstico de ambientes mal configurados.
if not os.getenv("GROQ_API_KEY"):
    raise ValueError(
        "Chave de API da Groq não encontrada! "
        "Crie um arquivo .env com a variável GROQ_API_KEY."
    )

cliente_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
