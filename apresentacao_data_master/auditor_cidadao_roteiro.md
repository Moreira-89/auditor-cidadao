# Auditor Cidadão — Roteiro de Fala (versão detalhada)
> 25 slides · ~50-52 min de fala + ~15 min de perguntas ≈ 1h07
> Uso em conjunto com `auditor_cidadao_slides.md` (mesma numeração e títulos)
> Esta versão é deliberadamente mais longa que uma "nota de direção de palco" — cada slide traz
> uma fala guiada quase literal, os números exatos pra não precisar decorar, e um "se perguntarem"
> nos pontos mais prováveis de aprofundamento. Use como rede de segurança, não como texto pra ler.

---

## Slide 1 - Capa
**Tempo:** ~1 min

**Fala guiada:**
Abertura rápida, sem enrolação — a plateia quer contexto, não uma introdução longa. Algo como: "Boa tarde. Meu nome é Lucas Moreira, e o projeto que vou apresentar é o Auditor Cidadão — um agente de IA generativa que audita licitações públicas municipais. Nos próximos 45 minutos vou mostrar o problema que resolvemos, como a arquitetura funciona de ponta a ponta, e os resultados reais da nossa avaliação — inclusive onde ela reprovou, porque isso faz parte do processo, não é um detalhe que estou escondendo."

**Números/fatos para ter na ponta da língua:**
- Nome do projeto: **Auditor Cidadão**
- Trilha do case: **Assistência e Interação + Automação e Extração de Conhecimento**
- Papel: **Data Master — Engenheiro de IA**
- Plataforma publicada: `auditor-cidadao-production.up.railway.app`

**Transição:** "Antes de entrar no problema, um mapa rápido de onde vamos."

---

## Slide 2 - Agenda
**Tempo:** ~1 min

**Fala guiada:**
Passe rápido pelos 6 blocos, sem detalhar nenhum ainda — o objetivo aqui é só dar um mapa mental pra banca acompanhar o raciocínio depois. Diga algo como: "Vou seguir seis blocos: o problema e a solução; a arquitetura — agente, RAG e ferramentas; engenharia de prompt e segurança; avaliação de desempenho com números reais; ética, LGPD e limitações; e por fim os próximos passos." Avise que perguntas podem ficar pro final (slide 24), mas que você pode pausar se a pergunta for crítica pro entendimento do que vem a seguir.

**Transição:** "Vamos começar pelo problema."

---

## Slide 3 - O problema
**Tempo:** ~2 min

**Fala guiada:**
Conte como uma história curta, concreta: "Imagine um jornalista ou um cidadão que recebe um edital de licitação de 40 páginas e quer saber se está tudo certo. Pra isso, ele precisaria abrir seis abas diferentes — o PNCP pra ver o histórico de contratações do órgão, a Receita Federal pra checar cada CNPJ envolvido, o CEIS e o CNEP pra ver se alguma empresa está sancionada — cruzar tudo manualmente, e ainda saber interpretar juridicamente o que está vendo. Isso não escala. E é por isso que a fiscalização social, que devia ser uma camada real de controle sobre gasto público, praticamente não acontece na prática — principalmente em municípios pequenos, que não têm imprensa especializada nem estrutura de auditoria própria."

Aponte o diagrama enquanto fala: edital no centro, três setas saindo pra PNCP, Receita Federal e CEIS/CNEP, todas rotuladas "consulta manual" — é exatamente o gargalo que você acabou de descrever em palavras.

**Números/fatos para ter na ponta da língua:**
- As 3 fontes que precisam ser cruzadas manualmente hoje: **PNCP, Receita Federal, CEIS/CNEP**
- O recorte do projeto é **municipal** (não estadual/federal) — municípios pequenos são o ponto mais carente de fiscalização

**Transição:** "É esse gargalo que o Auditor Cidadão resolve."

---

## Slide 4 - A solução
**Tempo:** ~2 min

**Fala guiada:**
Explique o fluxo em uma frase: "O cidadão faz upload do edital em PDF, o sistema indexa automaticamente por RAG, um agente de IA decide sozinho quais fontes oficiais consultar, varre 9 categorias de anomalia, e devolve um laudo estruturado com evidências e um score de risco — tudo isso em streaming, em tempo real." Aponte os três cards enquanto fala (upload/indexação → agente investiga → laudo).

**A frase mais importante do slide vem agora — diga-a devagar, com ênfase, é a postura ética do projeto inteiro e volta a aparecer no bloco de governança (slide 20):** "O sistema sinaliza padrões para investigação humana — não substitui uma auditoria formal."

**Números/fatos para ter na ponta da língua:**
- **9 categorias de anomalia** (A–I) — detalhe vem no slide 13
- O upload é de **edital ou contrato** em PDF

**Transição:** "Antes de entrar em arquitetura, um mapa de conformidade — pra deixar claro que sei exatamente o que a banca está avaliando."

---

## Slide 5 - O que a banca espera ver (requisitos do case)
**Tempo:** ~2 min

**Fala guiada:**
Apresente como um "mapa de conformidade": "Esse case tem seis requisitos técnicos obrigatórios — T1 a T6 — e cada um deles é tratado num bloco específico da apresentação. Deixo isso explícito agora pra não haver ambiguidade sobre onde cada ponto é respondido." Aponte a tabela rapidamente, sem ler célula por célula.

**Números/fatos para ter na ponta da língua (memorize os 6 códigos — são citados a apresentação toda):**
- **T1** — Modelo de IA → Bloco 2
- **T2** — Prompts + orquestração → Bloco 2/3
- **T3** — Uso de dados (RAG) → Bloco 3
- **T4** — Estratégia de modelo + avaliação → Bloco 4
- **T5** — Arquitetura com agentes → Bloco 2/5
- **T6** — Ética, privacidade, responsabilidade → Bloco 5

**Se perguntarem** "por que você separou em blocos assim?": responda que os blocos seguem a ordem natural do pipeline (modelo → prompt → dados → avaliação → arquitetura → ética), não uma ordem arbitrária.

**Transição:** "Bloco 2 começa aqui: visão de 30 mil pés da stack antes de entrar em cada escolha em detalhe."

---

## Slide 6 - Stack e arquitetura macro
**Tempo:** ~2 min

