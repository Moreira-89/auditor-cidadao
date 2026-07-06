# Investigação completa: variância e queda das métricas RAGAS na avaliação do Auditor Cidadão

**Data da investigação:** 2026-07-05
**Autor:** investigação conduzida em par com o Claude Code
**Branch:** `bloco-04-framework-avaliacao`

---

## Índice

1. [Contexto e motivação](#1-contexto-e-motivação)
2. [Glossário rápido](#2-glossário-rápido)
3. [O sintoma original](#3-o-sintoma-original)
4. [Como o pipeline de avaliação funciona](#4-como-o-pipeline-de-avaliação-funciona)
5. [Linha do tempo da investigação](#5-linha-do-tempo-da-investigação)
6. [Fase 1 — Hipóteses e leitura do código](#6-fase-1--hipóteses-e-leitura-do-código)
7. [Fase 2 — Fix mínimo: barreira de consistência do Pinecone](#7-fase-2--fix-mínimo-barreira-de-consistência-do-pinecone)
8. [Fase 3 — Fix reforçado: namespace exclusivo por caso](#8-fase-3--fix-reforçado-namespace-exclusivo-por-caso)
9. [Fase 4 — Troca do juiz RAGAS (gpt-4o-mini → gpt-4o)](#9-fase-4--troca-do-juiz-ragas-gpt-4o-mini--gpt-4o)
10. [Fase 5 — Diagnóstico de top_k e a descoberta do bug de metadados](#10-fase-5--diagnóstico-de-top_k-e-a-descoberta-do-bug-de-metadados)
11. [O bug de metadados, explicado em detalhe](#11-o-bug-de-metadados-explicado-em-detalhe)
12. [Tabela-mestra de todos os artefatos gerados](#12-tabela-mestra-de-todos-os-artefatos-gerados)
13. [Causas-raiz — visão consolidada](#13-causas-raiz--visão-consolidada)
14. [Estado atual do código](#14-estado-atual-do-código)
15. [Fase 6 — validação final com todas as correções aplicadas](#15-fase-6--validação-final-com-todas-as-correções-aplicadas)
16. [O que ainda falta fazer](#16-o-que-ainda-falta-fazer)
17. [Lições aprendidas](#17-lições-aprendidas)

---

## 1. Contexto e motivação

O projeto **Auditor Cidadão** usa um agente de IA (LangGraph + GPT-4o-mini) para
auditar editais de licitação pública brasileiros em busca de anomalias (sanções de
empresas, direcionamento de marca, prazos irregulares, etc.). Para garantir que
mudanças no agente (prompt, tools, modelo) não piorem a qualidade das respostas, o
projeto mantém um **golden dataset** (`evaluation/golden_dataset.json`) com 10 casos
de teste manualmente curados e um script de avaliação automatizada
(`evaluation/pipeline_avaliacao.py`) que roda o agente contra cada caso e mede três
famílias de métricas:

- **aderência de tools**: o agente chamou as ferramentas certas?
- **recall de anomalias**: o agente detectou as anomalias esperadas no laudo final?
- **RAGAS** (`faithfulness` e `context_recall`): quando o agente usa a ferramenta de
  busca semântica no edital (`buscar_contexto_edital`), o texto que ele recupera do
  edital realmente sustenta a resposta, e cobre o que deveria cobrir?

Esta investigação nasceu porque as últimas 3 execuções do pipeline mostraram uma
**queda progressiva e alta variabilidade** justamente nas métricas RAGAS — o que é
preocupante, porque essas métricas dependem de um pipeline de recuperação de
informação (RAG) que também roda em produção, atendendo usuários reais.

## 2. Glossário rápido

Para quem não acompanha RAG/RAGAS no dia a dia:

- **RAG (Retrieval-Augmented Generation)**: em vez de o modelo de linguagem "saber"
  tudo de cor, ele primeiro *busca* trechos relevantes de um documento (aqui, o
  edital) e depois *gera* a resposta com base nesses trechos. Isso reduz alucinação
  e permite responder sobre documentos que o modelo nunca viu no treinamento.
- **Chunk**: como um documento inteiro não cabe (ou não é eficiente) processar de
  uma vez, ele é cortado em pedaços menores ("chunks") antes de ser indexado.
- **Embedding**: uma representação numérica (um vetor, tipicamente de centenas de
  números) do significado de um texto. Textos com significado parecido têm vetores
  "próximos" no espaço matemático.
- **Pinecone**: o banco de dados vetorial usado neste projeto para armazenar os
  embeddings dos chunks e buscar, por similaridade, os mais relevantes para uma
  pergunta.
- **Namespace (no Pinecone)**: uma partição lógica dentro do mesmo índice — como
  "pastas" separadas onde se pode indexar e buscar sem misturar dados de contextos
  diferentes (ex.: dados de avaliação vs. dados de produção).
- **`top_k`**: quantos chunks mais similares à pergunta o sistema retorna. Em
  produção, `top_k=3` por padrão (agora configurável via `TOP_K_EDITAL`).
- **Consistência eventual**: a maioria dos bancos de dados distribuídos modernos
  (Pinecone incluso) não garante que um dado escrito agora já esteja 100% visível
  para uma leitura no instante seguinte — pode levar de milissegundos a alguns
  segundos para propagar. Se você não espera essa propagação, pode "ler" um estado
  incompleto do banco.
- **RAGAS**: um framework que usa um LLM como "juiz" para pontuar automaticamente a
  qualidade de um sistema RAG, sem precisar de um humano avaliando cada resposta.
  Aqui usamos duas métricas dele:
  - **`faithfulness`** (fidelidade): a resposta do agente só afirma coisas que estão
    de fato sustentadas pelo contexto recuperado, ou ele "inventou" (alucinou) algo
    a mais?
  - **`context_recall`** (cobertura do contexto): o contexto que foi recuperado
    contém a informação necessária para responder corretamente (comparado a um
    "gabarito" — o `contexto_edital_esperado` do golden dataset)?
- **Ground truth / gabarito**: no golden dataset, o campo `contexto_edital_esperado`
  é o trecho exato do edital que *deveria* ter sido recuperado para responder bem
  àquela pergunta. É contra ele que o RAGAS mede `context_recall`.
- **Juiz LLM**: tanto `faithfulness` quanto `context_recall` são calculados
  **chamando um modelo de linguagem** para julgar (não é uma fórmula matemática
  determinística) — por isso qual modelo se usa como juiz (`AVALIADOR_MODEL`)
  importa para a estabilidade dos números.

## 3. O sintoma original

O usuário reportou as últimas 3 execuções do pipeline de avaliação, todas medindo
apenas os 6 casos do golden dataset que usam `buscar_contexto_edital`:

| Execução | `faithfulness` | `context_recall` |
|---|---|---|
| Run A | 0.72 | 0.83 |
| Run B | 0.65 | 0.72 |
| Run C | 0.57 | 0.50 |

Duas coisas chamavam atenção: (1) uma **queda consistente** ao longo das 3 rodadas
e (2) uma **amplitude grande** entre a melhor e a pior rodada (0.15 em
`faithfulness`, 0.33 em `context_recall`) — rodando exatamente o mesmo código e o
mesmo dataset. Hipóteses levantadas pelo usuário, sem compromisso com nenhuma
delas a priori:

- **(A)** Amostra pequena (n=6): 1-2 casos ruins numa rodada derrubam a média —
  seria ruído estatístico, não degradação real.
- **(B)** O retrieval (RAG) está trazendo trechos incorretos/irrelevantes do edital.
- **(C)** O `contexto_edital_esperado` (gabarito) do golden dataset está
  desalinhado com o que o retriever deveria buscar.
- **(D)** O laudo gerado pelo agente principal infere além do que o contexto
  recuperado sustenta (problema real de faithfulness).

## 4. Como o pipeline de avaliação funciona

Antes de investigar, vale entender a mecânica de
[`evaluation/pipeline_avaliacao.py`](../pipeline_avaliacao.py) (estado antes de
qualquer fix desta investigação):

1. Limpa o namespace `"avaliacao"` do Pinecone (estado limpo geral, uma vez, antes
   de todo o loop).
2. Para cada um dos 10 casos do golden dataset, **em sequência**:
   a. Extrai o texto do edital de teste (PDF real, ou o próprio texto sintético
      para casos fictícios) e concatena um `trecho_injetado` (dados fictícios de
      empresa vencedora, CNPJ, etc., quando aplicável).
   b. Chama `gerenciador.executar(...)`, que faz `chunkizar_documento` (corta o
      texto em pedaços de até 2000 caracteres, com 200 de sobreposição) e depois
      `processar_e_salvar` (gera embeddings e faz upsert no Pinecone, no namespace
      `"avaliacao"`).
   c. Roda o agente de ponta a ponta (mesmo grafo LangGraph/tools/prompt de
      produção) para a pergunta daquele caso, capturando: laudo final, tools
      chamadas, e — quando `buscar_contexto_edital` foi usada — o texto retornado
      por ela (`contexto_recuperado`).
   d. Calcula `aderencia_tools` (comparação simples, sem LLM) e, com um extrator
      estruturado separado, `recall_anomalias`.
3. Ao final do loop, agrega as médias de `aderencia_tools` e `recall_anomalias`.
4. Limpa o namespace `"avaliacao"` de novo.
5. Roda o RAGAS **só** nos casos que esperavam `buscar_contexto_edital`
   (originalmente os 6 casos: `caso_02, caso_04a, caso_04b, caso_06, caso_08,
   caso_10` — ver seção 15/atualização sobre `excluir_do_ragas`), usando um LLM
   "juiz" (`AVALIADOR_MODEL`) para calcular `faithfulness` e `context_recall`.
6. Compara tudo contra limiares de aprovação e escreve
   `evaluation/relatorio.json`.

Um detalhe crítico do design (relevante para as fases 2 e 3 abaixo): **todos os
casos do golden dataset compartilhavam o mesmo namespace Pinecone**
(`"avaliacao"`), e a limpeza desse namespace só acontecia **uma vez antes** e **uma
vez depois** de todo o loop — nunca entre casos individuais.

## 5. Linha do tempo da investigação

| Fase | O que foi feito | O que descobrimos |
|---|---|---|
| 1 | Leitura do código (pipeline, tools, RAG, dataset) sem rodar nada | Identifiquei 3 mecanismos candidatos a causar variância, por análise estática |
| 2 | Fix mínimo: barreira de consistência do Pinecone | Reduziu a variância, mas não eliminou (`caso_06` ainda oscilava VAZIO↔cheio) |
| 3 | Fix reforçado: namespace exclusivo por caso | Eliminou a oscilação do `caso_06`; retrieval ficou 100% determinístico entre rodadas |
| 4 | Usuário trocou o juiz RAGAS de `gpt-4o-mini` para `gpt-4o` | Amplitude de `context_recall` caiu de 0.167 para **0.000** nas 3 rodadas de validação |
| 5 | Diagnóstico de `top_k=20/50` para entender por que 5 casos ainda tinham `context_recall` ruim | **Achado principal**: bug de metadados compartilhados em `gerenciadorvetorial.py` fazia TODO chunk armazenado carregar o texto do ÚLTIMO chunk do documento — afetando também produção, não só avaliação |

## 6. Fase 1 — Hipóteses e leitura do código

Sem rodar nada ainda, a leitura de
[`pipeline_avaliacao.py`](../pipeline_avaliacao.py),
[`gerenciadorvetorial.py`](../../app/services/gerenciadorvetorial.py),
[`tools.py`](../../app/services/tools.py),
[`dependencies.py`](../../app/core/dependencies.py) e
[`build_graph.py`](../../app/services/build_graph.py) revelou:

- **Configuração**: agente principal em `gpt-4o-mini` a `temperature=0.1`; extrator
  estruturado e juiz RAGAS (na época) a `temperature=0.0` em `gpt-4o-mini`;
  retrieval com `top_k=3` fixo, chunks de 2000 caracteres com 200 de sobreposição.
- **Mecanismo candidato 1 — corrida de consistência eventual do Pinecone**: o loop
  fazia `gerenciador.executar(...)` (upsert) e **imediatamente** invocava o agente
  (que consulta via `similarity_search`), sem nenhuma espera/poll entre os dois.
  Numa rodada "lenta" de propagação, a busca podia voltar vazia ou parcial.
- **Mecanismo candidato 2 — namespace compartilhado sem limpeza entre casos**: como
  a limpeza só rodava uma vez antes/depois de todo o loop, casos do mesmo
  município (ex.: `caso_05`/`caso_06` de Melgaço, ambos indexando o mesmo PDF)
  acumulavam chunks duplicados no mesmo namespace, competindo pelo `top_k=3`.
- **Mecanismo candidato 3 — retrieval frágil por design**: a pergunta usada na
  busca é gerada pelo próprio LLM (não é o `pergunta` fixo do caso), e o agente
  roda a `temperature=0.1` — pequenas variações de frase geram embeddings
  diferentes e por consequência um top-3 diferente a cada rodada.
- Um quarto fator, de *teto* (não de variância): o `caso_06` tem
  `contexto_edital_esperado` **negativo** (*"[O edital não traz a data de
  publicação]"*) — uma afirmação sobre ausência de informação, que não pode ser
  "atribuída" a nenhum chunk recuperado, então penaliza `context_recall`
  independentemente da qualidade real do retrieval.

## 7. Fase 2 — Fix mínimo: barreira de consistência do Pinecone

### O que foi feito

Adicionada a função `_aguardar_contagem_namespace(...)` em
`evaluation/pipeline_avaliacao.py`, que bloqueia (via polling de
`describe_index_stats`, com timeout de 60s) até o namespace atingir exatamente a
contagem de vetores esperada — tanto depois de limpar (esperar chegar a 0) quanto
depois de indexar (esperar chegar ao total de chunks). O loop passou a: limpar o
namespace, esperar zerar, indexar, esperar propagar — só então invocar o agente.

### Validação (3 execuções, mesmo protocolo, mesmo dataset)

| Rodada | `faithfulness` | `context_recall` |
|---|---|---|
| run1 | 0.331 | 0.667 |
| run2 | 0.447 | 0.556 |
| run3 | 0.379 | 0.528 |
| **amplitude** | **0.116** | **0.139** |

Comparado ao reportado originalmente (amplitude 0.15 / 0.33), a variância caiu,
mas **não o suficiente para considerar resolvido**. Investigando caso a caso,
achamos que o **`caso_06` (Melgaço) oscilava entre rodadas**: `run1` retornou 0
documentos (`"Nenhum trecho relevante encontrado"`), `run2` retornou 3 documentos
cheios, `run3` voltou a 0. Isso apontava para uma corrida residual: o padrão
"limpar e reindexar o **mesmo** namespace" em casos consecutivos do mesmo
município (`caso_05` seguido de `caso_06`, ambos indexando o edital de Melgaço)
sofria um lag de propagação no **filtro por metadados** do Pinecone que a barreira
por `vector_count` sozinha não capturava.

## 8. Fase 3 — Fix reforçado: namespace exclusivo por caso

### O que foi feito

Em vez de todos os casos compartilharem o namespace `"avaliacao"`, cada caso
passou a usar um namespace **próprio**: `f"avaliacao_{caso['id']}"` (ex.:
`avaliacao_caso_06`). Isso elimina de vez a adjacência de "limpar e reindexar o
mesmo namespace" entre casos consecutivos do mesmo município — não há mais
delete/re-add compartilhado, cada caso só limpa resíduo de execuções *anteriores*
suas (já propagado há muito tempo). Ao final da execução inteira, todos os
namespaces usados são limpos.

### Validação (3 execuções)

| Rodada | `faithfulness` | `context_recall` |
|---|---|---|
| v2_run1 | 0.399 | 0.556 |
| v2_run2 | 0.419 | 0.389 |
| v2_run3 | 0.446 | 0.500 |
| **amplitude** | **0.047** | 0.167 |

### Estabilidade do retrieval por caso (tamanho do contexto recuperado, em caracteres)

| caso | v2_run1 | v2_run2 | v2_run3 | estável? |
|---|---|---|---|---|
| caso_02 | 2110 | 2110 | 2110 | SIM |
| caso_04a | 5251 | 5251 | 5251 | SIM |
| caso_04b | 5251 | 10503 | 10503 | varia (nº de chamadas do agente, efeito do `temperature=0.1`) |
| **caso_06** | 9045 | 9045 | 9045 | **SIM — antes oscilava VAZIO↔cheio, agora não mais** |
| caso_08 | 2539 | 2539 | 2539 | SIM |
| caso_10 | 708 | 708 | 708 | SIM |

O `faithfulness` ficou bem mais estável (amplitude 0.047 vs. 0.116 antes). Mas o
`context_recall` continuou oscilando 0.167 — e aqui está o ponto mais revelador
desta fase: **entre v2_run1 e v2_run2 os contextos recuperados são praticamente
idênticos**, e mesmo assim `context_recall` caiu de 0.556 para 0.389. Se o
retrieval é idêntico mas o número muda, a variação **não pode vir do retrieval** —
só pode vir do juiz LLM que está pontuando. Essa foi a pista que motivou a fase 4.

## 9. Fase 4 — Troca do juiz RAGAS (gpt-4o-mini → gpt-4o)

O usuário trocou, no `.env`, `AVALIADOR_MODEL` de `openai:gpt-4o-mini` para
`openai:gpt-4o`. Rodamos novamente 3 execuções com o mesmo protocolo (namespace
por caso + barreira de consistência):

| Rodada | `faithfulness` | `context_recall` |
|---|---|---|
| v3_run1 | 0.488 | 0.167 |
| v3_run2 | 0.392 | 0.167 |
| v3_run3 | 0.451 | 0.167 |
| **amplitude** | 0.096 | **0.000** |

O `context_recall` deu **exatamente o mesmo valor nas 3 rodadas** — amplitude
zero. Isso confirma de forma direta a hipótese: a variância que sobrava depois do
fix de retrieval era **ruído do juiz `gpt-4o-mini`**, não instabilidade real do
pipeline. Com um juiz mais forte, o número deixou de oscilar.

**Efeito colateral esperado, não um novo bug** (na época): o valor absoluto de
`context_recall` caiu para 0.167 (= 1/6, ou seja, só 1 dos 6 casos pontuando cheio
e os outros 5 zerados). A hipótese inicial foi que um juiz mais rigoroso deixava
de dar falso-positivo de atribuição nos casos onde o contexto de fato não cobre
bem o gabarito. A fase 5 revelou que essa hipótese só era **parcialmente**
correta — parte desses 5 zeros vinha de um bug real de retrieval, não de excesso
de rigor do juiz (ver seção 11).

O `faithfulness` manteve alguma variância própria (0.392–0.488, amplitude 0.096) —
menor que a original, mas não nula. Hipótese (não totalmente investigada):
resíduo do `temperature=0.1` do agente principal, que gera laudos ligeiramente
diferentes por rodada, mudando o que o juiz tem para avaliar.

## 10. Fase 5 — Diagnóstico de top_k e a descoberta do bug de metadados

### O pedido original desta fase

Para os 5 casos com pior desempenho de `context_recall` (`caso_02, caso_04a,
caso_04b, caso_06, caso_08`), indexar o edital como o pipeline faz, consultar o
Pinecone diretamente com `top_k=20` (bem mais generoso que os 3 de produção),
imprimir os 20 chunks retornados numerados, e localizar manualmente em qual
posição aparece o chunk que contém o `contexto_edital_esperado`. Se não aparecer
nem em 20, escalar para `top_k=50`.

Criado o script [`testes_locais/diagnostico_top_k.py`](../../testes_locais/diagnostico_top_k.py)
para isso, isolado do pipeline principal (namespace de debug próprio,
`debug-topk-<caso_id>`, limpo ao final de cada caso).

### Primeira surpresa: todos os 20 chunks vinham com o MESMO texto

Ao rodar pela primeira vez, cada posição de 1 a 20 (ou até 1 a 16, quando o
documento tinha menos chunks) mostrava a **prévia de texto idêntica**, mudando só
o score de similaridade. Isso é matematicamente impossível se os chunks fossem de
fato distintos — a suspeita imediata foi bug no script de diagnóstico (talvez uma
corrida de consistência, já que o script ainda não tinha a barreira das fases 2/3
aplicada). Adicionamos a barreira de consistência ao script e rodamos de novo: **o
mesmo padrão persistiu, idêntico**. Isso descartou definitivamente a hipótese de
corrida — o problema estava em outro lugar.

### A pista decisiva

Checamos localmente (sem custo de API, só a função de chunking) quantos chunks
únicos cada documento realmente tinha — confirmando que não havia duplicação na
geração dos chunks (16 chunks, 16 únicos, por exemplo). Então comparamos o texto
que aparecia repetido em cada caso contra o **último chunk** (`chunks[-1]`) daquele
documento, calculado localmente. Bateu, char por char, nos 4 casos testados:

| caso | texto repetido em TODAS as posições do ranking | é igual a `chunks[-1]`? |
|---|---|---|
| caso_02 | `"b) Prazo de entrega: até 30 (trinta) dias..."` | SIM (chunk 15 de 16) |
| caso_04a | `"determina os artigos 105 e 107 da Lei nº 14.133/2021..."` | SIM (chunk 111 de 112) |
| caso_06 | `"CPF E RG NOME DA EMPRESA... PREFEITURA MUNICIPAL DE MELGAÇO..."` | SIM (chunk 76 de 77) |
| caso_08 | `"da Constituição. 8. DECLARA, que cumpre as exigências..."` | SIM (chunk 65 de 66) |

Todo chunk indexado, não importa sua posição real no documento, estava sendo
armazenado no Pinecone com o **conteúdo textual do último chunk do documento**.
Isso levou direto à causa raiz, detalhada na seção 11.

## 11. O bug de metadados, explicado em detalhe

### Onde está

Arquivo [`app/services/gerenciadorvetorial.py`](../../app/services/gerenciadorvetorial.py),
método `processar_e_salvar`, responsável por gerar embeddings e fazer o upsert dos
chunks no Pinecone. **Código antes do fix:**

```python
def processar_e_salvar(
    self, lista_chunks: list[str], metadados: dict, namespace: str = "production"
) -> None:
    self.vector_store.add_texts(
        texts=lista_chunks,
        metadatas=[metadados] * len(lista_chunks),   # <-- bug aqui
        namespace=namespace,
    )
```

### Por que `[metadados] * len(lista_chunks)` é um erro clássico do Python

Em Python, multiplicar uma lista que contém um objeto **mutável** (como um dict)
não cria cópias independentes — cria uma lista com **N referências ao mesmo
objeto na memória**. Um exemplo simples fora do contexto do projeto, para deixar
bem claro:

```python
>>> d = {"x": 1}
>>> lista = [d] * 3
>>> lista[0]["x"] = 999
>>> lista
[{'x': 999}, {'x': 999}, {'x': 999}]   # os "3 dicts" são, na verdade, o mesmo dict
```

Mudar `lista[0]` também muda `lista[1]` e `lista[2]`, porque não são três dicts —
são três nomes apontando para a mesma caixa de memória.

### Onde a mutação acontece de fato

Dentro da biblioteca `langchain_pinecone`, o método `add_texts` (que
`processar_e_salvar` chama) faz o seguinte, **antes** de montar os vetores para
upload (trecho real da lib, em
`.venv/Lib/site-packages/langchain_pinecone/vectorstores.py`, linha 347):

```python
metadatas = metadatas or [{} for _ in texts]
for metadata, text in zip(metadatas, texts):
    metadata[self._text_key] = text   # <-- injeta o texto do chunk DENTRO do metadata
```

Esse padrão é normal e correto **se cada `metadata` for um dict independente** —
é assim que o texto de cada chunk fica junto do seu embedding no Pinecone (afinal,
o Pinecone só guarda vetores + metadados; o "texto" do chunk em si é armazenado
como só mais um campo de metadado, chamado `text` por convenção do
`langchain_pinecone`).

O problema é que, como `processar_e_salvar` passou `[metadados] * len(lista_chunks)`
(N referências ao mesmo dict), esse loop **sobrescreve repetidamente o campo
`text` do mesmo objeto**, uma vez por chunk, em sequência. Ao terminar o loop, o
único dict que existe (mas que está "presente" em todas as N posições da lista)
tem `text = lista_chunks[-1]` — o valor da **última** atribuição, ou seja, o texto
do **último chunk processado**.

### Por que os embeddings continuavam corretos (e por que isso mascarou o bug por tanto tempo)

Os **embeddings** de cada chunk são calculados a partir do texto original de cada
chunk, ANTES dessa mutação de metadados acontecer — e cada embedding é enviado ao
Pinecone junto com uma referência ao dict de metadados (na hora, corrompido). Ou
seja:

- O **vetor matemático** que representa cada chunk está correto e é único por
  chunk → por isso o **ranking por similaridade** (quais chunks "parecem" mais
  relevantes para uma pergunta) continuava funcionando de forma plausível, com
  scores distintos e sensatos para cada posição.
- Mas o **texto retornado** junto de cada vetor (o que o agente de fato lê e usa
  para responder) era sempre o mesmo — o do último chunk do documento —
  independentemente de qual vetor tecnicamente "ganhou" a busca por similaridade.

Essa é a razão de o bug ser tão traiçoeiro: olhando só para os *scores* de uma
busca, tudo parecia normal (números diferentes, ordenados de forma coerente). Só
ao **imprimir o texto de cada resultado lado a lado** é que a anomalia (texto
idêntico em todas as posições) ficou visível.

### Consequência prática, com um exemplo

Imagine que o edital de São Luís foi cortado em 16 chunks. Não importa se a
pergunta do usuário for sobre "prazo de entrega", "marca Dell Inspiron", "valor
total" ou "sanções da empresa" — depois desse bug, `buscar_contexto_edital`
**sempre devolvia o mesmo trecho** (o último chunk do documento, por acaso um
trecho sobre prazo de entrega e forma de pagamento), disfarçado atrás de um score
de similaridade que parecia ter feito sentido para aquela pergunta específica.

### Por que isso é um bug de PRODUÇÃO, não só de avaliação

`processar_e_salvar` é chamado tanto pelo pipeline de avaliação quanto pelo fluxo
real de indexação de editais em produção (`GerenciadorVetorial.executar`, chamado
a partir do upload de PDF do usuário — ver `app/api/root_upload.py`). **Qualquer
edital indexado no ambiente de produção, antes deste fix, sofreu exatamente o
mesmo problema**: o agente real, atendendo um usuário real, recebia sempre o
último chunk do documento como "contexto do edital", não importa a pergunta.

> **Atualização pós-fix**: o banco vetorial (Pinecone) foi limpo em todos os
> namespaces, inclusive produção, depois deste fix — não é necessário reindexar
> nada retroativamente. Qualquer edital indexado a partir de agora já usa o
> `processar_e_salvar` corrigido.

### O fix

```python
self.vector_store.add_texts(
    texts=lista_chunks,
    metadatas=[dict(metadados) for _ in lista_chunks],  # cópia independente por chunk
    namespace=namespace,
)
```

Trocar a multiplicação de lista por uma *list comprehension* que chama
`dict(metadados)` uma vez por chunk garante que cada chunk tenha seu **próprio**
dict de metadados — a mutação de um não afeta os outros.

### Confirmação do fix: diagnóstico de top_k, depois de corrigido

Rodando o mesmo script de diagnóstico depois do fix, os 20 chunks retornados por
caso passaram a ter **texto genuinamente distinto em cada posição** (confirmado
manualmente, ver arquivo `11_diagnostico_topk_APOS_fix_metadados.log`). Com isso,
foi possível medir pela primeira vez a posição **real** do chunk-alvo:

| caso | posição do chunk-alvo, ANTES do fix (bug ativo) | posição do chunk-alvo, DEPOIS do fix |
|---|---|---|
| caso_02 | não encontrado (busca sempre retornava o mesmo chunk errado) | **não encontrado nem em top-50 de 16** — limitação genuína |
| caso_04a | não encontrado (idem) | **não encontrado nem em top-50 de 112** — limitação genuína |
| **caso_04b** | não encontrado (idem) | **posição 9 de 20** — recuperável! |
| caso_06 | não encontrado (idem) | não encontrado nem em top-50 de 77 — **esperado**, porque o gabarito é uma afirmação negativa ("o edital não traz a data"), não um trecho literal do texto |
| **caso_08** | não encontrado (idem) | **posição 2 de 20** — recuperável, e cairia dentro do `top_k=3` usado em produção! |

**Conclusão desta fase**: dos 5 casos com pior `context_recall`, **2 (`caso_04b` e
`caso_08`) eram vítimas diretas do bug de metadados** — o retriever, de fato,
conseguia encontrar o trecho certo, mas o bug fazia o texto devolvido ser sempre
outro. Só **`caso_02`, `caso_04a` e `caso_06`** representam limitação real do
sistema hoje: `top_k=3` não alcança o chunk-alvo porque ele está posicionalmente
distante no documento (ex.: `caso_02` precisa de um trecho no APÊNDICE I, bem
depois do corpo principal do edital), ou porque o gabarito, por natureza, não é
um trecho literal recuperável por similaridade semântica (`caso_06`).

## 12. Tabela-mestra de todos os artefatos gerados

Todos os arquivos abaixo estão em `evaluation/relatorios_investigacao/`:

| Arquivo | O que é | Fase |
|---|---|---|
| `01_fixminimo_run1.json` a `03_fixminimo_run3.json` | `relatorio.json` bruto de cada uma das 3 execuções com o fix mínimo (barreira de consistência, namespace único) | Fase 2 |
| `04_fixreforcado_run1.json` a `06_fixreforcado_run3.json` | `relatorio.json` bruto de cada uma das 3 execuções com o fix reforçado (namespace por caso), juiz ainda `gpt-4o-mini` | Fase 3 |
| `07_juiz_gpt4o_run1.json` a `09_juiz_gpt4o_run3.json` | `relatorio.json` bruto de cada uma das 3 execuções com o juiz trocado para `gpt-4o` | Fase 4 |
| `10a_diagnostico_topk_com_bug_metadados_v1.log` | 1ª rodada do diagnóstico de `top_k`, script ainda sem barreira de consistência, bug de metadados presente | Fase 5 |
| `10b_diagnostico_topk_com_bug_metadados_v2.log` | 2ª rodada, script já com barreira de consistência adicionada — bug de metadados persiste idêntico (prova de que não era race condition) | Fase 5 |
| `11_diagnostico_topk_APOS_fix_metadados.log` | 3ª rodada, após corrigir `gerenciadorvetorial.py` — chunks genuinamente distintos, posições reais medidas | Fase 5 |
| `12_final_todas_correcoes_run1.json` a `14_final_todas_correcoes_run3.json` | `relatorio.json` bruto de cada uma das 3 execuções com TODAS as correções ativas (fix de metadados + barreira de consistência + namespace por caso + juiz `gpt-4o` + `excluir_do_ragas` no `caso_06`) | Fase 6 |

> **Nota de continuidade**: esta pasta não é rastreada pelo git e já foi apagada
> (sem querer, pelo usuário) ao menos uma vez durante a investigação — o que
> também explica desaparecimentos anteriores registrados nesta mesma sessão.
> **Recomenda-se commitar esta pasta assim que possível** para não depender de
> arquivos não versionados sobreviverem entre sessões.

**Importante:** as 9 rodadas de RAGAS das fases 2-4 (arquivos `01` a `09`) foram
**todas medidas com o bug de metadados ainda ativo** (ele só foi descoberto na
fase 5). Isso significa que os números de `faithfulness`/`context_recall`
reportados nessas fases devem ser lidos como "o piso que o pipeline conseguia
mesmo com o retriever sistematicamente devolvendo o chunk errado" — não como a
medida final e correta do sistema. As conclusões *qualitativas* de cada fase (a
barreira de consistência reduz variância; o namespace por caso estabiliza o
`caso_06`; um juiz mais forte elimina o ruído de `context_recall`) continuam
válidas, porque são efeitos independentes e cumulativos ao bug de metadados — mas
os valores absolutos de `faithfulness`/`context_recall` precisam ser remedidos
agora que o bug foi corrigido — **essa remedição já foi feita, ver seção 15
(Fase 6)**: `faithfulness` subiu para ≈0.87 e `context_recall` para 0.6 (ainda
abaixo do limiar de aprovação de 0.75).

## 13. Causas-raiz — visão consolidada

| # | Causa | Afeta | Status | Onde foi corrigida |
|---|---|---|---|---|
| 1 | Corrida de consistência eventual do Pinecone (indexar-e-consultar sem esperar propagação) | Só avaliação (produção indexa uma vez, sem esse padrão de reindexação constante) | ✅ Corrigido | `evaluation/pipeline_avaliacao.py`, função `_aguardar_contagem_namespace` (commit `c8157b7`) |
| 2 | Namespace compartilhado entre casos consecutivos do mesmo município, causando delete-readd adjacente e flicker de retrieval | Só avaliação | ✅ Corrigido | `evaluation/pipeline_avaliacao.py`, namespace `avaliacao_<id>` por caso |
| 3 | Ruído do juiz RAGAS (`gpt-4o-mini` como avaliador, não-determinístico mesmo a `temperature=0`) | Só avaliação (o "juiz" não existe em produção, é conceito exclusivo de teste) | ✅ Corrigido | `.env`, `AVALIADOR_MODEL=openai:gpt-4o` |
| 4 | **Bug de metadados compartilhados** (`[dict] * N`) fazendo todo chunk armazenado carregar o texto do último chunk do documento | **Produção E avaliação** | ✅ Corrigido | `app/services/gerenciadorvetorial.py`, `processar_e_salvar` |
| 5 | `top_k=3` não alcança o chunk-alvo em documentos grandes quando o trecho relevante está posicionalmente distante (`caso_02`, `caso_04a`) | Produção e avaliação | ⚠️ Não corrigido — limitação real de design | `TOP_K_EDITAL` já é configurável via env (ver seção 14), mas ainda não decidido um valor final |
| 6 | Ground truth do `caso_06` é uma afirmação negativa, não um trecho literal recuperável por similaridade semântica | Só avaliação (é um problema do dataset de teste, não do sistema real) | ✅ Corrigido | `evaluation/golden_dataset.json`, campo `excluir_do_ragas: true` no `caso_06` + condição irmã em `pipeline_avaliacao.py` |

## 14. Estado atual do código

Mudanças já aplicadas no working tree (branch `bloco-04-framework-avaliacao`):

- **`evaluation/pipeline_avaliacao.py`** (commit `c8157b7`, já commitado):
  barreira de consistência via `_aguardar_contagem_namespace` + namespace
  exclusivo por caso (`avaliacao_<id>`) + limpeza de todos os namespaces usados
  ao final da execução. **Atualização**: agora também pula, na montagem do
  dataset do RAGAS, qualquer caso com `excluir_do_ragas: true` (condição irmã à
  checagem existente de `"buscar_contexto_edital" not in tools_esperadas`, sem
  substituí-la).
- **`.env`**: `AVALIADOR_MODEL` alterado de `openai:gpt-4o-mini` para
  `openai:gpt-4o`.
- **`app/services/gerenciadorvetorial.py`**: fix do bug de metadados
  compartilhados em `processar_e_salvar` (`[dict(metadados) for _ in
  lista_chunks]` no lugar de `[metadados] * len(lista_chunks)`).
- **`app/services/tools.py`**: `buscar_contexto_edital` agora lê
  `TOP_K_EDITAL` do ambiente (default `3`), permitindo configurar o `top_k` sem
  mudar código.
- **`evaluation/golden_dataset.json`**: `caso_06` ganhou o campo
  `"excluir_do_ragas": true`, sinalizando que seu `contexto_edital_esperado` é
  uma afirmação negativa, estruturalmente não avaliável por `context_recall`. O
  texto de `contexto_edital_esperado` **não foi alterado** — o caso continua
  valendo normalmente para `aderencia_tools` e `recall_anomalias`.
- **`testes_locais/diagnostico_top_k.py`** (novo arquivo): script standalone de
  diagnóstico, reutilizável para investigar a posição real de qualquer
  chunk-alvo no ranking de similaridade, para qualquer caso do golden dataset.
- **`evaluation/relatorios_investigacao/`** (esta pasta): artefatos brutos e
  este relatório. Não rastreada pelo git — recomenda-se commitar.

## 15. Fase 6 — validação final com todas as correções aplicadas

### Mudanças de dataset feitas antes desta rodada

Além das correções de código das fases 2-5, o `evaluation/golden_dataset.json`
recebeu um ajuste: o `caso_06` ganhou o campo `"excluir_do_ragas": true`. O texto
de `contexto_edital_esperado` **não foi alterado** (continua servindo normalmente
`aderencia_tools` e `recall_anomalias`) — só a montagem do dataset do RAGAS, em
`pipeline_avaliacao.py`, passou a pular esse caso especificamente, via uma
condição irmã à checagem já existente de `"buscar_contexto_edital" not in
tools_esperadas` (a condição antiga não foi substituída, só complementada).
Confirmado por inspeção: os 5 casos que entram no cálculo do RAGAS agora são
`caso_02, caso_04a, caso_04b, caso_08, caso_10` (6 elegíveis originalmente, menos
o `caso_06` excluído).

### Protocolo desta rodada

3 execuções completas do golden dataset (11 casos cada), com **todas** as
correções desta investigação simultaneamente ativas:
fix de metadados (`gerenciadorvetorial.py`) + barreira de consistência do
Pinecone + namespace exclusivo por caso + `AVALIADOR_MODEL=openai:gpt-4o` +
`excluir_do_ragas` no `caso_06`. `TOP_K_EDITAL` confirmado em `3` (valor padrão,
não alterado nesta rodada — a comparação a seguir isola o efeito das correções,
sem confundir com uma mudança de `top_k`).

### Resultado, métrica por métrica, as 3 rodadas individuais (nenhum valor omitido)

| Métrica | run1 | run2 | run3 | amplitude (máx−mín) |
|---|---|---|---|---|
| `faithfulness` | 0.8762 | 0.8583 | 0.8700 | 0.0179 |
| `context_recall` | 0.6000 | 0.6000 | 0.6000 | **0.0000** |
| `media_aderencia_tools` | 1.0 | 1.0 | 1.0 | 0.0000 |
| `media_recall_anomalias` | 1.0 | 1.0 | 1.0 | 0.0000 |

### Veredito de aprovação, as 3 rodadas (nenhum campo omitido)

| Métrica | Limiar | run1 | run2 | run3 |
|---|---|---|---|---|
| `aderencia_tools` | ≥ 0.70 | 1.000 — ✅ aprovado | 1.000 — ✅ aprovado | 1.000 — ✅ aprovado |
| `faithfulness` | ≥ 0.85 | 0.876 — ✅ aprovado | 0.858 — ✅ aprovado | 0.870 — ✅ aprovado |
| `context_recall` | ≥ 0.75 | 0.600 — ❌ **reprovado** | 0.600 — ❌ **reprovado** | 0.600 — ❌ **reprovado** |
| `recall_anomalias` | ≥ 0.80 | 1.000 — ✅ aprovado | 1.000 — ✅ aprovado | 1.000 — ✅ aprovado |
| **`aprovacao["geral"]`** | — | **❌ false** | **❌ false** | **❌ false** |

**O veredito geral é reprovado nas 3 rodadas**, única e exclusivamente por
`context_recall` (0.600) ficar abaixo do limiar de aprovação (0.75) — todas as
outras três métricas passam confortavelmente, de forma idêntica ou quase idêntica
nas 3 execuções.

Checagem de integridade: as 3 rodadas processaram os 11 casos do dataset sem
nenhum `"erro"` registrado (nenhuma falha silenciosa de caso).

### Comparação explícita contra o baseline mais recente (fase 4, antes do fix de metadados)

| Métrica | Baseline (fase 4, juiz `gpt-4o`, 6 casos, bug de metadados ainda ativo) | Fase 6 (juiz `gpt-4o`, 5 casos, bug corrigido) | Direção |
|---|---|---|---|
| `faithfulness` | 0.488 / 0.392 / 0.451 (média ≈ 0.444) | 0.876 / 0.858 / 0.870 (média ≈ 0.868) | **Subiu**, quase dobrou (+0.424 em média, +95%) |
| `context_recall` | 0.167 / 0.167 / 0.167 (constante) | 0.600 / 0.600 / 0.600 (constante) | **Subiu** (+0.433 absoluto, ≈ +260%), mas **continua abaixo do limiar de aprovação (0.75)** |

**Duas mudanças foram aplicadas juntas entre o baseline e esta rodada** — o fix do
bug de metadados E a exclusão do `caso_06` da amostra do RAGAS (6 casos → 5
casos). Isso significa que **não é possível, com os dados desta rodada, separar
quanto da melhoria veio de cada uma** das duas causas isoladamente. O que se pode
afirmar com confiança, sem arredondar a leitura:

- A melhoria é grande e vai na direção esperada pelas duas mudanças (o retriever
  parou de devolver sistematicamente o chunk errado; e um caso estruturalmente
  não-pontuável em `context_recall` saiu da amostra).
- `context_recall=0.6` é **exatamente** o valor esperado se 3 dos 5 casos
  pontuassem cheio e 2 não (3/5 = 0.6) — compatível com o que o diagnóstico de
  `top_k` da fase 5 já indicava: `caso_02` e `caso_04a` continuam sendo limitação
  genuína de `top_k=3` (chunk-alvo não aparece nem em `top_k=50`), enquanto
  `caso_04b`, `caso_08` e `caso_10` são recuperáveis. Isso é uma leitura
  **plausível e consistente com evidência anterior**, não uma confirmação
  direta desta rodada (o `relatorio.json` não grava o score de `context_recall`
  por caso individual, só o agregado).
- **`context_recall` ainda não está resolvido**: mesmo com as duas correções, o
  sistema reprova esse critério nas 3 rodadas. A causa remanescente já era
  conhecida antes desta rodada (seção 11/13, causa #5): `top_k=3` não alcança o
  chunk-alvo em `caso_02` e `caso_04a` porque ele está posicionalmente distante
  no documento — isso não foi corrigido nesta investigação.
- Com apenas 3 rodadas nesta série, **não declaro os números "confirmados" para
  sempre** — mas a amplitude zero de `context_recall` e quase-zero de
  `faithfulness` nas 3 execuções é uma evidência forte (não uma prova
  definitiva) de que a instabilidade original do pipeline foi, de fato, resolvida
  pelas correções aplicadas.

### Artefatos desta rodada

| Arquivo | Conteúdo |
|---|---|
| `12_final_todas_correcoes_run1.json` | `relatorio.json` bruto, rodada 1, todas as correções ativas |
| `13_final_todas_correcoes_run2.json` | `relatorio.json` bruto, rodada 2, todas as correções ativas |
| `14_final_todas_correcoes_run3.json` | `relatorio.json` bruto, rodada 3, todas as correções ativas |

## 16. O que ainda falta fazer

1. **Resolver `context_recall` < 0.75 (reprovado nas 3 rodadas da fase 6)**:
   causa já identificada — `caso_02` e `caso_04a` têm o chunk-alvo fora do
   alcance de `top_k=3` (não aparece nem em `top_k=50`). Opções: aumentar
   `TOP_K_EDITAL` de produção (já configurável via env), introduzir reranking,
   ou revisar se a pergunta/gabarito desses dois casos está bem desenhada.
2. **Isolar o efeito do fix de metadados vs. a exclusão do `caso_06`** na melhoria
   observada na fase 6, se for importante quantificar cada causa separadamente —
   exigiria rodar uma série adicional com o `caso_06` ainda incluído (mas com o
   bug de metadados já corrigido) para comparação controlada.
3. **Investigar a variância residual de `faithfulness`** (amplitude 0.0179 na
   fase 6 — pequena, mas não nula). Hipótese não confirmada: efeito do
   `temperature=0.1` do agente principal na avaliação. Poderia ser testado
   congelando `temperature=0` só durante a avaliação (produção manteria 0.1).
4. **Commitar** o fix de `gerenciadorvetorial.py`, o script de diagnóstico, as
   mudanças em `golden_dataset.json`/`pipeline_avaliacao.py`, e esta pasta de
   relatórios — nenhuma dessas mudanças está commitada ainda, e a pasta de
   relatórios já foi perdida (sem querer) uma vez nesta investigação.
5. **Considerar auditar outros usos de `[X] * N` no projeto** (o padrão
   `[metadados] * len(...)` pode ter sido copiado ou repetido em outro lugar) —
   não foi feita uma varredura completa do repositório em busca desse padrão.

## 17. Lições aprendidas

- **Scores de similaridade plausíveis não provam que o conteúdo retornado está
  correto.** O bug de metadados só ficou visível quando o *texto* de cada
  resultado foi impresso lado a lado — os números (embeddings/scores) mascaravam
  completamente o problema.
- **Eliminar uma causa de variância pode revelar a próxima.** A investigação
  avançou em camadas: consistência do Pinecone → ruído do juiz → bug de
  metadados. Cada fix tornou o sinal mais "limpo", permitindo enxergar o
  problema seguinte, que antes estava encoberto por ruído maior.
- **"Reduzir a amplitude para quase zero" é um sinal forte de causa
  identificada corretamente** — quando a troca do juiz para `gpt-4o` zerou a
  variância de `context_recall` entre 3 rodadas, isso foi uma confirmação
  praticamente experimental (não apenas plausível) de que aquela causa
  específica era, de fato, ruído do juiz.
- **Um bug de avaliação pode ser, na verdade, um bug de produção.** O
  `gerenciadorvetorial.py` é compartilhado entre o pipeline de avaliação e o
  fluxo real de indexação de editais — o que começou como uma investigação de
  métricas de teste terminou revelando um defeito que afeta usuários reais.
- **Nem todo caso de teste "ruim" é um bug de sistema.** O `caso_06` nunca ia
  pontuar bem em `context_recall` por construção (gabarito negativo) — a
  correção certa não era "consertar o retrieval para esse caso", era reconhecer
  que a métrica não se aplicava a ele e ajustar o desenho do dataset de
  avaliação, não o sistema sob teste.
