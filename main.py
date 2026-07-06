"""
Ponto de entrada da aplicação FastAPI. Registra os routers de upload e chat,
serve o frontend estático (Home + página de chat) e delega a inicialização
pesada (MCP, grafo, modelo extrator) ao lifespan em app/services/lifespan.py.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
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


@app.exception_handler(Exception)
async def tratar_excecao_nao_prevista(request: Request, exc: Exception):
    """Rede de segurança final: qualquer exceção não tratada por um router específico
    cai aqui, evitando vazar stack trace ao cliente e garantindo que fique logada."""
    logger.exception("Erro não tratado | path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno inesperado. Tente novamente em instantes."},
    )

# Serve o front-end (index.html, chat.html, css/, js/) como arquivos estáticos —
# não há build step nem framework, é HTML/CSS/JS puro na mesma origem da API.
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", include_in_schema=False, response_class=FileResponse)
async def serve_home():
    """Serve a landing page (apresentação do produto)."""
    return FileResponse("frontend/index.html")


@app.get("/chat", include_in_schema=False, response_class=FileResponse)
async def serve_chat():
    """Serve a página de chat (upload de edital + conversa com o agente)."""
    return FileResponse("frontend/chat.html")
