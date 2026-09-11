from datetime import datetime, timezone
from pathlib import Path

from app.config.logging import logger
from app.ingestion.cnpj import extrair_cnpj
from app.ingestion.pdf import documento_tem_texto_nativo
from app.ingestion.pdf_hierarquico import extrair_estrutura_pdf
from app.storage.mongo_db import COLECAO_CHUNKS, get_database
from app.storage.vetorial import get_gerenciador
from pydantic import BaseModel

from evaluation.dataset.schema import Caso

EDITAIS_DIR = Path(__file__).parent / "dataset" / "editais"

class EditalIndexado(BaseModel):
    caso_id: str
    edital_id: str  # valor gravado nos chunks e usado no filtro do RAG (= o thread_id da execução)
    estado: str
    municipio: str
    lista_cnpj: list[str]
    num_filhos: int

def limpar_edital(edital_id: str) -> None:
    """Apaga do Mongo todos os chunks (pais e filhos) deste edital. Silencioso se
    não houver o que apagar (caso normal na 1ª rodada)."""
    resultado = get_database()[COLECAO_CHUNKS].delete_many({"edital_id": edital_id})
    logger.info(
        "Chunks limpos | edital_id=%s | removidos=%d", edital_id, resultado.deleted_count
    )

def indexar_caso(caso: Caso) -> EditalIndexado:
    """Prepara o edital de um caso pelo mesmo pipeline de indexação da produção — ver
    docs/ia/rag_dados.md."""
    pdf_bytes = (EDITAIS_DIR / caso.edital_pdf).read_bytes()
    tem_texto = documento_tem_texto_nativo(pdf_bytes, caso.edital_pdf)
    edital = extrair_estrutura_pdf(pdf_bytes, caso.edital_pdf, tem_texto)
    texto = edital.texto
    logger.info(
        "Estrutura extraída | caso=%s | chars=%d | paginas=%d | secoes=%d",
        caso.id,
        len(texto),
        edital.num_paginas,
        len(edital.secoes),
    )

    if caso.trecho_injetado:
        # O trecho entra tanto no texto (para o extrair_cnpj) quanto como uma seção
        # sintética, para virar um filho indexado e ficar recuperável pelo RAG.
        texto = f"{texto}\n\n{caso.trecho_injetado}"
        ordem = len(edital.secoes)
        edital.secoes.append(
            {
                "ordem": ordem,
                "nivel": 1,
                "titulo": "TRECHO INJETADO (AVALIAÇÃO)",
                "caminho": "TRECHO INJETADO (AVALIAÇÃO)",
                "texto_completo": f"{caso.trecho_injetado}\n",
            }
        )
        edital.filhos_brutos.append(
            {"secao_ordem": ordem, "tipo": "TextItem", "texto": caso.trecho_injetado}
        )
        logger.info("Trecho injetado | caso=%s | +chars=%d", caso.id, len(caso.trecho_injetado))

    lista_cnpj = extrair_cnpj(texto)
    logger.info("CNPJs no texto combinado | caso=%s | cnpjs=%s", caso.id, lista_cnpj)

    edital_id = f"eval-{caso.id}"
    limpar_edital(edital_id)

    get_gerenciador().indexar_hierarquia(
        edital.secoes,
        edital.filhos_brutos,
        metadados_base={
            "edital_id": edital_id,
            "municipio": caso.municipio,
            "estado": caso.estado,
            "arquivo": caso.edital_pdf,
            "timestamp_indexacao": int(datetime.now(timezone.utc).timestamp()),
            "origem": "avaliacao",
        },
    )

    return EditalIndexado(
        caso_id=caso.id,
        edital_id=edital_id,
        estado=caso.estado,
        municipio=caso.municipio,
        lista_cnpj=lista_cnpj,
        num_filhos=len(edital.filhos_brutos),
    )
