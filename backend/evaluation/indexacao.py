import time
from pathlib import Path

from app.config.logging import logger
from app.ingestion.cnpj import extrair_cnpj
from app.ingestion.pdf import extrair_texto_pdf
from app.storage.vetorial import get_gerenciador
from pydantic import BaseModel

from evaluation.dataset.schema import Caso

EDITAIS_DIR = Path(__file__).parent / "editais"

class EditalIndexado(BaseModel):
    caso_id: str
    namespace: str
    estado: str
    municipio: str
    lista_cnpj: list[str]
    num_chunks: int
    texto_indexado: str

def _index_pinecone():
    gerenciador = get_gerenciador()
    return gerenciador.pinecone.Index(gerenciador.index_name)

def limpar_namespace(namespace: str) -> None:
    """Apaga todos os vetores do namespace. Silencioso se ele ainda não existe."""
    try:
        _index_pinecone().delete(delete_all=True, namespace=namespace)
        logger.info("Namespace limpo | namespace=%s", namespace)
    except Exception:  # noqa: BLE001 — namespace inexistente devolve 404, é o caso normal na 1ª rodada
        logger.info("Namespace já estava vazio | namespace=%s", namespace)

def _aguardar_consistencia(namespace: str, chunks_esperados: int) -> None:
    """Pinecone é eventualmente consistente: espera o upsert aparecer no describe_index_stats."""
    index = _index_pinecone()
    for _ in range(30):
        stats = index.describe_index_stats()
        atual = stats.get("namespaces", {}).get(namespace, {}).get("vector_count", 0)
        if atual >= chunks_esperados:
            logger.info("Namespace consistente | namespace=%s | vetores=%d", namespace, atual)
            return
        time.sleep(2)
    logger.warning(
        "Timeout aguardando consistência | namespace=%s | esperado=%d", namespace, chunks_esperados
    )

def indexar_caso(caso: Caso) -> EditalIndexado:
    """
    Prepara o edital de um caso para avaliação:
    extrai o texto do PDF, injeta o trecho sintético (se houver), extrai os CNPJs
    do texto combinado e indexa tudo num namespace isolado (= caso.id).
    """
    pdf_bytes = (EDITAIS_DIR / caso.edital_pdf).read_bytes()
    texto, num_paginas = extrair_texto_pdf(pdf_bytes, caso.edital_pdf)
    logger.info("PDF extraído | caso=%s | chars=%d | paginas=%d", caso.id, len(texto), num_paginas)

    if caso.trecho_injetado:
        texto = f"{texto}\n\n{caso.trecho_injetado}"
        logger.info("Trecho injetado | caso=%s | +chars=%d", caso.id, len(caso.trecho_injetado))

    lista_cnpj = extrair_cnpj(texto)
    logger.info("CNPJs no texto combinado | caso=%s | cnpjs=%s", caso.id, lista_cnpj)

    gerenciador = get_gerenciador()
    chunks = gerenciador.chunkizar_documento(texto)

    limpar_namespace(caso.id)
    gerenciador.processar_e_salvar(
        chunks,
        metadados={
            "municipio": caso.municipio,
            "estado": caso.estado,
            "arquivo": caso.edital_pdf,
            "origem": "avaliacao",
        },
        namespace=caso.id,
    )
    _aguardar_consistencia(caso.id, len(chunks))

    return EditalIndexado(
        caso_id=caso.id,
        namespace=caso.id,
        estado=caso.estado,
        municipio=caso.municipio,
        lista_cnpj=lista_cnpj,
        num_chunks=len(chunks),
        texto_indexado=texto,
    )