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

**Exemplo real** (`caso_01`, truncado — o campo completo `contexto_edital_esperado` é mais longo):

```json
{
  "id": "caso_01",
  "descricao": "São Luís/MA — sanção CEIS/CNEP vigente da empresa vencedora fictícia na dispensa de notebooks",
  "categoria": "hibrido",
  "estado": "Maranhão (MA)",
  "municipio": "São Luís",
  "cnpjs": ["38504819000169"],
  "caminho_pdf": "evaluation/editais_teste/edital_saoluis.pdf",
  "trecho_injetado": "[Trecho sintetizado para fins de teste — não consta do edital original] Resultado da Fase de Lances: sagrou-se vencedora do certame uma empresa, CNPJ 38.504.819/0001-69, classificada em primeiro lugar com valor total de R$ 58.400,00 para o fornecimento dos 09 notebooks.",
  "pergunta": "Audite essa empresa e verifique se há alguma sanção que a impeça de contratar com o poder público.",
  "tools_esperadas": [
    {"tool": "consultar_sancoes_empresa", "argumentos_esperados": {"cnpj": "38504819000169"}}
  ],
  "anomalias_esperadas": ["H"],
  "resposta_esperada": "laudo",
  "score_minimo_esperado": 0.9
}
```

`trecho_injetado` é concatenado ao texto extraído do PDF antes da indexação — permite testar um
cenário específico (aqui, uma sanção) sem precisar de um edital real que já contenha esse dado.
`tools_esperadas` e `anomalias_esperadas` são o gabarito usado por `aderencia_tools` e
`recall_anomalias`, respectivamente (ver abaixo).

## As três famílias de métrica

| Métrica | Como é medida | Usa LLM? |
|---|---|---|
| **`aderencia_tools`** | Comparação determinística entre `tools_esperadas` e `tools_chamadas` | Não |
| **`recall_anomalias`** | Reusa o mesmo mecanismo de extração estruturada de produção (`with_structured_output` + `CATALOGO_ANOMALIAS`) sobre o laudo e compara os códigos A–I detectados com os esperados | Sim (extrator dedicado, réplica do de produção) |
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
    `recall_anomalias` como fração reaproveitando o mesmo mecanismo de extração estruturada da
    produção (`PROMPT_EXTRATOR`/`RespostaLaudo`, em [`app/agents/prompt.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/prompt.py)/[`app/api/schemas/laudo.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/schemas/laudo.py) —
    réplica dedicada à avaliação, ver [Relatório Automático e Extração de Laudo](extracao_laudo.md)).
    É uma decisão de engenharia, não desvio por falta de tempo — vale como resposta para "por que a
    implementação diverge do plano original?".

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

## Rodando o pipeline

```bash
pip install -r requirements.txt -r requirements-dev.txt   # requirements-dev.txt tem ragas
python -m evaluation.pipeline_avaliacao
```

Precisa das mesmas chaves de API que a aplicação principal (`OPENAI_API_KEY`, `PINECONE_API_KEY`
— ver [Variáveis de ambiente](../operacional/variaveis_ambiente.md)); não precisa de Redis nem de
Node.js/MCP — o pipeline monta o grafo direto com `build_graph(TOOLS, checkpointer=InMemorySaver())`,
fora do `lifespan` da API.

!!! warning "Só exercita as 4 tools nativas, não as 11 do PNCP nem o cache"
    O agente do pipeline roda **sem** as tools MCP e **sem** a camada `aplicar_cache` que a produção
    usa (`app/services/lifespan.py`) — ele testa o raciocínio do agente e as 4 tools nativas, não a
    integração completa. Isso já mordeu na prática: a migração de `InjectedState` para `ToolRuntime`
    (ver [Arquitetura](../arquitetura/visao_geral.md)) introduziu um bug que só aparecia dentro de
    `aplicar_cache` — o golden dataset passou normalmente nas duas vezes em que foi rodado durante
    essa migração, porque nunca chega perto do código que quebrou. Ao interpretar "o golden dataset
    passou" como evidência de que nada quebrou, vale lembrar desse ponto cego.

O terminal imprime um resumo ao final (`_formatar_relatorio_aprovacao`):

```text
============================================================
                   RESULTADO DA AVALIAÇÃO
============================================================
  aderencia_tools   : 1.000  (mínimo 0.70)  [OK]     APROVADO
  faithfulness      : 0.858  (mínimo 0.85)  [OK]     APROVADO
  context_recall    : 0.600  (mínimo 0.75)  [FALHOU] REPROVADO
  recall_anomalias  : 1.000  (mínimo 0.80)  [OK]     APROVADO
------------------------------------------------------------
  VEREDITO GERAL: [FALHOU] REPROVADO
============================================================
```

(Números da rodada de 2026-07-08 documentada abaixo — reproduzido a partir do código real de
`_formatar_relatorio_aprovacao`, não digitado à mão.)

!!! note "`python -m evaluation.pipeline_avaliacao` não grava `evaluation/relatorio.json`"
    `main()` tem `salvar_json: bool = True` por padrão, mas o bloco `if __name__ == "__main__":` do
    próprio arquivo chama `main(salvar_json=False)` — rodar o script direto do terminal só imprime o
    resumo acima, sem escrever o relatório completo em disco (todas as métricas, por caso e
    agregadas). Para gravar o JSON, importe e chame `main()` sem esse argumento (ou com
    `salvar_json=True` explícito) a partir de outro script/notebook.

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

### Nova rodada de validação (2026-07-08)

Uma rodada adicional de 3 execuções da `evaluation/pipeline_avaliacao.py`, mesmo protocolo, trouxe:

| Métrica | Limiar | Resultado | Veredito |
|---|---|---|---|
| `aderencia_tools` | ≥ 0.70 | **1.000** | ✅ aprovado |
| `faithfulness` | ≥ 0.85 | **0.858** | ✅ aprovado |
| `context_recall` | ≥ 0.75 | **0.600** | ❌ reprovado |
| `recall_anomalias` | ≥ 0.80 | **1.000** | ✅ aprovado |

`aderencia_tools` e `recall_anomalias` seguem estáveis em `1.00`. `faithfulness` — que oscilava entre
`0.79` e `0.88` nas 6 execuções anteriores, reprovando em 2 delas — aprovou com folga nesta rodada
(`0.858`). É um sinal encorajador, mas uma única rodada nova ainda não é suficiente para declarar a
instabilidade resolvida; o item continua em acompanhamento (ver Backlog V2). `context_recall`
permanece **idêntico** às execuções anteriores (`0.60`) — reforça que a causa raiz (posição do
trecho-alvo fora do alcance de `top_k=3`) é sistemática, não ruído pontual de uma rodada específica.
O veredito geral segue **reprovado**, agora com uma causa ainda mais isolada: das quatro métricas, só
`context_recall` reprova.
