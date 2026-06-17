from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.root_perguntar import router as perguntar_router
from app.api.root_upload import router as upload_router

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO DA APLICAÇÃO
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Auditor Cidadão",
    description="Auditor Cidadão é uma plataforma baseada em Inteligência Artificial (RAG e Agentes) "
                "que permite analisar editais, extrair CNPJs e responder a perguntas com contexto enriquecido.",
    version="0.1.0"
)

# -----------------------------------------------------------------------------
# REGISTRO DE ROTAS DE API (ENDPOINTS)
# -----------------------------------------------------------------------------
# Os routers de API são registrados PRIMEIRO para ter prioridade sobre o mount
# de arquivos estáticos. Isso evita qualquer ambiguidade de roteamento.
app.include_router(upload_router)
app.include_router(perguntar_router)

# -----------------------------------------------------------------------------
# FRONTEND DE TESTES (ARQUIVOS ESTÁTICOS)
# -----------------------------------------------------------------------------
# Serve os assets do frontend (CSS, JS) no caminho /static.
# O diretório "frontend/" na raiz do projeto contém index.html, css/ e js/.
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", include_in_schema=False, response_class=FileResponse)
async def serve_frontend():
    """Rota raiz — entrega o painel de testes do frontend."""
    return FileResponse("frontend/index.html")

