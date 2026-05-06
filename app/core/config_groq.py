import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


# -----------------------------------------------------------------------------
# FUNÇÃO DE CONFIGURAÇÃO (LEGADO — USE O SINGLETON EM dependencies.py)
# -----------------------------------------------------------------------------
def retornar_cliente_groq() -> Groq:
    """
    Objetivo: Criar e retornar uma instância do cliente Groq inicializada de forma segura.

    COMO FUNCIONA:
    1. Verificação da Chave: Checa se a variável de ambiente 'GROQ_API_KEY' existe.
       Sem ela, a aplicação lança um erro imediato com uma mensagem clara, evitando
       falhas silenciosas ou erros genéricos difíceis de depurar.
    2. Criação do Cliente: Instancia o objeto `Groq` com a chave lida do ambiente,
       nunca escrita diretamente no código-fonte.

    OBSERVAÇÃO ARQUITETURAL:
        Esta função não é mais chamada diretamente nas rotas. O padrão Singleton
        adotado em `app/core/dependencies.py` instancia o cliente uma única vez
        na inicialização do servidor e compartilha a mesma referência entre todas
        as requisições, eliminando o overhead de criar uma nova conexão por chamada.

    Returns:
        Groq: Objeto cliente conectado à API da Groq, pronto para gerar respostas.

    Raises:
        ValueError: Se a variável de ambiente 'GROQ_API_KEY' não estiver definida.
    """
    # --- 1. Verificação da Chave ---
    # Falha imediatamente e com mensagem clara, antes de qualquer requisição chegar.
    # Muito melhor do que deixar a aplicação subir e falhar apenas na primeira chamada à API.
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError(
            "Chave de API da Groq não encontrada! Crie um arquivo .env com a GROQ_API_KEY."
        )

    # --- 2. Criação do Cliente ---
    return Groq(api_key=os.getenv("GROQ_API_KEY"))
