from pydantic import BaseModel

LIMIARES = {
    "aderencia_tools": 0.70,
    "recall_anomalias": 0.80,
    "faithfulness": 0.70,
    "context_recall": 0.75,
}

class MetricasDoCaso(BaseModel):
    caso_id: str
    aderencia_tools: float
    recall_anomalias: float
    faithfulness: float | None
    context_recall: float | None

class MetricaAgregada(BaseModel):
    metrica: str
    media: float
    limiar: float
    casos_considerados: int
    aprovado: bool


class Aprovacao(BaseModel):
    metricas: list[MetricaAgregada]
    aprovado_geral: bool


def avaliar_aprovacao(casos: list[MetricasDoCaso]) -> Aprovacao:
    colunas: dict[str, list[float]] = {nome: [] for nome in LIMIARES}
    for caso in casos:
        colunas["aderencia_tools"].append(caso.aderencia_tools)
        colunas["recall_anomalias"].append(caso.recall_anomalias)
        if caso.faithfulness is not None:
            colunas["faithfulness"].append(caso.faithfulness)
        if caso.context_recall is not None:
            colunas["context_recall"].append(caso.context_recall)

    metricas: list[MetricaAgregada] = []
    for nome, limiar in LIMIARES.items():
        valores = colunas[nome]
        if not valores:
            continue  # nenhum caso exercitou essa métrica
        media = sum(valores) / len(valores)
        metricas.append(
            MetricaAgregada(
                metrica=nome,
                media=media,
                limiar=limiar,
                casos_considerados=len(valores),
                aprovado=media >= limiar,
            )
        )

    return Aprovacao(
        metricas=metricas,
        aprovado_geral=all(m.aprovado for m in metricas),
    )

def formatar_relatorio(aprovacao: Aprovacao) -> str:
    linhas = ["=" * 60, "RESULTADO DA AVALIAÇÃO".center(60), "=" * 60]
    for m in aprovacao.metricas:
        selo = "[OK]    " if m.aprovado else "[FALHOU]"
        veredito = "APROVADO" if m.aprovado else "REPROVADO"
        linhas.append(
            f"  {m.metrica:<17}: {m.media:.3f}  (mínimo {m.limiar:.2f})  {selo} {veredito}"
        )
    linhas.append("-" * 60)
    selo_geral = "[OK]" if aprovacao.aprovado_geral else "[FALHOU]"
    veredito_geral = "APROVADO" if aprovacao.aprovado_geral else "REPROVADO"
    linhas.append(f"  VEREDITO GERAL: {selo_geral} {veredito_geral}")
    linhas.append("=" * 60)
    return "\n".join(linhas)