**Fala guiada:**
"Esta é a visão de 30 mil pés. Backend em FastAPI com LangGraph orquestrando o agente. O LLM é o OpenAI `gpt-4o-mini`, embeddings com `text-embedding-3-small`. Banco vetorial é o Pinecone, e as ferramentas externas de licitação vêm via protocolo MCP, conectado ao PNCP. Deploy é um único container Docker no Railway." Avise que cada uma dessas escolhas tem uma justificativa específica que você vai detalhar peça por peça nos próximos slides — não é "usamos X porque é popular".

**Números/fatos para ter na ponta da língua:**
- Backend: **FastAPI + LangGraph**
- LLM: **OpenAI `gpt-4o-mini`** · Embeddings: **`text-embedding-3-small`**
- Banco vetorial: **Pinecone**
- Ferramentas externas via **MCP** (`@licinexusbr/mcp`)
- Deploy: **1 container Docker** no **Railway**

**Transição:** "Primeira escolha a justificar: por que esse modelo, e não outro."

---

## Slide 7 - T1: Por que `gpt-4o-mini`?
**Tempo:** ~2 min

**Fala guiada:**
Frame como decisão de custo-benefício, não de limitação técnica: "O papel do agente aqui é orquestrar ferramentas e redigir um laudo a partir de dados já recuperados — isso não exige raciocínio de fronteira. Só que esse modelo é chamado a cada turno de cada usuário, então custo importa de verdade. O `gpt-4o-mini` entrega qualidade suficiente pra essa tarefa a uma fração do custo, com uma janela de contexto de 128 mil tokens — folgada o bastante pra acomodar múltiplos resultados de tool num único turno."

Aponte a tabela ao lado: "Agente principal e extrator de laudo usam o mesmo `gpt-4o-mini` — decisão de consistência e custo, não preguiça. Os embeddings usam o `text-embedding-3-small`. E o único papel que usa o `gpt-4o`, mais caro, é o juiz da nossa avaliação com RAGAS — que nunca é chamado por um usuário real, só quando o time roda o golden dataset."

Seja honesto sobre o que ainda não foi feito: "Escolhemos com critério de custo-benefício pra essa primeira versão; uma comparação formal contra outros modelos, usando o mesmo golden dataset, é o próximo passo — não uma suposição."

**Números/fatos para ter na ponta da língua:**
- Contexto: **128k tokens**
- 4 papéis e modelos: agente (`gpt-4o-mini`, temp 0.1) · extrator (`gpt-4o-mini`, temp 0.0) · embeddings (`text-embedding-3-small`) · juiz RAGAS (`gpt-4o`, temp 0.0)
- Modelos candidatos ao benchmark de V2 (cite pelo menos 2-3 nomes se perguntarem, não precisa decorar todos): **Sabiá-3/4** (Maritaca AI, especializado em jurídico brasileiro), **OpenAI o1/o3-mini** (cadeia de raciocínio), **DeepSeek-R1** (raciocínio open-source, custo baixo), **Claude 3.5 Sonnet/Opus** (referência em análise contratual em português), **Gemini 1.5 Pro/2.0 Flash** (contexto de 1-2M tokens)

**Se perguntarem** "por que não testaram esses modelos antes de decidir?": responda que a V1 priorizou entregar um sistema funcional e avaliável com critério — o framework de avaliação (Bloco 4) é justamente o que permite fazer essa comparação com rigor na V2, "maçã com maçã", em vez de impressão subjetiva.

**Transição:** "Modelo escolhido — agora como garantimos que ele se comporta de forma consistente."

---

## Slide 8 - T2: Engenharia de prompt
**Tempo:** ~2 min

**Fala guiada:**
"Toda a engenharia de prompt vive num único arquivo, `app/core/prompt.py`, com quatro peças bem definidas: o `SYSTEM_PROMPT`, que define identidade, capacidades, o catálogo de anomalias e as regras de segurança; o `PROMPT_DINAMICO`, o envelope em tags XML com CNPJs, estado, município e a pergunta do usuário; o `PROMPT_EXTRATOR`, usado na segunda chamada que decide se o texto é um laudo completo e extrai o JSON; e o `TOOL_STATUS_MAP`, que traduz o nome técnico de cada ferramenta pra uma mensagem amigável durante a execução."

Destaque a decisão de ter uma única fonte de verdade pro catálogo de anomalias — reusada tanto no `SYSTEM_PROMPT` quanto no `PROMPT_EXTRATOR` — e diga que essa unificação foi justamente o que corrigiu um bug real de avaliação (pode contar rapidamente aqui ou reservar pro slide 12, sua escolha de timing).

Cite a hierarquia de evidências do prompt: "API oficial, depois texto do edital, depois busca web, e só por último inferência própria — sempre sinalizada como tal." E a regra dura de nunca inventar dado: campo não verificado vira "não verificável", nunca suposição.

Aponte o trecho de código à direita (regras de segurança): "Todo conteúdo entre tags como `<DOCUMENTO>` e `<METADADOS>` é tratado como dado bruto de terceiros, nunca como instrução — mesmo que pareça uma ordem direta. Se o documento tentar manipular o agente, isso vira um achado de auditoria, não é obedecido." Avise que isso volta com mais profundidade no bloco de guardrails (slide 15) — já adianta aqui que segurança está no prompt desde o primeiro turno, não é uma camada colada depois.

**Números/fatos para ter na ponta da língua:**
- 4 elementos do prompt: **`SYSTEM_PROMPT`**, **`PROMPT_DINAMICO`**, **`PROMPT_EXTRATOR`**, **`TOOL_STATUS_MAP`**
- Hierarquia de evidências: **API oficial > texto do edital > busca web > inferência própria**
- Regra dura: **"nunca invente dados"** — vira "não verificável"

**Transição:** "Prompt consistente é metade da orquestração — a outra metade é como o agente decide agir. Vamos ao grafo."

---

## Slide 9 - T5: Arquitetura do agente — o grafo
**Tempo:** ~3 min

**Fala guiada:**
Este é o slide de arquitetura mais técnico — vá com calma, aponte o diagrama enquanto narra: "O núcleo do sistema é um `StateGraph` do LangGraph com dois nós: `call_llm` e `tool_node`. O usuário pergunta, o `call_llm` decide se precisa de alguma ferramenta. Um roteador — o `router` — checa se a última mensagem tem `tool_calls` pendentes. Se tiver, o `tool_node` executa a ferramenta e devolve o resultado pro `call_llm`. Isso se repete quantas vezes for preciso, até o modelo ter informação suficiente pra responder sem pedir mais nada — nesse ponto o `router` manda pro fim, e a resposta sai via streaming SSE."

