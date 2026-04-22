import logging

from fastapi import FastAPI, File, Request, UploadFile 
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.core.config import setup_logging
from app.services.ai_engine import consultar_auditor
from app.services.processor import processar_documento

# Inicializa as configurações de log e cria o logger deste módulo
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Auditor Cidadão")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


class PerguntaRequest(BaseModel):
    pergunta: str


@app.get("/", response_class=HTMLResponse)
async def ler_index(request: Request):
    """Renderiza a interface principal do chat para o usuário."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/perguntar")
async def fazer_pergunta(req: PerguntaRequest):
    """Endpoint para receber perguntas do frontend e retornar respostas geradas pelo RAG."""
    resposta_ia = consultar_auditor(req.pergunta)
    return {"resposta": resposta_ia}


@app.post("/api/upload")
async def upload_pdf(arquivo: UploadFile = File(...)):
    """Recebe arquivos PDF enviados pelo usuário para extração, fatiamento e vetorização."""
    caminho_temp = f"temp_{arquivo.filename}"

    with open(caminho_temp, "wb") as buffer:
        conteudo = await arquivo.read()
        buffer.write(conteudo)

    resultado = processar_documento(caminho_temp)

    if resultado["status"] == "sucesso":
        logger.info(f"Upload processado com sucesso: {arquivo.filename}")
        return {"mensagem": resultado["mensagem"]}
    else:
        logger.error(
            f"Erro ao processar upload de {arquivo.filename}: {resultado['mensagem']}"
        )
        return {"mensagem": f"Erro ao processar: {resultado['mensagem']}"}
