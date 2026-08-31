from typing import Literal

from pydantic import BaseModel, Field

NivelRisco = Literal["BAIXO", "MÉDIO", "ALTO", "CRÍTICO"]

# Códigos do catálogo de anomalias definido no system prompt (app/agents/prompt.py):
# A. Sobrepreço | B. Direcionamento | C. Fracionamento irregular | D. Cartel/conluio
# E. Empresa recém-criada | F. Prazo insuficiente | G. Reincidência suspeita
# H. Sanção com possível impacto na participação | I. Compatibilidade cadastral da atividade
CodigoAnomalia = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I"]

# Estado da verificação de cada categoria (ver "CATÁLOGO DE ANOMALIAS" no system prompt).
# Só CONFIRMADO e INDÍCIO entram na lista `anomalias` do laudo — os demais estados
# descrevem categorias sem achado e não são anomalias.
EstadoAnomalia = Literal["CONFIRMADO", "INDÍCIO"]


class Anomalia(BaseModel):
    """Um achado individual do laudo (categoria CONFIRMADA ou com INDÍCIO), com evidência e risco."""

    codigo: CodigoAnomalia = Field(description="Código da anomalia.")
    estado: EstadoAnomalia = Field(
        description="CONFIRMADO (fatos essenciais verificados e critério atendido) ou "
        "INDÍCIO (sinais concretos, sem confirmação)."
    )
    descricao: str = Field(description="Descrição da anomalia.")
    evidencias: list[str] = Field(
        description="Lista de evidências relacionadas à anomalia."
    )
    nivel_risco: NivelRisco = Field(description="Nível de risco da anomalia.")


class LaudoEstruturado(BaseModel):
    """Laudo de auditoria completo: anomalias encontradas, risco consolidado e recomendações."""

    cnpjs_analisados: list[str] = Field(
        description="Lista de CNPJs analisados no laudo."
    )
    anomalias: list[Anomalia] = Field(
        description="Lista de anomalias identificadas no laudo."
    )
    nivel_risco_geral: NivelRisco = Field(description="Nível de risco geral do laudo.")
    resumo_executivo: str = Field(
        description="Resumo executivo do laudo, destacando os principais pontos e conclusões."
    )
    recomendacoes: list[str] = Field(
        description="Lista de recomendações para mitigação dos riscos identificados."
    )


class RelatorioInicial(BaseModel):
    """
    Envelope retornado pelo extrator do relatório automático pós-indexação (Bloco C do
    roadmap — Produto e experiência do usuário) — o único laudo estruturado gerado numa
    thread, emitido uma vez logo após o upload. Sempre traz `sugestoes_perguntas`: como
    esse turno é sintético (o sistema gera o relatório sozinho, sem pergunta do usuário),
    o laudo em si é sempre esperado aqui — a lista pode vir vazia só se a extração falhar
    em reconhecer o texto como laudo.
    """

    laudo: LaudoEstruturado | None = Field(
        description="Null se o texto não for um laudo de auditoria completo."
    )
    sugestoes_perguntas: list[str] = Field(
        description="Até 3 perguntas de acompanhamento sugeridas ao usuário, específicas ao conteúdo deste edital (nunca genéricas)."
    )
