import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from app.api.dependencies import get_client_id
from app.api.rate_limiter import RateLimiter
from app.config.logging import logger
from app.ingestion.cnpj import extrair_cnpj
from app.ingestion.pdf import ErroExtracaoPDF, documento_tem_texto_nativo
from app.ingestion.pdf_hierarquico import (
    EditalExtraido,
    ErroExtracaoEstrutura,
    extrair_estrutura_pdf,
)
from app.storage.vetorial import get_gerenciador
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

# Roteador com prefixo "/upload" — agrupa os endpoints de ingestão de editais
router = APIRouter(prefix="/upload", tags=["Upload"])

# A resposta do /upload/ é um stream SSE. Cada etapa longa (Docling ~2 min,
# indexação) roda numa thread e, enquanto não termina, o endpoint emite um
# `heartbeat` a cada _HEARTBEAT_SEGUNDOS — sem isso o request fica minutos sem
# trafegar byte nenhum e o navegador/proxy derruba a conexão ociosa (o cliente
# via "Failed to fetch" mesmo com o backend terminando com sucesso).
_HEARTBEAT_SEGUNDOS = 3.0

MAX_BYTES = 20 * 1024 * 1024


def _sse(tipo: str, **campos) -> str:
    """Formata um evento no protocolo SSE, no formato que o frontend consome."""
    return f"data: {json.dumps({'type': tipo, **campos})}\n\n"


def _indexar_hierarquico(
    edital: EditalExtraido,
    *,
    thread_id: str,
    estado: str,
    municipio: str,
    nome_arquivo: str,
) -> None:
    """Roda em thread separada: grava pais e filhos no MongoDB."""
    metadados_base = {
        "edital_id": thread_id,
        "municipio": municipio,
        "estado": estado,
        "arquivo": nome_arquivo,
        "timestamp_indexacao": int(datetime.now(timezone.utc).timestamp()),
        "origem": "upload_usuario",
    }
    get_gerenciador().indexar_hierarquia(
        edital.secoes, edital.filhos_brutos, metadados_base
    )


async def _com_heartbeat(
    tarefa: asyncio.Task, texto: str, pct: int
) -> AsyncGenerator[str, None]:
    """
    Emite um evento `progress` e, enquanto `tarefa` (um to_thread) não termina, um
    `heartbeat` a cada _HEARTBEAT_SEGUNDOS. Não consome o resultado nem a exceção
    da tarefa — o chamador faz `tarefa.result()` depois deste gerador retornar.
    """
    yield _sse("progress", content=texto, pct=pct)
    while True:
        concluidas, _ = await asyncio.wait({tarefa}, timeout=_HEARTBEAT_SEGUNDOS)
        if concluidas:
            return
        yield _sse("heartbeat")


async def _stream_indexacao(
    conteudo_bytes: bytes,
    nome_arquivo: str,
    *,
    thread_id: str,
    estado: str,
    municipio: str,
) -> AsyncGenerator[str, None]:
    """Corpo do /upload/: extrai (Docling) e indexa, emitindo progresso por SSE."""
    try:
        tem_texto = await asyncio.to_thread(
            documento_tem_texto_nativo, conteudo_bytes, nome_arquivo
        )

        tarefa = asyncio.create_task(
            asyncio.to_thread(
                extrair_estrutura_pdf, conteudo_bytes, nome_arquivo, tem_texto
            )
        )
        async for evento in _com_heartbeat(
            tarefa, "Extraindo a estrutura do documento…", 35
        ):
            yield evento
        edital: EditalExtraido = tarefa.result()
        logger.info(
            "Estrutura extraída | arquivo=%s | chars=%d | paginas=%d | secoes=%d | com_ocr=%s",
            nome_arquivo,
            len(edital.texto),
            edital.num_paginas,
            len(edital.secoes),
            not tem_texto,
        )

        tarefa = asyncio.create_task(
            asyncio.to_thread(
                _indexar_hierarquico,
                edital,
                thread_id=thread_id,
                estado=estado,
                municipio=municipio,
                nome_arquivo=nome_arquivo,
            )
        )
        async for evento in _com_heartbeat(
            tarefa, "Indexando as seções e os trechos…", 82
        ):
            yield evento
        tarefa.result()
        logger.info("Indexação concluída | arquivo=%s", nome_arquivo)

        cnpjs = extrair_cnpj(edital.texto)
        logger.info(
            "CNPJs extraídos | arquivo=%s | quantidade=%d | cnpjs=%s",
            nome_arquivo,
            len(cnpjs),
            cnpjs,
        )
        yield _sse("done", cnpjs=cnpjs)

    except (ErroExtracaoPDF, ErroExtracaoEstrutura):
        logger.exception("Falha ao extrair o PDF | arquivo=%s", nome_arquivo)
        yield _sse(
            "error",
            content="Não foi possível ler o PDF. O arquivo pode estar corrompido ou protegido por senha.",
        )
    except Exception:  # noqa: BLE001 — qualquer falha vira um evento `error` pro frontend
        logger.exception("Falha ao indexar edital | arquivo=%s", nome_arquivo)
        yield _sse(
            "error",
            content="Falha ao indexar o edital. Tente novamente em instantes.",
        )


@router.post(
    "/",
    # Upload dispara indexação no RAG (custo de embeddings) — limite mais
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
    """
    Recebe um edital em PDF, extrai a estrutura (Docling) e indexa (MongoDB).
    Responde em **streaming SSE**: eventos `progress`/`heartbeat` durante o processamento
    e, no fim, `done` com os CNPJs ou `error`. As validações baratas (tipo, tamanho)
    ainda respondem `415`/`413` antes de o stream começar.
    """
    logger.info(
        "Upload recebido | arquivo=%s | estado=%s | municipio=%s | client_id=%s",
        file.filename,
        estado,
        municipio,
        client_id,
    )

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

    conteudo_bytes = await file.read()
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

    # file.filename pode vir None do FastAPI — usa um nome padrão nesse caso
    nome_arquivo = file.filename or "arquivo.pdf"
    return StreamingResponse(
        _stream_indexacao(
            conteudo_bytes,
            nome_arquivo,
            thread_id=thread_id,
            estado=estado,
            municipio=municipio,
        ),
        media_type="text/event-stream",
    )