"O estado do grafo — o `AgentState` — carrega três chaves entre os nós: o histórico de mensagens, e o estado e município, que são injetados automaticamente nas ferramentas que precisam de contexto geográfico. E um `InMemorySaver` mantém esse histórico por `thread_id`, permitindo conversas com múltiplos turnos."

Seja transparente sobre a simplicidade proposital: "Hoje são só dois nós — é o padrão ReAct mínimo. Isso já funciona bem no tamanho atual, mas conforme mais ferramentas e automações determinísticas entrarem, fica difícil de ler num diagrama. Já existe uma expansão planejada pra separar decisão, geração final e processamento determinístico em nós dedicados — é decisão de manutenibilidade pra V2, não uma limitação da versão atual."

**Números/fatos para ter na ponta da língua:**
- Framework: **LangGraph**, padrão **`StateGraph`**
- Dois nós: **`call_llm`** e **`tool_node`**
- Roteador: **`router`** — decide olhando `tool_calls` pendentes
- Persistência de conversa: **`InMemorySaver`**, chaveado por **`thread_id`**
- `recursion_limit` do grafo: **50**

**Se perguntarem** "e se o grafo entrar em loop infinito?": cite o `recursion_limit=50` como rede de segurança.

**Transição:** "Esse `tool_node` executa ferramentas — quais, exatamente, e de onde elas vêm?"

---

## Slide 10 - Ferramentas do agente e o protocolo MCP
**Tempo:** ~2-3 min

**Fala guiada:**
"O agente tem 4 ferramentas nativas: consulta à Receita Federal, busca semântica no edital indexado, consulta de sanções no CEIS/CNEP, e busca web complementar. E tem mais 11 ferramentas de PNCP, consumidas via um protocolo chamado MCP — Model Context Protocol." Explique em uma frase pra quem não conhece: "é um protocolo aberto que permite a um agente consumir ferramentas prontas de terceiros, como se fossem plugins."

"O ganho real foi de escopo: não precisamos reimplementar paginação, schemas e tratamento de erro de uma API pública inteira — reaproveitamos 11 ferramentas de PNCP já validadas. O custo foi arquitetural: o container agora roda Node.js 20 além de Python, porque o servidor MCP roda como subprocesso Node. Se o `npx` falhar no boot, a aplicação falha de propósito — fail-fast, não silenciosamente."

Mencione o cache: "Um cache com TTL de 24 horas envolve todas as tools, nativas e MCP — os dados do PNCP mudam pouco ao longo do dia, então cachear evita custo e latência repetidos."

Se sobrar tempo ou vier pergunta de profundidade, o detalhe do `patch_mcp_tools`: "o LLM às vezes manda número como texto — '2024' em vez de 2024. Isso gera conflito: o Pydantic do lado Python rejeitaria antes da chamada, e o servidor MCP, validado via Zod do lado Node, rejeitaria do outro lado. O patch afrouxa o schema pra aceitar o texto e depois converte de volta pro tipo nativo antes de chamar o MCP."

**Números/fatos para ter na ponta da língua:**
- **4 ferramentas nativas**: Receita Federal, RAG do edital, sanções CEIS/CNEP, busca web
- **11 ferramentas de PNCP via MCP** (`@licinexusbr/mcp`) — confirmado em `app/services/lifespan.py` (`TOOLS_MCP_SELECIONADAS` tem exatamente 11 entradas: `search_licitacoes`, `search_contratos`, `get_contrato`, `list_contrato_termos`, `list_licitacao_arquivos`, `aggregate_licitacoes_por_periodo`, `get_licitacao`, `list_licitacao_itens`, `list_licitacao_resultados`, `search_atas_rp`, `compare_periodos`)
- Cache: **TTL de 24h**, `cachetools.TTLCache`, chave MD5 (tool + argumentos)
- Existe uma **5ª ferramenta nativa implementada mas desativada de propósito** (`buscar_contratos_fornecedor_pncp`) — motivo: rate limit agressivo do PNCP e risco de timeout de proxy, já que o streaming SSE não emite eventos durante a execução de uma tool

**Se perguntarem** "por que não ativar essa 5ª ferramenta?": responda que está documentada como limitação conhecida, não esquecida — a varredura completa de um órgão pode levar minutos, e ativá-la sem heartbeats periódicos no SSE arrisca quebrar o streaming em produção.

**Transição:** "Uma dessas ferramentas nativas é o RAG do edital — vamos ao pipeline de dados."

---

## Slide 11 - T3: Pipeline de dados — RAG do edital
**Tempo:** ~3 min

**Fala guiada:**
"O fluxo é: upload do PDF, extração de texto com `pdfplumber`, chunking, geração de embeddings, e upsert no Pinecone." Justifique RAG vs fine-tuning de forma direta: "Fine-tuning ensinaria um estilo, não um documento específico — e teria que ser refeito a cada edital novo, o que é inviável. RAG ancora a resposta em texto real recuperado, reduz alucinação, e permite responder sobre um documento que o modelo nunca viu."

Detalhe o pipeline: "Os chunks são de 2000 caracteres, com overlap de 200, usando separadores hierárquicos — parágrafo, linha, frase. A busca semântica é filtrada por estado e município, com `top_k=3`." Seja honesto: "esses valores de chunking e o `top_k` foram escolhas de boa prática de mercado, não ajustadas empiricamente neste projeto — e a avaliação, no próximo bloco, mostrou que isso é uma alavanca real, não só teórica."

Mencione também a extração de CNPJs: "em paralelo, o texto passa por regex e validação via `validate-docbr`, extraindo os CNPJs do edital — eles voltam pro frontend e são reenviados em cada pergunta subsequente."

**Números/fatos para ter na ponta da língua:**
- Extração: **`pdfplumber`**
- Limites de upload: rejeita não-PDF (**415**) ou arquivos acima de **20 MB** (**413**)
- Chunking: **2000 caracteres**, overlap **200**, separadores hierárquicos (parágrafo → linha → frase → palavra)
- Embeddings: **`text-embedding-3-small`**, **1536 dimensões**
- Busca: filtrada por **estado + município**, **`top_k=3`** (configurável via env var `TOP_K_EDITAL`, não exposta à tool que o LLM chama)
- Extração de CNPJ: **regex + `validate-docbr`**

