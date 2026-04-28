import logging

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

logger = logging.getLogger(__name__)
logger.info("Inicializando o motor de IA e carregando o banco vetorial ChromaDB...")

modelo_embedding = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
pasta_banco = "./banco_chroma"
banco_vetorial = Chroma(
    persist_directory=pasta_banco, embedding_function=modelo_embedding
)

# Configura o retriever utilizando MMR (Maximal Marginal Relevance)
# para garantir diversidade e precisão nos trechos retornados
retriever = banco_vetorial.as_retriever(
    search_type="mmr", search_kwargs={"k": 15, "fetch_k": 50}
)

logger.info("Conectando ao modelo LLaMA via Groq...")
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
    Processa a pergunta do usuário através da cadeia RAG (Retrieval-Augmented Generation).

    Args:
        pergunta_usuario (str): A pergunta formulada pelo usuário final.

    Returns:
        str: A resposta gerada pelo modelo LLaMA fundamentada no contexto vetorial.
    """
    logger.info(f"Processando nova pergunta: {pergunta_usuario}")
    try:
        resposta = cadeia_rag.invoke(pergunta_usuario)
        logger.info("Resposta gerada com sucesso pela IA.")
        return resposta
    except Exception as e:
        logger.error(f"Erro durante a execução do RAG: {e}", exc_info=True)
        return f"Erro interno ao consultar o modelo: {str(e)}"