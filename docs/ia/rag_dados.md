# Uso de Dados e RAG

O Auditor Cidadão trabalha com dois tipos de dado: o **edital** que o usuário envia (não
estruturado, em PDF) e as **bases oficiais** consultadas em tempo real (PNCP, Receita Federal,
CEIS/CNEP). Esta página cobre como o edital é preparado, armazenado e recuperado — o pipeline de RAG
(Retrieval-Augmented Generation).

## Por que RAG

Um edital pode ter dezenas de páginas e não existe no treinamento de nenhum modelo. Jogar o
documento inteiro no contexto a cada pergunta seria caro e diluiria a atenção do modelo. RAG resolve
isso: o texto é indexado uma vez, e a cada pergunta só os trechos mais relevantes são recuperados e
enviados ao LLM. Isso reduz alucinação (a resposta se ancora em texto real recuperado) e permite
responder sobre um documento que o modelo nunca viu.

## O pipeline de indexação

Quando o usuário faz upload de um edital (`POST /upload/`):

**Extração — Docling** ([`app/ingestion/pdf_hierarquico.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/ingestion/pdf_hierarquico.py)).
Antes de converter, uma checagem barata com `pdfplumber` (`documento_tem_texto_nativo`, em
[`app/ingestion/pdf.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/ingestion/pdf.py))
abre as primeiras páginas e vê se há texto extraível — se não houver, é PDF escaneado e o Docling
precisa acionar OCR. O `lifespan` mantém **dois `DocumentConverter` quentes** (um `do_ocr=True`,
outro `do_ocr=False`, ambos com `heading_hierarchy` para recuperar o nível dos títulos), então a
requisição só escolhe qual usar — nunca carrega modelo. A conversão em si é o passo mais lento do
upload (segundos a ~2 min por edital em CPU) e roda em `asyncio.to_thread`.

`extrair_estrutura_pdf` devolve um `EditalExtraido` com o **texto linear** (em ordem de leitura, sem
a sintaxe de Markdown, que poluiria o `extrair_cnpj` e os embeddings) e a **estrutura hierárquica**:
`secoes` (um dict por cabeçalho, com `ordem`/`nivel`/`titulo`/`caminho`/`texto_completo`) e
`filhos_brutos` (um dict por bloco de conteúdo, referenciando a seção pela `ordem`).

