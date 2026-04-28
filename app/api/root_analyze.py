from fastapi import APIRouter, File, UploadFile, HTTPException
import pdfplumber
import io
import re

from app.services.ai_engine import run_agent

router = APIRouter(
    prefix="/analisar-edital",
    tags=["Análise de Editais"]
)

@router.post("/")
async def executar_analise(file: UploadFile = File()):
    """
    Recebe um arquivo PDF de edital ou contrato público, extrai seu conteúdo textual
    e o envia ao agente de IA para análise de conformidade.

    O endpoint executa três etapas em sequência:
    1. Valida que o arquivo enviado é um PDF (rejeita outros formatos com HTTP 415).
    2. Extrai todo o texto do PDF usando pdfplumber, incluindo conteúdo de tabelas.
    3. Identifica os CNPJs presentes no texto via regex e os passa ao agente junto
       com o texto completo, permitindo que o agente consulte a Receita Federal.

    Args:
        file (UploadFile): Arquivo PDF enviado via multipart/form-data.

    Returns:
        dict: Dicionário com a chave 'resultado_analise' contendo o texto da análise
              gerada pelo agente, ou uma mensagem de erro caso o processo falhe.

    Raises:
        HTTPException 415: Se o arquivo enviado não for do tipo 'application/pdf'.
    """

    # Rejeita imediatamente arquivos que não sejam PDF.
    # HTTP 415 = "Unsupported Media Type" — mais semântico que um 400 genérico.
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=415,
            detail=f"Formato inválido: '{file.content_type}'. Apenas arquivos PDF são aceitos."
        )

    # UploadFile.read() é uma corrotina — o await é obrigatório para receber os bytes reais.
    # Sem o await, a variável receberia um objeto de corrotina, não o conteúdo do arquivo.
    conteudo_bytes = await file.read()

    # PDFs são arquivos binários e não podem ser decodificados diretamente como UTF-8.
    # O pdfplumber abre o PDF a partir dos bytes em memória (sem salvar em disco),
    # extrai o texto de cada página e une tudo em uma única string separada por quebras de linha.
    # O "or ''" garante que páginas sem texto (ex: imagens escaneadas) não quebrem o join.
    with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
        texto = "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)

        # Extrai todos os CNPJs do texto usando regex no formato XX.XXX.XXX/XXXX-XX.
        # Essa lista é passada ao agente para que ele saiba exatamente quais CNPJs consultar
        # na Receita Federal, sem depender apenas da interpretação do modelo.
        cnpjs = re.findall(r'\b\d{2}\.\d{3}\.\d{3}\/\d{4}\-\d{2}\b', texto)

    # Aciona o motor do agente com o texto completo do edital e a lista de CNPJs encontrados.
    resultado = run_agent(texto_edital=texto, lista_cnpj=cnpjs)
    return {"resultado_analise": resultado}