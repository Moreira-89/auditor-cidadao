import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.root_perguntar import router as perguntar_router
from app.api.root_upload import router as upload_router
from app.services.lifespan import lifespan

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)

app = FastAPI(
    title="Auditor Cidadão",
    description="Auditor Cidadão é uma plataforma baseada em Inteligência Artificial (RAG e Agentes) "
    "que permite analisar editais, extrair CNPJs e responder a perguntas com contexto enriquecido.",
    version="1.0.3",
    lifespan=lifespan,
)

app.include_router(upload_router)
app.include_router(perguntar_router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", include_in_schema=False, response_class=FileResponse)
async def serve_home():
    """Serve a landing page (apresentação do produto)."""
    return FileResponse("frontend/index.html")


@app.get("/chat", include_in_schema=False, response_class=FileResponse)
async def serve_chat():
    """Serve a página de chat (upload de edital + conversa com o agente)."""
    return FileResponse("frontend/chat.html")
