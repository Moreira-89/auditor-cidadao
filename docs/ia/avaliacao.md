# Avaliação de Desempenho

Toda vez que alguém mexe no prompt, troca o modelo ou ajusta uma ferramenta, existe o risco de
piorar a qualidade das respostas sem perceber — o agente continua respondendo, só que pior, e
ninguém nota até um caso real dar errado. Para não depender de "parece que ficou bom", o projeto
mantém um framework de avaliação automatizado: um conjunto de casos de teste curados (o **golden
dataset**) e um script que roda o agente de verdade contra cada caso e mede a qualidade da resposta
com números, não com impressão.

O código vive em [`backend/evaluation/`](https://github.com/Moreira-89/auditor-cidadao/tree/main/backend/evaluation),
ao lado de `backend/app/` (a avaliação importa do `app`, nunca o contrário — ela é consumidora do
código de produção, não uma cópia dele). Roda assim:

```bash
cd backend
python -m evaluation.runner
```

## O golden dataset: um conjunto de casos com gabarito

Um "caso" é um edital (PDF real ou fabricado para o teste) mais um **gabarito**: quais ferramentas
o agente deveria chamar, com quais argumentos, e quais anomalias deveria encontrar. Todos os casos
vivem num único arquivo, `evaluation/dataset/golden_dataset.json`, e cada um é validado contra um
schema Pydantic antes de rodar — um erro de digitação no gabarito (por exemplo, um código de
anomalia que não existe) quebra na hora, não some em silêncio.

Existem dois tipos de caso, guardados no mesmo dataset, mas cobrando coisas diferentes:

| Tipo | O que cobra | Quantos casos |
|---|---|---|
| `real` | O agente recuperou o trecho certo do edital e chamou a ferramenta certa | 4 — editais verdadeiros, baixados de portais reais |
| `sintetico` | O agente encontrou a anomalia certa | 9 — um caso por letra do catálogo A–I |

**Por que separar assim.** Um edital real e complexo não tem um "gabarito de anomalia" 100%
confiável — mesmo um humano especialista pode discordar se um trecho específico é ou não
irregularidade. Isso já aconteceu na prática: em dois dos quatro casos reais, o agente apontou uma
anomalia a mais do que o gabarito previa, e não dava pra saber com segurança se era erro do agente
ou do gabarito (num dos dois, era mesmo erro de gabarito — corrigido depois de conferir CNPJ e CNAE
reais). Por isso os 4 casos reais só cobram o que é **objetivamente** checável — achou o trecho
certo, chamou a ferramenta certa — e toda a checagem de "achou a anomalia certa" foi para os 9 casos
sintéticos, onde o gabarito é escrito antes de o PDF existir e não tem margem pra interpretação.

Os 9 casos sintéticos, um por letra do catálogo (ver [Catálogo de Anomalias](anomalias.md)):

| Anomalia | Cenário resumido |
|---|---|
| **A** — sobrepreço | Papel sulfite 40% acima da mediana de referência |
| **B** — direcionamento | Cláusula de credenciamento sem relação demonstrada com o objeto |
| **C** — fracionamento | Pavimentação dividida em 2 certames, ~2 meses de intervalo |
| **D** — indício de conluio | 3 empresas, mesmo endereço/sócios, propostas muito próximas |
| **E** — empresa incompatível | Vencedora de obra de R$ 4,8 mi constituída 7 meses antes do edital |
| **F** — prazo insuficiente | Sem os 30 dias mínimos entre publicação e sessão |
| **C + G** — fracionamento + concentração | Uma empresa venceu 64,3% dos certames do órgão em 12 meses |
| **H** — sanção vigente | Vencedora consta no CEIS, adjudicada mesmo assim |
| **I** — CNAE incompatível | Empresa fictícia do ramo gráfico concorrendo a manutenção de climatização |

Um desses casos merece nota à parte: o caso-controle não espera **nenhuma** anomalia, mas ainda
assim espera que o agente chame `buscar_contexto_edital` — ele precisa consultar o edital pra
escrever o relatório, mesmo quando conclui que está tudo em ordem. "Não espero nenhuma ferramenta"
e "não tenho gabarito de ferramenta pra este caso" são coisas diferentes, e o schema do dataset
distingue as duas.

## Como um caso roda: o mesmo caminho de código da produção

Este é o ponto mais importante do design: **a avaliação não tem um "modo de teste" separado do
agente real.** Ela chama exatamente a mesma função que o endpoint `/conversar-com-auditor/` chama
em produção:

```python
# é isso que o harness de avaliação chama por trás — mesma função, mesmo grafo, mesmo prompt
await run_agent(
    pergunta_usuario=PROMPT_RELATORIO_INICIAL,  # mesma constante que o relatório automático usa
    lista_cnpj=caso.cnpjs,
    estado=caso.estado,
    municipio=caso.municipio,
    thread_id=edital_id,
)
```

Isso importa porque elimina uma categoria inteira de bug: "passou na avaliação, mas quebrou em
produção porque o caminho de teste era diferente do caminho real". Se `run_agent()` muda amanhã, a
avaliação sente a mudança imediatamente — não existe uma segunda cópia da lógica do agente pra
manter sincronizada.

Depois que o agente termina o turno, o harness precisa reconstruir duas coisas a partir do que
sobrou: o texto final do laudo (juntando os tokens que `run_agent()` foi emitindo) e a lista de
ferramentas que ele chamou, com os argumentos — isso não vem pronto no stream de eventos (que só
manda o *nome* da ferramenta, pra atualizar a UI), então o harness lê o checkpoint do LangGraph
depois do turno terminar e extrai os `tool_calls` do histórico de mensagens salvo ali.

**Como os achados de anomalia são extraídos: regex, não um segundo LLM.** O prompt já obriga o
agente a escrever cada achado num formato fixo (`**[ESTADO: CONFIRMADO] [NÍVEL DE RISCO: ALTO] —
H. Sanção...**`), então basta procurar esse padrão no Markdown:

```python
_PADRAO_ACHADO = re.compile(
    r"\*\*\[ESTADO:\s*(CONFIRMADO|INDÍCIO)\]\s*"
    r"\[NÍVEL DE RISCO:\s*(?:BAIXO|MÉDIO|ALTO|CRÍTICO)\]\s*"
    r"[—-]\s*([A-I])\."
)

def extrair_anomalias(texto_laudo: str) -> list[tuple[str, str]]:
    """Devolve [(codigo, estado), ...] achados no laudo."""
    return [(m.group(2), m.group(1)) for m in _PADRAO_ACHADO.finditer(texto_laudo)]
```

Nada de chamar um LLM pra "ler e extrair" — o dado já está lá, formatado, só precisa ser lido. Mais
rápido, sem custo de API, e sem a instabilidade de pedir pra outro modelo interpretar o texto.

## Como cada resposta é julgada: G-Eval

A pergunta que a avaliação precisa responder é semântica, não textual: *"o laudo afirma algo que as
fontes consultadas não sustentam?"* — não *"o texto se parece com um texto de referência?"*. Isso
já descarta métricas clássicas de comparação de texto (BLEU, ROUGE): elas comparam string contra
string, e não existe um "laudo perfeito" único pra comparar — dois laudos com redação totalmente
diferente podem estar igualmente certos.

Sobra julgar com outro LLM. A forma mais comum de fazer isso é dar a um "LLM-juiz" a resposta e o
contexto, e pedir uma nota — é o que o [RAGAS](https://docs.ragas.io/) faz, e foi o que o projeto
usou antes. O problema medido na prática: rodando a **mesma** avaliação 4 vezes seguidas, sem mudar
nada no código, uma das métricas do RAGAS saiu `0.0`, `0.33`, `0.67` e `1.0` nas quatro rodadas — a
variação não vinha do que estava sendo avaliado, vinha da falta de um critério explícito de
julgamento.

**G-Eval** ataca esse problema na raiz: em vez de pedir "julgue a qualidade" e deixar o juiz
decidir sozinho o que isso significa, quem escreve a métrica define os **passos de raciocínio** que
o juiz precisa seguir e uma **régua de nota** fixa antes de rodar. O juiz tem menos espaço pra
divergir de rodada pra rodada porque o critério já está escrito no prompt, não na "opinião" livre
do modelo. A biblioteca [`deepeval`](https://deepeval.com/) já entrega isso pronto.

## As quatro métricas

| Métrica | O que mede | Limiar para passar | Usa LLM? |
|---|---|---|---|
| **Tool Correctness** | O agente chamou as ferramentas certas (só o nome, não os argumentos) | ≥ 0.50 | Não |
| **Argumentos da Tool** | Os argumentos que importam (ex.: o CNPJ) chegaram certos na ferramenta | ≥ 1.00 | Não |
| **Fidelidade** | O laudo só afirma o que as ferramentas realmente sustentam | ≥ 0.60 | Sim |
| **Cobertura de Contexto** (só `real`) / **Recall de Anomalias** (só `sintetico`) | O agente recuperou o trecho certo do edital / achou a anomalia certa | ≥ 0.70 / ≥ 0.65 | Sim / Não |

**Por que duas métricas de ferramenta em vez de uma.** A métrica nativa do `deepeval` para tool use
compara os argumentos por igualdade exata — o que quebraria casos onde o argumento esperado é
intencionalmente vazio (a pergunta que vai pra `buscar_contexto_edital` é texto livre, nunca faz
sentido cobrar um valor exato). Por isso uma segunda métrica, escrita para este projeto, cobra só os
argumentos que realmente importam (como o CNPJ que uma tool de sanção recebeu), aceitando que a
chamada real tenha outros campos a mais.

### Fidelidade: como o juiz decide a nota

O juiz recebe uma lista de passos: listar cada afirmação factual do laudo, procurar se ela é
sustentada pelo que as ferramentas devolveram, e marcar cada uma como sustentada ou não. Uma
afirmação que **extrapola** a fonte conta como não sustentada — se a fonte diz "3 sanções" e o
laudo diz "sanções recorrentes e graves", isso é extrapolação, mesmo sem inventar um número novo.
Depois de aplicar esses passos, o juiz usa esta régua para converter em nota de 1 a 5:

```python
rubric=[
    Rubric(score_range=(5, 5), expected_outcome="Todas as afirmações sustentadas."),
    Rubric(score_range=(4, 4), expected_outcome="1 não sustentada, detalhe menor que não muda o achado."),
    Rubric(score_range=(3, 3), expected_outcome="1 não sustentada que afeta a evidência de um achado."),
    Rubric(
        score_range=(2, 2),
        expected_outcome="2+ não sustentadas, ou 1 que inventa dado central "
        "(CNPJ, valor, sanção, cláusula) sem base em nenhuma fonte.",
    ),
    Rubric(
        score_range=(1, 1),
        expected_outcome="Achado (CONFIRMADO/INDÍCIO) cuja evidência central "
        "não existe em nenhuma fonte consultada.",
    ),
]
```

Essa régua foi testada de propósito: rodando a métrica isolada contra um caso onde o laudo
propositalmente extrapola a fonte, ela deu 0.32 (reprovado); contra um caso fiel, deu 1.0
(aprovado). Ou seja, a régua discrimina de verdade — não dá nota alta só porque o texto está bem
escrito.

### Recall de Anomalias: por que é F1, não só "acertou ou não"

Essa métrica compara os códigos que o agente apontou (A a I) contra os que o gabarito esperava, e
faz duas perguntas diferentes sobre a mesma comparação:

- **Precisão** — "das anomalias que o agente apontou, quantas estavam certas?" Pega um agente que
  chuta todas as 9 letras em todo edital: ele nunca erra por falta (acha tudo, óbvio), mas a
  precisão dele despenca porque a maioria dos chutes está errada.
- **Recall** — "das anomalias que o gabarito esperava, quantas o agente achou?" Pega o oposto: um
  agente caladão, que só fala quando tem certeza absoluta, pode ter precisão perfeita mas deixar
  passar metade das anomalias reais.

Nenhuma das duas sozinha basta — cada uma pode ser "enganada" isoladamente, como nos dois exemplos
acima. A métrica final é o **F1**, a média harmônica entre as duas:

```
F1 = 2 × (precisão × recall) / (precisão + recall)
```

Diferente de uma média simples, o F1 pune desequilíbrio: se uma das duas for zero, o F1 vai a zero
junto, mesmo que a outra seja perfeita.

**Exemplo real, o caso "fracionamento + concentração"** (gabarito esperava `["C", "G"]`, o agente
só apontou `["G"]`):

- Precisão = 1/1 = **1.0** — tudo que ele disse (`G`) estava certo.
- Recall = 1/2 = **0.5** — achou 1 das 2 anomalias esperadas.
- F1 = 2 × (1.0 × 0.5) / (1.0 + 0.5) = **0.667** — acima do limiar de 0.65, esse caso passa, mesmo
  sem detectar a anomalia secundária.

## O pipeline, passo a passo

Para cada caso do dataset, na ordem:

1. **Prepara o ambiente** — monta o mesmo conjunto de ferramentas que a produção usa (nativas + MCP
   + cache), com a temperatura do LLM zerada para reduzir variação entre rodadas.
2. **Indexa o caso** — roda o mesmo pipeline de extração (Docling) e indexação (MongoDB) que o
   `/upload/` real usa.
3. **Executa** — chama `run_agent()`, o mesmo caminho de produção (ver acima).
4. **Limpa** — remove o edital indexado do banco, sempre, mesmo se o passo anterior falhou.

Um detalhe de isolamento: como o pipeline usa o mesmo Redis de cache que a produção, a avaliação
roda num banco lógico separado do Redis (não o mesmo namespace de chaves) e limpa esse banco antes
de cada rodada — sem isso, um caso corrigido no dataset continuaria batendo num resultado
cacheado de uma rodada anterior, e a correção não apareceria no resultado.

**Se um provider de LLM falhar no meio de um caso** (erro 500/503 transiente — já aconteceu com
OpenAI, Gemini e Maritaca), o caso é re-tentado até 3 vezes antes de ser descartado. Sem isso, uma
falha de rede no meio da lista jogaria fora o trabalho de todos os casos já rodados antes dele.

No final, os casos `real` e `sintetico` são avaliados separadamente (cobram métricas diferentes) e
o resultado de cada rodada é salvo num arquivo JSON com timestamp. Se qualquer caso reprovar em
qualquer métrica — ou se algum caso foi descartado pelo retry — o script termina com erro, pra ficar
óbvio no terminal (ou no CI) que algo não passou.

## Rodando

```bash
cd backend
python -m evaluation.runner                          # todos os casos
python -m evaluation.runner caso_02_saoluis_sancao    # um caso específico
python -m evaluation.runner --tipo=sintetico          # só a suíte sintética (mais rápida)
python -m evaluation.runner --tipo=real               # só a suíte real
```

Precisa das mesmas variáveis de ambiente da produção (`OPENAI_API_KEY`, `MONGODB_URI`, `REDIS_URI`,
Node.js no PATH para o MCP) — porque, de novo, é o mesmo código de produção rodando. O juiz (LLM
que avalia Fidelidade e Cobertura de Contexto) é configurável separadamente do modelo do agente
(`AVALIADOR_MODEL`), útil quando o provider padrão tem um limite de taxa baixo demais para um edital
grande — ver [Variáveis de ambiente](../operacional/variaveis_ambiente.md).

## Por que vale ler o motivo, não só o número

Cada métrica do `deepeval` devolve, além da nota, uma explicação em texto de por que deu aquela
nota — a Fidelidade aponta exatamente qual frase do laudo não tem base na fonte; a Tool Correctness
lista exatamente quais ferramentas faltaram ou sobraram. Essa explicação é o que de fato orienta uma
correção: dá pra levar direto pro `SYSTEM_PROMPT` ou pra docstring de uma ferramenta, em vez de só
saber que "a nota caiu" sem saber por quê.

## Estado atual do veredito

!!! success "Suíte `real`: 4/4 — Tool Correctness, Argumentos e Cobertura de Contexto em 1.0, Fidelidade 0.89-0.99"
    Os 4 casos reais passam em todas as métricas. O caso de Belém (Fidelidade 0.889, o mais baixo
    do lote) ainda mostra sinal do problema de retrieval documentado em
    [Uso de Dados e RAG](rag_dados.md#limitacoes-conhecidas-do-retrieval) — mas não reprova.

!!! success "Suíte `sintetico`: 9/9 estável em 3 rodadas seguidas"
    Três rodadas completas contra os 9 casos (um por letra do catálogo A-I), sem mudança de código
    entre a 2ª e a 3ª: Tool Correctness e Argumentos da Tool em 1.0 nas 3, Fidelidade sempre ≥ 0.92.

    Duas divergências de classificação se repetiram nas 3 rodadas — tratadas como limitações
    conhecidas, não bugs de pipeline:

    - O caso de **empresa recém-criada em obra complexa** (esperado **E**): o modelo às vezes
      classifica o mesmo achado como **I** (CNAE incompatível) em vez de **E** (capacidade
      técnica) — confusão entre duas categorias vizinhas do catálogo, não uma alucinação de fato.
    - O caso de **fracionamento + reincidência** (esperado **C + G**): o modelo consistentemente só
      aponta **G**, nunca o **C** que também tem evidência textual no PDF — o F1 fica em 0.667
      (acima do limiar de 0.65, então passa), mas não detecta a anomalia secundária.

    O caso de **cartel** (esperado **D**) teve uma ocorrência intermitente (1 das 3 rodadas) de
    apontar também **B** (direcionamento), emprestando evidência do próprio achado D sem uma
    cláusula de direcionamento real no edital — não é consistente como os dois casos acima, por ora
    só anotado.
