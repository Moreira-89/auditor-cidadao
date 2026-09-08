# Avaliação de Desempenho

Para que mudanças no agente (prompt, ferramentas, modelo, pipeline de extração) não piorem a
qualidade das respostas em silêncio, o projeto mantém um framework de avaliação automatizado: um
**golden dataset** de casos curados e um pipeline que roda o agente de ponta a ponta contra cada
caso e mede duas métricas.

O código fica em [`backend/evaluation/`](https://github.com/Moreira-89/auditor-cidadao/tree/main/backend/evaluation),
pacote irmão de `backend/app/` (não vive dentro dele — a avaliação importa do `app`, nunca o
contrário). Roda com `python -m evaluation.runner [ids...]` de dentro de `backend/`.

## O golden dataset

`evaluation/dataset/casos/caso_*.json` — **4 casos** (`carregar_casos` faz glob e valida cada um
contra o schema `Caso`):

| id | Município | Anomalia esperada | Injeção sintética |
|---|---|---|---|
| `caso_01_brejao_direcionamento` | São Francisco do Brejão/MA | **B** — direcionamento (exigência de credenciamento ABVAQ sem previsão de equivalência, cláusula **real** do edital) | — |
| `caso_02_saoluis_sancao` | São Luís/MA | **H** — sanção vigente | vencedora sintética (CNPJ real sancionado, CNAE de comércio compatível com o objeto) |
| `caso_03_belem_limpeza` | Belém/PA | **H + I** — sanção + CNAE de comércio incompatível com serviço de limpeza | vencedora sintética (mesmo CNPJ) |
| `caso_04_controle` | Miracema/RJ | *nenhuma* | — (caso-controle: o agente não pode inventar irregularidade) |

Cada caso declara o gabarito: `anomalias_esperadas` (códigos A–I) e `tools_esperadas`
(`{tool, argumentos_esperados}`). O campo `contexto_edital_esperado` continua no schema mas não é
consumido por nenhuma métrica hoje (ver "RAGAS removido" abaixo) — fica pronto para quando entrar
uma métrica determinística de recuperação.

**Injeção sintética.** `trecho_injetado` permite testar um cenário (uma vencedora com sanção) sem
precisar de um edital real que já o contenha. `indexar_caso`
([`evaluation/indexacao.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/indexacao.py))
não concatena o trecho ao texto plano — ele entra como uma **seção sintética**
(`"TRECHO INJETADO (AVALIAÇÃO)"`) no `EditalExtraido`, para virar um chunk indexado no MongoDB e
ficar recuperável pelo RAG como qualquer outra cláusula. O `edital_id` do caso é `eval-<caso.id>`,
casado com o `thread_id` que `execucao.py` usa (senão o filtro por `edital_id` deixaria a busca da
avaliação inócua).

## As duas métricas

Limiares em [`evaluation/aprovacao.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/evaluation/aprovacao.py)
(`LIMIARES`). O veredito geral é aprovado só se **todas** passarem.

| Métrica | Limiar | Como é medida | Usa LLM? |
|---|---|---|---|
| **`aderencia_tools`** | ≥ 0.70 | Recall determinístico: `1 − faltantes/esperadas`. O CNPJ é normalizado só a dígitos antes de comparar (a IA manda `"47.417.848/0001-84"`, o gabarito `"47417848000184"`) | Não |
| **`recall_anomalias`** | ≥ 0.80 | **F1** (precisão + recall) entre os códigos A–I esperados e os detectados no laudo estruturado. Falso positivo (apontar a Anomalia I num edital de notebook) derruba o score. Caso-controle sem anomalia esperada → só precisão | Sim (extrator dedicado) |

## RAGAS removido

O framework já teve duas métricas adicionais via RAGAS (`faithfulness`, `context_recall`), com um
juiz LLM (`gpt-4o`) comparando o contexto recuperado contra um gabarito. Foram removidas: em 4
rodadas de avaliação sobre o **mesmo** golden dataset, o `context_recall` produziu valores
`{0.0, 0.33, 0.67, 1.0}` sem nenhuma mudança de código entre elas — instabilidade de julgamento LLM,
não sinal de regressão real. Um agravante concreto: o juiz truncava o contexto em 3000 caracteres
antes de julgar, enquanto o RAG (antes da simplificação descrita em
[Uso de Dados e RAG](rag_dados.md)) chegou a devolver 189 mil caracteres num único caso — a métrica
julgava uma fração pequena do que o agente via de verdade.

Ficou só `aderencia_tools` (recall puro, sem julgamento de precisão) e `recall_anomalias` — nenhuma
das duas mede diretamente a qualidade da recuperação vetorial. Candidatas determinísticas para o
próximo bloco: uma métrica de âncora (a string-chave do gabarito aparece no contexto recuperado?),
posição do primeiro chunk relevante (MRR) e um guarda-corpo de tamanho de contexto.

## O pipeline

`runner.py` roda os casos **sequencialmente** de propósito (rate limit dos LLMs, logs legíveis).
Por caso:

```
preparar_ambiente()          → grafo montado fora do lifespan: só as 4 TOOLS_NATIVAS,
                               sem MCP, sem aplicar_cache. LLM_TEMPERATURE = 0.0.
  indexar_caso(caso)         → Docling → seção sintética (se houver trecho) →
                               MongoDB (chunks_edital, edital_id isolado por caso)
  executar_caso(edital)      → gerar_relatorio_inicial (relatorio.py): grafo.ainvoke() +
                               2ª chamada de LLM → RelatorioInicial; lê as mensagens do checkpoint
  avaliar_aderencia / avaliar_recall_anomalias
  finally: limpar_edital(edital_id)   # apaga os chunks deste caso no Mongo
```

Ao fim, grava `evaluation/resultados/avaliacao_<timestamp>.json` (todas as métricas, por caso e
agregadas) e imprime o resumo de `formatar_relatorio`:

```text
============================================================
                   RESULTADO DA AVALIAÇÃO
============================================================
  aderencia_tools  : 1.000  (mínimo 0.70)  [OK]     APROVADO
  recall_anomalias : 0.667  (mínimo 0.80)  [FALHOU] REPROVADO
------------------------------------------------------------
  VEREDITO GERAL: [FALHOU] REPROVADO
============================================================
```

## Rodando

```bash
cd backend
python -m evaluation.runner              # todos os casos
python -m evaluation.runner caso_02_saoluis_sancao   # um caso
```

Precisa de `OPENAI_API_KEY` e `MONGODB_URI` (o mesmo cluster Atlas da produção — a avaliação usa o
mesmo pipeline de indexação). **Não** precisa de Redis nem de Node/MCP — o grafo é montado com
`InMemorySaver` e só as 4 tools nativas.

`TOP_K_EDITAL` (env var, default 5) vale para a avaliação também.

## Pontos cegos — onde a avaliação diverge da produção

!!! warning "Só exercita as 4 tools nativas, sem MCP nem cache"
    `preparar_ambiente` monta o grafo com `TOOLS_NATIVAS`, sem as 11 tools do PNCP (MCP) e sem a
    camada `aplicar_cache`. Isso já mordeu: a migração de `InjectedState` para `ToolRuntime`
    introduziu um bug que só aparecia **dentro** de `aplicar_cache`, e o golden dataset
    passou normalmente nas rodadas feitas durante a migração — nunca chega perto do código que
    quebrou. "O golden dataset passou" não é prova de que nada quebrou.

!!! note "`ainvoke` no harness, `astream_events` na produção"
    A avaliação roda o turno via `grafo.ainvoke()` (`relatorio.py`), a produção via
    `astream_events()` (`run_agent`). Mesmo grafo, mesmo `PROMPT_RELATORIO_INICIAL`, mesmo envelope,
    mesmas tools — a diferença é só de entrega (o harness precisa do texto completo de uma vez para
    o extrator). As *decisões* do agente são idênticas.

!!! note "A extração estruturada é do harness, não um espelho da produção"
    Produção **não estrutura** o laudo — o relatório automático é só um turno de Markdown
    streamado. O `recall_anomalias` precisa de códigos A–I para pontuar, então
    `gerar_relatorio_inicial` faz uma 2ª chamada de LLM (o *extrator*, `PROMPT_EXTRATOR_INICIAL` →
    `RelatorioInicial`) sobre o Markdown do agente. Isso continua sendo um proxy válido de "o agente
    detectou a anomalia" — produção streama o mesmo texto —, mas o extrator hoje é um componente da
    avaliação (ver [Relatório automático e extração do laudo](extracao_laudo.md)).

## O caso do bug de produção

A investigação mais importante do framework não foi sobre um número — foi um bug real, descoberto
por uma instabilidade de métrica ainda na época do RAGAS. Detalhes em
[Uso de Dados e RAG](rag_dados.md#o-bug-de-producao-que-a-avaliacao-revelou). É a resposta concreta
para "como a avaliação ajudou a achar problema real, não só medir número?".

## Estado atual do veredito

!!! danger "Reprovado — o caso_01 (cláusula ABVAQ) segue sem ser detectado"
    A última rodada (pós-migração para MongoDB, sem RAGAS): `aderencia_tools` 1.000, `recall_anomalias`
    0.667 — reprovado pelo limiar de 0.80. O `caso_01` marca 0.0: a cláusula que exige credenciamento
    ABVAQ nunca aparece no contexto recuperado, em nenhuma rodada testada até agora.

    Duas causas identificadas, ainda não corrigidas (fora do escopo da migração de banco): o texto
    embedado de cada chunk é o texto cru do bloco, sem o caminho da seção (uma linha de tabela não
    carrega sinal de que é sobre qualificação técnica); e `TableItem` nunca é fatiado, então uma
    tabela inteira vira um único vetor diluído. Ver "Limitações conhecidas do retrieval" em
    [Uso de Dados e RAG](rag_dados.md).
