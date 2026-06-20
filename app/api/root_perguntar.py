from fastapi import APIRouter

from app.core.logging_config import logger
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
    1. Execução do Agente (Generation): Envia a pergunta, o contexto recuperado e a
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

    logger.info("Pergunta recebida | user=%s | thread=%s | estado=%s | municipio=%s | cnpjs=%s",
                request.user_name, request.thread_id, request.estado,
                request.municipio, request.lista_cnpjs)
    logger.info("Texto da pergunta | chars=%d | preview=%s",
                len(request.pergunta), request.pergunta[:80])

    # --- 1. Execução do Agente ---
    # run_agent é uma corrotina assíncrona nativa, portanto o await direto é suficiente.
    # Não é mais necessário asyncio.to_thread pois todo o pipeline (LLM + tools) usa I/O async.
    resposta = await run_agent(
        pergunta_usuario=request.pergunta,
        lista_cnpj=request.lista_cnpjs,
        user_name=request.user_name,
        estado=request.estado,
        municipio=request.municipio,
        thread_id=request.thread_id,
    )
    logger.info("Resposta gerada | user=%s | thread=%s | chars=%d",
                request.user_name, request.thread_id, len(resposta))

    return {"resultado_pergunta": resposta}
