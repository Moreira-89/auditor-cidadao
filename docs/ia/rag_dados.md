# Uso de Dados e RAG

O Auditor Cidadão trabalha com dois tipos de dado: o **edital** que o usuário envia (não
estruturado, em PDF) e as **bases oficiais** consultadas em tempo real (PNCP, Receita Federal,
CEIS/CNEP). Esta página cobre o primeiro — como o edital é preparado, armazenado e recuperado, o
pipeline de RAG (Retrieval-Augmented Generation) — e fecha com uma tabela das bases oficiais.

## Por que RAG

Um edital pode ter dezenas de páginas, e não existe no treinamento de nenhum modelo — é um
documento que o usuário acabou de subir. Colar o documento inteiro no contexto a cada pergunta
seria caro e diluiria a atenção do modelo num monte de texto irrelevante pra pergunta atual. RAG
resolve isso: o texto é indexado uma vez, e a cada pergunta só os trechos mais relevantes são
recuperados e enviados ao LLM. Isso também reduz alucinação, porque a resposta fica ancorada em
texto real recuperado, em vez do modelo "lembrar" (errado) do que estava no documento.

**Por que RAG e não fine-tuning.** Fine-tuning ensinaria um estilo de escrita, não o conteúdo de um
documento específico — e teria que ser refeito a cada novo edital, o que não escala. RAG resolve o
problema certo aqui: busca semântica sobre um documento que muda a cada upload.

**Por que RAG *hierárquico* e não RAG tradicional.** No RAG tradicional, o documento é fatiado em
pedaços de tamanho fixo, e é esse pedaço pequeno — sem o parágrafo ao redor — que volta pro modelo.
Isso é bom pra achar o trecho certo, mas ruim porque o contexto em volta dele se perde. É a
abordagem certa quando não se sabe de antemão que tipo de dado vai entrar no banco vetorial (CSV,
imagem, PDF, texto solto, tudo misturado na mesma coleção) — mas ela paga esse preço de perder o
entorno de cada trecho.

Este projeto lida só com um tipo de dado (o edital em PDF), então dá pra fazer melhor: como a
estrutura do documento é conhecida (o PDF tem seções e parágrafos), a indexação segue essa
estrutura, não um tamanho de fatia arbitrário. É o padrão **pai-filho** (*small-to-big*): o pedaço
pequeno (filho, um parágrafo) é o que compete na busca vetorial — é ele que casa com a pergunta,
parágrafo a parágrafo —, mas quem volta pro agente é a **seção inteira** (pai) a que esse parágrafo
pertence. O modelo recebe o contexto completo em volta do match, não só o trecho isolado. Isso
custa mais tokens por chamada, mitigado por um mecanismo de dedup explicado mais abaixo.

## O pipeline de indexação

Isto acontece quando o usuário faz upload de um edital (`POST /upload/`):

**1. Extração, com o Docling.** Antes de converter o PDF inteiro, uma checagem barata
(`documento_tem_texto_nativo`) abre as primeiras páginas e vê se há texto extraível. Se não houver,
é um PDF escaneado e a conversão precisa acionar OCR. Para não pagar o custo de carregar um modelo
de OCR a cada requisição, o `lifespan` da aplicação já sobe **dois conversores prontos** no
startup — um com OCR ligado, outro desligado — e a requisição só escolhe qual dos dois usar. A
conversão em si (rodando numa thread separada, pra não travar o resto da aplicação) é o passo mais
lento do upload: de alguns segundos a ~2 minutos por edital, dependendo do tamanho.

O resultado dessa extração é um objeto com duas coisas: o **texto linear** do documento (em ordem
de leitura) e a **estrutura hierárquica** — uma árvore de seções (cada uma com título, nível e
caminho) e os blocos de conteúdo (parágrafos, tabelas) que pertencem a cada seção.

!!! info "Por que Docling e não `pdfplumber` (ou LlamaParse)"
    O projeto usava `pdfplumber` antes, um extrator de texto plano: ele lê o PDF mas não reconhece
    tabela nem estrutura de seção — tudo vira texto corrido. Isso foi identificado como a causa raiz
    de uma baixa taxa de recuperação na avaliação (o trecho relevante virava texto sem estrutura e
    ficava difícil de recuperar). Docling resolve os dois problemas de uma vez — reconhece tabela e
    extrai a hierarquia de seções, o que o RAG hierárquico desta página depende diretamente — e foi
    preferido a alternativas como o LlamaParse por não ter custo por página nem depender de um
    serviço externo: roda localmente, junto com o resto da aplicação.

**2. Persistência no MongoDB.** Só o **filho** (o parágrafo ou tabela) é vetorizado — é ele que
compete na busca por similaridade. O texto completo da seção-pai viaja junto em cada filho, sem
embedding próprio, só para a busca poder devolver a seção inteira quando esse filho vencer (ver
"O pipeline de busca" abaixo):

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