**Se perguntarem** "por que top_k=3 e não mais?": adiante que o slide 17 mostra o impacto real disso na avaliação — 2 dos 5 casos problemáticos seriam resolvidos com `top_k` maior.

**Transição:** "Esse mesmo pipeline de indexação foi onde encontramos o bug mais sério do projeto."

---

## Slide 12 - O bug de produção que a avaliação encontrou
**Tempo:** ~2 min

**Fala guiada:**
Este é o slide de maior impacto de storytelling — não tenha pressa. "Durante a validação do nosso framework de avaliação, notamos uma instabilidade estranha numa métrica. Investigando a fundo — não foi um teste manual, foi a avaliação automatizada que expôs isso — encontramos um bug real no código de indexação, o `gerenciadorvetorial.py`, que é compartilhado entre o pipeline de teste e o fluxo real de produção."

Aponte o diff: "A linha errada multiplicava uma lista por um dicionário — `[metadados] * len(lista_chunks)` — o que cria N referências ao *mesmo* dicionário, não N cópias independentes. O resultado: todo chunk indexado, de qualquer edital, inclusive de usuários reais em produção, era salvo com o texto do *último* chunk do documento. E o pior: os embeddings, calculados antes dessa mutação, continuavam corretos — então o bug ficava mascarado atrás de scores de similaridade que pareciam plausíveis."

"Corrigimos trocando pra `[dict(metadados) for _ in lista_chunks]` — uma cópia independente por chunk. O banco de produção já estava limpo no momento da correção, então não precisou reindexar nada."

Feche com a resposta pronta pra T4: "essa é a resposta direta pra 'como a avaliação ajudou a encontrar problemas reais, não só medir números' — e vale citar que esse foi 1 de 5 bugs reais encontrados durante a validação do framework; os outros quatro corrigiram o próprio pipeline de teste, esse aqui era o único que afetava usuários reais."

**Números/fatos para ter na ponta da língua:**
- Arquivo: **`app/services/gerenciadorvetorial.py`**
- Linha errada: **`[metadados] * len(lista_chunks)`**
- Correção: **`[dict(metadados) for _ in lista_chunks]`**
- **5 bugs reais** encontrados na validação do framework — esse foi o único de produção

**Transição:** "Falando em critérios de anomalia — o que exatamente o agente está procurando?"

---

## Slide 13 - Catálogo de anomalias (A–I)
**Tempo:** ~2 min

**Fala guiada:**
Não leia as 9 categorias uma a uma — cite 2 ou 3 exemplos concretos e diga que o catálogo completo está na documentação. Sugestão de exemplos: "sobrepreço, quando o valor unitário está mais de 30% acima da mediana de mercado; direcionamento, quando o edital parece escrito sob medida pra uma empresa específica; e a mais grave, sanção vigente — quando a empresa vencedora já está proibida por lei de contratar com o poder público, conforme a Lei 14.133, artigo 14."

O ponto técnico a reforçar: "ter uma única fonte de verdade pros critérios — a mesma constante usada no prompt do agente e no do extrator — evitou divergência entre o que o agente investiga e o que o extrator classifica. Foi exatamente a ausência dessa unificação que causou um dos bugs que encontramos na avaliação."

**Referência rápida das 9 categorias (não precisa recitar, mas tenha por perto caso perguntem uma específica):**
- **A** — Sobrepreço (>30% acima da mediana, 12 meses)
- **B** — Direcionamento (especificação restritiva demais)
- **C** — Fracionamento irregular (Lei 14.133, art. 75)
- **D** — Cartel/Conluio (sócios/endereço em comum)
- **E** — Empresa recém-criada (<12 meses de CNPJ)
- **F** — Prazo insuficiente (Lei 14.133, art. 55)
- **G** — Reincidência suspeita (>50% das vitórias no órgão)
- **H** — Sanção vigente (Lei 14.133, art. 14) — **a mais grave, risco crítico**
- **I** — Incompatibilidade de atividade (CNAE × objeto)

**Se perguntarem sobre a Anomalia H especificamente:** qualquer registro em CEIS ou CNEP caracteriza H — suspensão, impedimento, inidoneidade, multa — e registros acessórios (como uma multa) não anulam nem diluem a caracterização trazida por outros registros do mesmo CNPJ.

**Transição:** "Nem todas as 9 são verificáveis hoje — vamos à cobertura real."

---

## Slide 14 - Cobertura real hoje
**Tempo:** ~1 min

**Fala guiada:**
Transparência rápida: "Nem tudo que o catálogo promete está 100% coberto hoje, e isso é intencional e documentado. Hoje 6 das 9 anomalias são verificáveis com as fontes já integradas. Sobrepreço e Cartel/Conluio dependem de bases que ainda não temos — catálogo de preços de referência, e quadro societário. O sistema nunca declara um edital totalmente limpo quando uma verificação não pôde ser concluída — o score mínimo aplicado nesse caso é MÉDIO, nunca 'limpo'."

**Números/fatos para ter na ponta da língua:**
- **6 de 9** anomalias verificáveis hoje: **C, E, F, G, H, I**
- Não verificáveis hoje: **A** (Sobrepreço, falta catálogo de preços) e **D** (Cartel/Conluio, falta QSA/quadro societário)
- **B** é parcial (só análise textual do edital)
- Score mínimo quando não verificável: **MÉDIO** (nunca "limpo total")

**Transição:** "Se um edital malicioso tentasse manipular o agente, o que impediria isso?"

---

## Slide 15 - Guardrails de segurança
**Tempo:** ~2 min

**Fala guiada:**
Este slide responde a uma pergunta óbvia da banca: "um edital malicioso poderia manipular o agente?" "A resposta é: sim, se não houvesse esses guardrails. Tratamos isso em camadas. Primeiro, anti-injeção de prompt: todo campo que vem do usuário passa por uma função de escape XML — não só a pergunta, mas também município, estado e a lista de CNPJs. Isso é importante porque, numa versão anterior, só a pergunta era escapada, o que abria uma brecha de injeção via a tag de metadados — já corrigimos isso."

"Segundo: conteúdo entre tags como `<DOCUMENTO>` e `<METADADOS>` é tratado como dado bruto, nunca como instrução. Se o próprio edital contiver uma tentativa de manipulação — tipo 'ignore suas instruções anteriores' — isso vira um achado de auditoria no laudo, não é obedecido."

