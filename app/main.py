from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.services.ai_engine import consultar_auditor
from app.services.processor import processar_documento

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

@app.post("/api/upload")
async def upload_pdf(arquivo: UploadFile = File(...)):
    # 1. Salva o arquivo temporariamente na pasta do projeto
    caminho_temp = f"temp_{arquivo.filename}"
    
    with open(caminho_temp, "wb") as buffer:
        conteudo = await arquivo.read()
        buffer.write(conteudo)
    
    # 2. Manda o arquivo para a nossa pipeline de IA processar
    resultado = processar_documento(caminho_temp)
    
    if resultado["status"] == "sucesso":
        return {"mensagem": resultado["mensagem"]}
    else:
        return {"mensagem": f"Erro ao processar: {resultado['mensagem']}"}