Um parágrafo muito longo (mais de 200 palavras) é fatiado em pedaços menores antes de virar
embedding — um parágrafo inteiro diluiria demais o vetor. Tabelas nunca são fatiadas, pra não
quebrar a relação entre linha e coluna. Cada filho vira um documento assim na coleção de chunks:

```javascript
{
  _id: ObjectId("..."),
  edital_id: "thread-abc-123",  // identifica o edital; filtro principal de toda busca
  texto: "Juiz de vaquejada, com credenciamento junto à ABVAQ...",  // só usado pra vetorizar
  embedding: [0.013, -0.224, ...],       // gerado na indexação
  secao_ordem: 12,                       // posição da seção — chave do dedup, não o título
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

O campo que mais chama atenção é `secao_ordem`: é a posição da seção na extração, não o título
dela, e é isso que identifica a seção de forma confiável para deduplicar buscas (mais abaixo). Um
edital real pode ter dois lotes com o título "DO OBJETO" — são seções fisicamente diferentes, e
usar o título pra identificar cada uma trataria a segunda como "já vista".

Nome do banco, da coleção e do índice são configuráveis por variável de ambiente
(`MONGODB_DATABASE`, `MONGODB_COLECAO_CHUNKS`, `MONGODB_INDICE_VETORIAL` — ver
[Variáveis de ambiente](../operacional/variaveis_ambiente.md)). O índice de busca (tipo
`vectorSearch` no Atlas) cobre o campo `embedding` e declara `edital_id`/`estado`/`municipio` como
campos de filtro — só um campo declarado assim no índice pode ser usado num filtro de busca. Ele
precisa ser criado manualmente uma vez (não é código da aplicação), com o `name` batendo com
`MONGODB_INDICE_VETORIAL`:

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
                    "numDimensions": 1536,       # dimensão nativa do text-embedding-3-small
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

`numDimensions` precisa bater exatamente com a saída do modelo de embedding — trocar de modelo (ou
de dimensão) exige recriar esse índice do zero.

## O pipeline de busca

Quando o agente decide consultar o edital, ele chama a ferramenta `buscar_contexto_edital`, que por
baixo faz o seguinte: converte a pergunta em vetor, busca os `top_k` parágrafos (filhos) mais
próximos no índice — já filtrando por `edital_id`, `estado` e `municipio`, pra nunca misturar
trechos de dois editais diferentes — e devolve a **seção inteira** de cada filho que bateu, não só
o parágrafo vetorizado:

```python
def buscar_contexto(self, pergunta, estado, municipio, edital_id, top_k=3) -> list[dict]:
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

Repare no `if ordem in vistas: continue` — é o dedup por seção que mencionamos acima: se dois
parágrafos da mesma seção bateram na busca, a seção só é devolvida uma vez.

Isso é só a primeira camada de dedup. A segunda mora na ferramenta que chama essa função, e olha
pro histórico da conversa inteira, não só desta busca: se a mesma seção já apareceu numa pergunta
anterior da thread, ela não é repetida de novo — o agente recebe uma nota curta avisando que aquele
conteúdo já está no contexto dele, em vez do texto inteiro de novo. É essa segunda camada que
controla o custo de token do padrão pai-filho: sem ela, cada pergunta nova sobre o mesmo edital
pagaria de novo pelo texto de seções que o modelo já tinha lido antes na mesma conversa.

O `top_k` real usado em produção é **3** (variável `TOP_K_EDITAL`, configurável sem mudar código —
o `top_k=3` na assinatura acima já é esse valor). Se a busca não encontra nada, a ferramenta devolve
uma mensagem explícita dizendo isso, em vez de contexto vazio — assim o agente sabe que precisa
tratar como "não verificado", e não fica tentando "adivinhar" o conteúdo do edital.

!!! note "Editais indexados antes desta migração"
    Vetores gravados pelo pipeline antigo (Pinecone, com seção-pai separada em outra coleção) não
    existem mais no banco atual — a migração recriou a coleção do zero. Não é preciso migração
    manual: a retenção automática e o próximo upload cobrem qualquer edital.

## Padrão pai-filho: descartado uma vez, reintroduzido depois

Vale registrar a história completa deste padrão, porque ele já foi testado, removido e voltou —
raramente uma decisão de design é tão direta assim.

**Por que foi tirado, na primeira vez.** Numa versão anterior do projeto, a seção-pai também era
vetorizada e buscada no banco a cada consulta. Medido contra o dataset de teste da época (bem menor
que o atual), remover o pai e devolver só o pedaço pequeno cortou o tamanho médio do contexto por
caso à metade, sem piorar a métrica de detecção de anomalia medida então.

**Por que voltou.** O instrumento de medição mudou (métricas mais rigorosas, dataset maior cobrindo
todo o catálogo de anomalias) — o "sem piorar a métrica" antigo não necessariamente se sustentava
com a régua nova. Trazer a seção inteira ataca o problema de fragmentação direto — menos chamadas de
ferramenta por caso, o que também ajuda a não estourar o rate limit de alguns providers.

