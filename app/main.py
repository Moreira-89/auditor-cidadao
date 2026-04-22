from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.services.ai_engine import consultar_auditor

app = FastAPI(title="Auditor Cidadão")

templates = Jinja2Templates(directory="app/templates")

# Modelo de dados que o Front-end vai enviar para a API
class PerguntaRequest(BaseModel):
    pergunta: str

# Rota 1: Exibir a página inicial (Front-end)
@app.get("/", response_class=HTMLResponse)
async def ler_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Rota 2: O Endpoint da IA (Onde o JavaScript vai bater)
@app.post("/api/perguntar")
async def fazer_pergunta(req: PerguntaRequest):
    # Chama a função que criamos no ai_engine.py
    resposta_ia = consultar_auditor(req.pergunta)
    
    # Retorna um JSON para o front-end
    return {"resposta": resposta_ia}