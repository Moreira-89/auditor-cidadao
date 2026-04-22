import logging
import os
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)

def fatiar_texto(texto: str) -> list[str]:
    """Divide o texto extraído em pedaços menores (chunks) para vetorização."""
    logger.info("Iniciando o fatiamento do texto (Chunking)...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    
    pedacos = text_splitter.split_text(texto)
    logger.info(f"O texto foi dividido em {len(pedacos)} chunks.")
    return pedacos


def extrair_texto_pdf(caminho_arquivo: str) -> str:
    """Extrai todo o conteúdo textual de um arquivo PDF fornecido."""
    logger.info(f"Lendo e extraindo texto do arquivo: {caminho_arquivo}")
    texto_completo = ""
    
    with pdfplumber.open(caminho_arquivo) as pdf:
        total_paginas = len(pdf.pages)
        logger.info(f"Documento carregado. Total de páginas: {total_paginas}")
        
        for i, pagina in enumerate(pdf.pages):
            texto = pagina.extract_text()
            if texto:
                texto_completo += f"\n--- [PÁGINA {i+1}] ---\n" 
                texto_completo += texto
                
    return texto_completo


def criar_banco_vetorial(fatias: list[str]):
    """Gera embeddings dos chunks de texto e os adiciona ao banco vetorial ChromaDB."""
    logger.info("Inicializando modelo de Embeddings HuggingFace...")
    modelo_embedding = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    pasta_banco = "./banco_chroma"
    logger.info(f"Atualizando o banco de dados vetorial em: {pasta_banco}")
    
    db = Chroma.from_texts(
        texts=fatias, 
        embedding=modelo_embedding, 
        persist_directory=pasta_banco
    )
    
    logger.info("Banco vetorial atualizado com sucesso.")
    return db    


def processar_documento(caminho_arquivo: str) -> dict:
    """
    Fluxo principal para extrair texto de um PDF, particioná-lo e vetorizar seu conteúdo.
    
    Args:
        caminho_arquivo (str): Caminho local temporário para o arquivo PDF recebido.
        
    Returns:
        dict: Dicionário contendo o status da operação ('sucesso' ou 'erro') e uma mensagem.
    """
    logger.info(f"Iniciando pipeline de processamento para: {caminho_arquivo}")
    
    try:
        texto_bruto = extrair_texto_pdf(caminho_arquivo)
        fatias = fatiar_texto(texto_bruto)
        criar_banco_vetorial(fatias)
        
        # Remove o arquivo PDF temporário para liberar espaço
        os.remove(caminho_arquivo)
        logger.info(f"Arquivo temporário {caminho_arquivo} removido após processamento.")
        
        return {"status": "sucesso", "mensagem": f"Documento processado. {len(fatias)} fatias vetorizadas!"}
    
    except Exception as e:
        logger.error(f"Erro ao processar o documento {caminho_arquivo}: {e}", exc_info=True)
        return {"status": "erro", "mensagem": str(e)}