O custo — mais tokens por chamada — é aceito conscientemente, não ignorado: a aposta é que mais
contexto correto vale mais que a economia de token, com o dedup contra o histórico da thread como
principal mitigação hoje. Um gerenciamento de contexto mais sofisticado (resumir seções muito
grandes, por exemplo) fica pra V2.

## Limpeza de dados expirados

Um edital vive todo na mesma coleção — não há um segundo banco pra manter sincronizado. A regra de
limpeza: um chunk é apagado quando `origem` é `"upload_usuario"` **e** sua data de indexação é mais
antiga que a janela de retenção configurada (`MONGO_RETENCAO_DIAS`, 2 dias por default). Registros
de outra origem, como uma futura indexação automática via PNCP, não são tocados por essa regra.

O job de limpeza roda como um script standalone, pensado pra ser disparado por um cron — e termina
com erro explícito em caso de falha (credencial expirada, por exemplo), em vez de falhar em
silêncio, pra aparecer como falha visível no painel de cron. Ver
[Retenção de editais](../governanca/lgpd.md) para o racional de privacidade por trás do prazo curto.

## O bug de produção que a avaliação revelou

!!! danger "O bug de metadados compartilhados"
    Durante o desenvolvimento do framework de avaliação (numa versão antiga do projeto, ainda com
    outro banco vetorial), uma investigação de instabilidade de métrica revelou um bug **real de
    produção**: o código multiplicava um dicionário de metadados por `N` para gerar `N` cópias —
    mas em Python isso cria `N` referências ao **mesmo** dicionário, não `N` cópias independentes.
    Como o texto de cada chunk era gravado *dentro* desse dicionário compartilhado, o resultado era
    que todo chunk indexado — em qualquer edital, inclusive de usuários reais — acabava armazenado
    com o texto do **último** chunk do documento. Os embeddings continuavam corretos (calculados
    antes da mutação), então os scores de similaridade pareciam plausíveis e mascaravam o defeito.

    A correção foi trocar por uma cópia independente por chunk, um dicionário novo a cada item, em
    vez de reaproveitar a mesma referência. Este é o melhor exemplo de como o framework de
    avaliação encontrou um problema real do sistema, não só mediu números — ver
    [Avaliação](avaliacao.md).

## As bases oficiais (dados em tempo real)

Diferente do edital, as bases governamentais não são indexadas — são consultadas ao vivo pelas
ferramentas do agente, e o resultado fica em cache por 24h (ver
[Protocolo MCP](../arquitetura/protocolo_mcp.md)):

| Fonte | Ferramenta | Dado |
|---|---|---|
| Receita Federal (via BrasilAPI) | `consultar_receita_federal` | Situação cadastral, CNAE, data de fundação, endereço |
| CEIS/CNEP (Portal da Transparência) | `consultar_sancoes_empresa` | Sanções ativas (suspensão, inidoneidade, multa) |
| PNCP | 11 ferramentas MCP | Licitações, contratos, itens, resultados, atas |
| Web aberta | `buscar_informacao_web` (Tavily) | Notícias e contexto complementar |

## Limitações conhecidas do retrieval

- **`top_k=3` não alcança trechos posicionalmente distantes.** Em alguns editais, o trecho-alvo
  pode não aparecer mesmo com `top_k` mais alto — limitação genuína de busca por similaridade,
  endereçável com reranking ou com um texto de embedding mais rico (ver próximo ponto) na V2.
- **O texto usado no embedding é cru, sem o caminho da seção.** Uma linha de tabela isolada como
  "Juiz de vaquejada... ABVAQ..." não carrega, no vetor, o sinal de que é sobre qualificação
  técnica — só o texto literal do bloco compete na busca. Prefixar o texto vetorizado com o caminho
  da seção é candidato de melhoria, ainda não feito.
- **Tabelas nunca são fatiadas.** Uma tabela grande (dezenas de linhas) vira um único vetor, o que
  dilui o embedding e prejudica o match de uma linha específica dessa tabela.
- **Subir o `top_k` não é de graça, e hoje custa mais que antes.** Como cada resultado devolve a
  seção inteira (não só o parágrafo), uma seção grande pode ser dezenas de milhares de caracteres.
  Mais contexto por chamada aumenta o custo de token e pode piorar a fidelidade da resposta (mais
  texto irrelevante pro modelo se confundir); gerenciamento de contexto mais sofisticado é V2.
- **A conversão do Docling roda dentro do próprio request de `/upload/`.** São segundos a ~2 min
  por edital, com o cliente segurando a conexão aberta o tempo todo. Os modelos já ficam
  pré-carregados, então o custo é só o processamento em si — mas ainda é o passo mais lento do
  upload. Mover isso para um job assíncrono é candidato de V2.
