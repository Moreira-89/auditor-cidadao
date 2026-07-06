# Auditor Cidadão — Roadmap Consolidado

> Documento único: requisitos oficiais do case (Data Master) + status do projeto +
> plano de entrega até 13/07/2026.
> **Mudança de paradigma:** sair de "valida CNPJ + busca contexto" para "cruza múltiplas
> fontes oficiais, detecta padrões anômalos e entrega laudo estruturado".
>
> **Última atualização:** 2026-07-05 (Bloco 4 concluído — framework de avaliação, golden dataset,
> 3 métricas validadas, bug de produção em `gerenciadorvetorial.py` encontrado e corrigido)

---

# 🎓 REQUISITOS OFICIAIS DO CASE (Data Master — Engenheiro de IA)

> **⚠️ NÃO PERDER O FOCO:** esta seção é a fonte da verdade sobre o que a banca exige.
> Toda decisão técnica abaixo deve servir a estes requisitos — eles impactam diretamente
> a classificação final (Driving, Advanced ou Expert).

**Missão do case:** criar uma solução funcional de IA Generativa para um caso real de negócio, desenhada, validada e implementada. Apresentação de 1h30 com funcionamento end-to-end, arquitetura explicada e escolhas tecnológicas justificadas com exemplos práticos. A solução deve ser **escalável, segura e eficiente**.

**Tema:** auditoria de licitações públicas municipais. **Trilha:** Assistência e Interação + Automação e Extração de Conhecimento.

## Tópicos obrigatórios

| # | Requisito | O que a banca quer ver |
|---|---|---|
| T1 | Modelo(s) de IA que solucionam a dor | Qual modelo, por quê, como resolve o problema |
| T2 | Prompts + orquestração | Como garantem respostas consistentes e controladas |
| T3 | Uso de dados | Como são preparados, armazenados e utilizados |
| T4 | Estratégia de modelos (RAG etc.) **+ avaliação de desempenho** | Justificar RAG vs alternativas **e** ter método de avaliação |
| T5 | Arquitetura com agentes | Diagrama + decisões e trade-offs explícitos |
| T6 | Ética, privacidade e responsabilidade | LGPD, alucinação, vieses |

## Entregáveis obrigatórios

| # | Entregável |
|---|---|
| E1 | Projeto funcional, empacotado e reprodutível |
| E2 | Documentação: explicação do case |
| E3 | Documentação: instruções de execução |
| E4 | Documentação: desenho/arquitetura |
| E5 | Documentação: decisões e trade-offs |
| E6 | Documentação: próximos passos |

## Reprodutibilidade

| # | Requisito |
|---|---|
| R1 | Solução reproduzível em outra máquina |
| R2 | Scripts de setup/execução no Git |
| R3 | Instruções claras de configuração |

## Status atual de conformidade (visão rápida)

| Req | Status | Lacuna principal |
|---|---|---|
| T1 | ✅ | Documentar justificativa (OpenAI `gpt-4o-mini` + `text-embedding-3-small`) |
| T2 | ✅ Forte | Só consolidar na apresentação |
| T3 | ✅ | Articular que os dados são editais públicos + bases governamentais |
| T4 | ✅ | Framework de avaliação concluído (Bloco 4): 3 métricas, critérios documentados, validado com dado real |
| T5 | ⚠️ | Falta diagrama de arquitetura e doc de trade-offs consolidado → Bloco 5 |
| T6 | ⚠️ **GAP** | Falta seção explícita de ética/LGPD/limitações → Bloco 5 |
| E1 | ✅ | Dockerfile + lifespan + frontend prontos |
| E2/E3/R3 | ⚠️ | README completo ainda não existe → Bloco 5 |
| E4 | ❌ | Sem diagrama → Bloco 5 |
| E5 | ⚠️ | Decisões espalhadas em comentários → consolidar → Bloco 5 |
| E6 | ✅ | Este roadmap cobre isso (seção Backlog V2) |

---

## Status Geral do Projeto

| Fase | Objetivo | Status |
|---|---|---|
| **Fase 0 — Limpeza técnica** | Logger, redundância, env vars | ✅ Concluída |
| **Fase 1 — Engenharia de prompt e segurança** | System prompt V2, catálogo de anomalias | ✅ Concluída |
| **Fase 2 — Async nativo + ToolNode** | `.ainvoke`, `ToolNode`, `astream_events` | ✅ Concluída |
| **Fase 3 — Novas fontes de dados** | PNCP (12 tools ativas), CEIS/CNEP, busca web | ✅ Concluída |
| **Fase 4 — Cache + Output estruturado** | Cache TTL ✅, JSON de risco ✅ | ✅ Concluída |
| **Fase 5 — Streaming** | Tokens em tempo real no frontend | ✅ Concluída |
| **Fase 6 — Framework de avaliação** | Golden dataset + RAGAS + aderência/anomalia | ✅ Concluída |
| **Fase 7 — Indexação automática via PNCP** | Busca + ingestão sem upload manual | 🚫 Backlog V2 |
| **Fase 8 — Infraestrutura e deploy** | Docker ✅, Railway ✅, Frontend ✅ | ✅ Concluída |

---

## ✅ O Que Já Foi Feito

**Fase 0:** logger padronizado, remoção de código morto, env vars centralizadas.

**Fase 1:** `SYSTEM_PROMPT` reescrito com identidade de auditor, catálogo de 9 anomalias (A–I),
dois modos de resposta (conversacional e laudo), guardrails contra prompt injection,
`data_hoje` injetada dinamicamente.

**Fase 2:** stack migrada para `async/await` com `ToolNode` nativo do LangGraph,
`StreamingResponse` com `astream_events()`, `httpx.AsyncClient`. Zero thread síncrona
bloqueando o event loop.

**Fase 4.1 — Cache TTL:** cache em memória com chave MD5 por tool + argumentos, TTL de 24h
alinhado ao ciclo do PNCP, aplicado no `lifespan.py` após o patch MCP.

**Fase 5:** SSE com eventos `token` e `status`, frontend renderiza tokens em tempo real com Markdown.

