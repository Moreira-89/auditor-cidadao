from pydantic import BaseModel, Field

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
    user_name: str = Field(description="Nome do usuário.")
    lista_cnpjs: list[str] = Field(
        description="Lista de CNPJs encontrados no edital."
    )
