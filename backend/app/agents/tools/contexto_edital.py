import asyncio

from app.config.settings import TOP_K_EDITAL
from app.storage.vetorial import get_gerenciador
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

_NADA_ENCONTRADO = (
    "Nenhum trecho relevante encontrado no edital para a combinação de estado, "
    "município e pergunta informados. Verifique se o edital foi indexado corretamente."
)


@tool
async def buscar_contexto_edital(
    pergunta: str,
    runtime: ToolRuntime,
) -> Command:
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
    # to_thread: pymongo é síncrono e bloquearia o event loop do FastAPI, travando
    # todas as outras requisições em andamento enquanto a busca não voltasse.
    secoes = await asyncio.to_thread(
        get_gerenciador().buscar_contexto,
        pergunta=pergunta,
        estado=runtime.state["estado"],
        municipio=runtime.state["municipio"],
        edital_id=runtime.state["thread_id"],
        top_k=TOP_K_EDITAL,
    )

    if not secoes:
        texto = _NADA_ENCONTRADO
        novas: set[int] = set()
    else:
        # Dedup contra a thread inteira, não só esta chamada — sem isso, a mesma
        # seção grande (RAG small-to-big, ver docs/ia/rag_dados.md) se repete a cada
        # pergunta nova que reencontra ela. Por `ordem`, não por `caminho`: um edital
        # real pode ter títulos repetidos (ex.: "DO OBJETO" em lotes diferentes) que
        # são seções fisicamente distintas — dedup por título trataria conteúdo novo
        # como já visto e travaria o agente pedindo a mesma coisa sem nunca receber.
        vistas = runtime.state.get("secoes_vistas", set())
        novas = {s["ordem"] for s in secoes} - vistas
        partes = [
            f"[{s['caminho']}]\n{s['texto']}"
            if s["ordem"] in novas
            else f"[{s['caminho']}] Já mostrado antes nesta análise — não repetido."
            for s in secoes
        ]
        texto = "\n\n".join(partes)

    return Command(
        update={
            "secoes_vistas": novas,
            "messages": [ToolMessage(content=texto, tool_call_id=runtime.tool_call_id)],
        }
    )