**Bloco 0 — Correções técnicas herdadas:** 9 apontamentos de revisão de código aplicados antes do
Bloco 1. `dependencies.py` com defaults seguros para `LLM_MODEL`, `LLM_TEMPERATURE` e
`LLM_MAX_TOKENS` (boot não quebra mais se a env var faltar no Railway). SSE de `run_agent()`
envolvido em `try/except`, emitindo `{"type": "done"}` ao final normal e `{"type": "error", ...}`
em falha (com `logger.exception`) — frontend trata os dois eventos e nunca mais fica esperando
para sempre. Cache MCP migrado de dict cru para `cachetools.TTLCache` (expiração automática +
`maxsize`), eliminando o risco de OOM em runtime longo; o mesmo cache passou a envolver também as
tools nativas (`consultar_receita_federal`, `buscar_contexto_edital`) no `lifespan.py`. Comentário
enganoso sobre "subprocess Node.js persistente" corrigido — a versão instalada do
`langchain-mcp-adapters` (0.3.0) já abre e fecha sessão por chamada, então não há shutdown
explícito a fazer. `chunk.tool_calls` agora é lido com `getattr(chunk, "tool_calls", None)` para
não quebrar em chunks intermediários. Novo helper `escape_xml()` aplicado em `pergunta_usuario`,
`municipio`, `estado` e `cnpjs_formatados` — antes só a pergunta era escapada, abrindo brecha de
prompt injection via `<METADADOS>`. `PerguntaRequest.lista_cnpjs` ganhou `field_validator`: corta
em 10 CNPJs e descarta os matematicamente inválidos via `validate_docbr`, logando tentativas de
abuso. Coleta do nome do usuário removida de ponta a ponta (`PerguntaRequest`, endpoints,
`SYSTEM_PROMPT`, formulário do frontend) — reduz superfície de dado pessoal coletado.

**Extras concluídos:**
- Modelo em produção: **OpenAI `gpt-4o-mini`** (128k tokens), embeddings `text-embedding-3-small`
  (1536 dim), índice Pinecone recriado.
- MCP LiciNexus expandido: 12 tools ativas (licitações, contratos, atas de RP, comparação de períodos).
- `build_graph.py` refatorado: singleton com `initialize_graph(tools)`, closure para `call_llm`,
  `recursion_limit: 50`.
- `mcp_utils.py` com patch de schema, coerção de tipos e captura de exceções MCP.
- Docker: `Dockerfile` com Python 3.12 + Node.js 20, build local validado.

