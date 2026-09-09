import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

CASOS_DIR = Path(__file__).parent / "casos"

# Catálogo completo em docs/ia/anomalias.md.
CodigoAnomalia = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I"]

class ToolEsperada(BaseModel):
    tool: str
    argumentos_esperados: dict = Field(default_factory=dict)

class Caso(BaseModel):
    id: str
    descricao: str

    edital_pdf: str
    estado: str
    municipio: str

    trecho_injetado: str | None = None

    anomalias_esperadas: list[CodigoAnomalia] = Field(default_factory=list)
    tools_esperadas: list[ToolEsperada] = Field(default_factory=list)

    # Gabarito de referência para uma futura métrica de cobertura de contexto
    # (ver docs/ia/avaliacao.md). Ainda sem consumidor.
    contexto_edital_esperado: str | None = None


def carregar_casos() -> list[Caso]:
    return [
        Caso.model_validate(json.loads(caminho.read_text(encoding="utf-8")))
        for caminho in sorted(CASOS_DIR.glob("caso_*.json"))
    ]