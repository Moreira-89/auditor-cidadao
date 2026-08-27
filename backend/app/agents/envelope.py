from datetime import UTC, datetime

from app.agents.prompt import PROMPT_DINAMICO
from langchain_core.messages import HumanMessage


def escape_xml(texto: str) -> str:
    """Escapa < e > para o usuário não quebrar as tags XML do prompt (ex.: `</METADADOS>`)."""
    return texto.replace("<", "&lt;").replace(">", "&gt;")


def montar_primeiro_turno(
    pergunta_usuario: str, lista_cnpj: list[str], estado: str, municipio: str
) -> HumanMessage:
    """
    Monta o envelope PROMPT_DINAMICO usado como primeiro HumanMessage de uma thread nova.

    Serve aos dois fluxos que abrem uma thread: a primeira pergunta de uma conversa
    (conversa.py) e o relatório automático pós-upload (relatorio.py), que também é,
    por definição, o primeiro turno da thread.
    """
    cnpjs_formatados = escape_xml(
        ", ".join(lista_cnpj) if lista_cnpj else "Nenhum CNPJ encontrado no documento."
    )
    data_hoje = datetime.now(UTC).date().strftime("%Y%m%d")
    return HumanMessage(
        content=PROMPT_DINAMICO.format(
            pergunta_usuario=pergunta_usuario,
            cnpjs_formatados=cnpjs_formatados,
            municipio=municipio,
            estado=estado,
            data_hoje=data_hoje,
        )
    )
