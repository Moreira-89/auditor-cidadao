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
    critérios de julgamento ou qualquer cláusula específica do edital em análise.

    A busca é por similaridade de texto: recupera os trechos cujo conteúdo mais se parece
    com o texto da consulta. Descreva o trecho procurado com as palavras que o próprio edital
    usaria (títulos de cláusula, jargão do domínio), não como pergunta. Ex.: em vez de
    "qual o prazo de abertura?", use "data e hora de abertura das propostas, prazo para
    apresentação, aviso de retificação".

    Args:
        pergunta: Frase curta descrevendo o trecho procurado, rica em termos que apareceriam
            no próprio edital.

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
