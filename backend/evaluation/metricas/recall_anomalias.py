from pydantic import BaseModel


class ResultadoRecall(BaseModel):
    score: float
    precisao: float
    recall: float
    esperadas: list[str]
    detectadas: list[str]
    faltantes: list[str]
    extras: list[str]

def avaliar_recall_anomalias(
    anomalias_esperadas: list[str],
    laudo: dict | None,
) -> ResultadoRecall:
    detectadas = sorted(
        {a["codigo"] for a in (laudo or {}).get("anomalias", []) if a.get("codigo")}
    )
    esperadas = sorted(set(anomalias_esperadas))
    faltantes = [c for c in esperadas if c not in detectadas]
    extras = [c for c in detectadas if c not in esperadas]

    if not esperadas:
        # Caso-controle: só precisão. Qualquer anomalia apontada é falso positivo.
        acertou = not detectadas
        return ResultadoRecall(
            score=1.0 if acertou else 0.0,
            precisao=1.0 if acertou else 0.0,
            recall=1.0,
            esperadas=[],
            detectadas=detectadas,
            faltantes=[],
            extras=detectadas,
        )

    verdadeiros = len(esperadas) - len(faltantes)
    recall = verdadeiros / len(esperadas)
    precisao = verdadeiros / len(detectadas) if detectadas else 0.0
    soma = precisao + recall
    f1 = 2 * precisao * recall / soma if soma else 0.0

    return ResultadoRecall(
        score=f1,
        precisao=precisao,
        recall=recall,
        esperadas=esperadas,
        detectadas=detectadas,
        faltantes=faltantes,
        extras=extras,
    )