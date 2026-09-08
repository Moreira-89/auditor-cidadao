import io
import re
from collections import Counter

from app.config.logging import logger
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import (
    HeadingHierarchyOptions,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from pydantic import BaseModel

PADRAO_TEXTO_HEADER = re.compile(r"^[A-ZÀ-Ý][A-ZÀ-Ý0-9º°\s,\-/:]{2,80}$")
PADRAO_MARKER_NUMERACAO = re.compile(r"^\d+(?:\.\d+)*\.?$")
PADRAO_NUMERACAO_PREFIXO = re.compile(r"^\d+(?:\.\d+)*\.?\s+")

# Timbre/rodapé institucional ("ESTADO DO ...", "COORDENADORIA GERAL DE ...") se
# repete página a página e o layout model do Docling costuma marcá-lo como
# cabeçalho de seção. Um cabeçalho de verdade não repete o texto exato; a partir
# desta contagem, tratamos como rodapé corrido e removemos.
MIN_REPETICAO_RODAPE = 4


class ErroExtracaoEstrutura(Exception):
    """Levantada quando o Docling não consegue converter o PDF (arquivo corrompido, protegido ou ilegível)."""


class EditalExtraido(BaseModel):
    """Resultado da extração hierárquica de um edital."""

    secoes: list[dict]  # um dict por cabeçalho — destino: MongoDB
    filhos_brutos: list[dict]  # um dict por item de conteúdo — destino: MongoDB
    texto: str  # texto linear em ordem de leitura — pipeline vetorial atual
    num_paginas: int


def _eh_cabecalho_por_padrao(item) -> tuple[bool, int]:
    """
    Detecta cabeçalho numerado de edital que o layout model do Docling classificou
    incorretamente (como ListItem com numeração separada no marker, ou como
    TextItem comum com número e título grudados no mesmo texto).
    Retorna (eh_cabecalho, nivel), nivel = profundidade da numeração (1 -> 1, 3.6 -> 2).
    """
    tipo = type(item).__name__
    texto = (getattr(item, "text", "") or "").strip()
    marker = getattr(item, "marker", None)

    if tipo == "ListItem" and marker and PADRAO_MARKER_NUMERACAO.match(marker):
        # numeração já veio separada no marker — confirma que o texto é
        # curto/caixa-alta (senão pega item de lista de verdade, tipo
        # "2.2. O objeto da contratação está previsto..." que também é
        # ListItem com marker numérico, mas não é cabeçalho)
        if PADRAO_TEXTO_HEADER.match(texto):
            nivel = marker.rstrip(".").count(".") + 1
            return True, nivel
        return False, 0

    if tipo == "TextItem":
        # fallback: número e texto grudados na mesma string, ex. "1. DO OBJETO"
        match = re.match(r"^(?P<num>\d+(?:\.\d+)*)\.?\s+(?P<titulo>.+)$", texto)
        if match and PADRAO_TEXTO_HEADER.match(match.group("titulo")):
            nivel = match.group("num").count(".") + 1
            return True, nivel

    return False, 0


def _limpar_titulo(texto: str) -> str:
    """Remove o prefixo de numeração ('1.', '3.6.1 ') do início do título,
    deixando o campo consistente não importa qual rota detectou o cabeçalho
    (SectionHeaderItem nativo, ListItem resgatado, ou fallback TextItem)."""
    return PADRAO_NUMERACAO_PREFIXO.sub("", texto).strip()


def _rodapes_corridos(doc) -> set[str]:
    """
    Textos classificados como cabeçalho que se repetem em muitas páginas — timbre
    e rodapé institucional. Removidos por completo: não abrem seção nem entram no
    texto; o conteúdo real da página segue para a seção aberta no momento.
    """
    contagem: Counter[str] = Counter()
    for item, _ in doc.iterate_items():
        texto = (getattr(item, "text", "") or "").strip()
        if not texto:
            continue
        if type(item).__name__ == "SectionHeaderItem" or _eh_cabecalho_por_padrao(item)[0]:
            contagem[texto] += 1
    return {t for t, n in contagem.items() if n >= MIN_REPETICAO_RODAPE}


def _extrair_estrutura(doc) -> tuple[list[dict], list[dict], str]:
    """
    Percorre o DoclingDocument em ordem de leitura e monta:
    - secoes: um dict por cabeçalho (pai — vai pro Mongo)
    - filhos_brutos: um dict por item de conteúdo (filho — vai pro MongoDB),
      referenciando a seção pela `ordem` em `secoes`, não por _id (o _id só
      existe depois da inserção no Mongo)
    - texto_linear: todos os itens concatenados na ordem de leitura, para o
      pipeline vetorial atual (chunking plano) enquanto o RAG hierárquico não existe
    """
    secoes: list[dict] = []
    filhos_brutos: list[dict] = []
    pilha: list[dict] = []  # headers abertos no momento, do nível 1 pro mais fundo
    linhas: list[str] = []
    rodapes = _rodapes_corridos(doc)

    def secao_atual_idx() -> int | None:
        return len(secoes) - 1 if secoes else None

    for item, _ in doc.iterate_items():
        tipo = type(item).__name__
        # TableItem não tem `.text`; o conteúdo só sai pelo export.
        if tipo == "TableItem":
            texto = item.export_to_markdown(doc).strip()
        else:
            texto = (getattr(item, "text", "") or "").strip()
        if not texto:
            continue

        eh_header_docling = tipo == "SectionHeaderItem"
        eh_header_heuristica, nivel_heuristica = _eh_cabecalho_por_padrao(item)

        # timbre/rodapé repetido em toda página — ignora por completo
        if (eh_header_docling or eh_header_heuristica) and texto in rodapes:
            continue
        linhas.append(texto)

        if eh_header_docling or eh_header_heuristica:
            nivel = getattr(item, "level", None) or nivel_heuristica or 1
            titulo = _limpar_titulo(texto)

            # fecha tudo que está no mesmo nível ou mais fundo que o novo header
            pilha = [h for h in pilha if h["nivel"] < nivel]
            caminho = (
                " > ".join(h["titulo"] for h in pilha)
                + (" > " if pilha else "")
                + titulo
            )

            secoes.append(
                {
                    "ordem": len(secoes),
                    "nivel": nivel,
                    "titulo": titulo,
                    "caminho": caminho,
                    "texto_completo": "",
                }
            )
            pilha.append({"nivel": nivel, "titulo": titulo})
            continue

        # não é header: vira filho da seção aberta no momento (se houver)
        idx = secao_atual_idx()
        if idx is not None:
            secoes[idx]["texto_completo"] += texto + "\n"

        filhos_brutos.append(
            {
                "secao_ordem": idx,  # None só se aparecer conteúdo antes do 1º header
                "tipo": tipo,  # TableItem fica inteiro; TextItem pode ser subdividido depois
                "texto": texto,
            }
        )

    return secoes, filhos_brutos, "\n".join(linhas)


def _construir_e_aquecer(*, com_ocr: bool) -> DocumentConverter:
    """Monta um DocumentConverter e já baixa/carrega os modelos (layout, tabela e,
    se `com_ocr`, OCR) — assim a primeira conversão não paga esse custo."""
    opcoes = PdfPipelineOptions(
        heading_hierarchy_options=HeadingHierarchyOptions(enabled=True, use_style=False),
        do_ocr=com_ocr,
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opcoes)}
    )
    converter.initialize_pipeline(InputFormat.PDF)
    logger.info("Converter Docling pronto | com_ocr=%s", com_ocr)
    return converter


