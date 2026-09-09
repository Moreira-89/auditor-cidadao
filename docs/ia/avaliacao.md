# Avaliação de Desempenho

Para que mudanças no agente (prompt, ferramentas, modelo) não piorem a qualidade das respostas em
silêncio, o projeto mantém um framework de avaliação automatizado: um **golden dataset** de casos
curados e um pipeline que roda o agente de ponta a ponta contra cada caso e mede quatro métricas com
[`deepeval`](https://deepeval.com/).

O código fica em [`backend/evaluation/`](https://github.com/Moreira-89/auditor-cidadao/tree/main/backend/evaluation),
pacote irmão de `backend/app/` — a avaliação importa do `app`, nunca o contrário. Roda com
`python -m evaluation.runner [ids...]` de dentro de `backend/`.

## O golden dataset

`evaluation/dataset/casos/caso_*.json`, validados contra o schema `Caso`
([`evaluation/dataset/schema.py:19-34`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/dataset/schema.py#L19-L34)),
carregados por `carregar_casos()` (`schema.py:37`). O `id` do caso e o nome do PDF em `editais/`
usam o mesmo número (`caso_02_saoluis_sancao` → `caso_02.pdf`):

| id | Município | Anomalia esperada | Injeção sintética |
|---|---|---|---|
| `caso_01_brejao_direcionamento` | São Francisco do Brejão/MA | **B** — direcionamento (exigência de credenciamento ABVAQ sem previsão de equivalência, cláusula **real** do edital) | — |
| `caso_02_saoluis_sancao` | São Luís/MA | **H** — sanção vigente | vencedora sintética (CNPJ real sancionado, CNAE de comércio compatível com o objeto) |
| `caso_03_belem_limpeza` | Belém/PA | **H + I** — sanção + CNAE de comércio incompatível com serviço de limpeza | vencedora sintética (mesmo CNPJ) |
| `caso_04_controle` | Miracema/RJ | *nenhuma* | — (caso-controle: o agente não pode inventar irregularidade) |

Cada caso declara o gabarito, três campos (`schema.py:29-34`):

- `anomalias_esperadas: list[CodigoAnomalia]` — códigos A–I tipados como `Literal` (`schema.py:13`),
  reaproveitado de `app/agents/prompt.py`; um typo no JSON (ex.: `"J"`) não passa validação em
  silêncio.
- `tools_esperadas: list[ToolEsperada]` — cada item é `{tool, argumentos_esperados}`
  (`schema.py:15-16`).
- `contexto_edital_esperado` — referência textual do trecho relevante do edital; ainda sem métrica
  que o consuma (gabarito pronto para uma futura métrica de cobertura de contexto).

**Injeção sintética.** `caso.trecho_injetado` (`caso_02.json`, `caso_03.json`) simula uma vencedora
com sanção sem precisar de um edital real que já a contenha. `indexar_caso`
([`evaluation/indexacao.py:51-68`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/indexacao.py#L51-L68))
não concatena o trecho ao texto plano — ele vira uma **seção sintética** (título
`"TRECHO INJETADO (AVALIAÇÃO)"`, `indexacao.py:60-61`) e um filho, indo pro MongoDB pelo mesmo
caminho de indexação hierárquica de um edital real (ver [Uso de Dados e RAG](rag_dados.md)). O
`edital_id` gravado é `eval-<caso.id>` (`indexacao.py:73`), casado com o `thread_id` que
`executar_caso` usa para filtrar o RAG.

!!! note "Um caso-controle também tem tool esperada"
    `caso_04_controle` não espera nenhuma anomalia, mas **espera** `buscar_contexto_edital` (com
    `argumentos_esperados: {}`) — o agente precisa consultar o edital pra escrever o relatório
    independente de haver ou não irregularidade. Lista vazia em `tools_esperadas` significaria "esperar
    **zero** chamadas de tool" para a métrica nativa `ToolCorrectnessMetric` (ver abaixo), o que é
    diferente de "não tenho expectativa sobre tools neste caso".

## O harness: mesmo caminho de código da produção

`executar_caso()` ([`evaluation/execucao.py:37-92`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/execucao.py#L37-L92))
chama `run_agent()` ([`app/agents/conversa.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/conversa.py)),
o mesmo ponto de entrada que `POST /conversar-com-auditor/` usa em produção, passando
`PROMPT_RELATORIO_INICIAL` (`app/agents/prompt.py:521`) como se fosse a pergunta do usuário — é
exatamente o que a produção faz quando `inicial: true` (`app/api/endpoints/chat.py:81`). Não existe
um segundo caminho de execução "só para avaliação": o mesmo `astream_events()`, o mesmo grafo, o
mesmo prompt.

O harness consome os eventos de domínio (`TokenGerado`, `ErroNoTurno`, ver `app/agents/eventos.py`)
pra reconstruir o Markdown completo (`execucao.py:53-58`) e lê o checkpoint do LangGraph
(`get_graph().aget_state(...)`, `execucao.py:65`) para os `tool_calls` completos — `run_agent()`
só emite o **nome** da tool no stream (`FerramentaIniciada`), não os argumentos nem o resultado.

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

## As quatro métricas

| Métrica | Limiar | Como é medida | Usa LLM? |
|---|---|---|---|
| **Tool Correctness** | ≥ 0.50 | Nativa do deepeval (`ToolCorrectnessMetric`, `evaluation/runner.py:70`) — confere só o **nome** da tool chamada contra `expected_tools`, sem exigir ordem | Não |
| **Argumentos da Tool** | ≥ 1.00 | Customizada (`ArgumentosToolMetric`, [`evaluation/metricas/argumentos_tool.py:17-65`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/metricas/argumentos_tool.py#L17-L65)) — subset-match dos argumentos esperados (ex.: `cnpj`), normalizando dígitos (`argumentos_tool.py:5-14`) | Não |
| **Recall de Anomalias** | ≥ 0.80 | Customizada (`RecallAnomaliasMetric`, [`evaluation/metricas/recall_anomalias.py:21-66`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/metricas/recall_anomalias.py#L21-L66)) — F1 entre os códigos A–I esperados e os extraídos por regex do Markdown. Caso-controle sem anomalia esperada → binário (qualquer código apontado é falso positivo) | Não |
| **Fidelidade** | ≥ 0.60 | `GEval` com `Rubric` de 5 níveis ([`evaluation/metricas/fidelidade.py:7-59`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/metricas/fidelidade.py#L7-L59)) — o laudo só afirma o que as saídas das tools sustentam, sem inventar nem extrapolar | Sim (juiz) |

**Por que duas métricas de tool em vez de uma.** `ToolCorrectnessMetric` compara `input_parameters`
por **igualdade exata** quando `ToolCallParams.INPUT_PARAMETERS` está em `evaluation_params` — isso
quebraria os casos com `argumentos_esperados: {}` (ex.: `buscar_contexto_edital`, cujo argumento
real é uma pergunta livre e nunca deveria ser cobrado). `ArgumentosToolMetric` existe só para os
argumentos que **importam de verdade** (o `cnpj` que uma tool de sanção/cadastro recebeu), com
subset-match — a chamada real pode ter mais campos que o esperado, só não pode faltar o que importa.

O juiz da Fidelidade é configurável por `AVALIADOR_MODEL` / `AVALIADOR_TEMPERATURE`
(`app/config/settings.py`, default `gpt-4o` / `0.0` — `temperature=0` reduz mais uma fonte de
variância no julgamento).

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
(`_montar_test_case`, `runner.py:34-53`):

```
preparar_ambiente()     → grafo montado fora do lifespan: só as 4 TOOLS_NATIVAS,
                          sem MCP, sem aplicar_cache. LLM_TEMPERATURE = 0.0.
  indexar_caso(caso)    → Docling → seção sintética (se houver trecho) → MongoDB
  executar_caso(edital) → run_agent() (mesmo caminho da produção) + leitura do
                          checkpoint pros tool_calls
  finally: limpar_edital(edital_id)
```

Depois de rodar todos os casos, `_rodar` (`runner.py:56-92`) monta um `LLMTestCase` por caso e chama
`deepeval.evaluate(test_cases=..., metrics=...)` (`runner.py:77-87`) uma vez só — o relatório
(score/threshold/motivo por métrica, agregado por métrica) é todo do `deepeval`. `evaluate()` grava
`evaluation/resultados/test_run_<timestamp>.json` com o resultado completo; `_rodar` sai com
`sys.exit(1)` (`runner.py:92`) se algum caso reprovou em qualquer métrica.

## Rodando

```bash
cd backend
python -m evaluation.runner              # todos os casos
python -m evaluation.runner caso_02_saoluis_sancao   # um caso
```

Precisa de `OPENAI_API_KEY` e `MONGODB_URI` (o mesmo cluster Atlas da produção). **Não** precisa de
Redis nem de Node/MCP — o grafo é montado com `InMemorySaver` e só as 4 tools nativas.
`DEEPEVAL_TELEMETRY_OPT_OUT=1` mantém a rodada 100% local, sem enviar nada pra Confident AI (ver
[Variáveis de ambiente](../operacional/variaveis_ambiente.md)).

## Pontos cegos — onde a avaliação diverge da produção

!!! warning "Só exercita as 4 tools nativas, sem MCP nem cache"
    `preparar_ambiente` (`execucao.py:26-35`) monta o grafo com `TOOLS_NATIVAS`, sem as 11 tools do
    PNCP (MCP) e sem a camada `aplicar_cache`. Um bug que só existisse dentro de `aplicar_cache`
    passaria pelo golden dataset inteiro sem ser pego — "o golden dataset passou" não é prova de que
    o caminho de produção com cache e MCP também passaria.

## O que o G-Eval revela, além do número

Ler o `reason` de cada métrica no relatório do `deepeval` é diagnóstico por si só — não só "quanto",
mas "por quê". A métrica de Fidelidade aponta exatamente qual afirmação do laudo não tem base na
fonte; o `Tool Correctness` mostra a lista exata de tools que faltaram ou sobraram. Isso é
informação acionável direto no `SYSTEM_PROMPT` e nas docstrings das tools (é o texto que o LLM lê
para decidir o que buscar e como reportar) — não só um número pra decidir aprovado/reprovado.

## Estado atual do veredito

!!! danger "Reprovado — `caso_01` (cláusula ABVAQ) e parte do `caso_03` continuam sem detecção"
    Última rodada de referência: `Tool Correctness` 4/4, `Argumentos da Tool` 4/4, `Recall de
    Anomalias` 2/4 (média 0.67), `Fidelidade` 4/4 (média ~0.99). Pass rate geral: 1/4 casos com
    **todas** as métricas passando.

    O `caso_01` não acha a cláusula ABVAQ (score 0.0) e o `caso_03` só acha a sanção (H), não a
    incompatibilidade cadastral (I) — causa é retrieval, não a avaliação em si: o texto embedado do
    filho não carrega o caminho da seção, e `TableItem` nunca é fatiado (ver "Limitações conhecidas
    do retrieval" em [Uso de Dados e RAG](rag_dados.md#limitacoes-conhecidas-do-retrieval)).