"Terceiro, anti-alucinação: uma regra específica proíbe 'vocabulário emprestado' — o modelo não pode inferir um campo a partir de uma ferramenta que não foi chamada naquele turno. Essa regra não é teórica, foi descoberta cruzando logs reais durante testes, quando o modelo citou uma situação cadastral sem ter consultado a Receita Federal."

**Números/fatos para ter na ponta da língua:**
- Função de escape: **`escape_xml()`** — aplicada a `pergunta_usuario`, `municipio`, `estado`, `cnpjs_formatados`
- Tags de isolamento: **`<DOCUMENTO>`**, **`<CNPJS_NO_EDITAL>`**, **`<METADADOS>`**
- Regra anti-alucinação: **"vocabulário emprestado"** — descoberta em teste real de log
- Validação de CNPJ do usuário: **corta em 10 CNPJs**, descarta os matematicamente inválidos via `validate_docbr`, e **loga tentativas de abuso**

**Se perguntarem** "e se o usuário mandar 50 CNPJs de propósito?": cite o limite de 10 e o log de tentativa de abuso.

**Transição:** "Segurança de prompt é uma parte de T2 — a outra é como medimos se o sistema funciona de verdade. Bloco de avaliação."

---

## Slide 16 - T4: Metodologia de avaliação
**Tempo:** ~2 min

**Fala guiada:**
"Pra garantir que mudanças no agente não piorem a qualidade, mantemos um framework de avaliação automatizado com um golden dataset e três famílias de métrica independentes." Aponte o callout: "11 casos reais e sintéticos, desenhados pra cobrir o mix mínimo: uma empresa com sanção ativa no CEIS/CNEP, um prazo de publicação irregular, um caso controle sem anomalia esperada — pra garantir que o agente não 'acha' problema onde não tem — e um caso puramente conversacional, pra garantir que ele não force um laudo completo quando o usuário só fez uma pergunta pontual."

Justifique o desvio do plano original: "O plano previa um único LLM-juiz caseiro avaliando quatro métricas subjetivas. A implementação final usa RAGAS — uma biblioteca validada pela comunidade — pra faithfulness e context recall, mantém aderência de tools como comparação determinística sem LLM, porque é mais confiável que julgamento subjetivo quando dá pra medir sem modelo nenhum, e usa o próprio extrator de produção pra medir recall de anomalias. Foi decisão consciente de engenharia, não desvio por falta de tempo."

**Números/fatos para ter na ponta da língua:**
- Golden dataset: **11 casos** (reais + sintéticos)
- 3 métricas: **`aderencia_tools`** (determinística, sem LLM) · **`recall_anomalias`** (reusa o extrator de produção) · **RAGAS** `faithfulness` + `context_recall` (juiz `gpt-4o`)
- Plano original descartado conscientemente: um único LLM-juiz caseiro avaliando 4 métricas (`relevancia`, `fidelidade`, `aderencia_tools`, `deteccao_anomalia` booleana)

**Transição:** "E os números reais dessa avaliação são estes."

---

## Slide 17 - T4: Resultados da avaliação
**Tempo:** ~3 min

**Fala guiada:**
Este é o slide mais importante da apresentação em termos de credibilidade técnica — não esconda o resultado reprovado, apresente com confiança. "Na rodada mais recente de validação, três métricas aprovaram com folga: aderência de tools em 1.00, recall de anomalias em 1.00, e faithfulness em 0.858 — acima do limiar de 0.85. A única métrica que reprova é context recall, em 0.60, abaixo do limiar de 0.75."

Se quiser mostrar profundidade histórica (bom sinal de rigor metodológico, não é obrigatório): "isso já foi mais instável — em seis execuções anteriores, faithfulness oscilava entre 0.79 e 0.88, reprovando em duas delas. Essa rodada mais recente aprovou com folga, o que é um sinal encorajador, mas uma rodada só ainda não é suficiente pra declarar a instabilidade resolvida — seguimos monitorando."

Explique a causa raiz do context_recall, que é a mesma de sempre e não mudou: "De 5 casos elegíveis ao RAGAS, 2 têm o trecho-alvo posicionalmente distante no documento — fora do alcance do nosso `top_k=3`, e continuam fora mesmo testando até `top_k=50`. É uma limitação real de recuperação, não um bug — endereçável com `top_k` maior ou reranking, já mapeada como próximo passo. E o fato desse número se repetir idêntico entre rodadas reforça que é uma causa sistemática, não ruído pontual."

Feche com a frase: "o framework existe para expor limitações, não para maquiar números — e foi isso que ele fez: hoje, das quatro métricas, só uma reprova, e sabemos exatamente por quê."

**Números/fatos para ter na ponta da língua (os mais importantes da apresentação inteira — use os da rodada mais recente):**
- `aderencia_tools`: limiar **≥0.70**, resultado **1.000** ✅
- `recall_anomalias`: limiar **≥0.80**, resultado **1.000** ✅
- `faithfulness`: limiar **≥0.85**, resultado **0.858** ✅ (histórico: oscilava 0.79–0.88 em 6 execuções anteriores, com 2 reprovações — mencione só se quiser mostrar profundidade)
- `context_recall`: limiar **≥0.75**, resultado **0.600** ❌ — **inalterado** em relação às execuções anteriores
- Veredito geral: **reprovado**, causa isolada de `context_recall` — agora ainda mais isolada (só 1 de 4 métricas falha)
- Causa raiz do `context_recall`: **2 de 5 casos** elegíveis têm o trecho-alvo fora do alcance mesmo em `top_k=50`
- `caso_06` foi **excluído do cálculo de RAGAS** (afirmação negativa, métrica não tem mecanismo pra validar ausência de informação) — mantido nas demais métricas

**Se perguntarem** "por que não subiram o top_k antes da apresentação?": responda que subir top_k aumenta custo de token por chamada e pode piorar faithfulness (mais contexto irrelevante pro modelo confundir) — não é troca sem custo, decisão de valor final foi adiada pra V2 com dado suficiente.

**Se perguntarem** "faithfulness estava instável, por que agora está aprovado?": seja honesto — é uma rodada nova que aprovou com folga, um sinal encorajador, mas ainda cedo pra declarar resolvido com uma única rodada. O item continua em acompanhamento no backlog de V2 (hipótese da `temperature=0.1` do agente ainda não testada isoladamente).

