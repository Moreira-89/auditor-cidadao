import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def retornar_cliente_groq():
    """Retorna um cliente Groq inicializado com a chave de API."""
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError("Chave de API da Groq não encontrada!")
    return Groq(api_key=os.getenv("GROQ_API_KEY"))
