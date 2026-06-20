import io
import asyncio

import pdfplumber
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.dependencies import gerenciador
from app.core.logging_config import logger
from app.utils.func_extrair_cnpj import extrair_cnpj

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO
# -----------------------------------------------------------------------------
# Criação do roteador FastAPI. O prefixo "/upload" será adicionado automaticamente
# antes da rota base ("/"). A tag "Upload" agrupa isso na documentação (Swagger UI).
router = APIRouter(prefix="/upload", tags=["Upload"])


# -----------------------------------------------------------------------------
# ENDPOINTS
# -----------------------------------------------------------------------------
@router.post("/")
async def upload_edital(
    file: UploadFile = File(...),
    estado: str = Form(...),
    municipio: str = Form(...),
    user_name: str = Form(...),
):
    """
    Objetivo: Endpoint responsável por ingerir novos editais no banco de dados vetorial.

    COMO FUNCIONA:
    1. Validação de Formato: Checa se o arquivo enviado é realmente um PDF.
    2. Leitura dos Bytes: Transforma o arquivo de Upload em bytes brutos pausando a execução até a leitura.
    3. Extração de Texto: Usa a biblioteca `pdfplumber` para ler o PDF página
       por página e consolidar tudo em uma grande string.
    4. Indexação no Banco Vetorial: Envia o texto e os metadados (estado, município) para
       o `GerenciadorVetorial`, que vai "fatiar" o texto em partes menores e salvar os embeddings.
    5. Extração de CNPJs: Por fim, extrai e retorna os CNPJs encontrados no texto bruto usando expressão regular.

    Args:
        file (UploadFile): O arquivo PDF enviado pelo usuário na requisição.
        estado (str): Sigla ou nome do estado (para compor os metadados).
        municipio (str): Nome do município (para compor os metadados).
        user_name (str): Nome do usuário que enviou o arquivo.

    Returns:
        dict: Confirmação de que o arquivo foi processado e salvo.

    Raises:
        HTTPException (415): Se o formato do arquivo não for 'application/pdf'.
    """

    logger.info("Upload recebido | arquivo=%s | estado=%s | municipio=%s | user=%s",
                file.filename, estado, municipio, user_name)

    # --- 1. Validação de Formato ---
    # Rejeita imediatamente arquivos que não sejam PDF.
    # Utilizamos o HTTP Status 415 (Unsupported Media Type) por ser o padrão
    # semântico correto quando o tipo do arquivo não é aceito pelo servidor.
    if file.content_type != "application/pdf":
        logger.warning("Formato inválido rejeitado | arquivo=%s | content_type=%s",
                       file.filename, file.content_type)
        raise HTTPException(
            status_code=415,
            detail=f"Formato inválido: '{file.content_type}'. Apenas arquivos PDF são aceitos.",
        )

    # --- 2. Leitura dos Bytes ---
    # UploadFile.read() é uma função assíncrona (corrotina). O `await` é obrigatório
    # para pausar a execução da requisição até que os bytes do arquivo sejam lidos.
    conteudo_bytes = await file.read()
    logger.info("Arquivo lido | arquivo=%s | bytes=%d", file.filename, len(conteudo_bytes))

    # --- 3. Extração de Texto ---
    # PDFs não são texto puro, são binários complexos.
    # io.BytesIO simula um arquivo em disco na memória RAM para não precisarmos
    # salvar arquivos temporários físicos (mais rápido e seguro).
    # O pdfplumber abre esse arquivo virtual e nós iteramos por cada página extraindo texto.
    with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
        # A expressão `or ""` previne erros caso alguma página contenha apenas
        # imagens e o retorno do extract_text() seja None.
        texto = "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
    logger.info("Texto extraído | arquivo=%s | chars=%d | paginas=%d",
                file.filename, len(texto), len(pdf.pages))

    # --- 4. Indexação no Banco Vetorial ---
    # Acionamos a orquestração do RAG. A função executar:
    # - Chunkiza o texto (divide em partes lógicas de até 2000 caracteres)
    # - Gera os vetores para cada pedaço
    # - Salva tudo no Pinecone amarrado aos metadados abaixo.
    # Esses metadados são cruciais para podermos filtrar depois (ex: "Buscar
    # apenas nos editais de São Paulo").
    logger.info("Iniciando indexação no Pinecone | arquivo=%s", file.filename)
    await asyncio.to_thread(
        gerenciador.executar,
        texto_edital=texto,
        metadados={
            "municipio": municipio,
            "estado": estado,
            "arquivo": file.filename
        },
    )
    logger.info("Indexação concluída | arquivo=%s", file.filename)

    # --- 5. Extração de CNPJs ---
    # Usa a função auxiliar para encontrar todos os CNPJs no texto extraído.
    cnpjs_encontrados = extrair_cnpj(texto)
    logger.info("CNPJs extraídos | arquivo=%s | quantidade=%d | cnpjs=%s",
                file.filename, len(cnpjs_encontrados), cnpjs_encontrados)

    # Retorna a confirmação junto com a lista de CNPJs encontrados.
    return {"mensagem": "Edital indexado!", "cnpjs": cnpjs_encontrados}
