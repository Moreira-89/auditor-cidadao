# Avaliação de Desempenho

Para que mudanças no agente (prompt, ferramentas, modelo) não piorem a qualidade das respostas em
silêncio, o projeto mantém um framework de avaliação automatizado: um **golden dataset** de casos
curados e um pipeline que roda o agente de ponta a ponta contra cada caso e mede quatro métricas com
[`deepeval`](https://deepeval.com/).

O código fica em [`backend/evaluation/`](https://github.com/Moreira-89/auditor-cidadao/tree/main/backend/evaluation),
pacote irmão de `backend/app/` — a avaliação importa do `app`, nunca o contrário. Roda com
`python -m evaluation.runner [ids...]` de dentro de `backend/`.

## O golden dataset

`evaluation/dataset/golden_dataset.json` — uma lista única de casos, validados contra o schema
`Caso` ([`evaluation/dataset/schema.py:20-35`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/dataset/schema.py#L20-L35)),
carregados por `carregar_casos()` (`schema.py:38-40`). O nome do PDF é declarado por caso em
`edital_pdf` e vive em `evaluation/dataset/editais/` — não há mais convenção de nome
(`EDITAIS_DIR / caso.edital_pdf`, `indexacao.py:14,35`), então o `id` do caso e o nome do arquivo
não precisam bater.

**Um dataset, dois `tipo`.** Editais reais têm gabarito de anomalia ambíguo por natureza — não dá
pra saber com certeza, só olhando o texto extraído, se o agente errou ou se foi o gabarito que
errou (ver "Por que os 4 editais reais não cobram anomalia" abaixo). Em vez de manter dois
datasets separados, `Caso.tipo` (`schema.py:14`, `Literal["real", "sintetico"]`) marca o que cada
caso cobra, e `runner.py` roda um `evaluate()` por tipo (`runner.py:91-142`) com listas de métrica
diferentes:

| `tipo` | O que cobra | Editais |
|---|---|---|
| `real` | Retrieval do contexto (`ContextualRecallMetric`) + tool correta | os 4 originais — documentos verdadeiros, PDF real |
| `sintetico` | Anomalia detectada certa (`RecallAnomaliasMetric`) + tool + argumento | 9 casos, um por código do catálogo A–I |

| id | Município | Objeto |
|---|---|---|
| `caso_01_brejao_direcionamento` | São Francisco do Brejão/MA | Eventos culturais — o edital real tem uma cláusula de credenciamento ABVAQ que **parece** direcionamento (B), mas isso não é cobrado aqui, só o retrieval do objeto |
| `caso_02_saoluis_sancao` | São Luís/MA | Dispensa eletrônica para notebooks |
| `caso_03_belem_limpeza` | Belém/PA | Pregão de limpeza e conservação |
| `caso_04_controle` | Miracema/RJ | Dispensa para câmeras de vigilância (caso-controle) |

Suíte `sintetico` — um caso por código do catálogo (ver [Anomalias](anomalias.md)):

| id | Anomalia | Cenário |
|---|---|---|
| `caso_05_sobrepreco_materiais_escolares` | **A** — sobrepreço | Papel sulfite 40% acima da mediana de referência |
| `caso_06_brejao_direcionamento` | **B** — direcionamento | Credenciamento ABVAQ sem relação demonstrada com o objeto (mesma cláusula do `caso_01`, aqui com gabarito de anomalia) |
| `caso_07_piumhi_fracionamento_obras` | **C** — fracionamento | Pavimentação dividida em 2 certames, ~2 meses de intervalo |
| `caso_08_cartel_empresas_endereco_socios` | **D** — indício de conluio | 3 empresas, mesmo endereço/sócios, propostas muito próximas |
| `caso_09_empresa_recente_obra_complexa` | **E** — empresa incompatível | Vencedora de obra de R$ 4,8 mi constituída 7 meses antes do edital |
| `caso_10_barra_do_corda_prazo_insuficiente` | **F** — prazo insuficiente | Sem os 30 dias mínimos entre publicação e sessão |
| `caso_11_reincidencia_empresa_vencedora` | **C + G** — fracionamento + concentração | Uma empresa venceu 64,3% dos certames do órgão em 12 meses, com objetos licitados separadamente apesar de requisitos semelhantes |
| `caso_12_empresa_sancionada_ceis` | **H** — sanção vigente | Vencedora consta no CEIS, adjudicada mesmo assim |
| `caso_13_sintetico_incompatibilidade_cnae` | **I** — CNAE incompatível | Empresa fictícia do ramo gráfico, sem atividade compatível com o objeto (manutenção de climatização); CNPJ deliberadamente inválido |

Cada caso declara o gabarito (`schema.py:20-35`):

- `anomalias_esperadas: list[CodigoAnomalia]` — códigos A–I tipados como `Literal` (`schema.py:10`),
  reaproveitado de `app/agents/prompt.py`; um typo no JSON (ex.: `"J"`) não passa validação em
  silêncio. Vazio nos 4 casos `real` de propósito — ver seção seguinte.
- `tools_esperadas: list[ToolEsperada]` — cada item é `{tool, argumentos_esperados}`
  (`schema.py:17-18`).
- `contexto_edital_esperado` — gabarito textual do objeto do edital, consumido pela
  `ContextualRecallMetric` (ver "As métricas" abaixo).

**Por que os 4 editais reais não cobram anomalia.** `caso_01` e `caso_02` já passaram por isso na
prática: o agente apontou um código a mais do que o gabarito previa (`caso_01`: B + I; `caso_02`:
H + I), e não deu pra decidir com segurança se era over-detection do modelo ou um gabarito
incompleto — o `caso_02` era de fato o segundo (corrigido depois de conferir CNAE/CNPJ reais), mas
o `caso_01` ficou sem veredito claro. Documento real e mensagens de erro reais (Docling variando
extração PDF a PDF) tornam o "gabarito certo" um alvo móvel. Por isso a suíte `real` agora só
audita o que é objetivamente checável num edital de verdade — o agente recuperou o trecho certo do
edital e chamou a tool certa — e toda a detecção de anomalia migrou pra suíte `sintetico`, onde o
gabarito é escrito antes do PDF existir e não tem outra leitura possível.

**Injeção sintética.** `caso.trecho_injetado` (`schema.py:29`) simula um trecho que não existe no
PDF original sem precisar de um edital real que já o contenha — usado hoje só pelo
`caso_06_brejao_direcionamento` (reaproveita o PDF real do `caso_01`, injetando a cláusula ABVAQ
como achado com gabarito de anomalia). `indexar_caso`
([`evaluation/indexacao.py:32-64`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/indexacao.py#L32-L64))
não concatena o trecho só ao texto plano — ele também vira uma **seção sintética** (título
`"TRECHO INJETADO (AVALIAÇÃO)"`, `indexacao.py:55-59`), indo pro MongoDB pelo mesmo caminho de
indexação hierárquica de um edital real. Os 4 casos `real` não usam mais o mecanismo — a injeção de
vencedora/CNPJ é exatamente o tipo de cenário que a suíte `sintetico` assume por inteiro, com
controle total do texto do PDF (ex.: `caso_12`, PDF já nasce com a sanção no corpo do documento).

!!! note "Um caso-controle também tem tool esperada"
    `caso_04_controle` não espera nenhuma anomalia, mas **espera** `buscar_contexto_edital` (com
    `argumentos_esperados: {}`) — o agente precisa consultar o edital pra escrever o relatório
    independente de haver ou não irregularidade. Lista vazia em `tools_esperadas` significaria "esperar
    **zero** chamadas de tool" para a métrica nativa `ToolCorrectnessMetric` (ver abaixo), o que é
    diferente de "não tenho expectativa sobre tools neste caso".

## O harness: mesmo caminho de código da produção

`executar_caso()` ([`evaluation/execucao.py:35-85`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/execucao.py#L35-L85))
chama `run_agent()` ([`app/agents/conversa.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/conversa.py)),
o mesmo ponto de entrada que `POST /conversar-com-auditor/` usa em produção, passando
`PROMPT_RELATORIO_INICIAL` (`app/agents/prompt.py:521`) como se fosse a pergunta do usuário — é
exatamente o que a produção faz quando `inicial: true` (`app/api/endpoints/chat.py:81`). Não existe
um segundo caminho de execução "só para avaliação": o mesmo `astream_events()`, o mesmo grafo, o
mesmo prompt.

O harness consome os eventos de domínio (`TokenGerado`, `ErroNoTurno`, ver `app/agents/eventos.py`)
pra reconstruir o Markdown completo (`execucao.py:39-54`) e lê o checkpoint do LangGraph
(`get_graph().aget_state(...)`, `execucao.py:58`) para os `tool_calls` completos, extraídos do
histórico de mensagens em `execucao.py:65` — `run_agent()` só emite o **nome** da tool no stream
(`FerramentaIniciada`), não os argumentos nem o resultado.

Os códigos de anomalia saem por **regex sobre o Markdown**, sem chamada de LLM. O prompt já obriga
um formato fixo por achado (`app/agents/prompt.py:577`,
`**[ESTADO: CONFIRMADO | INDÍCIO] [NÍVEL DE RISCO: ...] — <código>. <categoria>**`), então ler esse
padrão é ler o dado real, não um proxy:

```python
# evaluation/metricas/recall_anomalias.py:10-18
_PADRAO_ACHADO = re.compile(
    r"\*\*\[ESTADO:\s*(CONFIRMADO|INDÍCIO)\]\s*"
    r"\[NÍVEL DE RISCO:\s*(?:BAIXO|MÉDIO|ALTO|CRÍTICO)\]\s*"
    r"[—-]\s*([A-I])\."
)

def extrair_anomalias(texto_laudo: str) -> list[tuple[str, str]]:
    """Devolve [(codigo, estado), ...] achados no laudo."""
    return [(m.group(2), m.group(1)) for m in _PADRAO_ACHADO.finditer(texto_laudo)]
```

## Por que G-Eval em vez de métricas convencionais (RAGAS, BLEU/ROUGE)

A pergunta que a avaliação precisa responder é semântica, não textual: *"o laudo afirma algo que as
fontes consultadas não sustentam?"* e *"o agente detectou a anomalia certa?"* — não *"o texto gerado
parece com um texto de referência?"*. Isso descarta de saída métricas de sobreposição
n-grama (BLEU, ROUGE, ChrF): elas comparam string contra string, e não existe um "laudo de
referência" único e correto para comparar — dois laudos com redação totalmente diferente podem ser
igualmente corretos, e um laudo com alta sobreposição textual ainda pode alucinar um fato.

Sobra julgamento por LLM. A opção mais comum é o [RAGAS](https://docs.ragas.io/) (`faithfulness`,
`context_recall`), que o projeto usou antes: um LLM-juiz recebe resposta + contexto e devolve uma
nota, sem que o chamador controle o raciocínio que o juiz segue nem a régua de pontuação — o prompt
de julgamento é genérico, interno à biblioteca. Medido neste projeto: 4 rodadas sobre o **mesmo**
golden dataset, sem nenhuma mudança de código entre elas, produziram `context_recall` de
`{0.0, 0.33, 0.67, 1.0}` — a variância vem da ausência de um critério explícito, não do conteúdo
avaliado.

**G-Eval** ataca exatamente esse ponto: em vez de pedir "julgue a qualidade", o chamador escreve os
**passos de raciocínio** que o juiz segue (chain-of-thought fixo) e a **régua de nota** (`Rubric`)
antes de rodar. O juiz tem menos liberdade pra divergir de rodada a rodada porque o critério já está
no prompt, não na "opinião" livre do modelo. A biblioteca [`deepeval`](https://deepeval.com/)
implementa isso pronto (`GEval` + `Rubric`, ver `evaluation/metricas/fidelidade.py`) e ainda pondera
a nota final pela probabilidade dos tokens de saída (`logprobs`) quando o modelo/provider suporta —
mais um fator de estabilidade que não precisou ser implementado à mão.

## As métricas

Comuns aos dois lotes — declaradas nas duas listas de `_metricas_por_tipo` (`runner.py:74-88`):

| Métrica | Limiar | Como é medida | Usa LLM? |
|---|---|---|---|
| **Tool Correctness** | ≥ 0.50 | Nativa do deepeval (`ToolCorrectnessMetric`) — confere só o **nome** da tool chamada contra `expected_tools`, sem exigir ordem | Não |
| **Argumentos da Tool** | ≥ 1.00 | Customizada (`ArgumentosToolMetric`, [`evaluation/metricas/argumentos_tool.py:17-65`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/metricas/argumentos_tool.py#L17-L65)) — subset-match dos argumentos esperados (ex.: `cnpj`), normalizando dígitos (`argumentos_tool.py:5-14`) | Não |
| **Fidelidade** | ≥ 0.60 | `GEval` com `Rubric` de 5 níveis ([`evaluation/metricas/fidelidade.py:7-59`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/metricas/fidelidade.py#L7-L59)) — o laudo só afirma o que as saídas das tools sustentam, sem inventar nem extrapolar | Sim (juiz) |

Uma métrica por `tipo` (`_metricas_por_tipo`, `runner.py:74-88`):

| `tipo` | Métrica | Limiar | Como é medida | Usa LLM? |
|---|---|---|---|---|
| `real` | **Cobertura de Contexto** | ≥ 0.70 | Nativa do deepeval (`ContextualRecallMetric`) — quebra `contexto_edital_esperado` (`expected_output`) em sentenças e verifica quantas têm sustentação em `retrieval_context` (o que `buscar_contexto_edital` de fato devolveu) | Sim (juiz) |
| `sintetico` | **Recall de Anomalias** | ≥ 0.65 | Customizada (`RecallAnomaliasMetric`, [`evaluation/metricas/recall_anomalias.py:18-53`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/metricas/recall_anomalias.py#L18-L53)) — F1 entre os códigos A–I esperados e os extraídos por regex do Markdown. Caso-controle sem anomalia esperada → binário (qualquer código apontado é falso positivo) | Não |

!!! note "`ContextualRecallMetric` não é G-Eval"
    É a exceção à régua da seção anterior — usa o algoritmo "veredito por sentença, depois
    proporção" (mesma família do `context_recall` do RAGAS), sem `evaluation_steps`/`Rubric`. A
    diferença pro RAGAS é que o deepeval força a saída do juiz por schema (Pydantic), o que tende a
    ser mais estável que o prompt solto do RAGAS — mas, sem rubric, o placar dela deve ser lido com
    mais desconfiança que o da Fidelidade até se acumular evidência de rodadas repetidas. Foi aceita
    mesmo assim porque reaproveita o gabarito `contexto_edital_esperado` (que já existia sem
    consumidor) sem escrever uma métrica nova do zero.

**Por que duas métricas de tool em vez de uma.** `ToolCorrectnessMetric` compara `input_parameters`
por **igualdade exata** quando `ToolCallParams.INPUT_PARAMETERS` está em `evaluation_params` — isso
quebraria os casos com `argumentos_esperados: {}` (ex.: `buscar_contexto_edital`, cujo argumento
real é uma pergunta livre e nunca deveria ser cobrado). `ArgumentosToolMetric` existe só para os
argumentos que **importam de verdade** (o `cnpj` que uma tool de sanção/cadastro recebeu), com
subset-match — a chamada real pode ter mais campos que o esperado, só não pode faltar o que importa.

O juiz (Fidelidade e Cobertura de Contexto) é configurável por `AVALIADOR_MODEL` /
`AVALIADOR_TEMPERATURE` (`app/config/settings.py`, default `gpt-4o` / `0.0` — `temperature=0`
reduz mais uma fonte de variância no julgamento). `construir_juiz` (`evaluation/juiz.py`) lê o
prefixo `provider:model` — mesma convenção do `LLM_MODEL` — e monta `OpenAIModel` (default) ou
`GeminiModel` (prefixo `gemini:`, exige `GOOGLE_API_KEY`). O motivo de ter um segundo provider:
o tier gratuito da OpenAI tem TPM baixo (30k/min) e um único caso real grande já pode pedir mais
que isso numa chamada só — trocar de juiz é bem mais direto que forçar o contexto a caber.

### F1: como o Recall de Anomalias calcula a nota

`RecallAnomaliasMetric` compara os códigos A–I extraídos do laudo (`extrair_anomalias`,
`recall_anomalias.py:13-15`) contra `anomalias_esperadas` do gabarito, com duas perguntas
diferentes sobre a mesma lista:

- **Precisão** — "das anomalias que o agente apontou, quantas estavam certas?" Mede **falso
  positivo**: um agente que aponta as 9 letras do catálogo em todo edital, sem critério, nunca
  erraria por *recall* (acha tudo, óbvio — chutou tudo), mas a precisão baixa entrega o problema.
- **Recall** — "das anomalias que o gabarito espera, quantas o agente achou?" Mede **falso
  negativo**: um agente caladão, que só aponta quando tem certeza absoluta, pode ter precisão
  perfeita (nunca erra o que fala) mas deixar passar anomalias reais — é o recall baixo que entrega
  isso.

Nenhuma das duas sozinha é suficiente (dá pra "trapacear" cada uma isoladamente, como nos exemplos
acima), então a métrica combina as duas num só número — o **F1**, a média harmônica entre elas
(`recall_anomalias.py:39-44`):

```
F1 = 2 × (precisão × recall) / (precisão + recall)
```

Diferente de uma média simples, o F1 **penaliza desequilíbrio**: se qualquer uma das duas cai a
zero, F1 vai a zero junto, mesmo que a outra seja perfeita — não dá pra compensar "não achei nada"
com "não menti nada".

**Exemplo real, `caso_11_reincidencia_empresa_vencedora`** (gabarito `["C", "G"]`, agente apontou
só `["G"]`):

- Precisão = 1/1 = **1.0** — tudo que ele disse (`G`) estava certo, não inventou nada.
- Recall = 1/2 = **0.5** — achou 1 das 2 anomalias esperadas.
- F1 = 2 × (1.0 × 0.5) / (1.0 + 0.5) = **0.667** — é esse número que é comparado contra o
  `threshold` (`0.65`, `recall_anomalias.py:21`) pra decidir passou/reprovou.

### O rubric de Fidelidade

```python
# evaluation/metricas/fidelidade.py:35-56
rubric=[
    Rubric(score_range=(5, 5), expected_outcome="Todas as afirmações sustentadas."),
    Rubric(score_range=(4, 4), expected_outcome="1 não sustentada, detalhe menor."),
    Rubric(score_range=(3, 3), expected_outcome="1 não sustentada que afeta um achado."),
    Rubric(score_range=(2, 2), expected_outcome="2+ não sustentadas, ou 1 que inventa dado central."),
    Rubric(score_range=(1, 1), expected_outcome="Achado sem evidência em nenhuma fonte."),
]
```

Os `evaluation_steps` (`fidelidade.py:18-33`) mandam o juiz listar cada afirmação factual do laudo,
procurar sustentação em `CONTEXT` (as saídas de tool, `SingleTurnParams.CONTEXT`) e marcar cada uma
como sustentada ou não — uma afirmação que **extrapola** a fonte (fonte diz "3 sanções", laudo diz
"sanções recorrentes e graves") conta como não sustentada, mesmo sem inventar um dado novo. Validado
rodando a métrica isolada contra um caso sintético de extrapolação (score 0.32, abaixo do limiar) e
um caso fiel (score 1.0) — a régua discrimina de fato, não dá nota alta por padrão.

## O pipeline

`runner.py` roda os casos **sequencialmente** (rate limit dos LLMs, logs legíveis). Por caso
(`_montar_test_case`, `runner.py:49-68`):

```
preparar_ambiente()     → grafo montado fora do lifespan, mas com montar_tools()
                          (execucao.py:27-33) — nativas + MCP + aplicar_cache,
                          igual à produção. LLM_TEMPERATURE = 0.0.
  indexar_caso(caso)    → Docling → seção sintética (se houver trecho) → MongoDB
  executar_caso(edital) → run_agent() (mesmo caminho da produção) + leitura do
                          checkpoint pros tool_calls
  finally: limpar_edital(edital_id)
```

`montar_tools()` exige um client Redis — `_rodar` abre um só pra rodada inteira
(`abrir_client_redis`, `runner.py:100`), num **banco lógico dedicado**
(`REDIS_DB_AVALIACAO = 1`, `runner.py:31-34`) pra nunca ler nem escrever em cima de uma
entrada de cache real. Esse db é limpo (`flushdb`, `runner.py:103`) antes de cada
rodada — sem isso, um caso corrigido no dataset continuaria batendo num resultado
cacheado da rodada anterior e a mudança não apareceria na próxima execução.

Depois de rodar todos os casos, `_rodar` (`runner.py:91-142`) monta um `LLMTestCase` por caso e
chama `deepeval.evaluate(test_cases=..., metrics=...)` **uma vez por `tipo`** (`runner.py:124-138`)
— não uma vez só: `real` e `sintetico` cobram métricas diferentes (ver "As métricas" acima), e o
`evaluate()` do deepeval só aceita uma lista de métrica global por chamada, não uma por
`test_case`. Cada `evaluate()` grava seu próprio
`evaluation/resultados/test_run_<timestamp>.json`; `_rodar` sai com `sys.exit(1)` (`runner.py:142`)
se algum caso, em qualquer lote, reprovou em qualquer métrica.

## Rodando

```bash
cd backend
python -m evaluation.runner              # todos os casos
python -m evaluation.runner caso_02_saoluis_sancao   # um caso
```

Precisa de `OPENAI_API_KEY`, `MONGODB_URI` (o mesmo cluster Atlas da produção) e agora também
`REDIS_URI` + Node/npx no PATH — `preparar_ambiente` chama o mesmo `montar_tools()` da produção,
que conecta ao MCP LiciNexus e monta o cache Redis das tools (ver "O pipeline" acima).
`DEEPEVAL_TELEMETRY_OPT_OUT=1` mantém a rodada 100% local, sem enviar nada pra Confident AI (ver
[Variáveis de ambiente](../operacional/variaveis_ambiente.md)).

## Pontos cegos — onde a avaliação diverge da produção

!!! warning "Checkpointer em memória, não o Redis persistente da produção"
    `preparar_ambiente` (`execucao.py:27-33`) usa `InMemorySaver()` em vez do
    `abrir_checkpointer()` (Redis) que a produção usa (`app/api/lifespan.py:37`) — cada rodada de
    avaliação começa com histórico de conversa zerado, e nada testa a camada de persistência entre
    turnos. Um bug que só existisse ali passaria pelo golden dataset inteiro sem ser pego.

Até a rodada anterior, a avaliação também não exercitava as tools do MCP nem passava pelo
`aplicar_cache` — corrigido junto com a inclusão do Redis (ver "O pipeline"), depois que o
golden dataset expôs isso: casos sintéticos que esperavam `search_licitacoes`/
`list_licitacao_resultados` (só existem via MCP) reprovavam de forma estrutural, não por erro do
agente.

## O que o G-Eval revela, além do número

Ler o `reason` de cada métrica no relatório do `deepeval` é diagnóstico por si só — não só "quanto",
mas "por quê". A métrica de Fidelidade aponta exatamente qual afirmação do laudo não tem base na
fonte; o `Tool Correctness` mostra a lista exata de tools que faltaram ou sobraram. Isso é
informação acionável direto no `SYSTEM_PROMPT` e nas docstrings das tools (é o texto que o LLM lê
para decidir o que buscar e como reportar) — não só um número pra decidir aprovado/reprovado.

## Estado atual do veredito

!!! success "Suíte `real`: 4/4 — Tool Correctness, Argumentos e Cobertura de Contexto em 1.0, Fidelidade 0.89-0.99"
    Primeira rodada depois do MCP + Redis entrarem na avaliação (ver "O pipeline"): os 4 casos
    reais passaram em todas as métricas. O `caso_03` (Fidelidade 0.889, o mais baixo do lote) ainda
    mostra sinal do problema de retrieval documentado em
    [Uso de Dados e RAG](rag_dados.md#limitacoes-conhecidas-do-retrieval) — mas não reprovou.

!!! info "Suíte `sintetico`: maioria passa; falhas explicadas caso a caso, não um padrão só"
    Rodando os 9 casos (um por código A-I), as reprovações tiveram causas diferentes, todas
    investigadas com evidência (não só aceitas por "é assim mesmo"): `tools_esperadas` cobrando
    `search_licitacoes`/`buscar_informacao_web`/`list_licitacao_resultados` em casos cujo PDF já é
    autocontido (o agente não tem necessidade funcional de verificar externamente algo que já está
    resolvido no texto — corrigido removendo essas tools do gabarito) e um gabarito incompleto no
    `caso_11` (o PDF continha evidência textual de fracionamento (C) além da reincidência (G)
    esperada — corrigido para `["C", "G"]`).

**Duas mudanças recentes ainda sem rodada de referência pós-implementação:**

- **RAG small-to-big reintroduzido** (ver "Padrão pai-filho" em [Uso de Dados e RAG](rag_dados.md)):
  `buscar_contexto_edital` agora devolve a seção inteira do filho vencedor, não só o pedaço de 200
  palavras — deve reduzir o número de chamadas de tool por caso (hoje 10-16 por caso na suíte
  sintética) e pode melhorar a Fidelidade em casos como o `caso_03`. Ainda não medido depois da
  mudança.
- **`RecallAnomaliasMetric.threshold`** ajustado de `0.8` pra `0.65` (`recall_anomalias.py:21`) —
  tolera o agente detectar N-1 de N anomalias esperadas num caso multi-anomalia sem reprovar por
  isso, reconhecendo que qual anomalia secundária o agente nota numa passada varia entre rodadas
  (não-determinismo do LLM mesmo em temperatura baixa).
