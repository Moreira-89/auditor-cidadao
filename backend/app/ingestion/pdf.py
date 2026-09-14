import io

import pdfplumber
from app.config.logging import logger


class ErroExtracaoPDF(Exception):
    """Levantada quando o pdfplumber não consegue abrir ou ler o PDF (arquivo corrompido ou protegido por senha)."""


def documento_tem_texto_nativo(
    conteudo_bytes: bytes, nome_arquivo: str, paginas_amostra: int = 3
) -> bool:
    """
    Verificação barata para decidir se o PDF precisa de OCR: abre as primeiras
    `paginas_amostra` páginas e checa se alguma tem texto extraível. Se nenhuma
    tiver, é PDF escaneado (imagem) e a extração hierárquica precisa acionar OCR.
    """
    try:
        with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
            return any(
                (pagina.extract_text() or "").strip()
                for pagina in pdf.pages[:paginas_amostra]
            )
    except Exception as e:
        logger.error(
            "Falha ao checar texto nativo | arquivo=%s | erro=%s", nome_arquivo, str(e)
        )
        raise ErroExtracaoPDF(nome_arquivo) from e
