import asyncio

from app.config.settings import PINECONE_NAMESPACE, TOP_K_EDITAL
from app.storage.vetorial import get_gerenciador
from langchain.tools import ToolRuntime, tool


@tool
async def buscar_contexto_edital(
    pergunta: str,
    runtime: ToolRuntime,
) -> str:
    """
    Busca trechos relevantes do edital ativo no banco vetorial com base em uma pergunta.

    Use esta ferramenta sempre que precisar encontrar regras, prazos, exigências, penalidades,
    critérios de julgamento ou qualquer cláusula específica do edital em análise. A busca é
    semântica — não é necessário usar as palavras exatas do edital, basta descrever o que procura.

    Args:
        pergunta: A dúvida ou termo específico a ser pesquisado no texto do edital.

    Returns:
        Trechos do edital mais relevantes para a pergunta, prontos para análise.
        Se nenhum trecho for encontrado, retorna uma mensagem informando que o edital pode não estar indexado.
    """
    # to_thread: a busca no Pinecone é síncrona e bloquearia o event loop do FastAPI,
    # travando todas as outras requisições em andamento enquanto ela não voltasse.
    return await asyncio.to_thread(
        get_gerenciador().buscar_contexto,
        pergunta=pergunta,
        estado=runtime.state["estado"],
        municipio=runtime.state["municipio"],
        namespace=PINECONE_NAMESPACE,
        top_k=TOP_K_EDITAL,
    )
