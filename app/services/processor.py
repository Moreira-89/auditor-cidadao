from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import pdfplumber

def fatiar_texto(texto):
    print("Iniciando o fatiamento do texto (Chunking)...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    
    pedacos = text_splitter.split_text(texto)
    
    print(f"O texto foi dividido em {len(pedacos)} fatias (chunks).")
    return pedacos

def extrair_texto_pdf(caminho_arquivo):
    print(f"Iniciando a leitura do arquivo: {caminho_arquivo}")
    texto_completo = ""
    
    # Abrindo o PDF
    with pdfplumber.open(caminho_arquivo) as pdf:
        total_paginas = len(pdf.pages)
        print(f"O documento tem {total_paginas} páginas.")
        
        for i, pagina in enumerate(pdf.pages):
            # Extraindo o texto página por página
            texto = pagina.extract_text()
            
            if texto:
                # Adicionamos uma marcação invisível para sabermos de onde veio
                texto_completo += f"\n--- [PÁGINA {i+1}] ---\n" 
                texto_completo += texto
                
    return texto_completo


def criar_banco_vetorial(fatias):
    print("\nIniciando o modelo de Embeddings...")
    
    # Usando um modelo gratuito, leve e excelente para o idioma Português
    modelo_embedding = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    print("Criando/Atualizando o Banco de Dados Vetorial Local (ChromaDB)...")
    
    # O Chroma vai transformar os textos em números usando o modelo acima
    # e salvar tudo numa pasta chamada 'banco_chroma_suzano'
    pasta_banco = "./banco_chroma"
    
    db = Chroma.from_texts(
        texts=fatias, 
        embedding=modelo_embedding, 
        persist_directory=pasta_banco
    )
    
    print(f"Sucesso! Banco vetorial criado na pasta '{pasta_banco}'.")
    return db    

# ==========================================
# FLUXO PRINCIPAL DE EXECUÇÃO
# ==========================================
caminho_pdf_suzano = "scripts_dados/PE_1012025__Servios_de_Segurana_do_Trabalho__SRP_BLL.pdf" 

# 1. Extrai o texto
texto_bruto = extrair_texto_pdf(caminho_pdf_suzano)

# 2. Fatiamento (Chunking)
fatias = fatiar_texto(texto_bruto)

# 3. Criação dos Embeddings e Salvamento no Vector DB
banco_vetorial = criar_banco_vetorial(fatias)

# ==========================================
# TESTANDO A MÁGICA (A Busca Vetorial)
# ==========================================
print("\n--- TESTANDO A BUSCA SEMÂNTICA ---")
pergunta = "Qual é o valor total da contratação ou da licitação?"
print(f"Sua Pergunta: '{pergunta}'")

# Vamos pedir para o banco trazer as 3 fatias que mais se parecem com a pergunta
resultados = banco_vetorial.similarity_search(pergunta, k=3)

for i, doc in enumerate(resultados):
    print(f"\n[ RESULTADO {i+1} ENCONTRADO ]")
    print(doc.page_content)
    print("-" * 40)