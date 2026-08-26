"""
Endpoint HTTP de upload de editais.

Recebe um PDF, valida (tipo e tamanho), extrai o texto, indexa no banco vetorial
(Pinecone) e devolve os CNPJs encontrados no documento — que o frontend guarda para
usar nas perguntas seguintes. A extração de texto e a indexação ficam em módulos
dedicados; aqui é só a "borda" HTTP: validar a entrada e traduzir falhas em respostas
com o código HTTP certo (415 tipo inválido, 413 grande demais, 422 PDF ilegível,
502 falha ao indexar).
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import get_client_id
from app.storage.vetorial import get_gerenciador
from app.config.logging import logger
from app.agents.relatorio import gerar_relatorio_inicial
from app.api.rate_limiter import RateLimiter
from app.ingestion.cnpj import extrair_cnpj
from app.ingestion.pdf import ErroExtracaoPDF, extrair_texto_pdf

# Roteador com prefixo "/upload" — agrupa os endpoints de ingestão de editais
router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post(
    "/",
    # Upload dispara indexação no Pinecone (custo de embeddings) — limite mais
    # apertado que o de conversa, já que um usuário legítimo sobe poucos editais
    # por dia. Janela de 86400s = 24h.
    dependencies=[
        Depends(
            RateLimiter(
                limit=5,
                window_seconds=86400,
                prefixo="quota_upload",
                descricao="upload diário",
            )
        )
    ],
)
async def upload_edital(
    file: UploadFile = File(...),  # noqa: B008
    estado: str = Form(...),
    municipio: str = Form(...),
    thread_id: str = Form(...),
    client_id: str = Depends(get_client_id),
):
    """Recebe um edital em PDF, extrai o texto, indexa no banco vetorial e retorna os CNPJs encontrados."""

    logger.info(
        "Upload recebido | arquivo=%s | estado=%s | municipio=%s | client_id=%s",
        file.filename,
        estado,
        municipio,
        client_id,
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
    # file.filename pode vir None do FastAPI, então usamos um nome padrão nesse caso
    nome_arquivo = file.filename or "arquivo.pdf"
    try:
        texto, num_paginas = extrair_texto_pdf(conteudo_bytes, nome_arquivo)
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
    try:
        await asyncio.to_thread(
            get_gerenciador().executar,
            texto_edital=texto,
            metadados={
                # Metadados usados para filtrar buscas por localidade depois da indexação
                "municipio": municipio,
                "estado": estado,
                "arquivo": file.filename,
                "timestamp_indexacao": int(
                    datetime.now(timezone.utc).timestamp()
                ),
                "origem": "upload_usuario",
            },
        )
    except Exception:  # noqa: BLE001 — qualquer falha aqui vira um 502 amigável pro frontend
        logger.exception("Falha ao indexar edital no Pinecone | arquivo=%s", file.filename)
        raise HTTPException(
            status_code=502,
            detail="Falha ao indexar o edital no banco vetorial. Tente novamente em instantes.",
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

    # Relatório automático pós-indexação (Backlog V2, Seção C): gera o primeiro turno
    # da thread sozinho, sem esperar o usuário perguntar. Roda dentro da mesma requisição
    # de upload — por isso consome a quota_upload (5/dia), não a quota_chat — e nunca
    # levanta exceção: se falhar, o upload segue bem-sucedido com relatorio_inicial: null,
    # e o frontend cai de volta nas sugestões de pergunta estáticas.
    logger.info("Gerando relatório automático pós-indexação | thread=%s", thread_id)
    relatorio_inicial = await gerar_relatorio_inicial(
        thread_id=thread_id,
        lista_cnpj=cnpjs_encontrados,
        estado=estado,
        municipio=municipio,
    )
    logger.info(
        "Relatório automático concluído | thread=%s | sucesso=%s",
        thread_id,
        relatorio_inicial is not None,
    )

    return {
        "mensagem": "Edital indexado!",
        "cnpjs": cnpjs_encontrados,
        "relatorio_inicial": relatorio_inicial,
    }
