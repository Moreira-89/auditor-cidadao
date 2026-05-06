import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


# -----------------------------------------------------------------------------
# GERAÇÃO DE PDF
# -----------------------------------------------------------------------------

def gerar_pdf(caminho_saida: str, titulo: str, paragrafos: list[str]) -> None:
    """
    Objetivo: Gerar um arquivo PDF estruturado (título + parágrafos) e salvá-lo em disco.

    COMO FUNCIONA:
    1. Preparação do Diretório: Garante que a pasta de destino exista antes de tentar
       gravar o arquivo, evitando erros de caminho inexistente.
    2. Criação do Documento: Instancia o `SimpleDocTemplate` do ReportLab, que define
       o tamanho de página (A4) e as margens do documento.
    3. Definição de Estilos: Cria dois estilos tipográficos — um para o título
       (centralizado, negrito, tamanho 14) e um para o corpo do texto (justificado,
       espaçamento entre linhas de 16 pontos).
    4. Montagem dos Elementos: Constrói uma lista de objetos `Paragraph` e `Spacer`
       que o ReportLab irá renderizar em sequência na página.
    5. Renderização: Chama `doc.build()` para processar todos os elementos e escrever
       o arquivo PDF no caminho especificado.

    Args:
        caminho_saida (str): Caminho completo (relativo ou absoluto) onde o PDF será salvo.
                             Ex: "app/editais_teste/caso_001.pdf".
        titulo (str): Texto do título do documento, renderizado em destaque no topo da página.
        paragrafos (list[str]): Lista de strings, cada uma representando um parágrafo do corpo.

    Raises:
        OSError: Se o sistema de arquivos não permitir a criação do diretório ou do arquivo.
        Exception: Qualquer erro do motor de renderização do ReportLab (ex: conteúdo inválido).
    """
    # --- 1. Preparação do Diretório ---
    # `os.path.dirname` extrai apenas o caminho da pasta a partir do caminho completo do arquivo.
    # `exist_ok=True` evita erro se a pasta já existir — é seguro chamar sempre.
    pasta = os.path.dirname(caminho_saida)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    # --- 2. Criação do Documento ---
    # `SimpleDocTemplate` é o construtor de layout mais simples do ReportLab.
    # As margens de 2cm garantem uma aparência profissional compatível com documentos reais.
    doc = SimpleDocTemplate(
        filename=caminho_saida,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    # --- 3. Definição de Estilos ---
    # `getSampleStyleSheet()` fornece estilos base padrão do ReportLab.
    # Herdamos deles via `parent` para manter coerência e sobrescrever apenas o necessário.
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        name="Titulo",
        parent=estilos["Heading1"],
        alignment=1,   # 1 = centralizado (TA_CENTER)
        fontSize=14,
    )
    estilo_corpo = ParagraphStyle(
        name="Corpo",
        parent=estilos["Normal"],
        fontSize=12,
        leading=16,    # espaçamento entre linhas em pontos tipográficos
        alignment=4,   # 4 = justificado (TA_JUSTIFY)
    )

    # --- 4. Montagem dos Elementos ---
    # O ReportLab trabalha com uma lista de "flowables" (elementos que fluem na página).
    # `Spacer(1, 12)` insere um espaço vertical de 12 pontos após cada elemento.
    elementos = [Paragraph(titulo, estilo_titulo), Spacer(1, 12)]
    for paragrafo in paragrafos:
        elementos.append(Paragraph(paragrafo, estilo_corpo))
        elementos.append(Spacer(1, 12))

    # --- 5. Renderização ---
    # `build()` processa a lista de elementos e grava o arquivo PDF em disco.
    doc.build(elementos)