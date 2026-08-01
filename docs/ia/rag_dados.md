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

Quando o usuário faz upload de um edital (`POST /upload/`), o `GerenciadorVetorial`
(`app/services/gerenciadorvetorial.py`) executa:

1. **Chunking** — `RecursiveCharacterTextSplitter` divide o texto em pedaços de até **2000
   caracteres com 200 de sobreposição**, tentando separadores hierárquicos (parágrafo → linha →
   frase → palavra) para não cortar no meio de uma cláusula.
2. **Embeddings** — cada chunk é convertido em vetor pelo `text-embedding-3-small` da OpenAI.
3. **Upsert no Pinecone** — os vetores vão para o índice configurado em `PINECONE_INDEX_NAME`
   (`auditor-cidadao` por padrão), com os seguintes campos replicados como metadado **em cada
   chunk**:

   | Metadado | Descrição |
   |---|---|
   | `estado`, `municipio` | Usados para filtrar a busca por edital (ver abaixo) |
   | `arquivo` | Nome do arquivo original, para rastreabilidade |
   | `timestamp_indexacao` | Epoch (UTC) do momento da indexação — usado pelo job de limpeza para decidir o que expirou |
   | `origem` | `"upload_usuario"` para editais enviados via `/upload/`. Distingue de outras origens futuras (ex.: `"agente_busca"`, indexação automática via PNCP — ver [Próximos Passos](../governanca/limitacoes.md)), que o job de limpeza deve tratar com regras de retenção diferentes |

O metadado `estado`/`municipio` é o que permite, na busca, filtrar por edital — sem ele, uma
pergunta sobre o edital de um município poderia recuperar trechos de outro município indexado no
mesmo índice.

## Limpeza de dados expirados

`app/jobs/limpeza_pinecone.py` é um script standalone (pensado para rodar como cron, ex.: no
Railway) que apaga do índice os registros com `origem = "upload_usuario"` cujo
`timestamp_indexacao` seja mais antigo que `PINECONE_RETENCAO_DIAS` (default 7 dias). O filtro
combinado (`timestamp_indexacao` + `origem`) garante que só editais de upload manual expiram —
registros de outras origens (ex.: futura indexação automática) não são afetados por esse job. Ver
[Retenção de editais no Pinecone](../governanca/lgpd.md#retencao-de-editais-no-pinecone) para o
racional por trás dessa política.

!!! note "Por que 2000 caracteres e 200 de overlap?"
    São os valores padrão escolhidos na implementação — **não foram empiricamente ajustados** neste
    projeto, e é importante ser transparente sobre isso. O racional geral por trás desses números:
    um chunk pequeno demais perde contexto semântico (uma cláusula cortada ao meio vira ruído para
    o embedding); um chunk grande demais dilui o vetor (mistura assuntos diferentes, piorando a
    precisão da busca) — 2000 caracteres é uma faixa comum na prática de RAG para texto denso como
    um edital. O overlap de 200 (10%) evita que uma informação relevante caia exatamente na
    fronteira entre dois chunks e fique cortada nos dois.

    A avaliação (Bloco 4) já indicou que esse parâmetro **é** uma alavanca real, não só teórica:
    dos casos com `context_recall` baixo, alguns eram na verdade o
    [bug de metadados](#o-bug-de-producao-que-a-avaliacao-revelou) — mas outros continuam com o
    trecho-alvo tão distante no documento que não aparece nem em `top_k=50`, uma limitação genuína
    de posição que só chunking diferente ou reranking resolveria (ver
    [Próximos Passos](../governanca/limitacoes.md)).

## O pipeline de busca

A ferramenta `buscar_contexto_edital` (que o agente chama sozinho) faz uma `similarity_search` no
Pinecone: converte a pergunta em vetor, recupera os `top_k` chunks mais próximos e filtra por
`estado` + `municipio`. O `top_k` default é **3**, configurável via `TOP_K_EDITAL` sem mudar código.
Se nada é encontrado, a ferramenta retorna uma mensagem explícita ("Nenhum trecho relevante
encontrado...") em vez de contexto vazio — para o agente não "adivinhar" o edital.

## O bug de produção que a avaliação revelou

!!! danger "O bug de metadados compartilhados"
    Durante o desenvolvimento do framework de avaliação, uma investigação de instabilidade de
    métrica revelou um bug **real de produção** no `processar_e_salvar`: o código usava
    `[metadados] * len(lista_chunks)`, que em Python cria N referências ao **mesmo** dicionário, não
    N cópias. Como a biblioteca `langchain_pinecone` grava o texto de cada chunk *dentro* do dict de
    metadados, o resultado era que **todo chunk indexado — em qualquer edital, inclusive de usuários
    reais — era armazenado com o texto do último chunk do documento**. Os embeddings continuavam
    corretos (calculados antes da mutação), então os *scores* de similaridade pareciam plausíveis e
    mascaravam o defeito. Na prática, `buscar_contexto_edital` sempre devolvia o mesmo trecho, não
    importava a pergunta.

    A correção foi trocar por `[dict(metadados) for _ in lista_chunks]` (uma cópia independente por
    chunk). O banco vetorial de produção foi limpo após o fix, então não foi preciso reindexar nada
    retroativamente. Este é o melhor exemplo de como o framework de avaliação encontrou um problema
    real do sistema, não só mediu números — ver [Avaliação](avaliacao.md).

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

- **`top_k=3` não alcança trechos posicionalmente distantes.** O diagnóstico da avaliação mostrou
  que, em alguns editais, o trecho-alvo está tão longe no documento (ex.: num apêndice) que não
  aparece nem em `top_k=50` — limitação genuína de recuperação por similaridade, endereçável com
  reranking ou chunking diferente na V2.
- **Subir o `top_k` não é grátis.** Mais contexto por chamada aumenta o custo de token e pode
  piorar a fidelidade (mais texto irrelevante para o modelo se confundir) — por isso o valor final
  ainda está em avaliação, não foi simplesmente elevado.
