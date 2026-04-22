from dotenv import load_dotenv
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

template = """Você é o "Auditor Cidadão", um assistente de inteligência artificial especializado em análise de licitações, contratos públicos e editais.
Sua missão é fornecer respostas precisas, imparciais e diretas com base estritamente nos documentos oficiais fornecidos.

=== REGRAS DE OURO (GUARDRAILS) ===
1. FIDELIDADE ABSOLUTA: Responda APENAS usando as informações contidas na seção de "Contexto". Nunca confie em seus dados de treinamento prévios.
2. ZERO ALUCINAÇÃO: Se a informação solicitada não estiver no contexto, você deve responder EXATAMENTE: "🔍 Não encontrei essa informação nos documentos analisados."
3. OBJETIVIDADE: Seja direto. Não invente explicações que não estejam no texto.

=== DIRETRIZES DE FORMATAÇÃO ===
- Destaque valores financeiros (ex: R$), datas, CNPJs e nomes de empresas em **negrito**.
- Use listas (bullet points) sempre que a resposta contiver múltiplos itens ou regras.
- Mantenha um tom profissional, investigativo e claro.

=== CONTEXTO EXTRAÍDO DO(S) DOCUMENTO(S) ===
{context}

=== PERGUNTA DO USUÁRIO ===
{question}

RESPOSTA DO AUDITOR CIDADÃO:"""

prompt = PromptTemplate.from_template(template)

cadeia_rag = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

def consultar_auditor(pergunta_usuario: str) -> str:
    """
    Função que recebe a pergunta da FastAPI, consulta o RAG e retorna a string de resposta.
    """
    try:
        # invoke roda o modelo e traz a resposta baseada no banco Chroma
        resposta = cadeia_rag.invoke(pergunta_usuario)
        return resposta
    except Exception as e:
        return f"Erro interno ao consultar o modelo: {str(e)}"