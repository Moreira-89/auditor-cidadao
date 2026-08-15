# Modelos e Prompts

Este pilar cobre a **inteligência** do Auditor Cidadão: quais modelos de IA são usados e por quê,
como os prompts garantem respostas consistentes e controladas, e como o conhecimento (o edital) é
preparado e recuperado. Esta primeira página trata dos modelos e da engenharia de prompt.

## Os modelos usados

| Papel | Modelo (default) | Temperatura | Onde |
|---|---|---|---|
| Agente principal | `openai:gpt-4o-mini` | `0.1` | Conversa e geração do laudo (`app/core/dependencies.py`) |
| Extrator de laudo | `openai:gpt-4o-mini` | `0.0` | Segunda chamada que gera o JSON estruturado |
| Embeddings (RAG) | `text-embedding-3-small` | — | Indexação e busca no Pinecone (1536 dimensões) |
| Juiz de avaliação (RAGAS) | `openai:gpt-4o` | `0.0` | Só no framework de avaliação, nunca em produção |

Todos os modelos de LLM são configuráveis por variável de ambiente (`LLM_MODEL`, `EXTRATOR_MODEL`,
`AVALIADOR_MODEL`) — ver [Variáveis de ambiente](../operacional/variaveis_ambiente.md). O
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
    testados e descartados. Está no backlog rodar o golden dataset contra alternativas como
    **Sabiá-3/4** (Maritaca AI, especializado em jargão jurídico brasileiro), **OpenAI o1/o3-mini**
    e **DeepSeek-R1** (cadeia de raciocínio, para decretos e editais mais complexos), **Claude 3.5
    Sonnet/Opus** (referência em análise contratual em português) e **Gemini 1.5 Pro/2.0 Flash**
    (janela de contexto de 1–2M tokens) — usando o mesmo protocolo de avaliação do
    [Bloco 4](avaliacao.md), não impressão subjetiva. Detalhes de cada candidato no roadmap.

!!! note "Por que RAG (Geração Aumentada por Recuperação) e não fine-tuning?"
    Os editais mudam a cada upload e não existem no treinamento de nenhum modelo. Fine-tuning
    ensinaria um estilo, não um documento específico — e teria que ser refeito a cada novo edital.
    RAG (busca semântica no Pinecone) permite responder sobre um documento que o modelo nunca viu,
    citando trechos reais, e reduz alucinação ao ancorar a resposta no texto recuperado. Ver
    [Uso de Dados (RAG)](rag_dados.md) para o pipeline completo.

## Os quatro prompts do sistema

Toda a engenharia de prompt vive em `app/core/prompt.py` — quatro peças, sem lógica:

- **`SYSTEM_PROMPT`** — injetado uma vez no primeiro turno de cada conversa. Define a identidade de
  auditor, as capacidades, o catálogo de anomalias, a hierarquia de evidências e as regras de
  segurança.
- **`PROMPT_DINAMICO`** — o "envelope" em tags no estilo XML (`<CNPJS_NO_EDITAL>`, `<METADADOS>`,
  `<PERGUNTA>`) enviado como `HumanMessage` no primeiro turno.
- **`PROMPT_EXTRATOR`** — instrução da segunda chamada ao LLM, que decide se o texto gerado é um
  laudo completo e o converte em JSON — ver [Extração de Laudo](extracao_laudo.md).
- **`TOOL_STATUS_MAP`** — traduz o nome técnico de cada ferramenta na mensagem amigável exibida ao
  usuário durante a execução (ex.: "🏛️ Consultando dados cadastrais na Receita Federal...").

## Exemplo real: o que o modelo recebe no primeiro turno

`SYSTEM_PROMPT` (abertura, `app/core/prompt.py` — texto literal, só cortado com `[...]` onde o
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

`PROMPT_DINAMICO` é o `HumanMessage` enviado junto — o exemplo abaixo usa os valores reais do
`caso_01` do golden dataset (edital fictício de São Luís/MA, ver [Avaliação](avaliacao.md)):

```text
<CNPJS_NO_EDITAL>
38504819000169
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
depois de passar por `escape_xml()` (ver [Guardrails](../governanca/guardrails.md)).

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