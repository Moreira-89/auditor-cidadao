from pydantic import BaseModel, Field

class ConsultaCNPJ(BaseModel):
    cnpj: str = Field(description="Localize no texto do edital o identificador numérico da empresa, que pode estar com pontos e traços (ex.: 12.345.678/0001-90) ou apenas os números (ex.: 12345678000190). Você deve extrair esse dado e me entregar estritamente como uma string de 14 dígitos, sem nenhuma máscara ou pontuação.")