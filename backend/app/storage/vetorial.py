from app.config.logging import logger
from app.config.settings import EMBEDDING_MODEL
from app.storage.mongo_db import COLECAO_CHUNKS, NOME_INDICE_VETORIAL, get_database
from langchain_openai import OpenAIEmbeddings


class GerenciadorVetorial:
    """RAG hierárquico do edital: o filho (parágrafo/tabela) é o que é vetorizado e
    buscado; o texto completo da seção-pai viaja junto (sem embedding próprio) e é
    o que de fato volta pro agente quando o filho vence a busca — ver docs/ia/rag_dados.md."""

    def __init__(self):
        self.modelo_embedding = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    def indexar_hierarquia(
        self,
        secoes: list[dict],  # ordem/caminho/texto_completo (EditalExtraido)
        filhos_brutos: list[dict],  # secao_ordem/tipo/texto (EditalExtraido)
        metadados_base: dict,  # edital_id, estado, municipio, arquivo, origem, timestamp_indexacao
    ) -> None:
        """A seção não é vetorizada (nunca é buscada por si só) — mas seu texto
        completo vai junto de cada filho, pra devolução expandir pro pai na busca."""
        mapa_caminhos = {s["ordem"]: s["caminho"] for s in secoes}
        mapa_textos_secao = {s["ordem"]: s["texto_completo"] for s in secoes}

        filhos_prontos = _fatiar_filhos(filhos_brutos, mapa_caminhos, mapa_textos_secao)
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
    ) -> list[dict]:
        """Busca os `top_k` trechos mais parecidos com a pergunta e devolve a seção
        inteira de cada filho vencedor — sem repetir a mesma seção 2x nesta chamada
        (dedup contra o histórico da thread é responsabilidade de quem chama, ver
        app/agents/tools/contexto_edital.py)."""
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

        # Dedup por secao_ordem, não por caminho: um edital real pode ter títulos
        # repetidos ("DO OBJETO" em lotes diferentes, por exemplo) que são seções
        # fisicamente distintas — dedup por título trataria conteúdo novo como já visto.
        vistas: set[int] = set()
        secoes: list[dict] = []
        for d in resultados:
            ordem = d["secao_ordem"]
            if ordem in vistas:
                continue
            vistas.add(ordem)
            texto_secao = d.get("secao_texto_completo") or d["texto"]
            secoes.append({"ordem": ordem, "caminho": d["secao_caminho"], "texto": texto_secao})

        return secoes


def _fatiar_filhos(
    filhos_brutos: list[dict], mapa_caminhos: dict, mapa_textos_secao: dict
) -> list[dict]:
    """Rotula cada filho com o caminho da seção (+ o texto completo dela, pra
    devolução expandir do filho pro pai) e fatia TextItem longo em pedaços de 200
    palavras (TableItem nunca é fatiado — quebraria a relação linha/coluna)."""
    max_palavras = 200
    prontos: list[dict] = []

    for filho in filhos_brutos:
        caminho = mapa_caminhos.get(filho["secao_ordem"])
        if caminho is None:
            continue  # conteúdo antes do 1º cabeçalho — órfão, não indexa
        texto_secao = mapa_textos_secao.get(filho["secao_ordem"], "")

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
                {
                    "texto": pedaco,
                    "secao_ordem": filho["secao_ordem"],
                    "secao_caminho": caminho,
                    "secao_texto_completo": texto_secao,
                    "tipo_bloco": filho["tipo"],
                }
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
