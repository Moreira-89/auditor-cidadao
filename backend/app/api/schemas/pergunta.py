from app.config.logging import logger
from pydantic import BaseModel, Field, field_validator
from validate_docbr import CNPJ

# Limite de CNPJs aceitos por requisição — protege contra um cliente adulterado
# mandando dezenas de CNPJs de uma vez só e disparando o custo de tokens do agente.
MAX_CNPJS_POR_REQUISICAO = 10


# -----------------------------------------------------------------------------
# SCHEMA DE VALIDAÇÃO DE ENTRADA (PAYLOAD)
# -----------------------------------------------------------------------------
class PerguntaRequest(BaseModel):
    """
    O que o endpoint `/conversar-com-auditor` espera receber no corpo (body) da requisição.

    O FastAPI usa o Pydantic para validar isso automaticamente: se o front-end mandar um
    JSON faltando um campo obrigatório (ou com o tipo errado), a requisição é barrada com
    erro 422 antes de o nosso código rodar — não precisamos validar manualmente.

    Papel de cada campo:
    - `pergunta`    — o texto que o usuário digitou.
    - `estado` e `municipio` — filtram a busca vetorial no Pinecone, evitando misturar
      trechos de editais de municípios diferentes.
    - `lista_cnpjs` — CNPJs já extraídos do edital, entregues ao LLM para ele saber de
      antemão quem investigar (revalidados abaixo, por segurança).
    - `thread_id`   — identifica a conversa; é o que permite ao LangGraph recuperar o
      histórico e dar continuidade entre uma pergunta e a seguinte.
    """

    pergunta: str = Field(description="Pergunta sobre o edital.")
    estado: str = Field(description="Estado do edital.")
    municipio: str = Field(description="Município do edital.")
    lista_cnpjs: list[str] = Field(description="Lista de CNPJs encontrados no edital.")
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