**Transição:** "Voltando pro produto — como essa resposta chega até o usuário em tempo real?"

---

## Slide 18 - Streaming e extração estruturada
**Tempo:** ~1-2 min

**Fala guiada:**
"A resposta é transmitida via Server-Sent Events: tokens de texto conforme são gerados, e mensagens de status quando uma ferramenta é acionada, tipo 'Consultando Receita Federal...'." Mostre atenção a detalhe: "se o laudo fosse acumulado direto no stream, texto de raciocínio intermediário do agente contaminaria o resultado final — porque o modelo pode emitir conteúdo parcial antes de os `tool_calls` daquele turno aparecerem completos no chunk. Resolvemos isso com buffer-then-commit: cada fragmento vai pra um buffer temporário durante o streaming, e só é confirmado no laudo final quando a mensagem inteira termina sem pedir mais nenhuma ferramenta."

Feche mencionando a segunda chamada: "depois, uma segunda chamada ao LLM, agora com temperatura zero, converte esse Markdown final em JSON estruturado pro frontend. É uma chamada extra, um custo consciente — mas separar 'gerar a resposta' de 'estruturar a resposta' evita que o modelo tente preencher um laudo em cima de uma pergunta puramente conversacional."

**Números/fatos para ter na ponta da língua:**
- Protocolo: **Server-Sent Events (SSE)**
- Eventos emitidos: **`token`**, **`status`**, **`laudo_estruturado`**, **`laudo_estruturado_erro`**, **`done`/`error`**
- Mecanismo: **buffer-then-commit** — confirma em `on_chat_model_end`, não em `on_chat_model_stream`
- Segunda chamada ao LLM: **temperatura 0**, extrai JSON via `with_structured_output`

**Transição:** "Isso tudo roda onde, exatamente, em produção?"

---

## Slide 19 - T5: Infraestrutura e deploy
**Tempo:** ~2 min

**Fala guiada:**
"Um único container Docker, com Python 3.12 e Node.js 20, publicado no Railway. O mesmo Dockerfile usado localmente é o que roda em produção — zero divergência de ambiente. O FastAPI serve o frontend estático e a API na mesma porta." Reforce reprodutibilidade (requisitos R1/R2/R3 do case): "qualquer pessoa builda a mesma imagem localmente, ou usa o Railway, sem configuração divergente."

Seja direto sobre a limitação: "o histórico de conversa fica em memória, com `InMemorySaver` — é decisão consciente de simplicidade pro estágio atual, com migração pro `PostgresSaver` já mapeada. Isso não afeta o único estado que realmente precisa persistir, que é o Pinecone — gerenciado externamente, sobrevive a qualquer restart do container."

**Números/fatos para ter na ponta da língua:**
- 1 container: **Python 3.12 + Node.js 20**
- Deploy: **Railway**
- 6 serviços externos gerenciados: **OpenAI, Pinecone, Portal da Transparência/CGU (CEIS/CNEP), BrasilAPI, Tavily, PNCP**
- Único estado que sobrevive a restart: **Pinecone** (externo)
- Limitação conhecida: **`InMemorySaver`** → migração planejada pra **`PostgresSaver`**

**Transição:** "Arquitetura e infraestrutura cobertas — falta o bloco de responsabilidade: ética e LGPD."

---

## Slide 20 - T6: Ética, LGPD e responsabilidade
**Tempo:** ~2 min

**Fala guiada:**
"Esse é o requisito T6 do case — trato como bloco próprio, não como rodapé." Repita a frase do slide 4, com o mesmo peso: "o sistema sinaliza padrões, não substitui uma auditoria formal." Percorra os quatro princípios: "os dados tratados são só informação pública — CNPJ, editais, bases governamentais. O nome do usuário não é mais coletado em lugar nenhum do sistema — endpoint, prompt ou formulário — reduzindo a superfície de dado pessoal. O laudo é sempre um indício pra investigação humana, nunca uma acusação ou decisão final. E a retenção indefinida de editais no Pinecone é decisão deliberada, não descuido — pensada pra viabilizar cruzamento histórico numa V2, já que o dado em questão é público por natureza."

**Números/fatos para ter na ponta da língua:**
- Dado tratado: **apenas informação pública** (CNPJ, editais, bases governamentais)
- **Nome do usuário não é mais coletado** (removido de ponta a ponta: request, prompt, frontend)
- Retenção de editais no Pinecone: **indefinida, decisão deliberada** (sem dado pessoal sensível)

**Se perguntarem** "e se o edital tiver dado pessoal sensível dentro do texto (nome de servidor, etc.)?": reconheça como ponto em aberto — o projeto trata o dado agregado como público por natureza do documento (edital municipal), mas uma análise mais fina de PII dentro do corpo do texto não foi implementada; é uma resposta honesta, não tente inventar uma solução que não existe.

**Transição:** "Com tudo isso no lugar, um resumo das decisões que exigiram trade-off consciente."

---

## Slide 21 - Decisões e trade-offs (resumo)
**Tempo:** ~2 min

**Fala guiada:**
"Consolido aqui, num slide só, as decisões que já expliquei ao longo da apresentação." Não reexplique cada uma em detalhe — aponte e diga "já vimos o porquê de cada uma":
- **RAG vs fine-tuning** — venceu por não exigir retrain a cada edital novo
- **MCP vs integração própria com PNCP** — reuso de 11 tools validadas, custo de dependência Node.js
- **RAGAS + determinístico vs juiz único** — mais confiável pra métricas sem julgamento subjetivo
- **Buffer-then-commit vs regex** — delega ao LLM extrator decidir "isso é um laudo?", não a um padrão de texto frágil

A banca valoriza ver que cada trade-off foi tratado como decisão de engenharia, não acidente — reforce isso em uma frase e siga em frente, sem alongar.

**Transição:** "E olhando pra frente — o que ainda falta, e o que vem na V2."

---

## Slide 22 - Limitações conhecidas e próximos passos
**Tempo:** ~3 min

