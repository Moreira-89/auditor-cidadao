"""
Extração de texto de PDFs recebidos via upload, usando pdfplumber.

Separado de app/api/root_upload.py para manter a rota enxuta: aqui mora a
lógica de leitura do PDF; quem está na borda (o endpoint) decide como
traduzir ErroExtracaoPDF em uma resposta HTTP.
"""

import io

import pdfplumber

from app.core.logging_config import logger


class ErroExtracaoPDF(Exception):
    """Levantada quando o pdfplumber não consegue abrir ou ler o PDF (arquivo corrompido ou protegido por senha)."""


def extrair_texto_pdf(conteudo_bytes: bytes, nome_arquivo: str) -> tuple[str, int]:
    """
    Abre um PDF em memória (sem salvar em disco) e extrai o texto de cada página.
    Retorna o texto concatenado e o número de páginas.

    Levanta ErroExtracaoPDF em caso de falha, em vez de mascará-la — o
    chamador decide como traduzir isso em uma resposta para o usuário.
    """
    try:
        with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
            num_paginas = len(pdf.pages)
            # Concatena o texto de todas as páginas; usa "" se uma página não tiver texto legível
            texto = "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
    except Exception as e:
        logger.error(
            "Falha na extração de texto | arquivo=%s | erro=%s", nome_arquivo, str(e)
        )
        raise ErroExtracaoPDF(nome_arquivo) from e

    return texto, num_paginas
