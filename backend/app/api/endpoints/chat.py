"""
Endpoint HTTP de conversa com o agente.

Recebe a pergunta do usuário (já validada pelo schema PerguntaRequest) e devolve a
resposta do agente em STREAMING via Server-Sent Events (SSE) — assim o texto aparece
no frontend aos poucos, token a token, sem o usuário esperar a resposta inteira ficar
pronta. Aqui é só a "borda" HTTP: a lógica de verdade mora em run_agent
(app/agents/conversa.py).
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_client_id
from app.config.logging import logger
from app.api.schemas.pergunta import PerguntaRequest
from app.agents.conversa import run_agent
from app.api.rate_limiter import RateLimiter

# Roteador com prefixo "/conversar-com-auditor" — agrupa os endpoints de interação com o agente
router = APIRouter(prefix="/conversar-com-auditor", tags=["Conversar sobre o edital"])


@router.post(
    "/",
    # Conversa é o uso principal da aplicação — limite mais generoso que o de
    # upload, mas ainda existe para conter um cliente em loop/abuso gerando custo
    # de LLM sem limite. Janela de 86400s = 24h.
    dependencies=[
        Depends(
            RateLimiter(
                limit=50,
                window_seconds=86400,
                prefixo="quota_chat",
                descricao="perguntas diárias ao auditor",
            )
        )
    ],
)
async def executar_pergunta(
    request: PerguntaRequest,
    client_id: str = Depends(get_client_id),
):
    """Recebe a pergunta do usuário e retorna a resposta do agente de auditoria via streaming."""

    logger.info(
        "Pergunta recebida | thread=%s | estado=%s | municipio=%s | cnpjs=%s | client_id=%s",
        request.thread_id,
        request.estado,
        request.municipio,
        request.lista_cnpjs,
        client_id,
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
