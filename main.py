"""
Arquivo de Ponto de Entrada (Entry Point) da Aplicação.

COMO FUNCIONA:
Este é o arquivo que o servidor `uvicorn` procura para iniciar a API.
Ele inicializa a aplicação FastAPI e define metadados (título, descrição, versão)
que vão aparecer automaticamente no Swagger UI (/docs).
Aqui também importamos e "anexamos" todas as rotas (routers) criadas nos outros arquivos,
para que a aplicação principal saiba que elas existem.
"""

from fastapi import FastAPI

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
# REGISTRO DE ROTAS (ENDPOINTS)
# -----------------------------------------------------------------------------
# 'include_router' pega todas as rotas definidas no router específico e as integra na aplicação.
app.include_router(upload_router)
app.include_router(perguntar_router)
