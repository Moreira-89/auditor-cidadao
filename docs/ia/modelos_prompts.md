# Modelos e Prompts

Este pilar cobre a **inteligência** do Auditor Cidadão: quais modelos de IA são usados e por quê,
como os prompts garantem respostas consistentes e controladas, e como o conhecimento (o edital) é
preparado e recuperado. Esta primeira página trata dos modelos e da engenharia de prompt.

## Os modelos usados

| Papel | Modelo (default) | Temperatura | Onde |
|---|---|---|---|
| Agente principal | `openai:gpt-4o-mini` | `0.1` | Conversa e relatório automático ([`app/config/settings.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/config/settings.py)) |
| Juiz de Fidelidade (G-Eval) | `gpt-4o` | `0.0` | Só no framework de avaliação — ver [Avaliação](avaliacao.md) |
| Embeddings (RAG) | `text-embedding-3-large` | — | Indexação e busca no MongoDB Atlas (ver [Uso de Dados e RAG](rag_dados.md)) |

Todos os modelos de LLM são configuráveis por variável de ambiente (`LLM_MODEL`, `AVALIADOR_MODEL`)
— ver [Variáveis de ambiente](../operacional/variaveis_ambiente.md). O
`init_chat_model` do LangChain identifica o provider pelo prefixo do nome (`openai:`, `groq:`,
`google_genai:`), então trocar de modelo não exige mudar código.

!!! note "Por que `gpt-4o-mini` como agente principal?"
    O trabalho do agente é orquestrar ferramentas e redigir um laudo a partir de dados já
    recuperados — não exige raciocínio de fronteira, mas é chamado a cada turno de cada usuário. O
    `gpt-4o-mini` entrega qualidade suficiente para essa tarefa a uma fração do custo de um modelo
    maior, com janela de contexto (128k) folgada para acomodar múltiplos resultados de tool num
    único turno. O `gpt-4o` (mais caro) fica reservado ao **juiz da avaliação**, que roda poucas
    vezes e só quando o time executa o golden dataset — ver [Avaliação](avaliacao.md).

!!! info "Benchmark contra outros modelos fica para a V2"
    O `gpt-4o-mini` é a escolha da V1 pelo custo-benefício, não porque outros modelos tenham sido
    testados e descartados. O **Sabiá-4-thinking** (Maritaca AI) já foi benchmarkado contra o
    `gpt-4o` no golden dataset (Bloco 12) e saiu à frente para a tarefa, mas nenhum passou o veredito
    geral — a limitação hoje é a recuperação, não o modelo (ver [Avaliação](avaliacao.md)). Rodar
    contra `o1`/`o3-mini`, `DeepSeek-R1`, Claude e Gemini segue no backlog. `llm.py` já suporta o
    prefixo `maritaca:`; produção segue em `gpt-4o-mini` por custo.

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
  (`<CNPJS_NO_EDITAL>`, `<METADADOS>`, `<PERGUNTA>`) enviado como `HumanMessage` no primeiro turno
  de qualquer thread (`montar_primeiro_turno`, `app/agents/envelope.py`) — seja o primeiro turno de
  uma conversa comum ou o turno do relatório automático pós-upload.
- **`PROMPT_RELATORIO_INICIAL`** (`prompt.py:521`) — a "pergunta" sintética usada como
  `pergunta_usuario` no envelope acima quando é o sistema (não o usuário) que dispara o primeiro
  turno. Em produção, `app/api/endpoints/chat.py:81` troca a pergunta por essa constante quando
  `request.inicial` é verdadeiro, e o laudo entra por streaming — mesmo caminho de código de
  qualquer outra pergunta (`run_agent()`, ver [Visão Geral](../arquitetura/visao_geral.md)). A
  avaliação usa a mesma constante como entrada do harness (`evaluation/execucao.py:37`, ver
  [Avaliação](avaliacao.md)).

O `TOOL_STATUS_MAP` (`app/config/tool_status_map.py:2`) — que traduz o nome técnico de cada
ferramenta na mensagem exibida ao usuário durante a execução — não é prompt e vive à parte (ex.:
`"buscar_contexto_edital": "🖹 Analisando trechos do edital indexado..."`, `tool_status_map.py:5`).

## Exemplo real: o que o modelo recebe no primeiro turno

`SYSTEM_PROMPT` (abertura, [`app/agents/prompt.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/prompt.py) — texto literal, só cortado com `[...]` onde o
prompt continua):

```text
# IDENTIDADE
Você é o **Auditor Cidadão**, um agente especializado em auditoria de licitações,
contratos e editais públicos municipais brasileiros sob a Lei 14.133/2021.
Trate o usuário de forma cordial, profissional e direta.

# MISSÃO
Identificar indícios de irregularidade em documentos de contratação pública,
cruzando informações declaradas no edital com dados oficiais de fontes públicas
acessíveis através das suas capacidades de consulta.

Você NÃO é um validador de CNPJ. Você é um auditor. Sua função é detectar
PADRÕES SUSPEITOS, não apenas conformidade cadastral.

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

<PERGUNTA>
Audite essa empresa e verifique se há alguma sanção que a impeça de contratar com o poder público.
</PERGUNTA>
```

Note que a pergunta do usuário nunca chega "pura" ao modelo — sempre dentro da tag `<PERGUNTA>`,
depois de passar por `escape_xml()` (ver [Guardrails](../governanca/guardrails.md)). No **relatório
automático** (primeiro turno disparado pelo sistema, `inicial: true`), a mesma tag `<PERGUNTA>`
carrega o `PROMPT_RELATORIO_INICIAL` no lugar do texto do usuário.

## Técnicas de engenharia de prompt aplicadas

**Identidade e missão explícitas.** O `SYSTEM_PROMPT` abre reforçando que o agente é um *auditor*,
não um validador de CNPJ — a missão é detectar padrões suspeitos, não conferir conformidade
cadastral. Isso orienta o modelo a varrer o catálogo de anomalias proativamente.

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

**Score conservador.** Quando uma anomalia depende de uma base que não pôde ser verificada, o score
mínimo é MÉDIO (0.30) mesmo sem anomalias detectadas — e o prompt proíbe emitir "laudo limpo total",
exigindo sempre uma ressalva de que verificações não concluídas devem ser checadas manualmente. Isso
conecta diretamente com a [Governança](../governanca/limitacoes.md): o laudo é indício, não veredito.