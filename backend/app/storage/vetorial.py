from app.config.logging import logger
from app.config.settings import EMBEDDING_MODEL
from app.storage.mongo_db import COLECAO_CHUNKS, NOME_INDICE_VETORIAL, get_database
from langchain_openai import OpenAIEmbeddings


class GerenciadorVetorial:
    """RAG do edital: indexa e busca os filhos (parágrafos/tabelas) no MongoDB,
    cada um rotulado com o caminho da sua seção."""

    def __init__(self):
        self.modelo_embedding = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    def indexar_hierarquia(
        self,
        secoes: list[dict],  # ordem/caminho (EditalExtraido) — só para rotular o filho
        filhos_brutos: list[dict],  # secao_ordem/tipo/texto (EditalExtraido)
        metadados_base: dict,  # edital_id, estado, municipio, arquivo, origem, timestamp_indexacao
    ) -> None:
        """A seção não vira documento nem é vetorizada — só o filho é indexado,
        levando o caminho da seção como rótulo."""
        mapa_caminhos = {s["ordem"]: s["caminho"] for s in secoes}

        filhos_prontos = _fatiar_filhos(filhos_brutos, mapa_caminhos)
        if not filhos_prontos:
            return

        vetores = self.modelo_embedding.embed_documents(
            [f["texto"] for f in filhos_prontos]
        )
        get_database()[COLECAO_CHUNKS].insert_many(
            [{**metadados_base, "embedding": v, **f} for f, v in zip(filhos_prontos, vetores)]
        )

    def buscar_contexto(
        self,
        pergunta: str,
        estado: str,
        municipio: str,
        edital_id: str,
        top_k: int = 5,
    ) -> str:
        """Busca os `top_k` trechos mais parecidos com a pergunta."""
        vetor = self.modelo_embedding.embed_query(pergunta)

        pipeline = [
            {
                "$vectorSearch": {
                    "index": NOME_INDICE_VETORIAL,
                    "path": "embedding",
                    "queryVector": vetor,
                    "numCandidates": top_k,
                    "limit": top_k,
                    "filter": {
                        "edital_id": edital_id,
                        "estado": estado,
                        "municipio": municipio,
                    },
                }
            },
            {"$project": {"embedding": 0}},
        ]

        resultados = list(get_database()[COLECAO_CHUNKS].aggregate(pipeline))
        logger.info(
            "Busca semântica | pergunta=%s | edital_id=%s | resultados=%d",
            pergunta[:80],
            edital_id,
            len(resultados),
        )

        if not resultados:
            return (
                "Nenhum trecho relevante encontrado no edital para a combinação de "
                "estado, município e pergunta informados. Verifique se o edital foi "
                "indexado corretamente."
            )

        return "\n\n".join(f"[{d['secao_caminho']}]\n{d['texto']}" for d in resultados)


def _fatiar_filhos(filhos_brutos: list[dict], mapa_caminhos: dict) -> list[dict]:
    """Rotula cada filho com o caminho da seção e fatia TextItem longo em pedaços
    de 200 palavras (TableItem nunca é fatiado — quebraria a relação linha/coluna)."""
    max_palavras = 200
    prontos: list[dict] = []

    for filho in filhos_brutos:
        caminho = mapa_caminhos.get(filho["secao_ordem"])
        if caminho is None:
            continue  # conteúdo antes do 1º cabeçalho — órfão, não indexa

        if filho["tipo"] == "TableItem":
            pedacos = [filho["texto"]]
        else:
            palavras = filho["texto"].split()
            pedacos = [
                " ".join(palavras[i : i + max_palavras])
                for i in range(0, len(palavras), max_palavras)
            ] or [filho["texto"]]

        for pedaco in pedacos:
            prontos.append(
                {"texto": pedaco, "secao_caminho": caminho, "tipo_bloco": filho["tipo"]}
            )

    return prontos


# Singleton preguiçoso: a conexão/modelo só é aberto na primeira chamada.
_gerenciador: GerenciadorVetorial | None = None


def get_gerenciador() -> GerenciadorVetorial:
    """Devolve o GerenciadorVetorial compartilhado, criando-o na primeira chamada."""
    global _gerenciador
    if _gerenciador is None:
        _gerenciador = GerenciadorVetorial()
    return _gerenciador