**Fala guiada:**
Abra com a leitura de maturidade: "o projeto tem um roadmap real, não uma lista vaga de 'melhorias futuras' — cada item aqui nasceu de uma limitação identificada e documentada ao longo do próprio desenvolvimento e da avaliação." Depois, passe pelos quatro bullets dando 1 frase de causa a cada um — não é uma lista solta:
- **`context_recall`** veio direto do resultado reprovado que vimos no slide 17 — solução mapeada: aumentar `top_k` ou reranking.
- **`PostgresSaver`** resolve a limitação de memória do `InMemorySaver` do slide 19.
- **Fase 7** (indexação automática via PNCP) elimina o upload manual — e, junto dela, migra o metadado do Pinecone de `estado`/`município` pra uma lista de CNPJs extraída automaticamente do próprio edital.
- **Expansão do golden dataset** pra 30+ casos, cobrindo as 9 categorias de anomalia (hoje são 11 casos).

Conecte dois pontos que a banca vai gostar de ver ligados: "essa migração de metadado da Fase 7 é o que viabiliza uma tool nova, `buscar_historico_empresa` — ela recebe um CNPJ e cruza todos os editais já indexados onde ele aparece, mesmo em municípios diferentes. Hoje isso é impossível, porque a busca é isolada por município." Aponte o painel de módulos ao lado: "essa mesma ideia aparece ali como 'Monitor de Fornecedores' — uma vira ferramenta interna do agente, a outra vira módulo de produto pro usuário final. É a mesma peça de engenharia respondendo a dois públicos diferentes."

Se quiser reforçar ainda mais a maturidade técnica — bom gancho pra pergunta de profundidade: "boa parte dos novos cruzamentos já mapeados pro catálogo de anomalias não exige integrar nenhuma fonte nova. A Receita Federal, via BrasilAPI, já devolve capital social, CNAEs secundários e quadro societário no mesmo request que o projeto já faz hoje — só que esses campos são descartados antes de chegar no LLM. É uma resposta forte pra 'o que vem depois', porque mostra que já sabemos exatamente onde crescer sem reinventar a arquitetura, só parar de jogar dado fora."

**Números/fatos para ter na ponta da língua:**
- 4 bullets do slide: `context_recall`/`top_k` · `PostgresSaver` · Fase 7 (indexação automática + migração de metadado) · golden dataset 30+ casos
- Tool nova viabilizada pela Fase 7: **`buscar_historico_empresa`** (cruzamento cross-município por CNPJ)
- Dado já capturado e hoje descartado: **`capital_social`, CNAEs secundários, quadro societário (QSA)** via BrasilAPI
- Módulos futuros no painel (agora 5): **Auditor de Contratos, Monitor de Fornecedores, Alertas Automáticos, Auditoria Estadual** (marcada com o selo "plano futuro" — é a mais distante do escopo atual), **API Pública**

**Transição:** "Esse painel de módulos, na verdade, é só um recorte de uma visão bem maior — deixa eu mostrar."

---

## Slide 23 - Visão de longo prazo: o ecossistema
**Tempo:** ~1-2 min

**Fala guiada:**
Este é o slide de fechamento de visão — fala com mais energia e convicção pessoal aqui, é diferente do tom técnico dos slides anteriores. "O Auditor Cidadão não é o produto final — é a ponta visível de um iceberg. O que está em produção hoje, funcionando de ponta a ponta, é só uma fração do que pretendo construir. Por baixo da superfície está um ecossistema inteiro de fiscalização pública: um Auditor de Contratos, que estende a análise pra fase de execução; um Monitor de Fornecedores; Alertas Automáticos; uma expansão futura pra Auditoria Estadual; e uma API pública pra jornalistas, ONGs e sistemas de transparência consumirem esse laudo como serviço."

Feche com o compromisso pessoal, é o que dá peso a esse slide: "esse é o horizonte que já guiou boa parte das decisões técnicas que vocês viram até aqui — arquitetura pensada pra crescer, não pra ficar presa a essa única aplicação. Os meus próximos projetos vão ser dedicados a expandir esse ecossistema."

**Números/fatos para ter na ponta da língua:**
- Metáfora: **Auditor Cidadão = ponta do iceberg**; ecossistema completo = massa submersa
- 5 módulos do ecossistema (mesmos do painel do slide 22): **Auditor de Contratos, Monitor de Fornecedores, Alertas Automáticos, Auditoria Estadual, API Pública**
- Mensagem central: arquitetura da V1 já **pensada pra crescer** em ecossistema, não é um projeto isolado

**Se perguntarem** "isso é só uma ideia, ou já tem plano concreto?": responda que os módulos mais próximos (Auditor de Contratos, Monitor de Fornecedores) reaproveitam peças de engenharia que já existem hoje — cite de novo a tool `buscar_historico_empresa` do slide 22 como exemplo de algo que já está desenhado, não é só intenção vaga.

**Transição:** "Fechando com uma síntese curta do que foi entregue na V1."

---

## Slide 24 - Conclusão
**Tempo:** ~1 min

**Fala guiada:**
Fechamento curto e direto — não repita tudo. "Entrego uma ferramenta que já funciona hoje, ponta a ponta, reproduzível e documentada. Uma arquitetura de agente com ferramentas, RAG e guardrails de segurança reais. Uma avaliação com resultados honestos — inclusive onde reprovou. E sei exatamente onde ela ainda falha, com um plano concreto pra cada uma dessas falhas — e uma visão clara de até onde isso pode chegar." Abra pra perguntas.

**Transição:** "Fico à disposição para perguntas."

---

## Slide 25 - Perguntas
**Tempo:** ~15 min de perguntas

**Fala guiada:**
Abra o espaço e deixe a banca conduzir — não tente preencher o silêncio, dê tempo pra formularem a pergunta.

**Perguntas prováveis com resposta já preparada:**

1. **"Por que `gpt-4o-mini` e não outro modelo?"** → custo-benefício pro papel de orquestração (slide 7); benchmark formal contra Sabiá-3/4, o1/o3-mini, DeepSeek-R1, Claude 3.5, Gemini está mapeado como V2, usando o mesmo golden dataset.

2. **"Por que `context_recall` reprovou, e o que fazer a respeito?"** → 2 de 5 casos elegíveis têm o trecho-alvo fora do alcance mesmo em `top_k=50` — limitação real de posição no documento, endereçável com `top_k` maior ou reranking (slide 17/22).

3. **"Como os guardrails se comportam contra um edital malicioso?"** → escape XML em todos os campos, tags como dado bruto, tentativa de manipulação vira achado de auditoria, regra de vocabulário emprestado (slide 15).

