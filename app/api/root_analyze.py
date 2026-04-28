from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.ai_engine import run_agent

router = APIRouter(
    prefix="/analisar-edital",
    tags=["Análise de Editais"]
)

class EnviarEdital(BaseModel):
    edital: str = Field(description="Edital a ser analisado")

@router.post("/")
def executar_analise(edital: EnviarEdital):

    texto = edital.edital
    resultado = run_agent(texto_edital=texto)
    return {"resultado_analise": resultado}