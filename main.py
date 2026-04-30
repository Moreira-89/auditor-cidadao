from fastapi import FastAPI

from app.api.root_perguntar import router as perguntar_router
from app.api.root_upload import router as upload_router

app = FastAPI(
    title="Auditor Cidadão",
    description="Auditor Cidadão é uma plataforma que permite analisar editais e retornar o resultado da análise.",
    version="0.1.0"
)

# Registra os roteadores na aplicação principal
app.include_router(upload_router)
app.include_router(perguntar_router)
