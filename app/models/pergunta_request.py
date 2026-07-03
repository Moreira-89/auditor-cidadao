from pydantic import BaseModel, Field, field_validator
from validate_docbr import CNPJ

from app.core.logging_config import logger

# Limite de CNPJs aceitos por requisição — protege contra um cliente adulterado
# mandando dezenas de CNPJs de uma vez só e disparando o custo de tokens do agente.
MAX_CNPJS_POR_REQUISICAO = 10


# -----------------------------------------------------------------------------
# SCHEMA DE VALIDAÇÃO DE ENTRADA (PAYLOAD)
# -----------------------------------------------------------------------------
class PerguntaRequest(BaseModel):
    """
    Modelo de dados que o endpoint `/conversar-com-auditor` espera receber (Body da Requisição HTTP).

    COMO FUNCIONA:
    O FastAPI utiliza a biblioteca Pydantic nativamente para validar tudo que chega.
    Se o front-end mandar um JSON faltando algum desses campos (ou com o tipo de
    dado errado), o próprio FastAPI bloqueia a requisição e devolve um Erro 422
    (Unprocessable Entity) antes mesmo do seu código executar, garantindo segurança.

    Os campos `estado` e `municipio` são essenciais para servirem de filtro na
    busca vetorial no Pinecone, evitando mistura de editais diferentes.
    A `lista_cnpjs` é injetada para que o LLM saiba de antemão quem pesquisar.
    """
    pergunta: str = Field(description="Pergunta sobre o edital.")
    estado: str = Field(description="Estado do edital.")
    municipio: str = Field(description="Município do edital.")
    lista_cnpjs: list[str] = Field(
        description="Lista de CNPJs encontrados no edital."
    )
    thread_id: str | None = Field(
        default=None, description="Identificador único da thread/sessão de conversa."
    )

    @field_validator("lista_cnpjs")
    @classmethod
    def validar_lista_cnpjs(cls, cnpjs: list[str]) -> list[str]:
        """Descarta CNPJs matematicamente inválidos e corta a lista em
        MAX_CNPJS_POR_REQUISICAO, logando a tentativa quando o cliente manda mais que isso."""
        if len(cnpjs) > MAX_CNPJS_POR_REQUISICAO:
            logger.warning(
                "lista_cnpjs excedeu o limite | recebidos=%d | limite=%d",
                len(cnpjs),
                MAX_CNPJS_POR_REQUISICAO,
            )
            cnpjs = cnpjs[:MAX_CNPJS_POR_REQUISICAO]

        validador = CNPJ()
        return [c for c in cnpjs if validador.validate(c)]
