# Modelos e Prompts

Este pilar cobre a **inteligência** do Auditor Cidadão: quais modelos de IA são usados e por quê,
como os prompts garantem respostas consistentes e controladas, e como o conhecimento (o edital) é
preparado e recuperado. Esta primeira página trata dos modelos e da engenharia de prompt.

## Os modelos usados

| Papel | Modelo (default) | Temperatura | Onde |
|---|---|---|---|
| Agente principal | `maritaca:sabia-4` | `0.1` | Conversa e relatório automático ([`app/config/settings.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/config/settings.py)) |
| Juiz de Fidelidade (G-Eval) | `gpt-4o` | `0.0` | Só no framework de avaliação — ver [Avaliação](avaliacao.md) |
| Embeddings (RAG) | `text-embedding-3-small` | — | Indexação e busca no MongoDB Atlas (ver [Uso de Dados e RAG](rag_dados.md)) |

Todos os modelos de LLM são configuráveis por variável de ambiente (`LLM_MODEL`, `AVALIADOR_MODEL`)
— ver [Variáveis de ambiente](../operacional/variaveis_ambiente.md). O
`init_chat_model` do LangChain identifica o provider pelo prefixo do nome (`openai:`, `groq:`,
`google_genai:`); a Maritaca não é provider nativo dele, então `app/llm.py` roteia via `ChatOpenAI`
trocando `base_url` + chave (API compatível com a da OpenAI) quando o prefixo é `maritaca:`. Trocar
de modelo não exige mudar código em nenhum dos casos.

!!! note "Por que Sabiá-4 (Maritaca AI) como agente principal?"
    O trabalho do agente é orquestrar ferramentas e redigir um laudo a partir de dados já
    recuperados a cada turno de cada usuário. O Sabiá-4 saiu à frente do `gpt-4o` no golden dataset
    de avaliação (ver [Avaliação](avaliacao.md)) para essa tarefa específica, com custo menor que um
    modelo de fronteira. O `gpt-4o` (mais caro) fica reservado ao **juiz da avaliação**, que roda
    poucas vezes e só quando o time executa o golden dataset.

!!! info "Benchmark contra outros modelos"
    O Sabiá-4 (Maritaca AI) foi benchmarkado contra o `gpt-4o` no golden dataset e saiu à frente
    para a tarefa, mas nenhum dos dois passou o veredito geral — a limitação hoje é a recuperação,
    não o modelo (ver [Avaliação](avaliacao.md)). `LLM_MODEL` aceita qualquer provider suportado por
    `init_chat_model` (ou `maritaca:`, via o wrapper de `app/llm.py`) sem mudar código — rodar contra
    `o1`/`o3-mini`, `DeepSeek-R1`, Claude e Gemini segue no backlog.

!!! note "Por que RAG (Geração Aumentada por Recuperação) e não fine-tuning?"
    Os editais mudam a cada upload e não existem no treinamento de nenhum modelo. Fine-tuning
    ensinaria um estilo, não um documento específico — e teria que ser refeito a cada novo edital.
    RAG (busca semântica no MongoDB Atlas) permite responder sobre um documento que o modelo nunca viu,
    citando trechos reais, e reduz alucinação ao ancorar a resposta no texto recuperado. Ver
    [Uso de Dados (RAG)](rag_dados.md) para o pipeline completo.

## Os prompts do sistema

Toda a engenharia de prompt vive em
[`app/agents/prompt.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/prompt.py) — sem lógica, só texto:

- **`SYSTEM_PROMPT`** (`prompt.py:292`) — injetado uma vez no primeiro turno de cada conversa.
  Define a identidade de auditor, as capacidades, o catálogo de anomalias (`CATALOGO_ANOMALIAS`,
  `prompt.py:1`), a hierarquia de evidências e as regras de segurança.
- **`PROMPT_DINAMICO`** (`prompt.py:505`) — o "envelope" em tags no estilo XML
  (`<CNPJS_NO_EDITAL>`, `<METADADOS>`, `<PROMPT_USUARIO>`) enviado como `HumanMessage` no primeiro turno
  de qualquer thread (`montar_primeiro_turno`, `app/agents/envelope.py`) — seja o primeiro turno de
  uma conversa comum ou o turno do relatório automático pós-upload.
- **`PROMPT_RELATORIO_INICIAL`** (`prompt.py:521`) — a "pergunta" sintética usada como
  `pergunta_usuario` no envelope acima quando é o sistema (não o usuário) que dispara o primeiro
  turno. Em produção, `app/api/endpoints/chat.py:81` troca a pergunta por essa constante quando
  `request.inicial` é verdadeiro, e o laudo entra por streaming — mesmo caminho de código de
  qualquer outra pergunta (`run_agent()`, ver [Visão Geral](../arquitetura/visao_geral.md)). A
  avaliação usa a mesma constante como entrada do harness (`evaluation/execucao.py:40`, ver
  [Avaliação](avaliacao.md)).

O `TOOL_STATUS_MAP` (`app/config/tool_status_map.py:2`) — que traduz o nome técnico de cada
ferramenta na mensagem exibida ao usuário durante a execução — não é prompt e vive à parte (ex.:
`"buscar_contexto_edital": "🖹 Analisando trechos do edital indexado..."`, `tool_status_map.py:5`).

## Exemplo real: o que o modelo recebe no primeiro turno

`SYSTEM_PROMPT` (abertura, [`app/agents/prompt.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/prompt.py) — texto literal, só cortado com `[...]` onde o
prompt continua):

```text
# IDENTIDADE

Você é o Auditor Cidadão, um agente especializado em triagem de riscos em
licitações, contratos e editais públicos municipais brasileiros.

Atue de forma cordial, profissional, objetiva e tecnicamente cautelosa.

# MISSÃO

Identificar fatos e sinais verificáveis que possam justificar investigação humana
em documentos de contratação pública.

Você não substitui auditoria formal, controle externo, investigação administrativa
ou decisão judicial. Não acusa pessoas ou empresas e não emite conclusão jurídica
definitiva.

[...]
```

`PROMPT_DINAMICO` é o `HumanMessage` enviado junto. Numa primeira pergunta de conversa, fica assim:

```text
<CNPJS_NO_EDITAL>
47417848000184
</CNPJS_NO_EDITAL>

<METADADOS>
Município: São Luís
Estado: Maranhão (MA)
Data de hoje: 20260815
</METADADOS>

<PROMPT_USUARIO>
Audite essa empresa e verifique se há alguma sanção que a impeça de contratar com o poder público.
</PROMPT_USUARIO>
```

Note que a pergunta do usuário nunca chega "pura" ao modelo — sempre dentro da tag
`<PROMPT_USUARIO>`, depois de passar por `escape_xml()` (ver [Guardrails](../governanca/guardrails.md)).
No **relatório automático** (primeiro turno disparado pelo sistema, `inicial: true`), a mesma tag
`<PROMPT_USUARIO>` carrega o `PROMPT_RELATORIO_INICIAL` no lugar do texto do usuário.

## Técnicas de engenharia de prompt aplicadas

**Identidade e missão explícitas.** O `SYSTEM_PROMPT` abre definindo o agente como uma **triagem de
riscos**, não uma auditoria formal — deixa explícito que ele "não substitui auditoria formal,
controle externo, investigação administrativa ou decisão judicial" e "não acusa pessoas ou empresas".
Isso mantém o modelo dentro do papel de sinalizar, não de veredito.

**Hierarquia de evidências.** O prompt estabelece uma ordem de confiança nas fontes: (1) APIs
oficiais, (2) texto do documento, (3) busca web, (4) inferências próprias — sempre sinalizadas como
tal. Isso reduz o risco de o modelo tratar um resultado de busca web com o mesmo peso de um dado da
Receita Federal.

**Regra anti-alucinação por "vocabulário emprestado".** Uma regra específica (descoberta em teste
real via log) proíbe o modelo de inferir um campo a partir de uma fonte que não foi consultada — por
exemplo, afirmar a `situação cadastral` a partir de um resultado de sanções sem ter chamado a
Receita Federal. Toda afirmação factual precisa remeter a um campo literal de uma tool efetivamente
chamada naquele turno.

**Dois modos de resposta com gatilhos explícitos.** O prompt distingue *laudo completo* (Markdown
estruturado, só quando o usuário pede análise/auditoria) de *resposta conversacional* (direta, sem
score, para perguntas pontuais). Os gatilhos de cada modo estão listados no prompt.

**Score conservador, sem número fixo.** O score representa risco de triagem, nunca probabilidade de
fraude ou conclusão jurídica. O prompt proíbe risco crítico automático para indício ou dado
incompleto, proíbe reduzir a incerteza só porque uma fonte voltou "limpa", e só permite não atribuir
score numérico quando não houver dados suficientes — se a aplicação exigir um valor mesmo assim, o
prompt manda usar um "score conservador" e explicar a limitação, sem fixar um piso numérico. Isso
conecta diretamente com a [Governança](../governanca/limitacoes.md): o laudo é indício, não veredito.