"""
Schema de saída estruturada usado pelo modelo extrator (app/services/ai_engine.py,
via with_structured_output). O Markdown do laudo já foi entregue ao usuário pelo
streaming — este schema só formaliza a mesma informação em JSON para renderização
em cards no frontend. As descrições dos campos Field() são lidas pelo próprio LLM
extrator para saber o que preencher em cada um, não são só documentação.
"""

from typing import Literal
from pydantic import BaseModel, Field

NivelRisco = Literal["BAIXO", "MÉDIO", "ALTO", "CRÍTICO"]

# Códigos do catálogo de anomalias definido no system prompt (app/core/prompt.py):
# A. Sobrepreço | B. Direcionamento | C. Fracionamento irregular | D. Cartel/conluio
# E. Empresa recém-criada | F. Prazo insuficiente | G. Reincidência suspeita
# H. Sanção vigente | I. Incompatibilidade de atividade
CodigoAnomalia = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I"]


class Anomalia(BaseModel):
    """Uma anomalia individual detectada no laudo, com evidência e nível de risco."""

    codigo: CodigoAnomalia = Field(description="Código da anomalia.")
    descricao: str = Field(description="Descrição da anomalia.")
    evidencias: list[str] = Field(description="Lista de evidências relacionadas à anomalia.")
    nivel_risco: NivelRisco = Field(description="Nível de risco da anomalia.")


class LaudoEstruturado(BaseModel):
    """Laudo de auditoria completo: anomalias encontradas, risco consolidado e recomendações."""

    cnpjs_analisados: list[str] = Field(description="Lista de CNPJs analisados no laudo.")
    anomalias: list[Anomalia] = Field(description="Lista de anomalias identificadas no laudo.")
    nivel_risco_geral: NivelRisco = Field(description="Nível de risco geral do laudo.")
    resumo_executivo: str = Field(description="Resumo executivo do laudo, destacando os principais pontos e conclusões.")
    recomendacoes: list[str] = Field(description="Lista de recomendações para mitigação dos riscos identificados.")


class RespostaLaudo(BaseModel):
    """Envelope retornado pelo extrator — laudo None indica resposta conversacional, não um laudo."""

    laudo: LaudoEstruturado | None = Field(description="Null se o texto não for um laudo de auditoria completo, ex: resposta conversacional.")