4. **"Por que a métrica de avaliação diverge do plano original do roadmap?"** → RAGAS validado pela comunidade + determinístico onde dá, em vez de um único LLM-juiz caseiro — decisão consciente de engenharia (slide 16).

5. **"Como o sistema escala? O que impede um usuário de gastar tokens indefinidamente?"** — ⚠️ **gap real, não escondido, prepare-se para essa:** hoje não existe autenticação, rate limiting ou quota de uso — um usuário poderia conversar (e gastar tokens da OpenAI) sem limite algum. Seja direto: é um gap real e documentado no roadmap, não um descuido silencioso. Opções já avaliadas pra V2: rate limiting por sessão/IP, quota diária por `thread_id`, timeout de conversa por inatividade, e autenticação mínima como pré-requisito pra qualquer limite por usuário funcionar de fato. Ter essa resposta pronta transforma um ponto fraco em prova de que vocês sabem exatamente onde estão os riscos do sistema.

6. **"E se a V2 introduzir paralelismo entre sub-agentes?"** → o `buffer_temporario` do streaming hoje assume execução sequencial. Se houver paralelismo real, a migração seria pra um dicionário de buffers indexado por `run_id` — já mapeado, não é um limite desconhecido da arquitetura.

7. **"Quantas ferramentas de PNCP o agente realmente tem?"** → responda **11**, com confiança — confirmado direto em `app/services/lifespan.py` (`TOOLS_MCP_SELECIONADAS`). O roadmap tinha um número desatualizado (12) em três trechos, já corrigido para 11 em 2026-07-08.

8. **"O que acontece se dois usuários indexarem editais ao mesmo tempo?"** → hoje todo mundo indexa no mesmo namespace do Pinecone, isolado só por filtro de metadado (estado+município) — não há isolamento por `thread_id`/sessão ainda. É um cenário de concorrência mapeado, mas sem solução implementada; isolar por `thread_id` introduziria um problema novo de ciclo de vida (quando apagar o namespace de uma sessão encerrada).

9. **"Por que RAG e não simplesmente aumentar o contexto do modelo (ex.: Gemini com 1-2M tokens)?"** → mesmo com contexto grande, RAG ainda ancora a resposta em texto recuperado explicitamente, o que facilita citar a fonte exata e auditar de onde veio cada afirmação — contexto longo sozinho não resolve rastreabilidade de evidência.

**Transição:** encerramento natural — agradeça e, se ninguém mais tiver pergunta, aponte pro slide de contato/links caso a apresentação tenha esse encerramento formal em separado.

---

## Notas finais (não fazem parte do roteiro em si)

- **25 slides** (após a adição do slide 23 de visão de longo prazo) — dá ~1,8 min médio por slide de conteúdo, com folga real para os slides mais técnicos (9, 12, 17) e ~15 min reservados para perguntas.
- O slide 17 (resultados da avaliação) é o que mais separa esse projeto de uma apresentação genérica — não tenha pressa nele.
- **Revisão de 2026-07-08 (v1):** comparei o roteiro original com `AuditorCidadaoRoadmap.md` e enriqueci os slides 7, 8, 10, 16, 18, 20, 22 e 24 com pontos que estavam nos slides (ou no roadmap) mas não no discurso — principalmente a parte de V2/Engenharia de IA do slide 22 e o gap de controle de custo/rate limiting no slide 24.
- **Revisão de 2026-07-08 (v2 — esta versão):** reescrita completa pra formato de "fala guiada" quase literal, com uma seção de **números/fatos exatos** por slide (pra não precisar decorar sob pressão) e um **"se perguntarem"** nos pontos mais prováveis de aprofundamento técnico. Cobertura de todos os 24 slides, incluindo referência rápida do catálogo A–I completo (slide 13) e 9 perguntas prováveis com resposta pronta (slide 24, antes só tinha 4).
- **Revisão de 2026-07-08 (v3):** verificado direto em `app/services/lifespan.py` — `TOOLS_MCP_SELECIONADAS` tem exatamente **11** entradas, confirmando a doc técnica e o slide 10. O número "12" era um valor desatualizado, presente em 3 trechos de `AuditorCidadaoRoadmap.md` (Fase 3, Bloco 0 e seção de Bloco 5) — todos corrigidos para 11. Nenhuma outra menção a "12 tools/ferramentas" foi encontrada em `docs/` ou `README.md`. Slide 10 do `index.html` já estava correto (não precisou de alteração).
- **Revisão de 2026-07-08 (v4):** nova rodada de 3 execuções da pipeline de avaliação trouxe resultados atualizados — `aderencia_tools 1.000`, `faithfulness 0.858` (agora aprovado, antes oscilava 0.79–0.88 com 2 reprovações em 6 execuções), `context_recall 0.600` (inalterado, segue reprovado) e `recall_anomalias 1.000`. Atualizado em `docs/ia/avaliacao.md` (nova seção "Nova rodada de validação"), `AuditorCidadaoRoadmap.md` (nota no item de backlog sobre variância de faithfulness) e no gráfico do slide 17 do `index.html` (barra e ícone de faithfulness mudaram de "instável ⚠️" para "aprovado ✓", verificado visualmente no navegador). O histórico das 6 execuções anteriores foi preservado nos três lugares — não apaguei a instabilidade documentada, só acrescentei a rodada nova como dado adicional. O veredito geral do sistema **continua reprovado**, já que `context_recall` não mudou.
- **Revisão de 2026-07-08 (v5):** resolvida a pendência do "Auditoria Estadual" — adicionado ao painel de módulos do slide 22 (HTML), com o selo visual "plano futuro" (borda tracejada, mesma linguagem usada nos diagramas pra sinalizar "conceitual, ainda não construído"). Além disso, criado um **slide novo** — o 23, "Visão de longo prazo: o ecossistema" — com uma ilustração de iceberg (ponta visível = Auditor Cidadão em produção hoje; massa submersa tracejada = os 5 módulos futuros do ecossistema) e uma fala de fechamento sobre a visão de produto de longo prazo. Isso empurrou Conclusão de 23→24 e Perguntas de 24→25; a apresentação passou de 24 para **25 slides**. Verificado no navegador: renumeração sem quebra (contador dinâmico do deck lê `25` corretamente), novo slide renderiza sem erros de console, módulo com selo "plano futuro" legível.
- Revise comigo depois: posso ajustar tempos, cortar algum "se perguntarem" se achar excessivo, ou aprofundar ainda mais algum bloco técnico específico.
