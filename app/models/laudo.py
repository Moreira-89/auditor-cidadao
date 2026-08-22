"""
Formato (schema Pydantic) da versão ESTRUTURADA do laudo — o mesmo conteúdo do laudo,
porém em JSON em vez de texto.

Como é usado em produção: logo após o upload de um edital, gerar_relatorio_inicial() (em
app/services/ai_engine.py) gera o primeiro laudo da thread e faz uma segunda chamada ao LLM
(o "extrator") que lê esse texto e o converte para RelatorioInicial via
with_structured_output. O JSON serve para o frontend desenhar os "cards" de anomalia e de
risco. Detalhe importante: os textos em Field(description=...) NÃO são só documentação —
o próprio LLM extrator os lê para saber o que preencher em cada campo.

RespostaLaudo é o envelope mais simples (sem sugestões de pergunta) usado só pelo pipeline
de avaliação (evaluation/pipeline_avaliacao.py), que replica esse mesmo extrator turno a
turno contra o golden dataset — não é consumido em produção.
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
    """Envelope simples (laudo ou None) usado pelo extrator do pipeline de avaliação
    (evaluation/pipeline_avaliacao.py) — não é consumido em produção, ver módulo acima."""

    laudo: LaudoEstruturado | None = Field(description="Null se o texto não for um laudo de auditoria completo, ex: resposta conversacional.")


class RelatorioInicial(BaseModel):
    """
    Envelope retornado pelo extrator do relatório automático pós-indexação (Bloco C do
    roadmap — Produto e experiência do usuário) — o único laudo estruturado gerado numa
    thread, emitido uma vez logo após o upload. Sempre traz `sugestoes_perguntas`: como
    esse turno é sintético (o sistema gera o relatório sozinho, sem pergunta do usuário),
    o laudo em si é sempre esperado aqui — a lista pode vir vazia só se a extração falhar
    em reconhecer o texto como laudo.
    """

    laudo: LaudoEstruturado | None = Field(description="Null se o texto não for um laudo de auditoria completo.")
    sugestoes_perguntas: list[str] = Field(
        description="Até 3 perguntas de acompanhamento sugeridas ao usuário, específicas ao conteúdo deste edital (nunca genéricas)."
    )