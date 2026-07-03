from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.logging_config import logger
from app.models.pergunta_request import PerguntaRequest
from app.services.ai_engine import run_agent

# Roteador com prefixo "/conversar-com-auditor" — agrupa os endpoints de interação com o agente
router = APIRouter(prefix="/conversar-com-auditor", tags=["Conversar sobre o edital"])


@router.post("/")
async def executar_pergunta(request: PerguntaRequest):
    """Recebe a pergunta do usuário e retorna a resposta do agente de auditoria via streaming."""

    logger.info(
        "Pergunta recebida | thread=%s | estado=%s | municipio=%s | cnpjs=%s",
        request.thread_id,
        request.estado,
        request.municipio,
        request.lista_cnpjs,
    )
    logger.info(
        "Texto da pergunta | chars=%d | preview=%s",
        len(request.pergunta),
        request.pergunta[:80],
    )

    logger.info(
        "Iniciando streaming para o usuário | thread=%s",
        request.thread_id,
    )

    # StreamingResponse transmite os tokens do agente conforme são gerados, sem aguardar a resposta completa
    return StreamingResponse(
        run_agent(
            pergunta_usuario=request.pergunta,
            lista_cnpj=request.lista_cnpjs,
            estado=request.estado,
            municipio=request.municipio,
            thread_id=request.thread_id,
        ),
        media_type="text/event-stream",
    )
