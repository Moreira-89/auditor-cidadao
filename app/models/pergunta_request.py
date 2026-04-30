from pydantic import BaseModel, Field


class PerguntaRequest(BaseModel):
    pergunta: str = Field(description="Pergunta sobre o edital.")
    estado: str = Field(description="Estado do edital.")
    municipio: str = Field(description="Município do edital.")
    user_name: str = Field(description="Nome do usuário.")
    lista_cnpjs: list[str] = Field(
        description="Lista de CNPJs encontrados no edital."
    )
