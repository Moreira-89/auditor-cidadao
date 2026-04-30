import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def retornar_cliente_groq():
    """
    Retorna uma instância do cliente Groq inicializada de forma segura.

    COMO FUNCIONA:
    Em vez de escrever a chave da API (API Key) diretamente no código fonte (o que
    é uma falha de segurança gravíssima se o código for para o GitHub), utilizamos a 
    biblioteca `dotenv` para ler um arquivo oculto chamado `.env`.
    
    A função pega essa chave da memória do sistema (variáveis de ambiente), garante que
    ela existe e cria a conexão com a Groq. Se a chave não existir, a aplicação trava 
    com um erro claro, indicando que falta configurar o ambiente.

    Returns:
        Groq: Objeto cliente conectado à API da Groq, pronto para gerar respostas.

    Raises:
        ValueError: Se a variável de ambiente 'GROQ_API_KEY' não estiver definida.
    """
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError("Chave de API da Groq não encontrada! Crie um arquivo .env com a GROQ_API_KEY.")
    
    return Groq(api_key=os.getenv("GROQ_API_KEY"))
