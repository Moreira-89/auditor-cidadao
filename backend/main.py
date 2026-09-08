import logging

from app.api.endpoints.chat import router as perguntar_router
from app.api.endpoints.upload import router as upload_router
from app.api.lifespan import lifespan
from app.config.logging import logger
from app.config.settings import CORS_ORIGINS
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)

app = FastAPI(
    title="Auditor Cidadão",
    description="Auditor Cidadão é uma plataforma baseada em Inteligência Artificial (RAG e Agentes) "
    "que permite analisar editais, extrair CNPJs e responder a perguntas com contexto enriquecido.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(upload_router)
app.include_router(perguntar_router)

# allow_credentials=True é obrigatório para o cookie de sessão cross-site (ver
# "Identificação do cliente" em docs/arquitetura/visao_geral.md).
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _reaplicar_cookie_pendente(request: Request, resposta: Response) -> Response:
    """Reaplica na resposta de erro um cookie de sessão que get_client_id
    (app/api/dependencies.py) já tinha gravado antes de a exceção interromper a
    requisição — ver "Cookie perdido em resposta de erro" em
    docs/arquitetura/visao_geral.md."""
    cookie_pendente = getattr(request.state, "cookie_pendente", None)
    if cookie_pendente:
        resposta.headers.append("set-cookie", cookie_pendente)
    return resposta


@app.exception_handler(HTTPException)
async def tratar_http_exception(request: Request, exc: HTTPException):
    """Envolve o handler padrão do FastAPI para HTTPException (415, 422, 429, 502,
    etc.) só para garantir que um cookie de sessão pendente não se perca junto."""
    resposta = await http_exception_handler(request, exc)
    return _reaplicar_cookie_pendente(request, resposta)


@app.exception_handler(RequestValidationError)
async def tratar_erro_validacao(request: Request, exc: RequestValidationError):
    """Mesma garantia acima, para o 422 automático que o FastAPI gera quando o
    corpo da requisição (ex.: PerguntaRequest) não bate com o schema esperado."""
    resposta = await request_validation_exception_handler(request, exc)
    return _reaplicar_cookie_pendente(request, resposta)


@app.exception_handler(Exception)
async def tratar_excecao_nao_prevista(request: Request, exc: Exception):
    """Rede de segurança final: qualquer exceção não tratada por um router específico
    cai aqui, evitando vazar stack trace ao cliente e garantindo que fique logada."""
    logger.exception("Erro não tratado | path=%s", request.url.path)
    resposta = JSONResponse(
        status_code=500,
        content={"detail": "Erro interno inesperado. Tente novamente em instantes."},
    )
    return _reaplicar_cookie_pendente(request, resposta)


# O frontend é um serviço próprio no Railway (ver docs/operacional/docker.md) e não
# faz parte do contexto de build desta imagem — este serviço só serve a API.
@app.get("/", include_in_schema=False)
async def health_check():
    """Sem UI própria: usado só como health check (Railway, curl manual)."""
    return {"status": "ok", "service": "auditor-cidadao-backend"}
