import json
from collections.abc import AsyncGenerator

from app.agents.conversa import run_agent
from app.agents.eventos import (
    ErroNoTurno,
    EventoDoTurno,
    FerramentaIniciada,
    TokenGerado,
    TurnoConcluido,
)
from app.agents.prompt import PROMPT_RELATORIO_INICIAL
from app.api.dependencies import get_client_id
from app.api.rate_limiter import RateLimiter
from app.api.schemas.pergunta import PerguntaRequest
from app.config.logging import logger
from app.config.tool_status_map import TOOL_STATUS_MAP
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

MENSAGEM_ERRO_GENERICA = "Ocorreu um erro ao processar sua pergunta. Tente novamente."

# Roteador com prefixo "/conversar-com-auditor" — agrupa os endpoints de interação com o agente
router = APIRouter(prefix="/conversar-com-auditor", tags=["Conversar sobre o edital"])


def _linha_sse(tipo: str, content: str | None = None) -> str:
    """Formata uma linha no protocolo Server-Sent Events, no formato que o frontend consome."""
    payload = {"type": tipo} if content is None else {"type": tipo, "content": content}
    return f"data: {json.dumps(payload)}\n\n"


def _para_sse(evento: EventoDoTurno) -> str:
    """Traduz um evento do turno para a linha SSE correspondente."""
    match evento:
        case TokenGerado(texto):
            return _linha_sse("token", texto)
        case FerramentaIniciada(nome):
            # É aqui que o nome técnico da tool vira o texto que o usuário lê.
            return _linha_sse("status", TOOL_STATUS_MAP.get(nome, "Analisando..."))
        case TurnoConcluido():
            return _linha_sse("done")
        case ErroNoTurno():
            return _linha_sse("error", MENSAGEM_ERRO_GENERICA)


async def _stream_sse(
    eventos: AsyncGenerator[EventoDoTurno, None],
) -> AsyncGenerator[str, None]:
    """Converte o fluxo de eventos do agente no fluxo de linhas SSE enviado ao navegador."""
    async for evento in eventos:
        yield _para_sse(evento)


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

    # inicial=true: o primeiro turno da thread é o relatório automático, disparado
    # pelo frontend logo após o upload. O prompt vem do backend (o cliente manda
    # pergunta vazia), e o envelope com CNPJs/estado/município é montado igual ao
    # primeiro turno normal, dentro de run_agent.
    pergunta = PROMPT_RELATORIO_INICIAL if request.inicial else request.pergunta

    logger.info(
        "Pergunta recebida | thread=%s | inicial=%s | estado=%s | municipio=%s | cnpjs=%s | client_id=%s",
        request.thread_id,
        request.inicial,
        request.estado,
        request.municipio,
        request.lista_cnpjs,
        client_id,
    )
    logger.info(
        "Texto da pergunta | chars=%d | preview=%s", len(pergunta), pergunta[:80]
    )

    logger.info(
        "Iniciando streaming para o usuário | thread=%s",
        request.thread_id,
    )

    # StreamingResponse transmite conforme os eventos chegam, sem aguardar a resposta completa
    return StreamingResponse(
        _stream_sse(
            run_agent(
                pergunta_usuario=pergunta,
                lista_cnpj=request.lista_cnpjs,
                estado=request.estado,
                municipio=request.municipio,
                thread_id=request.thread_id,
            )
        ),
        media_type="text/event-stream",
    )
