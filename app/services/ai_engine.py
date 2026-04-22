from dotenv import load_dotenv
# Atualizamos a importação para remover o Warning!
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

print("Carregando o cérebro vetorial...")
modelo_embedding = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
pasta_banco = "./banco_chroma"
banco_vetorial = Chroma(persist_directory=pasta_banco, embedding_function=modelo_embedding)

# ==========================================
# O SEGREDO DO ENGENHEIRO SÊNIOR: MMR
# ==========================================
# fetch_k=50: Olha os 50 mais parecidos no banco
# k=15: Escolhe os 15 melhores e MAIS DIVERSOS dentre os 50
retriever = banco_vetorial.as_retriever(
    search_type="mmr", 
    search_kwargs={"k": 15, "fetch_k": 50}
)

# Seu novo modelo! Excelente escolha.
print("Conectando ao Llama 3.3...")
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1) 

template = """Você é um Auditor Cidadão especializado em analisar contratos públicos.
Responda à pergunta do usuário usando APENAS os trechos de contexto fornecidos abaixo.
Se a resposta não estiver no contexto, diga "Não encontrei essa informação no documento fornecido", não invente dados.

Contexto extraído do PDF:
{context}

Pergunta: {question}

Resposta elaborada:"""

prompt = PromptTemplate.from_template(template)

cadeia_rag = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

print("\n--- AUDITOR CIDADÃO PRONTO ---")
pergunta = "Qual é o valor total da contratação ou da licitação?"
print(f"\nSua Pergunta: '{pergunta}'")
print("\nPensando...")

resposta_final = cadeia_rag.invoke(pergunta)

print(f"\nResposta do Agente:\n{resposta_final}")
print("-" * 40)