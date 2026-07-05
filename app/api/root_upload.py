import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.dependencies import gerenciador
from app.core.logging_config import logger
from app.utils.func_extrair_cnpj import extrair_cnpj
from app.utils.func_extrair_texto_pdf import ErroExtracaoPDF, extrair_texto_pdf

# Roteador com prefixo "/upload" — agrupa os endpoints de ingestão de editais
router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/")
async def upload_edital(
    file: UploadFile = File(...),
    estado: str = Form(...),
    municipio: str = Form(...),
):
    """Recebe um edital em PDF, extrai o texto, indexa no banco vetorial e retorna os CNPJs encontrados."""

    logger.info(
        "Upload recebido | arquivo=%s | estado=%s | municipio=%s",
        file.filename,
        estado,
        municipio,
    )

    # Rejeita qualquer arquivo que não seja PDF antes de processá-lo
    if file.content_type != "application/pdf":
        logger.warning(
            "Formato inválido rejeitado | arquivo=%s | content_type=%s",
            file.filename,
            file.content_type,
        )
        raise HTTPException(
            status_code=415,
            detail=f"Formato inválido: '{file.content_type}'. Apenas arquivos PDF são aceitos.",
        )

    # Lê todos os bytes do arquivo enviado de forma assíncrona
    conteudo_bytes = await file.read()

    # Bloqueia arquivos acima de 20 MB para evitar sobrecarga no processamento
    MAX_BYTES = 20 * 1024 * 1024
    if len(conteudo_bytes) > MAX_BYTES:
        logger.warning(
            "Arquivo excede limite de tamanho | arquivo=%s | bytes=%d",
            file.filename,
            len(conteudo_bytes),
        )
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo muito grande: {len(conteudo_bytes)} bytes. O limite é de {MAX_BYTES} bytes.",
        )
    logger.info(
        "Arquivo lido | arquivo=%s | bytes=%d", file.filename, len(conteudo_bytes)
    )

    # Abre o PDF em memória (sem salvar em disco) e extrai o texto de cada página
    try:
        texto, num_paginas = extrair_texto_pdf(conteudo_bytes, file.filename)
    except ErroExtracaoPDF:
        raise HTTPException(
            status_code=422,
            detail="Não foi possível ler o PDF. O arquivo pode estar corrompido ou protegido por senha.",
        )
    logger.info(
        "Texto extraído | arquivo=%s | chars=%d | paginas=%d",
        file.filename,
        len(texto),
        num_paginas,
    )

    # Envia o texto para o GerenciadorVetorial, que chunkiza, gera embeddings e salva no Pinecone
    # Roda em thread separada porque a função é síncrona e bloquearia o event loop
    logger.info("Iniciando indexação no Pinecone | arquivo=%s", file.filename)
    await asyncio.to_thread(
        gerenciador.executar,
        texto_edital=texto,
        metadados={
            # Metadados usados para filtrar buscas por localidade depois da indexação
            "municipio": municipio,
            "estado": estado,
            "arquivo": file.filename,
        },
    )
    logger.info("Indexação concluída | arquivo=%s", file.filename)

    # Usa expressão regular para encontrar todos os CNPJs no texto do edital
    cnpjs_encontrados = extrair_cnpj(texto)
    logger.info(
        "CNPJs extraídos | arquivo=%s | quantidade=%d | cnpjs=%s",
        file.filename,
        len(cnpjs_encontrados),
        cnpjs_encontrados,
    )

    return {"mensagem": "Edital indexado!", "cnpjs": cnpjs_encontrados}
