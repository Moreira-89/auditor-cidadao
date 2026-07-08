# Avaliação de Desempenho

Para garantir que mudanças no agente (prompt, ferramentas, modelo) não piorem a qualidade das
respostas, o projeto mantém um framework de avaliação automatizado: um **golden dataset** de casos
curados e um pipeline que roda o agente de ponta a ponta contra cada caso e mede três famílias de
métrica independentes.

## O golden dataset

`evaluation/golden_dataset.json` tem 11 casos (reais + sintéticos), cobrindo o mix exigido: empresa
com sanção ativa no CEIS/CNEP (Anomalia H), prazo de publicação irregular (Anomalia F), caso
controle sem anomalia esperada e caso puramente conversacional. Cada caso declara o que se espera
(ferramentas, anomalias, contexto do edital), servindo de gabarito para as métricas.

## As três famílias de métrica

| Métrica | Como é medida | Usa LLM? |
|---|---|---|
| **`aderencia_tools`** | Comparação determinística entre `tools_esperadas` e `tools_chamadas` | Não |
| **`recall_anomalias`** | Reusa o extrator estruturado de produção sobre o laudo e compara os códigos A–I detectados com os esperados | Sim (o mesmo extrator de produção) |
| **RAGAS (`faithfulness`, `context_recall`)** | Mede alucinação e cobertura de contexto nos casos que usam `buscar_contexto_edital` | Sim (juiz `gpt-4o`) |

- **`faithfulness`** — a resposta só afirma coisas sustentadas pelo contexto recuperado, ou inventou
  algo a mais?
- **`context_recall`** — o contexto recuperado cobre a informação necessária (comparado ao gabarito
  do dataset)?

## Decisões de engenharia (trade-offs)

!!! note "RAGAS em vez de um juiz LLM caseiro"
    O plano original previa um único LLM-juiz caseiro (`avaliar.py`/`JulgamentoLLM`) avaliando 4
    métricas. A implementação final diverge conscientemente: usa **RAGAS** (biblioteca validada pela
    comunidade) para `faithfulness`/`context_recall`, mantém `aderencia_tools` como comparação
    **determinística sem LLM** (mais confiável que julgamento subjetivo para esse caso), e
    `recall_anomalias` como fração reaproveitando o extrator já usado em produção. É uma decisão de
    engenharia, não desvio por falta de tempo — vale como resposta para "por que a implementação
    diverge do plano original?".

!!! note "Exclusão do `caso_06` do cálculo de RAGAS"
    O `caso_06` tem `contexto_edital_esperado` como uma afirmação **negativa** ("o edital não traz a
    data de publicação"). O `context_recall` não tem mecanismo para validar ausência de informação
    contra chunks recuperados, então esse caso nunca pontuaria bem nessa métrica — é uma limitação
    da métrica, não do sistema. Foi excluído do RAGAS via um campo próprio no dataset
    (`excluir_do_ragas: true`), mantendo-se normalmente nas demais métricas, em vez de reescrever o
    gabarito.

!!! note "Juiz do RAGAS trocado de `gpt-4o-mini` para `gpt-4o`"
    O `gpt-4o-mini` dava notas inconsistentes para o mesmo contexto recuperado entre execuções
    (comprovado com contexto byte-a-byte idêntico e nota diferente). A troca para `gpt-4o` zerou a
    variância de `context_recall` (amplitude `0.000` em 3 execuções). O custo maior só incide na
    avaliação — esse modelo nunca é chamado por um usuário real.

## O caso do bug de produção

A investigação mais importante do framework não foi sobre um número, foi sobre um bug real. Uma
instabilidade nas métricas RAGAS levou, por camadas, à descoberta de que o `gerenciadorvetorial.py`
— compartilhado entre o pipeline de teste e o fluxo real de indexação — armazenava **todo chunk com
o texto do último chunk do documento**, afetando usuários reais em produção. Os detalhes completos
estão em [Uso de Dados e RAG](rag_dados.md#o-bug-de-producao-que-a-avaliacao-revelou). É a resposta
concreta para "como o framework de avaliação ajudou a encontrar problemas reais, não só medir
números?".

## Resultados consolidados

Após todas as correções, em 6 execuções (3 do pipeline + 3 manuais, mesmo protocolo):

| Métrica | Limiar | Resultado | Veredito |
|---|---|---|---|
| `aderencia_tools` | ≥ 0.70 | **1.00** (estável) | ✅ aprovado |
| `recall_anomalias` | ≥ 0.80 | **1.00** (estável) | ✅ aprovado |
| `faithfulness` | ≥ 0.85 | 0.79–0.88 (oscilante) | ⚠️ instável em torno do limiar |
| `context_recall` | ≥ 0.75 | **0.60** (estável) | ❌ reprovado |

!!! warning "Honestidade sobre o veredito geral"
    O veredito geral (`aprovacao["geral"]`) é **reprovado** na maioria das execuções, única e
    exclusivamente por `context_recall = 0.60` ficar abaixo do limiar. A causa é conhecida e
    documentada: dos 5 casos elegíveis, 2 têm o trecho-alvo posicionalmente distante no documento e
    fora do alcance de `top_k=3` (não aparecem nem em `top_k=50`) — limitação real de recuperação,
    endereçável na V2 com `top_k` maior ou reranking. `faithfulness` também não é uma aprovação
    sólida: oscila em torno do próprio limiar (hipótese não confirmada: variância herdada da
    `temperature=0.1` do agente, usada também na avaliação). Documentar isso honestamente é parte da
    metodologia — o framework serve para expor limitações, não para maquiar números.
