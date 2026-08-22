"""
Ponto de entrada da aplicação FastAPI. Aqui montamos o "app": registramos os endpoints
de upload e de conversa, servimos o frontend estático (a home e a página de chat) e
instalamos uma rede de segurança global que captura qualquer erro não tratado e responde
500 sem vazar stack trace ao cliente. A inicialização pesada (MCP, grafo do agente, modelo
extrator) é delegada ao lifespan em app/services/lifespan.py.
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.root_perguntar import router as perguntar_router
from app.api.root_upload import router as upload_router
from app.core.logging_config import logger
from app.services.lifespan import lifespan

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)

app = FastAPI(
    title="Auditor Cidadão",
    description="Auditor Cidadão é uma plataforma baseada em Inteligência Artificial (RAG e Agentes) "
    "que permite analisar editais, extrair CNPJs e responder a perguntas com contexto enriquecido.",
    version="1.2.0",
    lifespan=lifespan,
)

app.include_router(upload_router)
app.include_router(perguntar_router)


def _reaplicar_cookie_pendente(request: Request, resposta: Response) -> Response:
    """
    Reaplica na resposta de erro um cookie de sessão que uma dependency (ver
    get_client_id em app/api/dependencies_http.py) já tinha gravado antes de
    alguma exceção interromper a requisição.

    Por que isso é necessário: por padrão, quando qualquer exceção (HTTPException
    ou erro de validação do corpo) interrompe uma requisição, o FastAPI descarta
    o `Response` que as dependencies anteriores já tinham modificado e monta uma
    resposta de erro do zero — junto com o `Response` descartado vai qualquer
    Set-Cookie que tivesse sido gravado nele. Sem essa função, um visitante novo
    cujo primeiro request falhasse por QUALQUER motivo (ex.: 415 upload de
    arquivo inválido, 422 corpo malformado, 429 rate limit) nunca receberia o
    cookie de sessão — e seguiria sendo tratado como "visitante novo" a cada
    tentativa seguinte, indefinidamente.
    """
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


# Serve o front-end (index.html, chat.html, css/, js/) como arquivos estáticos —
# não há build step nem framework, é HTML/CSS/JS puro na mesma origem da API.
# Sem Cache-Control, o navegador aplica cache heurístico e pode continuar servindo
# HTML/JS/CSS antigos por conta própria mesmo depois de um deploy novo — daí o
# no-store aqui: nesta fase (sem build/hash de asset) é preferível servir sempre a
# versão atual do disco a economizar uma requisição.
_HEADERS_NO_CACHE = {"Cache-Control": "no-store"}


class StaticFilesSemCache(StaticFiles):
    """Mesma coisa que StaticFiles, mas força no-store em toda resposta — evita
    que o navegador guarde uma versão velha de /static/js/chat.js ou
    /static/css/style.css e ignore as mudanças feitas em disco."""

    def file_response(self, *args, **kwargs):
        resposta = super().file_response(*args, **kwargs)
        resposta.headers["Cache-Control"] = "no-store"
        return resposta


app.mount("/static", StaticFilesSemCache(directory="frontend"), name="static")


@app.get("/", include_in_schema=False, response_class=FileResponse)
async def serve_home():
    """Serve a landing page (apresentação do produto)."""
    return FileResponse("frontend/index.html", headers=_HEADERS_NO_CACHE)


@app.get("/chat", include_in_schema=False, response_class=FileResponse)
async def serve_chat():
    """Serve a página de chat (upload de edital + conversa com o agente)."""
    return FileResponse("frontend/chat.html", headers=_HEADERS_NO_CACHE)