**Bloco 1 — Tools de sanções e busca web:** `consultar_sancoes_empresa` implementada
consultando CEIS e CNEP (Portal da Transparência/CGU) via `asyncio.gather` em paralelo,
com `CGU_API_KEY` obtida e validada. Bug de parâmetro descoberto só em teste real com a
documentação Swagger: o filtro correto é `codigoSancionado`, não `cnpjSancionado` (este
último é aceito e ignorado silenciosamente pela API, retornando a listagem sem filtro).
Falha isolada em uma fonte (CEIS ou CNEP) não derruba a outra — `consultar_sancao_async`
retorna `None` como sentinela de "fonte indisponível", distinto de `[]` ("fonte consultada,
sem sanção"), preservando a diferença entre "não verificado" e "empresa limpa" exigida pela
Anomalia H. Cada registro é achatado (`filtragem_sancoes.py`) com campos planos, incluindo
`fonte_cadastro` (CEIS/CNEP) e `tipo_registro` (`"sancao"` | `"aviso"`) para rastreabilidade
jurídica e para o LLM diferenciar dado real de aviso de indisponibilidade sem ambiguidade.
`buscar_informacao_web` implementada com `langchain_tavily.TavilySearch` (a integração
`TavilySearchResults` do `langchain-community` está deprecated); município/estado são
concatenados à query via `InjectedState` de forma incondicional — decisão consciente de
não tentar detectar se o LLM já mencionou uma localização, evitando heurística frágil.
Pipeline de filtragem em `filtragem_resultados_web.py` (descarta fragmentos curtos/
corrompidos, trunca conteúdo longo, seleciona só `url`/`title`/`content`), com
`max_results=3` reduzindo volume na origem. Ambas as tools seguem o padrão já estabelecido
de nunca deixar exceção subir crua — sempre retornam `{"error": ...}` estruturado.
`SYSTEM_PROMPT` atualizado: capacidades das duas tools descritas, regra de precedência
PNCP/Receita vs. busca web, e uma regra anti-alucinação nova (descoberta em teste real via
log): proíbe "emprestar vocabulário" entre resultados de tools diferentes no mesmo turno
(ex.: citar `situação cadastral` a partir de um resultado de sanções sem ter chamado a
Receita Federal). `TOOL_STATUS_MAP` atualizado com as duas novas entradas. Validação feita
com dados reais (CNPJ da Andrade Gutierrez com sanção real no CNEP; CNPJ da Prefeitura de
Suzano como caso limpo) e cruzamento de logs do terminal, não apenas confiança na resposta
do modelo — esse método já pegou dois bugs (parâmetro de API errado; alucinação por
vocabulário emprestado) que não apareceriam só lendo a resposta final.

**Bloco 2 — Output Estruturado:** `app/models/laudo.py` criado com `Anomalia` e
`RespostaLaudo` (`laudo: LaudoEstruturado | None`, `None` para respostas conversacionais).
Segunda chamada LLM (`temperature=0.0`, instância dedicada instanciada no `lifespan.py` e
recuperada via `get_extrator()`) extrai o JSON do laudo com `with_structured_output`,
usando um `SystemMessage` próprio com critério explícito de decisão — o schema Pydantic
sozinho não bastava, o modelo tentava preencher o laudo mesmo em respostas conversacionais
até o critério ser explicitado no prompt. `laudo_completo` corrigido para não contaminar
com texto de rodadas intermediárias do agente: acumula em `buffer_temporario` durante
`on_chat_model_stream` e só confirma em `laudo_completo` no `on_chat_model_end`, quando dá
para checar se a mensagem final não teve `tool_calls`. SSE ganhou os eventos
`laudo_estruturado` e `laudo_estruturado_erro` (isolado em try/except próprio — falha na
extração não derruba o `done` nem reaproveita o erro genérico do streaming, já que o
Markdown já foi entregue com sucesso). Validado com dados reais (CNPJ da Andrade Gutierrez
com sanção, e pergunta puramente conversacional).

**Bloco 3 — Integração PNCP nativa, refatoração de services e documentação:**
`buscar_contratos_fornecedor_pncp` implementada em `app/services/consulta_pncp.py` para cruzar
órgão + fornecedor (histórico de contratos vencidos), substituindo a tool MCP `get_fornecedor_contratos`
que já vinha excluída da whitelist do LiciNexus por não funcionar corretamente. Fluxo (listar
compras do órgão → itens → resultados, com filtro client-side por `niFornecedor`) validado
manualmente endpoint a endpoint em notebook (`testes_locais/test_getcontratos_pncp.ipynb`) antes de
virar código de produção — só nessa validação foram descobertos: a API do PNCP é dividida em duas
bases (`/api/consulta` para busca, `/api/pncp` para dados por órgão), o campo do fornecedor vencedor
se chama `niFornecedor` (não `cnpjFornecedor`), e `codigoModalidadeContratacao` é obrigatório em
`/contratacoes/publicacao` — não existe "buscar todas as modalidades" num único request, então é
preciso varrer as ~19 modalidades ativas uma a uma. Essa varredura expôs um rate limit agressivo do
PNCP a nível de WAF (bloqueio de minutos após poucos requests simultâneos), mitigado com
espaçamento mínimo de 2s entre chamadas e retry com backoff exponencial em 429/erro de conexão.
Decisão consciente antes do merge: a tool ficou **implementada mas desativada** (removida de `TOOLS`
e do `SYSTEM_PROMPT`) — a varredura completa de um órgão pode levar minutos mesmo com o rate
limiting resolvido, e o streaming SSE não emite nenhum evento durante a execução de uma tool,
arriscando ser encerrado por timeout de proxy em produção antes da tool terminar. Documentado como
limitação conhecida em vez de arriscar quebrar o streaming na apresentação.

Aproveitando a tool nova, `app/services/tools.py` foi refatorado: cada tool nativa virou um wrapper
fino (valida input, delega a chamada externa, traduz erro) sobre um módulo de serviço dedicado
(`consulta_receita_federal.py`, `consulta_sancoes.py`, `busca_web.py`, `consulta_pncp.py`),
consolidando helpers que estavam espalhados em `app/utils/` (`filtragem_sancoes.py` e
`filtragem_resultados_web.py` absorvidos pelos respectivos módulos de serviço; `limpar_documento`
inlinado como regex por ser simples demais para justificar um arquivo próprio). Antes de mexer em
documentação, foi feita uma revisão completa do projeto atrás de bugs e código morto: encontrado e
corrigido `.env.docker` sendo copiado para dentro da imagem Docker (`.dockerignore` só excluía
`.env`, arriscando embutir chaves reais numa camada da imagem publicável); `TOOL_STATUS_MAP` ainda
tinha a entrada do `get_fornecedor_contratos` já abandonado; `requirements.txt` não tinha
`langchain-google-genai` apesar do `.env`/README já citarem Gemini como alternativa de LLM — todos
corrigidos.

`README.md` reescrito do zero: conteúdo alinhado ao estado real do projeto (contagem de tools,
modelo padrão correto `openai:gpt-4o-mini` em vez do Groq desatualizado, estrutura de pastas,
endpoints sem o campo `user_name` que não existe mais), `.env.example` completo e versionável criado
(exigiu adicionar `!.env.example` ao `.gitignore`, já que a regra `.env*` também o capturava), e uma
seção honesta de limitações conhecidas citando a tool de PNCP desativada. Versão da aplicação
(`main.py`) atualizada de `1.1.3` para `1.2.0`, unificando com o badge do README (antes divergente,
`v0.4.0`). Todo o trabalho foi para um PR único (#6), revisado e mesclado na `main`; branch de
feature removida local e remotamente após o merge.

**Bloco 4 — Framework de Avaliação:** `evaluation/golden_dataset.json` criado com 11 casos
(reais + sintéticos), cobrindo empresa com sanção ativa no CEIS/CNEP (Anomalia H), prazo de
publicação irregular (Anomalia F), caso controle sem anomalia esperada e caso puramente
conversacional — mix exigido pelo roadmap original coberto. `evaluation/pipeline_avaliacao.py`
(substitui o `avaliar.py`/`JulgamentoLLM` originalmente planejado — ver trade-off documentado
no Bloco 5) roda o agente de ponta a ponta contra cada caso e mede três famílias de métrica
independentes:
- **`aderencia_tools`** — comparação determinística (sem LLM) entre `tools_esperadas` e
  `tools_chamadas`; percorre só o que era esperado, tools extras chamadas pelo agente não
  entram na conta.
- **`recall_anomalias`** — reusa o extrator estruturado de produção (`RespostaLaudo`) sobre o
  `laudo_completo` de cada caso, comparando os códigos do catálogo A–I detectados contra
  `anomalias_esperadas`.
- **RAGAS (`faithfulness`, `context_recall`)** — mede alucinação e cobertura de contexto nos
  casos que usam `buscar_contexto_edital`, contra o `contexto_edital_esperado` de cada caso.

Cinco bugs reais foram encontrados e corrigidos durante a validação do framework, o mais grave
deles em produção, não só no teste:
1. **Catálogo de anomalias ausente no `PROMPT_EXTRATOR`** — o extrator via só a lista de
   códigos válidos (`Literal["A"..."I"]"`), sem os critérios de cada um, e por isso não sabia
   mapear texto de sanção para o código `H`. Corrigido extraindo o catálogo completo (com
   critério por letra) para uma constante única (`CATALOGO_ANOMALIAS`), reusada tanto no
   `SYSTEM_PROMPT` quanto no `PROMPT_EXTRATOR` — elimina duplicação de texto entre os dois.
2. **Corrida de consistência eventual do Pinecone** — o pipeline consultava o índice logo após
   indexar, sem esperar a propagação, derrubando `context_recall` de forma não-determinística.
   Corrigido com `_aguardar_contagem_namespace`, que faz *polling* em `describe_index_stats`
   até a contagem esperada de vetores aparecer.
3. **Namespace compartilhado entre casos do mesmo município** — causava delete-readd
   adjacente e contaminação de chunks entre casos consecutivos. Corrigido isolando cada caso
   num namespace exclusivo (`avaliacao_<id>`).
4. **Ruído do juiz RAGAS** — `gpt-4o-mini` como `AVALIADOR_MODEL` dava notas inconsistentes
   para o mesmo contexto recuperado entre execuções (comprovado: contexto byte-a-byte idêntico,
   nota diferente). Trocado para `gpt-4o`, que eliminou a variância de `context_recall` entre
   rodadas (amplitude `0.000` em 3 execuções).
5. **Bug de produção real: metadados compartilhados no upsert do Pinecone**
   (`app/services/gerenciadorvetorial.py`, `processar_e_salvar`) — `[metadados] * len(lista_chunks)`
   criava `N` referências ao mesmo dict em vez de `N` cópias independentes; o `add_texts` da
   lib então sobrescrevia repetidamente o mesmo objeto, fazendo **todo chunk indexado — em
   qualquer edital, inclusive os de usuários reais em produção — ser armazenado com o texto do
   último chunk do documento**, disfarçado atrás de scores de similaridade que continuavam
   plausíveis (os embeddings, calculados antes da mutação, permaneciam corretos). Corrigido
   trocando a multiplicação de lista por `[dict(metadados) for _ in lista_chunks]`. Achado
   durante uma investigação que começou como debug de métrica de teste e terminou revelando um
   defeito que afetava usuários reais — banco vetorial de produção já estava limpo no momento
   da correção, então não foi necessário reindexar nada retroativamente.

Além dos bugs, uma limitação estrutural foi identificada e tratada por decisão consciente, não
por correção de código: o `caso_06` tem `contexto_edital_esperado` como uma afirmação **negativa**
("o edital não traz a data de publicação") — `context_recall` do RAGAS não tem mecanismo para
validar ausência de informação contra chunks recuperados, então esse caso nunca pontuaria bem
nessa métrica específica, independentemente da qualidade do retrieval. Excluído do cálculo do
RAGAS via um campo próprio no dataset (`excluir_do_ragas: true`), mantendo-se normalmente nas
demais métricas (aderência de tools).

Critérios mínimos de aprovação definidos e aplicados automaticamente (`aprovacao["geral"]`):
`aderencia_tools ≥ 0.70`, `faithfulness ≥ 0.85`, `context_recall ≥ 0.75`, `recall_anomalias ≥
0.80`. Resultado consolidado em **6 execuções** após todas as correções acima (3 do pipeline +
3 manuais adicionais, mesmo protocolo): `aderencia_tools = 1.00` e `recall_anomalias = 1.00`
estáveis nas 6/6. `context_recall` ficou em `0.60` em 5 das 6 execuções (uma delas registrou
`0.90`, tratado como outlier pontual, não repetido) — reprovado, limitação documentada de
`top_k=3` em 2 dos 5 casos elegíveis ao RAGAS (ver Backlog V2). `faithfulness` se mostrou
**instável em torno do próprio limiar**: variou entre `0.79` e `0.88` nas 6 execuções (4
aprovadas, 2 reprovadas) — não é uma aprovação sólida, apesar de ter passado nas 3 primeiras
rodadas medidas. Hipótese não confirmada: variância herdada da `temperature=0.1` do agente
principal (mesma configuração de produção), usada também durante a avaliação — ver item
correspondente no Backlog V2. Veredito geral (`aprovacao["geral"]`) reprovado na maioria das
6 execuções, por causa de `context_recall`.

---

# 📚 BLOCO 5 — Documentação Final (paralelo aos blocos 2–4)

> Escrever a documentação de cada feature no mesmo dia em que ela é implementada — não deixar
> acumular. Esta seção cobre diretamente E2, E3, E4, E5 e o GAP-3 (T6).

### Estrutura `/docs` (MkDocs Material)
```
docs/
├── index.md           # Visão geral, problema, solução, stack
├── arquitetura.md      # Diagrama Mermaid + fluxo de dados (E4/T5)
├── etica.md             # LGPD, anti-alucinação, anti-injection, limitações (T6)
├── tools.md            # Catálogo de tools: parâmetros, exemplos, limitações
├── anomalias.md        # Catálogo A–I com exemplo real por anomalia
├── avaliacao.md         # Metodologia LLM-as-Judge + resultados (T4)
├── deploy.md            # Docker + Railway + variáveis de ambiente
└── contribuindo.md      # Como rodar localmente
```

- [ ] `arquitetura.md`: diagrama mostrando `Upload PDF → pdfplumber → chunking → Pinecone` e
      `Pergunta → LangGraph (call_llm ↔ ToolNode) → MCP/Receita/CGU/Tavily/Pinecone → SSE`
- [ ] `etica.md` — cobrir explicitamente:
  - **Privacidade/LGPD:** dados públicos (CNPJ, PNCP, editais); nome do usuário não é mais
    coletado (já implementado); retenção indefinida de editais no Pinecone é decisão deliberada
    (sem dado pessoal sensível envolvido), pensada para viabilizar cruzamento histórico na V2
  - **Anti-alucinação:** regra "nunca invente dados", hierarquia de evidências, score conservador
  - **Anti-injection:** escape XML em todos os campos (já implementado), tags de isolamento
  - **Limitações:** dependência de APIs externas, cobertura parcial de anomalias, necessidade
    de revisão humana
  - **Responsabilidade:** o laudo é indício, não decisão final — sempre recomenda checagem manual
- [ ] `README.md` na raiz: explicação do case, arquitetura resumida, stack, `.env.example`
      completo, passo a passo local + Docker, exemplos de uso (cobre E2/E3/R3)
- [ ] Seção de justificativa tecnológica (README ou slides): por que LangGraph vs LangChain
      puro, por que OpenAI `gpt-4o-mini`, por que Pinecone, por que MCP (reuso de 12 tools
      PNCP), por que RAG vs fine-tuning
- [ ] Exportar documentação como PDF para entrega à banca

### Apontamentos do Bloco 2 a documentar (decisões e trade-offs — E5)
- **Buffer-then-commit no streaming:** por que `laudo_completo` não é preenchido direto no
  `on_chat_model_stream` — decidir "isso é resposta final?" chunk a chunk é frágil, porque o
  modelo pode emitir texto antes do `tool_calls` aparecer completo no chunk. A correção
  espera o `on_chat_model_end` (mensagem inteira) para confirmar a ausência de `tool_calls`
  antes de mover o conteúdo do `buffer_temporario` para `laudo_completo`. Boa resposta para
  "como vocês garantem que o JSON reflete só a resposta final, sem ruído de raciocínio
  intermediário do agente?".
- **Schema define forma, prompt define comportamento:** `with_structured_output` (via
  `RespostaLaudo`) só garante que a saída *valida* contra o schema — não decide sozinho
  *quando* usar `laudo: null`. Isso exigiu um `SystemMessage` dedicado ao extrator, com o
  critério de decisão explícito. Vale citar como exemplo prático de prompt engineering (T2).
- **Por que não usar heurística por texto (regex/marcador no Markdown) nem por tool
  chamada:** ambas testadas e descartadas — a primeira quebra se o `SYSTEM_PROMPT` mudar de
  formato; a segunda gera falso positivo em consultas pontuais (ex.: "verifica esse CNPJ
  pra mim" chama uma tool de auditoria mas não é um laudo completo). A solução final delega
  a decisão para o próprio LLM extrator via `SystemMessage`, e não para uma heurística fixa
  no código.

### Apontamentos do Bloco 4 a documentar (decisões e trade-offs — E5)
- **RAGAS em vez do `avaliar.py`/`JulgamentoLLM` originalmente planejado:** o roadmap previa um
  único LLM-juiz caseiro julgando 4 métricas (`relevancia`, `fidelidade`, `aderencia_tools`,
  `deteccao_anomalia` booleana). A implementação final usa RAGAS (biblioteca validada pela
  comunidade) para `faithfulness`/`context_recall`, mantém `aderencia_tools` como comparação
  determinística sem LLM (mais confiável que julgamento subjetivo para esse caso), e
  `recall_anomalias` como fração (não booleano), reaproveitando o mesmo extrator estruturado
  já usado em produção. Decisão consciente de engenharia, não desvio por falta de tempo — vale
  como boa resposta para "por que a implementação diverge do plano original?" (T4/E5).
- **Bug de metadados como exemplo de "bug de avaliação que era, na verdade, bug de produção":**
  o `gerenciadorvetorial.py` é compartilhado entre o pipeline de teste e o fluxo real de
  indexação de editais — uma investigação que começou puramente sobre instabilidade de métrica
  terminou revelando que usuários reais recebiam sempre o último chunk do documento como
  contexto, independente da pergunta. Boa resposta prática para "como o framework de avaliação
  ajudou a encontrar problemas reais do sistema, não só medir números?" (T4).
- **Exclusão do `caso_06` do cálculo de RAGAS:** `context_recall` não tem mecanismo para validar
  uma afirmação negativa ("o edital não traz X") contra chunks recuperados — limitação da
  métrica, não do sistema. Excluído via campo próprio no golden dataset em vez de reescrever o
  gabarito, preservando o caso para as demais métricas.
- **Juiz do RAGAS trocado de `gpt-4o-mini` para `gpt-4o`:** o mini dava notas inconsistentes
  para o mesmo contexto recuperado entre execuções (comprovado com contexto byte-a-byte
  idêntico e nota diferente). Custo maior do `gpt-4o` só incide em CI/avaliação manual — esse
  modelo nunca é chamado por um usuário real (ver Backlog V2 para plano de retestar o mini após
  estabilizar o dado de entrada).

---

# 🚫 Backlog V2 — Fora do Escopo desta Entrega

> Candidatas naturais para a próxima versão. Boa resposta para "quais são os próximos passos?".

### Fase 7 — Indexação Automática via PNCP + Migração de Metadata
Elimina o upload manual: o agente busca, baixa e indexa o PDF a partir de uma conversa.
Junto com essa migração, o schema de metadata do Pinecone muda de `municipio`/`estado`
(informados manualmente) para **`cnpjs` (lista extraída automaticamente)** — o mesmo padrão
já usado hoje (metadata replicada em todos os chunks do documento), só trocando o campo.

```
Usuário: "Analise licitações de TI em SP desta semana"
       ↓
search_licitacoes → lista com numeroControlePNCP
       ↓
list_licitacao_arquivos → URLs dos PDFs
       ↓
Download + extração (pdfplumber) + deduplicação por numeroControlePNCP
       ↓
Embedding → upsert no Pinecone (metadata: cnpjs) → laudo automático
```

**Pré-requisitos:** verificar se `list_licitacao_arquivos` retorna URL direta; refatorar
`gerenciadorvetorial.py` para download por URL; deduplicação por `numeroControlePNCP`.

### Tool `buscar_historico_empresa` (cruzamento cross-município)
Depende da migração de metadata acima. Recebe um CNPJ e retorna todos os editais relacionados
já indexados no Pinecone — permitindo o agente cruzar, por exemplo, uma empresa sancionada em
Mogi das Cruzes (SP) com um padrão semelhante em outro município. Desenhada como **tool
explícita** (o LLM decide quando chamar via CNPJ já conhecido), não como varredura automática
em toda análise — evita custo de token desnecessário. Documentar no `SYSTEM_PROMPT` e citar
explicitamente na seção de ética (T6) como parte da visão de produto.

### `consultar_preco_referencia` (Painel de Preços / Compras.gov)
Habilitaria detecção de sobrepreço (Anomalia A). Endpoint instável — verificar disponibilidade
antes de implementar.

### Novos cruzamentos para o catálogo de anomalias (pesquisa de mercado, 2026-07-04)
> Dicas coletadas comparando o projeto com ferramentas de monitoramento público existentes,
> mais uma ideia própria. A maioria **reforça anomalias que já existem no catálogo A–I**
> em vez de criar categorias novas — por isso o esforço de várias é menor do que parece.

**Achado que muda a viabilidade de quase tudo abaixo:** a BrasilAPI já devolve `capital_social`,
`cnaes_secundarios`, `qsa` (quadro de sócios) e endereço completo no mesmo request que
`consultar_receita_federal` já faz — só que esses campos são descartados em
`app/services/consulta_receita_federal.py:34-41` antes de chegar no LLM. Boa parte do que
segue é reexpor dado que já está sendo buscado, não integrar uma fonte nova.

- **Reforço da Anomalia E (Empresa Recém-Criada) — "fator recém-nascida":** comparar
  `data_inicio_atividade` (já capturado) com a data de publicação do edital, com limiar mais
  agressivo (180 dias) quando o valor é alto e o município é isolado. Esforço **baixo** — dado
  já existe, é ajuste de critério no prompt.
- **Reforço da Anomalia I (Incompatibilidade de Atividade):** hoje só o CNAE principal é usado.
  Reexpor `cnaes_secundarios` (hoje descartado) permite pegar o caso de CNAE principal genérico
  ("comércio varejista em geral") vencendo objeto técnico complexo (saneamento, engenharia).
  Esforço **baixo**.
- **Capital social incompatível (candidato a novo sub-critério de E):** `capital_social` já vem
  da BrasilAPI. Comparar com o valor do contrato (ex.: capital de R$5.000 vs. contrato de
  R$2 milhões) é uma heurística simples de capacidade financeira. Esforço **baixo**; falta só
  decidir se vira sub-critério de E ou letra nova do catálogo.
- **Reforço real da Anomalia D (Cartel/Conluio) via QSA:** o critério "cruze quadro societário"
  já existe no prompt (`prompt.py:88-90`), mas **hoje não há nenhum dado de sócios** — nem para
  comparar sócios entre concorrentes, nem para checar CPF de sócio no CEIS/CNEP (útil para achar
  CNPJ "limpo" aberto por sócio já punido em outra empresa). Precisaria: (1) capturar `qsa` na
  consulta à Receita Federal, (2) chamar `consultar_sancoes` com o CPF do sócio — o parâmetro
  `codigoSancionado` do Portal da Transparência já aceita CPF, então a tool de sanções em si não
  muda. ⚠️ **Validar antes de investir:** a BrasilAPI costuma mascarar parte do CPF do sócio por
  LGPD (ex.: `***123456**`); se vier mascarado, o cruzamento com CEIS/CNEP (que exige documento
  completo) não funciona e a ideia trava nesse ponto. Esforço **médio**, com uma dependência de
  validação técnica antes de comprometer o escopo.
- **Consórcio camuflado (subcontratada sancionada em obra de saneamento):** exigiria extrair e
  ler atas de julgamento/subcontratação em PDF, procurando CNPJs sancionados ocultos como
  subcontratados. Não há hoje extração estruturada de atas nesse nível. Esforço **alto**, mais
  próximo de pesquisa do que de feature — melhor como item de "Módulos futuros" do que V2 imediata.
- **Indicador de "Atratividade" (licitação com concorrente único e lance igual ao valor máximo
  do edital):** dá para calcular hoje com as tools PNCP já ativas (`list_licitacao_resultados`),
  sem nenhuma integração nova — falta só o critério/cálculo. Reforça a Anomalia B
  (Direcionamento). Esforço **baixo-médio**.
- **Explosão de Atas de Registro de Preço ("carona" de município pequeno em ata de capital
  distante):** `search_atas_rp`/`get_ata_rp` já trazem órgão gerenciador e aderentes — falta o
  critério que sinaliza volume de adesão fora do padrão. Reforça a Anomalia C (Fracionamento).
  Esforço **médio**.
- **Propostas idênticas em PDF (metadados de autor/software/data de criação repetidos entre 1º e
  2º colocado):** reforça a Anomalia D, mas depende da **Fase 7** (download automático de PDF)
  já listada acima — sem isso, não dá para comparar o arquivo da vencedora com o da 2ª colocada
  sem exigir upload manual duplicado do usuário. Esforço **médio, bloqueado por Fase 7**.
- **Busca web direcionada por endereço (indício de sede "fachada" — residência, terreno baldio,
  escritório virtual/coworking):** o endereço completo já vem da BrasilAPI e hoje é descartado;
  dá para enriquecer a query da busca web com o endereço + termos como "sala comercial",
  "coworking", "endereço fiscal". Isso é diferente de analisar imagem de Street View de verdade
  (exigiria Google Maps Static API + um modelo de visão — integração nova, custo novo, esforço
  alto). Separar em duas versões: a "leve" (query enriquecida com endereço, já descartado hoje)
  é esforço **baixo** e cabe numa V2 próxima; a versão com imagem de rua é módulo futuro.
- **Monitoramento de mídia local** (termos como "atraso", "denúncia", "paralisada", "MPF"
  combinados com empresa + município, mirado em municípios pequenos com pouca cobertura de
  mídia nacional): ajuste de template de query na tool `buscar_informacao_web` já existente.
  Esforço **baixo**.

### Controle de custo e limite de uso (gap identificado, ainda sem solução)
Hoje não existe nenhum limite de uso: sem autenticação e sem quota por sessão/dia, um usuário
pode conversar — e gastar tokens da OpenAI — indefinidamente. É um ponto real de exposição a
custo não controlado e uma pergunta provável da banca sobre escalabilidade (T6). Ainda não
decidido; opções a avaliar na V2 antes de qualquer deploy público sem controle de acesso:
- Rate limiting por sessão/IP (ex.: N mensagens/hora)
- Quota diária por `thread_id`/usuário, bloqueando ao atingir o limite
- Timeout/expiração de conversa (encerrar thread após N turnos ou X minutos de inatividade)
- Autenticação mínima (mesmo que só um token de acesso) como pré-requisito para qualquer
  limite por usuário funcionar de fato

### Melhorias identificadas no Bloco 1, adiadas conscientemente pelo prazo
- **Resumo por resultado da busca web via modelo pequeno:** em vez do filtro/truncamento
  simples usado no V1, resumir cada resultado da Tavily individualmente (um por chamada,
  preservando o vínculo com a URL de origem) com um modelo pequeno/gratuito antes de
  devolver ao `gpt-4o-mini`. Melhora rastreabilidade e reduz tokens, mas adiciona uma
  segunda chamada de rede/provider dentro da tool — descartado no V1 por custo de
  engenharia e latência dado o prazo, documentar como trade-off no Bloco 5.
- **Estender `asyncio.gather` às demais tools nativas** (`consultar_receita_federal`,
  `buscar_contexto_edital`) sempre que fizerem múltiplas chamadas independentes — hoje só
  `consultar_sancoes_empresa` paraleliza porque é a única com duas fontes simultâneas.
  Documentar como decisão consciente no Bloco 5, não como pendência crítica.
- **`include_answer` da Tavily avaliado e descartado:** a API oferece um resumo sintetizado
  pronto, mas ele mistura informação de várias fontes sem vínculo por URL (quebra
  rastreabilidade) e é gerado em inglês mesmo com query em português — mantido fora do V1.

### Separação de nodes no grafo (decisão de tool vs. geração de resposta)
Hoje o grafo é o padrão ReAct simples: um único node `agent` chamado em loop até parar de
emitir `tool_calls`, seguido de `tools` → volta pro `agent`. Funciona, mas fica difícil de
ler num diagrama à medida que mais lógica Python (pequenas automações, análises fora de
tools) for entrando no fluxo. Separar em nodes dedicados (ex.: um node de
decisão/orquestração e um node de geração final, mais nodes de processamento determinístico
fora do ciclo de decisão do LLM) melhora legibilidade e reduz rodadas de LLM desnecessárias
conforme o número de tools/automações cresce na V2. Não é correção de bug — o
buffer-then-commit do Bloco 2 já resolve a extração correta do laudo independente da
topologia do grafo — é uma melhoria de manutenibilidade e clareza arquitetural.

### Buffer por `run_id` (streaming paralelo)
O `buffer_temporario` do Bloco 2 assume execução sequencial (uma chamada de LLM por vez no
grafo). Se a V2 introduzir paralelismo real (ex.: `Send` do LangGraph disparando sub-agentes
simultâneos), um buffer único global passa a misturar conteúdo de streams concorrentes —
nesse cenário, migrar para um dicionário de buffers indexado por `evento["run_id"]`.

### `consultar_dados_municipio` (API IBGE)
IDH, PIB per capita, população, IDEB — contextualiza o valor de uma contratação com a
capacidade fiscal real do município (ex.: prefeitura com PIB per capita de R$8.000 contratando
sistema de TI por R$2 milhões).

### Persistência
| Componente | V1 (atual) | V2 (alvo) |
|---|---|---|
| Histórico de conversas | `InMemorySaver` (RAM) | `PostgresSaver` (PostgreSQL) |
| Cache de tools | Dict/`TTLCache` em memória | Redis com TTL nativo, compartilhado entre instâncias |

### Qualidade
- **Busca semântica com `top_k` maior (hoje 3), já configurável via `TOP_K_EDITAL`** (env var,
  default 3, não exposta à tool que o LLM chama — só o código controla). Diagnóstico real feito
  no Bloco 4: de 5 casos com `context_recall` ruim, 2 (`caso_04b`, `caso_08`) são recuperáveis
  com `top_k` maior (posições 9 e 2 no ranking) — subir pra ~10 resolveria esses. Os outros 2
  (`caso_02`, `caso_04a`) **não aparecem nem em `top_k=50`** — limitação genuína de posição no
  documento (chunk-alvo no apêndice/muito distante), que só reranking ou chunking diferente
  resolveria. Decisão de valor final adiada — subir `top_k` em produção aumenta custo de token
  por chamada e pode piorar `faithfulness` (mais contexto irrelevante pro LLM confundir), não é
  troca sem custo.
- Expansão do golden dataset para 30+ casos cobrindo as 9 categorias
- **Reavaliar `AVALIADOR_MODEL` de volta para `gpt-4o-mini`** como otimização de custo de
  CI/avaliação recorrente (não afeta usuário final — esse modelo só roda quando o time executa
  o golden dataset). Adiado para depois da entrega: o `gpt-4o-mini` mostrou ruído de julgamento
  mesmo com dado de entrada correto (nota variando para o mesmo contexto recuperado); trocar de
  volta exige revalidar estabilidade em 3+ rodadas antes de confiar no resultado.
- **Investigar variância residual de `faithfulness`** — prioridade elevada após 6 execuções
  totais mostrarem oscilação de `0.79` a `0.88` (amplitude `0.086`), com 2 das 6 reprovando o
  limiar de `0.85` mesmo com o juiz `gpt-4o` e o bug de metadados já corrigido — não é mais
  ruído desprezível, é a métrica mais próxima de aprovação consistente e a mais fácil de destravar.
  Hipótese não confirmada: `temperature=0.1` do agente principal (mesma configuração de
  produção) usada também na avaliação, gerando laudos ligeiramente distintos por execução.
  Testável congelando `temperature=0` só durante a avaliação, sem mudar produção.
- **Auditar o repositório atrás de outros usos do padrão `[X] * N` com objeto mutável** — o bug
  de metadados do Bloco 4 foi corrigido pontualmente em `gerenciadorvetorial.py`; não houve
  varredura completa do projeto atrás do mesmo padrão em outro lugar.
- **Namespace de indexação por `thread_id` em produção:** hoje todo usuário indexa no mesmo
  namespace, isolado só por filtro de metadado (`estado`+`municipio`) — dois usuários indexando
  ao mesmo tempo podem, em tese, disputar entre si a mesma barreira de consistência usada na
  avaliação. Isolar por `thread_id` resolve, mas introduz um problema de ciclo de vida novo
  (quando apagar o namespace de uma sessão encerrada). `beforeunload`/`visibilitychange` no
  frontend não é confiável sozinho (não dispara em crash, perda de rede, ou boa parte do mobile)
  — precisaria de uma rotina de expiração no backend como rede de segurança, no mesmo espírito
  do TTL já aplicado ao cache de tools.

### Módulos futuros da plataforma
| Módulo | Descrição |
|---|---|
| Auditor de Contratos | Aditivos suspeitos e prorrogações irregulares pós-licitação |
| Monitor de Fornecedores | Dashboard por município: contratos, sanções, vínculos |
| Alertas Automáticos | Notifica quando fornecedor sancionado vence licitação monitorada |
| Auditoria Estadual | Expansão para contratos estaduais |
| API Pública | Laudos como API para jornalistas, ONGs, sistemas de transparência |

**Princípio fundamental da plataforma:** o sistema sinaliza padrões para investigação humana —
não acusa nem emite sentenças. Framing explícito no `SYSTEM_PROMPT`, na documentação e na apresentação.

---

## Pendências Técnicas Conhecidas (em aberto)

| # | Descrição | Risco | Ação |
|---|---|---|---|
| 1 | `InMemorySaver` perde histórico a cada restart | Baixo (MVP) | Backlog V2: `PostgresSaver` |
| 2 | ~~`float(None)` em `dependencies.py` se env vars faltarem~~ | Resolvido | ✅ Defaults adicionados |
| 3 | ~~Cache MCP nunca expira entradas antigas~~ | Resolvido | ✅ Migrado para `cachetools.TTLCache` |
| 4 | Tavily: cota gratuita de 1.000 req/mês | Baixo | Monitorar; pay-as-you-go se necessário |
| 5 | PNCP rate limits não documentados | Baixo | Cache TTL 24h mitiga. Parcial: comportamento do WAF já documentado como comentário em `consulta_pncp.py:44-53`, mas ainda não em doc formal (`docs/` não existe) |
| 6 | ~~`npm notice` nos logs do container~~ | Resolvido | ✅ `ENV NO_UPDATE_NOTIFIER=1` presente em `Dockerfile:8` |
| 7 | `.env.docker` não usa aspas | Baixo | Ainda sem aspas nos valores; sem doc em `deploy.md` (pasta `docs/` ainda não existe) |
| 8 | ~~Subprocess MCP sem shutdown explícito~~ | Resolvido | ✅ Falso positivo — lib já fecha sessão por chamada |
| 9 | `TAMANHO_MAXIMO_CONTEUDO=2000` em `app/services/busca_web.py:12` (migrado de `filtragem_resultados_web.py` no Bloco 3) quase não trunca na prática | Baixo | Valor ainda não revisado — pendente antes da apresentação |
| 10 | ~~Cobertura de `try/except` inconsistente fora das tools nativas~~ | Resolvido | ✅ Handler global de exceção em `main.py`, try/except em torno do upsert no Pinecone em `root_upload.py` e da conexão MCP no startup em `lifespan.py`. `busca_web.py`/`consulta_receita_federal.py` mantidos sem try/except de propósito — já seguem o padrão "levanta exceção nativa, chamador em `tools.py` traduz" |
| 11 | Sem autenticação nem limite de uso: usuário pode conversar (gastar tokens da OpenAI) indefinidamente | Alto | Confirmado: nenhum middleware, `Depends` de auth ou rate limiter em `app/`. Backlog V2: rate limiting/quota/timeout de conversa — ver seção "Controle de custo e limite de uso" |

---

## 🔍 Auditoria de Código Pré-Banca — Revisão Sênior (2026-07-05)

> Checklist de correções levantado numa revisão de qualidade antes da apresentação.
> Marque `- [x]` conforme for corrigindo. Nenhum item é de alta severidade — o projeto
> está sólido; são refinos de robustez e documentação.

### Bugs a corrigir
- [ ] **[média] `frontend/js/chat.js` (~L736-770) — parser SSE perde/corrompe evento em linha `data:` cortada na fronteira do chunk de rede.** O ramo que guarda o `leftover` nunca roda para linhas que começam com `data: ` (o `if` de cima captura antes), então uma linha parcial cai no `JSON.parse`, falha, e o `catch` injeta o fragmento quebrado dentro do texto da resposta (e perde o token). Correção mínima: tratar a última linha incompleta **antes** de processá-la como `data:` (guardar em `leftover` e `break` quando `text` não termina em `\n`). Intermitente — reproduzir forçando chunks pequenos.
- [ ] **[baixa — confirmar] `app/services/consulta_sancoes.py` (L88-89) — falha crua se `CGU_API_KEY` ausente.** Header com valor `None` gera `TypeError` no httpx, que **não** é `httpx.HTTPError` e escapa do `except` da L34, virando erro de tool ilegível em vez do `tipo_registro:"aviso"` ("não verificado") exigido pela Anomalia H. Correção mínima: checar a chave no início de `consultar_sancoes` e retornar dois avisos (CEIS/CNEP) se faltar. Só dispara sob má-configuração.
- [ ] **[baixa-média — confirmar] `app/services/ai_engine.py` (L161-173) — texto de raciocínio intermediário pode vazar para a resposta exibida.** O backend descarta corretamente esse texto do `laudo_completo`, mas ele já foi transmitido como `token` (L165) antes de sabermos que a rodada terminaria em `tool_calls`. Com `gpt-4o-mini` talvez nunca dispare (rodada de tool costuma vir sem conteúdo). Ação: **confirmar em log** antes de corrigir — um fix real conflita com o streaming em tempo real, então não é correção mínima trivial.

### Código morto / a confirmar (intencional — não remover agora)
- [ ] `buscar_contratos_fornecedor_pncp` (`tools.py` L215-293), `buscar_contratos_por_fornecedor` (`consulta_pncp.py`) e a entrada `"buscar_contratos_fornecedor_pncp"` no `TOOL_STATUS_MAP` (`prompt.py` L318) estão **inalcançáveis** hoje (tool fora de `TOOLS` e do `SYSTEM_PROMPT`). Desativação **documentada e consciente** — manter até reativar. Só registrado para rastreio.
- [ ] Ao reativar a tool PNCP: `buscar_contratos_por_fornecedor` acessa chaves cruas do JSON (`compra["sequencialCompra"]`, `item["numeroItem"]`); um `KeyError` não é pego pelos `except httpx.*` do wrapper. Adicionar `.get()`/checagem ou `except (KeyError, TypeError)`.

### Documentação a ajustar
- [ ] `app/core/logging_config.py` (L27 e L48): trocar referência a `avaliar.py` (não existe mais) por `evaluation/pipeline_avaliacao.py`.
- [ ] `app/services/gerenciadorvetorial.py` (docstring de `buscar_contexto`, L99): "os 3 trechos" → "os top_k trechos (default 3)", já que é configurável via `TOP_K_EDITAL`.
- [ ] `app/models/agent_state.py` (L22-24): exemplo cita "o nome do usuário", conceito removido no Bloco 0 — trocar por outro exemplo (ex.: "um score parcial de risco").
- [ ] `app/models/pergunta_request.py` (docstring): mencionar o papel de `thread_id` (continuidade da conversa via checkpointer).

### Regressão a garantir (não é bug)
- [ ] Manter no golden dataset um caso que exercite `buscar_contexto_edital` **pelo caminho com cache** (`aplicar_cache` reconstrói o `StructuredTool` — a detecção de `InjectedState` pelo `ToolNode` depende do `args_schema` preservado). Hoje funciona; o teste pega de imediato se uma futura atualização de lib quebrar isso.

### Causa raiz (para a apresentação)
Dois dos três achados têm a **mesma causa**: *fronteiras de streaming tratadas pela metade*. O backend resolve bem o lado do LLM (buffer-then-commit isola a resposta final), mas (a) o frontend não trata a fronteira do chunk de **rede** no parser SSE e (b) o texto intermediário que o backend descarta ainda é **transmitido**. Mesmo tema — "o que é um pedaço *completo* de dado?" — em dois pontos. O terceiro (CGU) é a família "robustez a variável de ambiente ausente", igual ao `float(None)` já corrigido em `dependencies.py`.