# Dois converters mantidos quentes: um sem OCR (PDF com texto nativo, ~toda
# licitação) e um com OCR (PDF escaneado). A checagem do pdfplumber
# (documento_tem_texto_nativo, em app/ingestion/pdf.py) decide qual usar por
# requisição. Trocar do_ocr num converter só forçaria recarga de modelo a cada
# request; manter os dois custa RAM fixa, mas nenhuma requisição paga carga.
_converter_sem_ocr: DocumentConverter | None = None
_converter_com_ocr: DocumentConverter | None = None


def inicializar_converters() -> None:
    """Pré-aquece os dois converters no startup (lifespan). Síncrona e pesada
    (baixa/carrega os modelos) — chame via asyncio.to_thread."""
    global _converter_sem_ocr, _converter_com_ocr
    if _converter_sem_ocr is None:
        _converter_sem_ocr = _construir_e_aquecer(com_ocr=False)
    if _converter_com_ocr is None:
        _converter_com_ocr = _construir_e_aquecer(com_ocr=True)


def _converter_para(tem_texto_nativo: bool) -> DocumentConverter:
    """Devolve o converter certo, criando-o na hora se o lifespan não rodou
    (ex.: script de avaliação, que só aquece o que usa)."""
    global _converter_sem_ocr, _converter_com_ocr
    if tem_texto_nativo:
        if _converter_sem_ocr is None:
            _converter_sem_ocr = _construir_e_aquecer(com_ocr=False)
        return _converter_sem_ocr
    if _converter_com_ocr is None:
        _converter_com_ocr = _construir_e_aquecer(com_ocr=True)
    return _converter_com_ocr


def extrair_estrutura_pdf(
    conteudo_bytes: bytes, nome_arquivo: str, tem_texto_nativo: bool
) -> EditalExtraido:
    """
    Converte o PDF com o Docling e monta a estrutura hierárquica do edital.
    `tem_texto_nativo` (da checagem em app/ingestion/pdf.py) escolhe o converter
    com ou sem OCR. Síncrona e cara (segundos a minutos) — chame via asyncio.to_thread.
    """
    converter = _converter_para(tem_texto_nativo)
    try:
        origem = DocumentStream(name=nome_arquivo, stream=io.BytesIO(conteudo_bytes))
        doc = converter.convert(origem).document
    except Exception as e:
        logger.error(
            "Falha na conversão Docling | arquivo=%s | erro=%s", nome_arquivo, str(e)
        )
        raise ErroExtracaoEstrutura(nome_arquivo) from e

    secoes, filhos_brutos, texto = _extrair_estrutura(doc)
    return EditalExtraido(
        secoes=secoes,
        filhos_brutos=filhos_brutos,
        texto=texto,
        num_paginas=doc.num_pages(),
    )