O timbre e o rodapé institucional que se repetem em toda página ("ESTADO DO …", "COORDENADORIA
GERAL DE …") são classificados como cabeçalho pelo layout model — chegavam a ser ~⅓ das "seções"
de um edital. `_rodapes_corridos` conta os textos-cabeçalho e descarta os que se repetem
`MIN_REPETICAO_RODAPE`+ vezes; o conteúdo real dessas páginas segue para a seção aberta no momento.

**Persistência — MongoDB Atlas** (`GerenciadorVetorial.indexar_hierarquia`,
[`app/storage/vetorial.py:15-35`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/storage/vetorial.py#L15-L35)),
tudo em `asyncio.to_thread`. Só o **filho** é vetorizado (é ele que compete na busca por
similaridade) — mas o texto completo da seção-pai (`texto_completo`, já montado por
`_extrair_estrutura` em `app/ingestion/pdf_hierarquico.py`) viaja desnormalizado em cada filho,
sem embedding próprio, só para a devolução expandir do filho pro pai (ver "O pipeline de busca"):

```python
def indexar_hierarquia(self, secoes, filhos_brutos, metadados_base):
    mapa_caminhos = {s["ordem"]: s["caminho"] for s in secoes}
    mapa_textos_secao = {s["ordem"]: s["texto_completo"] for s in secoes}

    filhos_prontos = _fatiar_filhos(filhos_brutos, mapa_caminhos, mapa_textos_secao)
    vetores = self.modelo_embedding.embed_documents(
        [f["texto"] for f in filhos_prontos]
    )
    get_database()[COLECAO_CHUNKS].insert_many(
        [{**metadados_base, "embedding": v, **f} for f, v in zip(filhos_prontos, vetores)]
    )
```

`_fatiar_filhos` ([`vetorial.py:93-128`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/storage/vetorial.py#L93-L128))
**fatia `TextItem` com mais de 200 palavras** em pedaços menores (sem overlap — ver
"Por que a fatia de 200 palavras, sem overlap" abaixo); `TableItem` nunca é fatiado, para não quebrar
a relação linha/coluna. Cada filho vira um documento na coleção `chunks_edital`:

```javascript
{
  _id: ObjectId("..."),
  edital_id: "thread-abc-123",  // == thread_id; filtro principal de toda busca
  texto: "Juiz de vaquejada, com credenciamento junto à ABVAQ...",  // só usado pra vetorizar
  embedding: [0.013, -0.224, ...],       // text-embedding-3-large, gerado na indexação
  secao_ordem: 12,                       // posição da seção na extração — chave do dedup, não o título
  secao_caminho: "Termo de Referência > Qualificação Técnica",  // rótulo, só exibição
  secao_texto_completo: "...",           // texto inteiro da seção — o que de fato volta pro agente
  tipo_bloco: "TextItem",                // TextItem | TableItem
  estado: "Maranhão (MA)",
  municipio: "São Francisco do Brejão",
  arquivo: "edital.pdf",
  origem: "upload_usuario",              // "upload_usuario" | "avaliacao"
  timestamp_indexacao: 1757000000
}
```

| Campo | Descrição |
|---|---|
| `secao_ordem` | Posição da seção na extração (`pdf_hierarquico.py`) — identidade real da seção, usada pra deduplicar (ver abaixo). Títulos podem se repetir no edital; a posição não |
| `secao_caminho` | Breadcrumb da seção onde o trecho está (`"## Habilitação > 4.1 Documentação"`) — só exibição, `[caminho]` antes do texto devolvido ao agente |
| `secao_texto_completo` | Texto inteiro da seção-pai, montado em `pdf_hierarquico.py` durante a extração — cada filho carrega uma cópia própria (denormalizado, sem `$lookup`) |
| `texto` | O pedaço do filho — só entra no embedding; não é o que volta pro agente (ver "O pipeline de busca") |
| `tipo_bloco` | `TextItem` / `TableItem` — o tipo do bloco no DoclingDocument |
| `edital_id` | Identificador do edital — é o `thread_id` do upload (a thread é 1:1 com o edital). Filtro principal da busca |
| `estado`, `municipio` | Filtro geográfico redundante da busca |
| `arquivo` | Nome do arquivo original, para rastreabilidade |
| `timestamp_indexacao` | Epoch (UTC) da indexação — usado pelo job de limpeza |
| `origem` | `"upload_usuario"` no `/upload/`, `"avaliacao"` no golden dataset. Só `"upload_usuario"` expira pelo job de limpeza |

Nome da coleção e do índice são constantes em
[`app/storage/mongo_db.py:13-14`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/storage/mongo_db.py#L13-L14)
(`COLECAO_CHUNKS`, `NOME_INDICE_VETORIAL`). Um índice **Atlas Search** do tipo `vectorSearch`
(`idx_chunks_vetor`) cobre o campo `embedding`, com `edital_id`/`estado`/`municipio` declarados
como campos de filtro — só um campo declarado assim no índice pode ser usado no `filter` do
`$vectorSearch`. Criado uma vez (via `mongosh` ou `pymongo`, não faz parte do código da aplicação):

```python
from pymongo.operations import SearchIndexModel

colecao.create_search_index(
    SearchIndexModel(
        name="idx_chunks_vetor",
        type="vectorSearch",
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": 3072,       # dimensão nativa do text-embedding-3-large
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "edital_id"},
                {"type": "filter", "path": "estado"},
                {"type": "filter", "path": "municipio"},
            ]
        },
    )
)
```

`numDimensions` tem que bater exatamente com a saída de `EMBEDDING_MODEL` — trocar de modelo (ou de
dimensão) exige recriar o índice.

## O pipeline de busca

A ferramenta `buscar_contexto_edital`
([`app/agents/tools/contexto_edital.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/tools/contexto_edital.py),
que o agente chama sozinho) chama `GerenciadorVetorial.buscar_contexto`
([`vetorial.py:37-90`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/storage/vetorial.py#L37-L90)),
que roda um `$vectorSearch` no MongoDB: converte a pergunta em vetor, casa os `top_k` filhos mais
próximos (filtrados por `edital_id` + `estado` + `municipio`), e devolve a **seção inteira** de
cada filho que bateu — não o pedaço vetorizado —, deduplicando por `secao_ordem` pra não repetir a
mesma seção se dois filhos dela aparecerem no mesmo `top_k`. É `secao_ordem`, não `secao_caminho`,
de propósito: um edital real pode ter títulos repetidos ("DO OBJETO" em lotes diferentes, por
exemplo) que são seções fisicamente distintas — dedup por título trataria conteúdo novo como já
visto:

```python
def buscar_contexto(self, pergunta, estado, municipio, edital_id, top_k=5) -> list[dict]:
    vetor = self.modelo_embedding.embed_query(pergunta)

    pipeline = [
        {
            "$vectorSearch": {
                "index": NOME_INDICE_VETORIAL,
                "path": "embedding",
                "queryVector": vetor,
                "numCandidates": top_k,
                "limit": top_k,
                "filter": {"edital_id": edital_id, "estado": estado, "municipio": municipio},
            }
        },
        {"$project": {"embedding": 0}},
    ]
    resultados = list(get_database()[COLECAO_CHUNKS].aggregate(pipeline))

    vistas: set[int] = set()
    secoes = []
    for d in resultados:
        ordem = d["secao_ordem"]
        if ordem in vistas:
            continue
        vistas.add(ordem)
        texto_secao = d.get("secao_texto_completo") or d["texto"]
        secoes.append({"ordem": ordem, "caminho": d["secao_caminho"], "texto": texto_secao})
    return secoes
```

O retorno é uma lista de dicts, não uma string pronta — quem monta o texto final pro agente é a
tool (`app/agents/tools/contexto_edital.py`), porque é lá que mora o dedup contra o **histórico da
thread inteira** (não só desta chamada): a mesma seção já mostrada numa pergunta anterior vira uma
nota curta em vez do texto repetido, também por `ordem`.

O `top_k` default é **5**, configurável via `TOP_K_EDITAL` sem mudar código. `numCandidates` é
quantos vizinhos o índice HNSW examina antes de ranquear os `limit` finais — hoje igual ao
`top_k`, o mínimo aceito (sem margem de exploração).

Se nada é encontrado, a ferramenta retorna uma mensagem explícita ("Nenhum trecho relevante
encontrado...") em vez de contexto vazio — para o agente não "adivinhar" o edital.

!!! note "Editais indexados antes desta migração"
    Vetores gravados pelo pipeline antigo (Pinecone, com seção-pai separada em outra coleção) não
    existem mais no banco atual — a migração recriou a coleção do zero. Não é preciso migração
    manual: a retenção (`MONGO_RETENCAO_DIAS`) e o próximo upload cobrem qualquer edital.

## Padrão pai-filho: descartado uma vez, reintroduzido depois

Esse padrão *small-to-big* (o filho pequeno dá o match preciso, o pai devolve o contexto ao redor)
já foi testado, removido e agora voltou — vale registrar os dois lados.

**Por que foi tirado, na 1ª vez.** Uma versão anterior vetorizava também a seção-pai e usava
`$lookup` pra trazer o texto completo dela a cada busca. Medido nos 4 casos do golden dataset **da
época** — ainda com RAGAS e um modelo principal mais caro —, o contexto por caso caiu de 27–52 mil
caracteres pra 10–15 mil ao remover o pai, sem piorar a métrica de detecção de anomalias medida
então.

**Por que voltou.** Duas coisas mudaram desde essa medição: (1) a avaliação trocou RAGAS por G-Eval
e o dataset cresceu de 4 pra 13 casos com o catálogo A-I inteiro coberto — o "sem piorar a métrica"
antigo não necessariamente se sustenta com o instrumento de medição atual; (2) rodando o dataset
novo, o padrão observado foi o agente chamar `buscar_contexto_edital` de 10 a 16 vezes no mesmo
caso — cada chamada só devolvendo um pedaço de ~200 palavras, insuficiente pra montar o quadro
completo sozinho. Trazer a seção inteira ataca isso direto: menos chamadas de tool por caso (o que
também ajuda a não estourar rate limit do provider, ver [Avaliação](avaliacao.md)) e mais fidelidade
ao desenho original de RAG hierárquico do projeto.

**O custo agora é aceito conscientemente, não ignorado:** mais caracteres por chamada de
`buscar_contexto_edital` significa mais tokens por turno. Gerenciamento de contexto (resumir,
truncar seções muito grandes, cortar o que já apareceu numa chamada anterior) fica como técnica de
V2 — por ora, a aposta é que mais contexto correto vale mais que economia de token, e a
observação empírica é o critério: acompanhar o tamanho médio de contexto por caso nas próximas
rodadas de avaliação.

## Limpeza de dados expirados

Um edital vive todo na coleção `chunks_edital` — não há mais um segundo banco/serviço para manter
sincronizado. A regra: `origem = "upload_usuario"` **e** `timestamp_indexacao` mais antigo que a
janela de retenção (`MONGO_RETENCAO_DIAS`, default 2 dias). Registros de outra origem (ex.: futura
indexação automática via PNCP) não são tocados.

[`app/jobs/limpeza_mongo.py:14-48`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/jobs/limpeza_mongo.py#L14-L48)
é um script standalone (pensado para rodar como cron no Railway) e encerra com `sys.exit(1)` em
caso de falha (credencial expirada, recurso renomeado) em vez de terminar em silêncio — assim uma
execução com erro aparece como falha no painel de cron, sem depender de checar o log. Ver
[Retenção de editais](../governanca/lgpd.md) para o racional.

!!! note "Por que a fatia de 200 palavras, sem overlap"
    A unidade indexada é o **bloco do DoclingDocument** (`TextItem`/`TableItem`), não um chunk de
    tamanho fixo — a estrutura do documento é que define a fronteira, o que já evita cortar no meio
    de uma cláusula. A fatia de 200 palavras em `_fatiar_filhos` só entra quando um `TextItem` é
    grande demais para um vetor único (parágrafo longo diluiria o embedding).

    Sem overlap: a fatia de 200 palavras só decide **o que é vetorizado e buscado** — o que volta
    pro agente é a seção inteira do filho vencedor, não a fatia em si (ver "O pipeline de busca").
    Overlap existe pra não cortar uma frase ao meio na fronteira entre dois chunks quando o chunk em
    si é o que volta pro modelo; aqui não é o caso — se uma fatia terminar no meio de uma frase, a
    busca ainda encontra a fatia mais próxima da pergunta normalmente, e o texto devolvido já é a
    seção completa, sem o corte. Overlap não mudaria isso, só duplicaria o texto vetorizado.

## O bug de produção que a avaliação revelou

!!! danger "O bug de metadados compartilhados"
    Durante o desenvolvimento do framework de avaliação (antes desta migração, ainda com Pinecone),
    uma investigação de instabilidade de métrica revelou um bug **real de produção**: o código
    usava `[metadados] * len(lista_chunks)`, que em Python cria N referências ao **mesmo**
    dicionário, não N cópias. Como a biblioteca de vetores gravava o texto de cada chunk *dentro*
    do dict de metadados, o resultado era que **todo chunk indexado — em qualquer edital, inclusive
    de usuários reais — era armazenado com o texto do último chunk do documento**. Os embeddings
    continuavam corretos (calculados antes da mutação), então os *scores* de similaridade pareciam
    plausíveis e mascaravam o defeito.

    A correção foi trocar por uma cópia independente por chunk — `indexar_hierarquia` monta cada
    documento com um spread `{**metadados_base, ...}` numa list comprehension, objeto novo por
    item, o mesmo bug evitado desde então. Este é o melhor exemplo de como o framework de avaliação
    encontrou um problema real do sistema, não só mediu números — ver [Avaliação](avaliacao.md).

## As bases oficiais (dados em tempo real)

Diferente do edital, as bases governamentais não são indexadas — são consultadas ao vivo pelas
ferramentas do agente, e o resultado é cacheado por 24h (ver [Protocolo MCP](../arquitetura/protocolo_mcp.md)):

| Fonte | Ferramenta | Dado |
|---|---|---|
| Receita Federal (via BrasilAPI) | `consultar_receita_federal` | Situação cadastral, CNAE, data de fundação, endereço |
| CEIS/CNEP (Portal da Transparência) | `consultar_sancoes_empresa` | Sanções ativas (suspensão, inidoneidade, multa) |
| PNCP | 11 ferramentas MCP | Licitações, contratos, itens, resultados, atas |
| Web aberta | `buscar_informacao_web` (Tavily) | Notícias e contexto complementar |

## Limitações conhecidas do retrieval

- **`top_k=5` não alcança trechos posicionalmente distantes.** Em alguns editais, o trecho-alvo
  pode não aparecer nem em `top_k` altos — limitação genuína de recuperação por similaridade,
  endereçável com reranking ou contextualização do texto embedado (ver próximo ponto) na V2.
- **O texto embedado de cada filho é o texto cru do bloco, sem o `secao_caminho`.** Uma linha de
  tabela isolada ("Juiz de vaquejada... ABVAQ...") não carrega, no embedding, o sinal de que é sobre
  qualificação técnica — só o texto literal do bloco compete na busca. Prefixar o texto embedado
  com o caminho da seção é candidato de melhoria, ainda não feito.
- **`TableItem` nunca é fatiado.** Uma tabela grande (dezenas de linhas) vira um único vetor, o que
  dilui o embedding e prejudica o match de uma linha específica dessa tabela.
- **Subir o `top_k` não é grátis — e agora custa mais que antes.** Cada resultado devolve a seção
  inteira do filho vencedor (ver "Padrão pai-filho" acima), não só o pedaço de 200 palavras — uma
  seção grande pode ser dezenas de milhares de caracteres. Mais contexto por chamada aumenta o custo
  de token e pode piorar a fidelidade (mais texto irrelevante para o modelo se confundir);
  gerenciamento de contexto (resumir seção grande, cortar repetição entre chamadas) é V2.
- **A conversão do Docling roda dentro do request de `/upload/`.** São segundos a ~2 min por edital
  em CPU, com o cliente segurando a conexão. Os modelos ficam pré-carregados no `lifespan`, então o
  custo é só o processamento — mas ainda é o passo mais lento do upload. Mover para um job
  assíncrono é candidato de V2.
