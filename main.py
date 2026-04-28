from fastapi import FastAPI

from app.api.root_analyze import router as analyze_router

app = FastAPI(
    title="Auditor Cidadão",
    description="Auditor Cidadão é uma plataforma que permite analisar editais e retornar o resultado da análise.",
    version="0.1.0"
)

app.include_router(analyze_router)
