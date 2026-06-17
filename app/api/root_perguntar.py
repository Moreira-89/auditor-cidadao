import asyncio

from fastapi import APIRouter

from app.core.dependencies import gerenciador
from app.models.pergunta_request import PerguntaRequest
from app.services.ai_engine import run_agent

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO
# -----------------------------------------------------------------------------
# Criação do roteador FastAPI para o endpoint de chat.
# O prefixo define a URL base e a tag organiza a exibição no Swagger UI.
router = APIRouter(prefix="/conversar-com-auditor", tags=["Conversar sobre o edital"])


# -----------------------------------------------------------------------------
# ENDPOINTS
# -----------------------------------------------------------------------------
@router.post("/")
async def executar_pergunta(request: PerguntaRequest):
    """
    Objetivo: Endpoint principal de chat (Perguntas e Respostas).
    Implementa a etapa de "Recuperação e Geração" (RAG - Retrieval-Augmented Generation).

    COMO FUNCIONA:
    1. Busca de Contexto (Retrieval): Pega a pergunta do usuário e busca no Pinecone
       os trechos do edital (chunks) que são mais parecidos semanticamente com a pergunta.
       Usa os filtros de estado e município para não misturar editais de locais diferentes.
       A chamada ao Pinecone é bloqueante (I/O de rede síncrono), por isso usamos
       `asyncio.to_thread` para executá-la em uma thread separada, liberando a event loop
       do FastAPI para atender outras requisições enquanto aguarda a resposta.
    2. Execução do Agente (Generation): Envia a pergunta, o contexto recuperado e a
       lista de CNPJs para o agente de IA (`run_agent`).
       O agente analisa os dados, podendo consultar APIs externas (como a Receita Federal)
       se necessário, e formula a resposta final. Também executado via `asyncio.to_thread`
       pela mesma razão: `run_agent` faz I/O de rede com a API Groq (síncrono).

    Args:
        request (PerguntaRequest): Corpo da requisição contendo a pergunta, estado,
                                   município, nome do usuário e lista de CNPJs previamente extraídos.

    Returns:
        dict: Resposta gerada pela Inteligência Artificial.
    """

    # --- 1. Busca de Contexto (Retrieval) ---
    # Em vez de enviar o edital inteiro para o LLM (o que seria caro e poderia
    # estourar o limite de tokens), buscamos apenas os parágrafos mais relevantes.
    # `asyncio.to_thread` recebe a função e os kwargs diretamente (Python 3.9+),
    # delegando a execução bloqueante para o thread pool do asyncio sem travar o servidor.
    contexto = await asyncio.to_thread(
        gerenciador.buscar_contexto,
        pergunta=request.pergunta,
        estado=request.estado,
        municipio=request.municipio
    )

    # --- 2. Execução do Agente (Generation) ---
    # Passamos o contexto enxuto (apenas as partes relevantes do edital) para o LLM.
    # A 'lista_cnpj' é enviada para que a IA saiba de antemão quais empresas pesquisar,
    # garantindo que o agente possa usar suas ferramentas para consultar a Receita Federal.
    resposta = await asyncio.to_thread(
        run_agent,
        pergunta_usuario=request.pergunta,
        lista_cnpj=request.lista_cnpjs,
        contexto=contexto,
        user_name=request.user_name,
        estado=request.estado,
        municipio=request.municipio,
        thread_id=request.thread_id
    )

    # Retorna a resposta final empacotada em um JSON
    return {"resultado_pergunta": resposta}
