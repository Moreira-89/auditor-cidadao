from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# SCHEMA DE FERRAMENTA (TOOL) PARA A IA
# -----------------------------------------------------------------------------
class ConsultaCNPJ(BaseModel):
    """
    Modelo Pydantic que serve como um "contrato" para o modelo de Inteligência Artificial.

    COMO FUNCIONA:
    Quando a IA decide que precisa chamar a ferramenta externa para buscar dados de
    um CNPJ na Receita Federal, ela precisa saber exatamente *quais* parâmetros 
    ela deve nos passar. 
    A propriedade `model_json_schema()` desta classe é lida pela API da Groq (LLM),
    e o `Field(description=...)` ensina a IA como extrair e formatar esse parâmetro.
    
    Isso força a IA a entregar apenas os números do CNPJ (14 dígitos), limpando 
    pontos e traços que possam atrapalhar a chamada da BrasilAPI na sequência.
    """
    cnpj: str = Field(
        description="localize no texto do edital o identificador numérico da empresa, que pode estar com pontos e traços (ex.: 12.345.678/0001-90) ou apenas os números (ex.: 12345678000190). Você deve extrair esse dado e me entregar estritamente como uma string de 14 dígitos, sem nenhuma máscara ou pontuação."
    )
