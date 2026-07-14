# Auditor Cidadão — Roadmap Consolidado

> Documento único: requisitos oficiais do case (Data Master) + status do projeto + plano de entrega até 13/07/2026.
>
> **Última atualização:** 2026-07-13 (Backlog V2: três ideias de pesquisa avançada priorizadas — pipeline de extração robusto e guardrails estritos em E, GraphRAG como evolução do item QSA em F)
>
> **Sobre a entrega:** o projeto, no estado atual, já é entregável — a entrega é feita via um arquivo `.txt` com dois links (repositório GitHub e site de documentação MkDocs publicado), **sem** envio de projeto ou documentação zipados. Por isso, nada neste roadmap tem prazo enquanto bloqueio de entrega: os itens do Backlog V2 (incluindo os "próximos passos" do E6) podem ser implementados aos poucos, em commits feitos em dias seguintes, sem pressa e sem afetar o que já foi entregue.

---

# 🎓 REQUISITOS OFICIAIS DO CASE (Data Master — Engenheiro de IA)

> **⚠️ NÃO PERDER O FOCO:** esta seção é a fonte da verdade sobre o que a banca exige. Toda decisão técnica abaixo deve servir a estes requisitos — eles impactam diretamente a classificação final (Driving, Advanced ou Expert).

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
| T5 | ✅ | Diagramas Mermaid (ciclo do agente, fluxo de dados, protocolo MCP) em `docs/arquitetura/` (Bloco 5) |
| T6 | ✅ | `docs/governanca/` (LGPD, guardrails, limitações) publicado (Bloco 5) |
| E1 | ✅ | Dockerfile + lifespan + frontend prontos |
| E2/E3/R3 | ✅ | `docs/operacional/` (setup local, Docker, variáveis de ambiente) + README (Bloco 5) |
| E4 | ✅ | Diagramas Mermaid em `docs/arquitetura/` (Bloco 5) |
| E5 | ✅ | Decisões e trade-offs consolidados em `docs/ia/` e `docs/arquitetura/` (Bloco 5) |
| E6 | ✅ | Este roadmap cobre isso (seção Backlog V2) |

---

## Status Geral do Projeto

| Fase | Objetivo | Status |
|---|---|---|
| **Fase 0 — Limpeza técnica** | Logger, redundância, env vars | ✅ Concluída |
| **Fase 1 — Engenharia de prompt e segurança** | System prompt V2, catálogo de anomalias | ✅ Concluída |
| **Fase 2 — Async nativo + ToolNode** | `.ainvoke`, `ToolNode`, `astream_events` | ✅ Concluída |
| **Fase 3 — Novas fontes de dados** | PNCP (11 tools ativas), CEIS/CNEP, busca web | ✅ Concluída |
| **Fase 4 — Cache + Output estruturado** | Cache TTL ✅, JSON de risco ✅ | ✅ Concluída |
| **Fase 5 — Streaming** | Tokens em tempo real no frontend | ✅ Concluída |
| **Fase 6 — Framework de avaliação** | Golden dataset + RAGAS + aderência/anomalia | ✅ Concluída |
| **Fase 7 — Indexação automática via PNCP** | Busca + ingestão sem upload manual | 🚫 Backlog V2 |
| **Fase 8 — Infraestrutura e deploy** | Docker ✅, Railway ✅, Frontend ✅ | ✅ Concluída |

---

## ✅ O Que Já Foi Feito

**Fase 0:** logger padronizado, remoção de código morto, env vars centralizadas.

**Fase 1:** `SYSTEM_PROMPT` reescrito com identidade de auditor, catálogo de 9 anomalias (A–I), dois modos de resposta (conversacional e laudo), guardrails contra prompt injection, `data_hoje` injetada dinamicamente.

**Fase 2:** stack migrada para `async/await` com `ToolNode` nativo do LangGraph, `StreamingResponse` com `astream_events()`, `httpx.AsyncClient`. Zero thread síncrona bloqueando o event loop.

**Fase 4.1 — Cache TTL:** cache em memória com chave MD5 por tool + argumentos, TTL de 24h alinhado ao ciclo do PNCP, aplicado no `lifespan.py` após o patch MCP.

**Fase 5:** SSE com eventos `token` e `status`, frontend renderiza tokens em tempo real com Markdown.

**Bloco 0 — Correções técnicas herdadas:** 9 apontamentos de revisão de código aplicados antes do Bloco 1. `dependencies.py` com defaults seguros para `LLM_MODEL`, `LLM_TEMPERATURE` e `LLM_MAX_TOKENS` (boot não quebra mais se a env var faltar no Railway). SSE de `run_agent()` envolvido em `try/except`, emitindo `{"type": "done"}` ao final normal e `{"type": "error", ...}` em falha (com `logger.exception`) — frontend trata os dois eventos e nunca mais fica esperando para sempre. Cache MCP migrado de dict cru para `cachetools.TTLCache` (expiração automática + `maxsize`), eliminando o risco de OOM em runtime longo; o mesmo cache passou a envolver também as tools nativas (`consultar_receita_federal`, `buscar_contexto_edital`) no `lifespan.py`. Comentário enganoso sobre "subprocess Node.js persistente" corrigido — a versão instalada do `langchain-mcp-adapters` (0.3.0) já abre e fecha sessão por chamada, então não há shutdown explícito a fazer. `chunk.tool_calls` agora é lido com `getattr(chunk, "tool_calls", None)` para não quebrar em chunks intermediários. Novo helper `escape_xml()` aplicado em `pergunta_usuario`, `municipio`, `estado` e `cnpjs_formatados` — antes só a pergunta era escapada, abrindo brecha de prompt injection via `<METADADOS>`. `PerguntaRequest.lista_cnpjs` ganhou `field_validator`: corta em 10 CNPJs e descarta os matematicamente inválidos via `validate_docbr`, logando tentativas de abuso. Coleta do nome do usuário removida de ponta a ponta (`PerguntaRequest`, endpoints, `SYSTEM_PROMPT`, formulário do frontend) — reduz superfície de dado pessoal coletado.

**Extras concluídos:**
- Modelo em produção: **OpenAI `gpt-4o-mini`** (128k tokens), embeddings `text-embedding-3-small` (1536 dim), índice Pinecone recriado.
- MCP LiciNexus expandido: 11 tools ativas (licitações, contratos, atas de RP, comparação de períodos).
- `build_graph.py` refatorado: singleton com `initialize_graph(tools)`, closure para `call_llm`, `recursion_limit: 50`.
- `mcp_utils.py` com patch de schema, coerção de tipos e captura de exceções MCP.
- Docker: `Dockerfile` com Python 3.12 + Node.js 20, build local validado.

**Bloco 1 — Tools de sanções e busca web:** `consultar_sancoes_empresa` implementada consultando CEIS e CNEP (Portal da Transparência/CGU) via `asyncio.gather` em paralelo, com `CGU_API_KEY` obtida e validada. Bug de parâmetro descoberto só em teste real com a documentação Swagger: o filtro correto é `codigoSancionado`, não `cnpjSancionado` (este último é aceito e ignorado silenciosamente pela API, retornando a listagem sem filtro). Falha isolada em uma fonte (CEIS ou CNEP) não derruba a outra — `consultar_sancao_async` retorna `None` como sentinela de "fonte indisponível", distinto de `[]` ("fonte consultada, sem sanção"), preservando a diferença entre "não verificado" e "empresa limpa" exigida pela Anomalia H. Cada registro é achatado (`filtragem_sancoes.py`) com campos planos, incluindo `fonte_cadastro` (CEIS/CNEP) e `tipo_registro` (`"sancao"` | `"aviso"`) para rastreabilidade jurídica e para o LLM diferenciar dado real de aviso de indisponibilidade sem ambiguidade. `buscar_informacao_web` implementada com `langchain_tavily.TavilySearch` (a integração `TavilySearchResults` do `langchain-community` está deprecated); município/estado são concatenados à query via `InjectedState` de forma incondicional — decisão consciente de não tentar detectar se o LLM já mencionou uma localização, evitando heurística frágil. Pipeline de filtragem em `filtragem_resultados_web.py` (descarta fragmentos curtos/corrompidos, trunca conteúdo longo, seleciona só `url`/`title`/`content`), com `max_results=3` reduzindo volume na origem. Ambas as tools seguem o padrão já estabelecido de nunca deixar exceção subir crua — sempre retornam `{"error": ...}` estruturado. `SYSTEM_PROMPT` atualizado: capacidades das duas tools descritas, regra de precedência PNCP/Receita vs. busca web, e uma regra anti-alucinação nova (descoberta em teste real via log): proíbe "emprestar vocabulário" entre resultados de tools diferentes no mesmo turno (ex.: citar `situação cadastral` a partir de um resultado de sanções sem ter chamado a Receita Federal). `TOOL_STATUS_MAP` atualizado com as duas novas entradas. Validação feita com dados reais (CNPJ da Andrade Gutierrez com sanção real no CNEP; CNPJ da Prefeitura de Suzano como caso limpo) e cruzamento de logs do terminal, não apenas confiança na resposta do modelo — esse método já pegou dois bugs (parâmetro de API errado; alucinação por vocabulário emprestado) que não apareceriam só lendo a resposta final.

**Bloco 2 — Output Estruturado:** `app/models/laudo.py` criado com `Anomalia` e `RespostaLaudo` (`laudo: LaudoEstruturado | None`, `None` para respostas conversacionais). Segunda chamada LLM (`temperature=0.0`, instância dedicada instanciada no `lifespan.py` e recuperada via `get_extrator()`) extrai o JSON do laudo com `with_structured_output`, usando um `SystemMessage` próprio com critério explícito de decisão — o schema Pydantic sozinho não bastava, o modelo tentava preencher o laudo mesmo em respostas conversacionais até o critério ser explicitado no prompt. `laudo_completo` corrigido para não contaminar com texto de rodadas intermediárias do agente: acumula em `buffer_temporario` durante `on_chat_model_stream` e só confirma em `laudo_completo` no `on_chat_model_end`, quando dá para checar se a mensagem final não teve `tool_calls`. SSE ganhou os eventos `laudo_estruturado` e `laudo_estruturado_erro` (isolado em try/except próprio — falha na extração não derruba o `done` nem reaproveita o erro genérico do streaming, já que o Markdown já foi entregue com sucesso). Validado com dados reais (CNPJ da Andrade Gutierrez com sanção, e pergunta puramente conversacional).

**Bloco 3 — Integração PNCP nativa, refatoração de services e documentação:** `buscar_contratos_fornecedor_pncp` implementada em `app/services/consulta_pncp.py` para cruzar órgão + fornecedor (histórico de contratos vencidos), substituindo a tool MCP `get_fornecedor_contratos` que já vinha excluída da whitelist do LiciNexus por não funcionar corretamente. Fluxo (listar compras do órgão → itens → resultados, com filtro client-side por `niFornecedor`) validado manualmente endpoint a endpoint em notebook (`testes_locais/test_getcontratos_pncp.ipynb`) antes de virar código de produção — só nessa validação foram descobertos: a API do PNCP é dividida em duas bases (`/api/consulta` para busca, `/api/pncp` para dados por órgão), o campo do fornecedor vencedor se chama `niFornecedor` (não `cnpjFornecedor`), e `codigoModalidadeContratacao` é obrigatório em `/contratacoes/publicacao` — não existe "buscar todas as modalidades" num único request, então é preciso varrer as ~19 modalidades ativas uma a uma. Essa varredura expôs um rate limit agressivo do PNCP a nível de WAF (bloqueio de minutos após poucos requests simultâneos), mitigado com espaçamento mínimo de 2s entre chamadas e retry com backoff exponencial em 429/erro de conexão. Decisão consciente antes do merge: a tool ficou **implementada mas desativada** (removida de `TOOLS` e do `SYSTEM_PROMPT`) — a varredura completa de um órgão pode levar minutos mesmo com o rate limiting resolvido, e o streaming SSE não emite nenhum evento durante a execução de uma tool, arriscando ser encerrado por timeout de proxy em produção antes da tool terminar. Documentado como limitação conhecida em vez de arriscar quebrar o streaming na apresentação.

Aproveitando a tool nova, `app/services/tools.py` foi refatorado: cada tool nativa virou um wrapper fino (valida input, delega a chamada externa, traduz erro) sobre um módulo de serviço dedicado (`consulta_receita_federal.py`, `consulta_sancoes.py`, `busca_web.py`, `consulta_pncp.py`), consolidando helpers que estavam espalhados em `app/utils/` (`filtragem_sancoes.py` e `filtragem_resultados_web.py` absorvidos pelos respectivos módulos de serviço; `limpar_documento` inlinado como regex por ser simples demais para justificar um arquivo próprio). Antes de mexer em documentação, foi feita uma revisão completa do projeto atrás de bugs e código morto: encontrado e corrigido `.env.docker` sendo copiado para dentro da imagem Docker (`.dockerignore` só excluía `.env`, arriscando embutir chaves reais numa camada da imagem publicável); `TOOL_STATUS_MAP` ainda tinha a entrada do `get_fornecedor_contratos` já abandonado; `requirements.txt` não tinha `langchain-google-genai` apesar do `.env`/README já citarem Gemini como alternativa de LLM — todos corrigidos.

`README.md` reescrito do zero: conteúdo alinhado ao estado real do projeto (contagem de tools, modelo padrão correto `openai:gpt-4o-mini` em vez do Groq desatualizado, estrutura de pastas, endpoints sem o campo `user_name` que não existe mais), `.env.example` completo e versionável criado (exigiu adicionar `!.env.example` ao `.gitignore`, já que a regra `.env*` também o capturava), e uma seção honesta de limitações conhecidas citando a tool de PNCP desativada. Versão da aplicação (`main.py`) atualizada de `1.1.3` para `1.2.0`, unificando com o badge do README (antes divergente, `v0.4.0`). Todo o trabalho foi para um PR único (#6), revisado e mesclado na `main`; branch de feature removida local e remotamente após o merge.

**Bloco 4 — Framework de Avaliação:** `evaluation/golden_dataset.json` criado com 11 casos (reais + sintéticos), cobrindo empresa com sanção ativa no CEIS/CNEP (Anomalia H), prazo de publicação irregular (Anomalia F), caso controle sem anomalia esperada e caso puramente conversacional — mix exigido pelo roadmap original coberto. `evaluation/pipeline_avaliacao.py` (substitui o `avaliar.py`/`JulgamentoLLM` originalmente planejado — ver trade-off documentado no Bloco 5) roda o agente de ponta a ponta contra cada caso e mede três famílias de métrica independentes:
- **`aderencia_tools`** — comparação determinística (sem LLM) entre `tools_esperadas` e `tools_chamadas`; percorre só o que era esperado, tools extras chamadas pelo agente não entram na conta.
- **`recall_anomalias`** — reusa o extrator estruturado de produção (`RespostaLaudo`) sobre o `laudo_completo` de cada caso, comparando os códigos do catálogo A–I detectados contra `anomalias_esperadas`.
- **RAGAS (`faithfulness`, `context_recall`)** — mede alucinação e cobertura de contexto nos casos que usam `buscar_contexto_edital`, contra o `contexto_edital_esperado` de cada caso.

Cinco bugs reais foram encontrados e corrigidos durante a validação do framework, o mais grave deles em produção, não só no teste:
1. **Catálogo de anomalias ausente no `PROMPT_EXTRATOR`** — o extrator via só a lista de códigos válidos (`Literal["A"..."I"]"`), sem os critérios de cada um, e por isso não sabia mapear texto de sanção para o código `H`. Corrigido extraindo o catálogo completo (com critério por letra) para uma constante única (`CATALOGO_ANOMALIAS`), reusada tanto no `SYSTEM_PROMPT` quanto no `PROMPT_EXTRATOR` — elimina duplicação de texto entre os dois.
2. **Corrida de consistência eventual do Pinecone** — o pipeline consultava o índice logo após indexar, sem esperar a propagação, derrubando `context_recall` de forma não-determinística. Corrigido com `_aguardar_contagem_namespace`, que faz *polling* em `describe_index_stats` até a contagem esperada de vetores aparecer.
3. **Namespace compartilhado entre casos do mesmo município** — causava delete-readd adjacente e contaminação de chunks entre casos consecutivos. Corrigido isolando cada caso num namespace exclusivo (`avaliacao_<id>`).
4. **Ruído do juiz RAGAS** — `gpt-4o-mini` como `AVALIADOR_MODEL` dava notas inconsistentes para o mesmo contexto recuperado entre execuções (comprovado: contexto byte-a-byte idêntico, nota diferente). Trocado para `gpt-4o`, que eliminou a variância de `context_recall` entre rodadas (amplitude `0.000` em 3 execuções).
5. **Bug de produção real: metadados compartilhados no upsert do Pinecone** (`app/services/gerenciadorvetorial.py`, `processar_e_salvar`) — `[metadados] * len(lista_chunks)` criava `N` referências ao mesmo dict em vez de `N` cópias independentes; o `add_texts` da lib então sobrescrevia repetidamente o mesmo objeto, fazendo **todo chunk indexado — em qualquer edital, inclusive os de usuários reais em produção — ser armazenado com o texto do último chunk do documento**, disfarçado atrás de scores de similaridade que continuavam plausíveis (os embeddings, calculados antes da mutação, permaneciam corretos). Corrigido trocando a multiplicação de lista por `[dict(metadados) for _ in lista_chunks]`. Achado durante uma investigação que começou como debug de métrica de teste e terminou revelando um defeito que afetava usuários reais — banco vetorial de produção já estava limpo no momento da correção, então não foi necessário reindexar nada retroativamente.

Além dos bugs, uma limitação estrutural foi identificada e tratada por decisão consciente, não por correção de código: o `caso_06` tem `contexto_edital_esperado` como uma afirmação **negativa** ("o edital não traz a data de publicação") — `context_recall` do RAGAS não tem mecanismo para validar ausência de informação contra chunks recuperados, então esse caso nunca pontuaria bem nessa métrica específica, independentemente da qualidade do retrieval. Excluído do cálculo do RAGAS via um campo próprio no dataset (`excluir_do_ragas: true`), mantendo-se normalmente nas demais métricas (aderência de tools).

Critérios mínimos de aprovação definidos e aplicados automaticamente (`aprovacao["geral"]`): `aderencia_tools ≥ 0.70`, `faithfulness ≥ 0.85`, `context_recall ≥ 0.75`, `recall_anomalias ≥ 0.80`. Resultado consolidado em **6 execuções** após todas as correções acima (3 do pipeline + 3 manuais adicionais, mesmo protocolo): `aderencia_tools = 1.00` e `recall_anomalias = 1.00` estáveis nas 6/6. `context_recall` ficou em `0.60` em 5 das 6 execuções (uma delas registrou `0.90`, tratado como outlier pontual, não repetido) — reprovado, limitação documentada de `top_k=3` em 2 dos 5 casos elegíveis ao RAGAS (ver Backlog V2). `faithfulness` se mostrou **instável em torno do próprio limiar**: variou entre `0.79` e `0.88` nas 6 execuções (4 aprovadas, 2 reprovadas) — não é uma aprovação sólida, apesar de ter passado nas 3 primeiras rodadas medidas. Hipótese não confirmada: variância herdada da `temperature=0.1` do agente principal (mesma configuração de produção), usada também durante a avaliação — ver item correspondente no Backlog V2. Veredito geral (`aprovacao["geral"]`) reprovado na maioria das 6 execuções, por causa de `context_recall`.

**Bloco 5 — Documentação Final:** site de documentação técnica publicado com MkDocs Material (`mkdocs.yml`) em `/docs`, organizado em quatro pilares em vez da estrutura flat originalmente planejada — `operacional/` (visão geral, setup local, Docker & deploy, variáveis de ambiente), `arquitetura/` (visão geral do ciclo do agente, fluxo de dados ponta a ponta, protocolo MCP), `ia/` (modelos e prompts, uso de dados e RAG, extração de laudo, avaliação RAGAS, catálogo de anomalias) e `governanca/` (LGPD e privacidade, guardrails, limitações conhecidas), somando ~1.230 linhas de Markdown. Cobre os requisitos T5 (arquitetura com agentes) e T6 (ética/privacidade) do case, além dos entregáveis E2–E6 (explicação do case, instruções de execução, diagrama de arquitetura, decisões/trade-offs, próximos passos). Diagramas do ciclo de decisão do agente e do fluxo de dados renderizados em Mermaid — com uma configuração própria (`javascripts/mermaid-init.js`, versão fixada em `11.16.0`) porque a renderização automática embutida no Material 9.7.6 falhava silenciosamente. `docs/governanca/limitacoes.md` documenta honestamente as lacunas da V1 (cobertura parcial do catálogo de anomalias, `top_k=3`, `InMemorySaver` volátil, ausência de autenticação/rate limiting, dependência de APIs externas, tool de PNCP desativada), reafirmando o princípio de que o sistema sinaliza padrões para investigação humana e nunca emite veredito final. Trade-offs técnicos dos Blocos 2 e 4 (buffer-then-commit do streaming, RAGAS em vez do juiz caseiro originalmente planejado, bug de metadados do Pinecone, exclusão do `caso_06` do RAGAS, troca do juiz para `gpt-4o`) consolidados como notas explicativas dentro das páginas de arquitetura e avaliação, em vez de ficarem só espalhados em comentários de código.

---

# 🚫 Backlog V2 — Fora do Escopo desta Entrega

> Candidatas naturais para a próxima versão. Boa resposta para "quais são os próximos passos?".
> Reorganizado em julho/2026 por tema (antes era uma lista plana em ordem de descoberta).
> Itens marcados 🆕 foram identificados em revisão posterior ao Bloco 5, ainda não estavam documentados nesta seção.
>
> **Nenhum item abaixo bloqueia a entrega.** A entrega já pode ser feita hoje, no estado atual do projeto (`.txt` com os dois links — repositório GitHub e documentação MkDocs publicada). Esta seção é o material de resposta para "quais são os próximos passos?" (E6) e uma lista de trabalho para depois da entrega — pode ser implementada aos poucos, em commits nos dias seguintes, sem prazo.

## A. Segurança, custo e escalabilidade

Agrupa tudo que trata do sistema aguentar produção real com múltiplos usuários simultâneos — o ponto que a banca mais tende a questionar (T6).

### Controle de custo e limite de uso (gap identificado, ainda sem solução)
Hoje não existe nenhum limite de uso: sem autenticação e sem quota por sessão/dia, um usuário pode conversar — e gastar tokens da OpenAI — indefinidamente. É um ponto real de exposição a custo não controlado e uma pergunta provável da banca sobre escalabilidade (T6). Ainda não decidido; opções a avaliar na V2 antes de qualquer deploy público sem controle de acesso:
- Rate limiting por sessão/IP (ex.: N mensagens/hora)
- Quota diária por `thread_id`/usuário, bloqueando ao atingir o limite
- Timeout/expiração de conversa (encerrar thread após N turnos ou X minutos de inatividade)
- Autenticação mínima (mesmo que só um token de acesso) como pré-requisito para qualquer limite por usuário funcionar de fato — **`thread_id` sozinho não serve como identificador de limite**: é gerado e descartável pelo próprio client (visível via DevTools), então rate limit baseado só nele não impõe custo real ao abuso.
- **Decisão: cookie `httpOnly` assinado como identificador de sessão/quota.** Resolve manipulação (o usuário não edita o valor via DevTools), mas resolve só metade do problema — não impede reset: limpar cookies, aba anônima ou outro navegador geram uma sessão nova e, portanto, uma quota nova. Aceitável para o escopo do MVP (não protege contra atacante sofisticado, só eleva o custo do abuso casual), mas é uma limitação a documentar explicitamente, porque é exatamente o tipo de pergunta que a banca faz em seguida ("e se o usuário limpar o cookie?"). Fingerprinting e Proof-of-Work (PoW) resolveriam o reset, mas são esforço desproporcional ao problema real do escopo atual — descartados conscientemente, não por omissão.

### 🆕 Workers e escalonamento horizontal (uvicorn/Railway)
Hoje a aplicação roda com o padrão implícito de 1 worker (`--workers` do uvicorn nunca foi configurado). Isso não é um bug — é o motivo pelo qual não há corrida entre processos hoje —, mas é uma lacuna de documentação/decisão que a banca pode perguntar direto ("como isso escala horizontalmente?"). Dois pontos a resolver juntos antes de aumentar workers/instâncias:
- Configurar explicitamente `--workers N` (ou múltiplas instâncias no Railway) exige revisar todo componente hoje assumido como singleton por processo — especialmente qualquer scheduler ou job periódico que vier a ser criado (ex.: rotina de expiração de namespace do Pinecone, ver item de Persistência abaixo): com N workers, cada processo instanciaria seu próprio job, rodando a mesma limpeza em paralelo. Solução mais simples: tirar esse tipo de job de dentro do processo da aplicação (ex.: Cron Job nativo do Railway rodando como serviço separado) em vez de usar um scheduler in-process.
- Documentar a decisão atual (1 worker, suficiente para o volume do MVP) como escolha consciente, não omissão — evita a lacuna virar pergunta sem resposta pronta na apresentação.

### Persistência
| Componente | V1 (atual) | V2 (alvo) |
|---|---|---|
| Histórico de conversas | `InMemorySaver` (RAM), sem TTL/eviction | Mantém-se `InMemorySaver`, mas com mecanismo de **eviction/TTL por thread** a implementar (hoje o dict cresce indefinidamente até o processo reiniciar — comportamento equivalente ao que o cache de tools tinha antes do Bloco 0, corrigido com `cachetools.TTLCache`; aplicar o mesmo padrão aqui) |
| Cache de tools | Dict/`TTLCache` em memória | Redis com TTL nativo, compartilhado entre instâncias — só relevante se a V2 realmente escalar para múltiplos workers/instâncias (ver item acima) |

### Namespace de indexação por `thread_id` em produção
Hoje todo usuário indexa no mesmo namespace, isolado só por filtro de metadado (`estado`+`municipio`) — dois usuários indexando ao mesmo tempo podem, em tese, disputar entre si a mesma barreira de consistência usada na avaliação. Isolar por `thread_id` resolve, mas introduz um problema de ciclo de vida novo (quando apagar o namespace de uma sessão encerrada). `beforeunload`/`visibilitychange` no frontend não é confiável sozinho (não dispara em crash, perda de rede, ou boa parte do mobile) — precisaria de uma rotina de expiração no backend como rede de segurança, no mesmo espírito do TTL já aplicado ao cache de tools.

> **Importante não confundir os dois TTLs acima:** o `InMemorySaver` guarda o *estado da conversa* (RAM do processo, some sozinho se o servidor reiniciar); o Pinecone guarda os *vetores do edital indexado* (serviço externo, **não** é afetado por restart do Railway). São dois ciclos de vida independentes — reiniciar a aplicação não limpa o Pinecone, e o Pinecone não sabe quando uma sessão de chat "acabou" sem um mecanismo de expiração próprio.

---

## B. 🆕 Reestruturação seguindo os padrões oficiais do LangGraph/LangChain

O agente foi construído acompanhando um tutorial que explica o funcionamento *por baixo do capô* — ótimo para entender os mecanismos (grafo de estados, checkpointer, tool calling), mas o próprio autor do material recomendou, ao final, revisitar a documentação oficial do LangGraph/LangChain antes de ir para produção, já que a biblioteca já resolve nativamente boa parte do que foi implementado manualmente. Vale uma auditoria dedicada comparando o projeto com os padrões recomendados — não é correção de bug (o sistema funciona e passou pela avaliação do Bloco 4), é dívida técnica de idiomaticidade: código mais verboso do que precisaria ser, e potencialmente mais difícil de manter conforme a V2 cresce em nodes/tools.

**Candidato mais claro, já identificado nesta revisão:** `app/services/build_graph.py` reimplementa manualmente o ciclo ReAct (`call_llm` → `router` condicional → `tool_node` → volta pro `call_llm`) que o LangGraph já oferece pronto via `langgraph.prebuilt.create_react_agent` — a lib cobre o mesmo loop, incluindo o roteamento por `tool_calls`, com uma fração das linhas hoje escritas à mão. Precisa avaliar se `create_react_agent` comporta as customizações que o projeto já depende (`InjectedState` para `estado`/`municipio` nas tools, checkpointer `InMemorySaver`, `bind_tools` com parâmetros de config) antes de migrar — se comportar, é a maior redução de código do item.

**Outros pontos a auditar contra a documentação oficial:**
- Padrão de definição de tools (`@tool` com `Annotated`/`Field` em `app/services/tools.py`) vs. formas alternativas recomendadas atualmente pelo LangChain para tools async com múltiplos parâmetros e `InjectedState`.
- Extração de output estruturado do laudo (Bloco 2, segunda chamada LLM com `with_structured_output`) vs. padrões oficiais de structured output dentro de um node do LangGraph, incluindo se a extração poderia virar parte do próprio grafo em vez de uma chamada externa a ele.
- Uso do checkpointer (`InMemorySaver`) e do padrão singleton (`initialize_graph`/`get_graph` em `build_graph.py`) vs. formas recomendadas de gerenciar ciclo de vida do grafo numa aplicação FastAPI (relaciona-se com o item de `PostgresSaver` na seção de Persistência acima).
- Streaming via `astream_events()` e o buffer-then-commit do laudo (Bloco 2) vs. mecanismos nativos do LangGraph para streaming de eventos por node/run — ver também o item de "Buffer por `run_id`" na seção de arquitetura abaixo, que pode ficar mais simples se resolvido com a abstração certa da lib em vez de um dicionário manual.
- Integração MCP (`langchain-mcp-adapters` em `lifespan.py`) vs. o padrão oficial mais atual de registro de tools externas no LangGraph.

**Como conduzir:** revisão indicada **antes** do item C (arquitetura do grafo e streaming) — faz sentido resolver primeiro a idiomaticidade da base (grafo, tools, checkpointer) para não redesenhar a separação de nodes duas vezes. Comparar cada ponto acima com a documentação oficial (LangGraph e LangChain), decidir migrar ou manter por caso, e rodar o golden dataset do Bloco 4 (`evaluation/`) contra a versão refatorada para garantir que nenhuma métrica regride antes de substituir o código em produção.

---

## C. Produto e experiência do usuário

### 🆕 Relatório automático pós-indexação
Hoje o laudo (resumo executivo ou completo) só é gerado mediante interação explícita do usuário com o modelo. Para o usuário leigo, que muitas vezes não sabe o que perguntar depois de subir o edital, isso é fricção desnecessária. Proposta: ao concluir a indexação, o sistema gera automaticamente um relatório inicial, acompanhado de sugestões de perguntas contextualizadas — torna a ferramenta mais intuitiva sem exigir que o usuário saiba formular a pergunta certa. **Trade-off a documentar:** isso dispara uma chamada de LLM (e possivelmente a segunda chamada de extração estruturada) em toda indexação, mesmo sem o usuário pedir — conversa diretamente com o item "Controle de custo e limite de uso" acima; se implementado, o rate limiting deixa de ser só sobre o chat e passa a cobrir também o upload.

### Módulos futuros da plataforma
| Módulo | Descrição |
|---|---|
| Auditor de Contratos | Aditivos suspeitos e prorrogações irregulares pós-licitação |
| Monitor de Fornecedores | Dashboard por município: contratos, sanções, vínculos |
| Alertas Automáticos | Notifica quando fornecedor sancionado vence licitação monitorada |
| Auditoria Estadual | Expansão para contratos estaduais |
| API Pública | Laudos como API para jornalistas, ONGs, sistemas de transparência |

**Princípio fundamental da plataforma:** o sistema sinaliza padrões para investigação humana — não acusa nem emite sentenças. Framing explícito no `SYSTEM_PROMPT`, na documentação e na apresentação.

---

## D. Arquitetura do grafo e streaming

### Separação de nodes no grafo (decisão de tool vs. geração de resposta)
Hoje o grafo é o padrão ReAct simples: um único node `agent` chamado em loop até parar de emitir `tool_calls`, seguido de `tools` → volta pro `agent`. Funciona, mas fica difícil de ler num diagrama à medida que mais lógica Python (pequenas automações, análises fora de tools) for entrando no fluxo. Separar em nodes dedicados (ex.: um node de decisão/orquestração e um node de geração final, mais nodes de processamento determinístico fora do ciclo de decisão do LLM) melhora legibilidade e reduz rodadas de LLM desnecessárias conforme o número de tools/automações cresce na V2. Não é correção de bug — o buffer-then-commit do Bloco 2 já resolve a extração correta do laudo independente da topologia do grafo — é uma melhoria de manutenibilidade e clareza arquitetural.

### Buffer por `run_id` (streaming paralelo)
O `buffer_temporario` do Bloco 2 assume execução sequencial (uma chamada de LLM por vez no grafo). Se a V2 introduzir paralelismo real (ex.: `Send` do LangGraph disparando sub-agentes simultâneos), um buffer único global passa a misturar conteúdo de streams concorrentes — nesse cenário, migrar para um dicionário de buffers indexado por `evento["run_id"]`.

---

## E. Modelo, avaliação e qualidade

### Avaliar modelos alternativos de LLM (benchmark contra o `gpt-4o-mini` atual)
O `gpt-4o-mini` foi escolhido para a V1 pelo custo-benefício (agente chamado a cada turno de cada usuário, tarefa não exige raciocínio de fronteira — ver [T1](docs/ia/modelos_prompts.md)). Fica como candidato de V2 rodar o golden dataset (`evaluation/`) contra outros modelos para comparar custo, latência e qualidade do laudo antes de trocar o padrão de produção:

- **Sabiá-3 / Sabiá-4 (Maritaca AI)** — principal modelo comercial puramente brasileiro, treinado especificamente para jargão jurídico e documentos institucionais do país, além de exames nacionais complexos (OAB, ENADE). Desempenho em português comparável a modelos globais de ponta, com suporte a function calling e leitura de arquivos via API — candidato natural por já ser otimizado para o domínio jurídico-institucional brasileiro que o Auditor Cidadão audita.
- **OpenAI o1 / o3-mini** — diferente do `gpt-4o-mini` (rápido, custo-benefício), a linha `o` usa cadeias de pensamento avançadas para resolver problemas passo a passo — potencialmente melhor para destrinchar decretos e encontrar "pegadinhas" em editais complexos.
- **DeepSeek-R1** — modelo open-source de raciocínio lógico que rivaliza com a linha `o` da OpenAI, com capacidade de interpretação de texto complexo a um custo de API extremamente baixo.
- **Claude 3.5 Sonnet / Claude 3.5 Opus (Anthropic)** — o Sonnet é amplamente considerado um dos melhores modelos do mercado para análise contratual e escrita jurídica de alta qualidade em português, pela interpretação sutil de nuances textuais e tom formal.
- **Google Gemini 1.5 Pro / Gemini 2.0 Flash** — janela de contexto colossal (1–2 milhões de tokens), permitindo em tese carregar o edital inteiro junto com a Lei 14.133/21 completa e outras instruções normativas na mesma conversa, sem depender de RAG para o corpo legal.

**Antes de trocar qualquer modelo em produção:** rodar o mesmo protocolo de avaliação já usado no Bloco 4 (aderência de tools, recall de anomalias, RAGAS) contra o golden dataset, para comparar maçã com maçã — não basta impressão subjetiva de qualidade, o framework de avaliação existe justamente para essa comparação (ver [Avaliação](docs/ia/avaliacao.md)).

### 🆕 Revisão de concisão do `SYSTEM_PROMPT`
`app/core/prompt.py` concentra os quatro prompts do projeto (337 linhas ao todo); o `SYSTEM_PROMPT` sozinho tem cerca de 190 linhas, com regras escritas em prosa longa (ex.: seções "COMPORTAMENTO QUANDO NÃO HÁ ANOMALIAS" e "REGRAS DE SEGURANÇA") que provavelmente podem virar instruções mais diretas sem perder precisão. Já se beneficia da deduplicação feita no Bloco 4 (`CATALOGO_ANOMALIAS` como constante única reusada em `SYSTEM_PROMPT` e `PROMPT_EXTRATOR`), mas o restante do texto nunca passou por uma revisão de concisão dedicada — foi crescendo organicamente a cada bloco (regra anti-vocabulário-emprestado do Bloco 1, critério de decisão do laudo do Bloco 2, regras de filtragem geográfica do PNCP, etc.), sem uma passada de volta para cortar redundância.

**Por que importa:** o `SYSTEM_PROMPT` é enviado por inteiro a cada primeiro turno de cada conversa — enxugá-lo reduz tokens de entrada e, portanto, custo por conversa (conecta com o item "Controle de custo e limite de uso" da seção A). Também facilita manutenção: um prompt mais enxuto é mais rápido de revisar quando uma nova anomalia ou regra for adicionada.

**Como conduzir:** revisar seção a seção em busca de instruções redundantes ou verbosas demais para o que comunicam, cortando sem perder nenhum critério de decisão (score, hierarquia de evidências e regras de segurança são inegociáveis). Depois de qualquer corte, rodar o golden dataset do Bloco 4 (`evaluation/`) contra a versão enxuta antes de substituir em produção — mesma disciplina já usada para validar mudanças no grafo e nos modelos, garantindo que a redução de tokens não derrube `aderencia_tools`, `recall_anomalias` ou `faithfulness`. Pode ser conduzida junto com o item B (padrões do LangChain), já que a forma de declarar prompts (`ChatPromptTemplate` vs. f-string simples hoje usado) também está no escopo daquela revisão.

### Qualidade
- **🆕 [Prioridade ALTA] Pipeline de extração robusto (LlamaParse / modelo Vision-Language)** — hoje `app/utils/func_extrair_texto_pdf.py` usa só `pdfplumber.extract_text()` por página: sem OCR e sem reconhecimento de estrutura de tabela. Em PDF escaneado (comum em edital de prefeitura pequena, digitalizado de papel), `extract_text()` retorna vazio/`None` para a página inteira, silenciosamente — o `or ""` no join não avisa que aquele conteúdo simplesmente não entrou no índice. Isso é candidato real a explicar parte do problema de `context_recall` já medido no Bloco 4: os 2 casos que não aparecem nem em `top_k=50` (`caso_02`, `caso_04a`, ver "Busca semântica" abaixo) foram atribuídos a "posição no documento", mas não foi descartada a hipótese de página escaneada sem texto extraível — vale conferir antes de assumir que só reranking/chunking resolve. Troca por LlamaParse (ou um VLM tipo `gpt-4o` em modo visão só para as páginas problemáticas) resolveria tabela e imagem/scan ao mesmo tempo. Esforço médio; validar primeiro se algum dos casos do golden dataset atual é de fato PDF escaneado antes de investir.
- **🆕 [Prioridade MÉDIA-ALTA] Guardrails estritos (NeMo Guardrails / Llama Guard) para citação obrigatória de artigo de lei** — hoje o anti-alucinação é só prompt-based (regra "não emprestar vocabulário" do Bloco 1, hierarquia de evidências, critério de score do `SYSTEM_PROMPT`) e medido via `faithfulness` do RAGAS. Faz sentido como resposta arquitetural à instabilidade de `faithfulness` já documentada (`0.79`–`0.88`, 2 de 6 execuções reprovando o limiar mesmo após o bug de metadados corrigido, ver acima): uma camada de guardrail que valide programaticamente se cada afirmação do laudo cita um artigo da Lei 14.133 (ou um campo literal de uma tool chamada) seria mais determinística do que confiar só na instrução do prompt. Reforça T6 (evita alucinação/viés). Rodar contra o golden dataset do Bloco 4 antes de adotar, comparando `faithfulness` com e sem a camada de guardrail.
- **Busca semântica com `top_k` maior (hoje 3), já configurável via `TOP_K_EDITAL`** (env var, default 3, não exposta à tool que o LLM chama — só o código controla). Diagnóstico real feito no Bloco 4: de 5 casos com `context_recall` ruim, 2 (`caso_04b`, `caso_08`) são recuperáveis com `top_k` maior (posições 9 e 2 no ranking) — subir pra ~10 resolveria esses. Os outros 2 (`caso_02`, `caso_04a`) **não aparecem nem em `top_k=50`** — limitação genuína de posição no documento (chunk-alvo no apêndice/muito distante), que só reranking ou chunking diferente resolveria. Decisão de valor final adiada — subir `top_k` em produção aumenta custo de token por chamada e pode piorar `faithfulness` (mais contexto irrelevante pro LLM confundir), não é troca sem custo.
- Expansão do golden dataset para 30+ casos cobrindo as 9 categorias
- **Reavaliar `AVALIADOR_MODEL` de volta para `gpt-4o-mini`** como otimização de custo de CI/avaliação recorrente (não afeta usuário final — esse modelo só roda quando o time executa o golden dataset). Adiado para depois da entrega: o `gpt-4o-mini` mostrou ruído de julgamento mesmo com dado de entrada correto (nota variando para o mesmo contexto recuperado); trocar de volta exige revalidar estabilidade em 3+ rodadas antes de confiar no resultado.
- **Investigar variância residual de `faithfulness`** — prioridade elevada após 6 execuções totais mostrarem oscilação de `0.79` a `0.88` (amplitude `0.086`), com 2 das 6 reprovando o limiar de `0.85` mesmo com o juiz `gpt-4o` e o bug de metadados já corrigido — não é mais ruído desprezível, é a métrica mais próxima de aprovação consistente e a mais fácil de destravar. Hipótese não confirmada: `temperature=0.1` do agente principal (mesma configuração de produção) usada também na avaliação, gerando laudos ligeiramente distintos por execução. Testável congelando `temperature=0` só durante a avaliação, sem mudar produção. **Atualização (2026-07-08):** uma rodada adicional de 3 execuções trouxe `faithfulness = 0.858`, aprovado com folga — sinal encorajador, mas uma rodada só ainda não é suficiente pra declarar a variância resolvida. Manter o item aberto até acumular mais execuções (ver [Avaliação](docs/ia/avaliacao.md#nova-rodada-de-validacao-2026-07-08)).
- **Auditar o repositório atrás de outros usos do padrão `[X] * N` com objeto mutável** — o bug de metadados do Bloco 4 foi corrigido pontualmente em `gerenciadorvetorial.py`; não houve varredura completa do projeto atrás do mesmo padrão em outro lugar.

---

## F. Novas fontes de dados e catálogo de anomalias

### Fase 7 — Indexação Automática via PNCP + Migração de Metadados
Elimina o upload manual: o agente busca, baixa e indexa o PDF a partir de uma conversa. Junto com essa migração, o schema de metadados do Pinecone muda de `municipio`/`estado` (informados manualmente) para **`cnpjs` (lista extraída automaticamente)** — o mesmo padrão já usado hoje (metadados replicados em todos os chunks do documento), só trocando o campo.

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

**Pré-requisitos:** verificar se `list_licitacao_arquivos` retorna URL direta; refatorar `gerenciadorvetorial.py` para download por URL; deduplicação por `numeroControlePNCP`.

### Tool `buscar_historico_empresa` (cruzamento cross-município)
Depende da migração de metadata acima. Recebe um CNPJ e retorna todos os editais relacionados já indexados no Pinecone — permitindo o agente cruzar, por exemplo, uma empresa sancionada em Mogi das Cruzes (SP) com um padrão semelhante em outro município. Desenhada como **tool explícita** (o LLM decide quando chamar via CNPJ já conhecido), não como varredura automática em toda análise — evita custo de token desnecessário. Documentar no `SYSTEM_PROMPT` e citar explicitamente na seção de ética (T6) como parte da visão de produto.

### `consultar_preco_referencia` (Painel de Preços / Compras.gov)
Habilitaria detecção de sobrepreço (Anomalia A). Endpoint instável — verificar disponibilidade antes de implementar.

### `consultar_dados_municipio` (API IBGE)
IDH, PIB per capita, população, IDEB — contextualiza o valor de uma contratação com a capacidade fiscal real do município (ex.: prefeitura com PIB per capita de R$8.000 contratando sistema de TI por R$2 milhões).

### Novos cruzamentos para o catálogo de anomalias (pesquisa de mercado, 2026-07-04)
> Dicas coletadas comparando o projeto com ferramentas de monitoramento público existentes, mais uma ideia própria. A maioria **reforça anomalias que já existem no catálogo A–I** em vez de criar categorias novas — por isso o esforço de várias é menor do que parece.

**Achado que muda a viabilidade de quase tudo abaixo:** a BrasilAPI já devolve `capital_social`, `cnaes_secundarios`, `qsa` (quadro de sócios) e endereço completo no mesmo request que `consultar_receita_federal` já faz — só que esses campos são descartados em `app/services/consulta_receita_federal.py:34-41` antes de chegar no LLM. Boa parte do que segue é reexpor dado que já está sendo buscado, não integrar uma fonte nova.

- **Reforço da Anomalia E (Empresa Recém-Criada) — "fator recém-nascida":** comparar `data_inicio_atividade` (já capturado) com a data de publicação do edital, com limiar mais agressivo (180 dias) quando o valor é alto e o município é isolado. Esforço **baixo** — dado já existe, é ajuste de critério no prompt.
- **Reforço da Anomalia I (Incompatibilidade de Atividade):** hoje só o CNAE principal é usado. Reexpor `cnaes_secundarios` (hoje descartado) permite pegar o caso de CNAE principal genérico ("comércio varejista em geral") vencendo objeto técnico complexo (saneamento, engenharia). Esforço **baixo**.
- **Capital social incompatível (candidato a novo sub-critério de E):** `capital_social` já vem da BrasilAPI. Comparar com o valor do contrato (ex.: capital de R$5.000 vs. contrato de R$2 milhões) é uma heurística simples de capacidade financeira. Esforço **baixo**; falta só decidir se vira sub-critério de E ou letra nova do catálogo.
- **Reforço real da Anomalia D (Cartel/Conluio) via QSA:** o critério "cruze quadro societário" já existe no prompt (`prompt.py:88-90`), mas **hoje não há nenhum dado de sócios** — nem para comparar sócios entre concorrentes, nem para checar CPF de sócio no CEIS/CNEP (útil para achar CNPJ "limpo" aberto por sócio já punido em outra empresa). Precisaria: (1) capturar `qsa` na consulta à Receita Federal, (2) chamar `consultar_sancoes` com o CPF do sócio — o parâmetro `codigoSancionado` do Portal da Transparência já aceita CPF, então a tool de sanções em si não muda. ⚠️ **Validar antes de investir:** a BrasilAPI costuma mascarar parte do CPF do sócio por LGPD (ex.: `***123456**`); se vier mascarado, o cruzamento com CEIS/CNEP (que exige documento completo) não funciona e a ideia trava nesse ponto. Esforço **médio**, com uma dependência de validação técnica antes de comprometer o escopo.
  - **🆕 [Prioridade BAIXA] Evolução via GraphRAG:** em vez de uma heurística simples de comparação de sócios, mapear as relações (sócio ↔ empresa ↔ licitação ↔ prefeitura) como um grafo, permitindo consultas de múltiplos saltos (ex.: "empresas diferentes, sócios sobrepostos, revezando vitórias no mesmo órgão ao longo do tempo" — hoje coberto de forma mais rasa pela Anomalia G/Reincidência Suspeita). Fraudes de cartel tipicamente envolvem redes de empresas parceiras que uma comparação par-a-par não enxerga bem. Ordenado como prioridade **baixa** de propósito: depende do item acima (captura de `qsa`) já estar resolvido e validado — inclusive o bloqueio de CPF mascarado — antes de fazer sentido investir em infraestrutura de grafo por cima de um dado que ainda nem foi confirmado como disponível. Mais próximo de "Módulos futuros" do que de V2 imediata, no mesmo espírito do item "Consórcio camuflado" abaixo.
- **Consórcio camuflado (subcontratada sancionada em obra de saneamento):** exigiria extrair e ler atas de julgamento/subcontratação em PDF, procurando CNPJs sancionados ocultos como subcontratados. Não há hoje extração estruturada de atas nesse nível. Esforço **alto**, mais próximo de pesquisa do que de feature — melhor como item de "Módulos futuros" do que V2 imediata.
- **Indicador de "Atratividade" (licitação com concorrente único e lance igual ao valor máximo do edital):** dá para calcular hoje com as tools PNCP já ativas (`list_licitacao_resultados`), sem nenhuma integração nova — falta só o critério/cálculo. Reforça a Anomalia B (Direcionamento). Esforço **baixo-médio**.
- **Explosão de Atas de Registro de Preço ("carona" de município pequeno em ata de capital distante):** `search_atas_rp`/`get_ata_rp` já trazem órgão gerenciador e aderentes — falta o critério que sinaliza volume de adesão fora do padrão. Reforça a Anomalia C (Fracionamento). Esforço **médio**.
- **Propostas idênticas em PDF (metadados de autor/software/data de criação repetidos entre 1º e 2º colocado):** reforça a Anomalia D, mas depende da **Fase 7** (download automático de PDF) já listada acima — sem isso, não dá para comparar o arquivo da vencedora com o da 2ª colocada sem exigir upload manual duplicado do usuário. Esforço **médio, bloqueado por Fase 7**.
- **Busca web direcionada por endereço (indício de sede "fachada" — residência, terreno baldio, escritório virtual/coworking):** o endereço completo já vem da BrasilAPI e hoje é descartado; dá para enriquecer a query da busca web com o endereço + termos como "sala comercial", "coworking", "endereço fiscal". Isso é diferente de analisar imagem de Street View de verdade (exigiria Google Maps Static API + um modelo de visão — integração nova, custo novo, esforço alto). Separar em duas versões: a "leve" (query enriquecida com endereço, já descartado hoje) é esforço **baixo** e cabe numa V2 próxima; a versão com imagem de rua é módulo futuro.
- **Monitoramento de mídia local** (termos como "atraso", "denúncia", "paralisada", "MPF" combinados com empresa + município, mirado em municípios pequenos com pouca cobertura de mídia nacional): ajuste de template de query na tool `buscar_informacao_web` já existente. Esforço **baixo**.

---

## G. Débito técnico adiado do Bloco 1

### Melhorias identificadas no Bloco 1, adiadas conscientemente pelo prazo
- **Resumo por resultado da busca web via modelo pequeno:** em vez do filtro/truncamento simples usado no V1, resumir cada resultado da Tavily individualmente (um por chamada, preservando o vínculo com a URL de origem) com um modelo pequeno/gratuito antes de devolver ao `gpt-4o-mini`. Melhora rastreabilidade e reduz tokens, mas adiciona uma segunda chamada de rede/provider dentro da tool — descartado no V1 por custo de engenharia e latência dado o prazo, documentar como trade-off no Bloco 5.
- **Estender `asyncio.gather` às demais tools nativas** (`consultar_receita_federal`, `buscar_contexto_edital`) sempre que fizerem múltiplas chamadas independentes — hoje só `consultar_sancoes_empresa` paraleliza porque é a única com duas fontes simultâneas. Documentar como decisão consciente no Bloco 5, não como pendência crítica.
- **`include_answer` da Tavily avaliado e descartado:** a API oferece um resumo sintetizado pronto, mas ele mistura informação de várias fontes sem vínculo por URL (quebra rastreabilidade) e é gerado em inglês mesmo com query em português — mantido fora do V1.

## Pendências Técnicas Conhecidas (em aberto)

| # | Descrição | Risco | Ação |
|---|---|---|---|
| 1 | `InMemorySaver` perde histórico a cada restart | Baixo (MVP) | Backlog V2: `PostgresSaver` |
| 2 | ~~`float(None)` em `dependencies.py` se env vars faltarem~~ | Resolvido | ✅ Defaults adicionados |
| 3 | ~~Cache MCP nunca expira entradas antigas~~ | Resolvido | ✅ Migrado para `cachetools.TTLCache` |
| 4 | Tavily: cota gratuita de 1.000 req/mês | Baixo | Monitorar; pay-as-you-go se necessário |
| 5 | ~~PNCP rate limits não documentados~~ | Resolvido | ✅ Cache TTL 24h mitiga; comportamento do WAF documentado em `docs/arquitetura/protocolo_mcp.md` (Bloco 5) |
| 6 | ~~`npm notice` nos logs do container~~ | Resolvido | ✅ `ENV NO_UPDATE_NOTIFIER=1` presente em `Dockerfile:8` |
| 7 | `.env.docker` não usa aspas | Baixo | Ainda sem aspas nos valores; `docs/operacional/docker.md` (Bloco 5) documenta o arquivo, mas não cobre essa convenção específica |
| 8 | ~~Subprocess MCP sem shutdown explícito~~ | Resolvido | ✅ Falso positivo — lib já fecha sessão por chamada |
| 9 | `TAMANHO_MAXIMO_CONTEUDO=2000` em `app/services/busca_web.py:12` (migrado de `filtragem_resultados_web.py` no Bloco 3) quase não trunca na prática | Baixo | Valor ainda não revisado — pendente antes da apresentação |
| 10 | ~~Cobertura de `try/except` inconsistente fora das tools nativas~~ | Resolvido | ✅ Handler global de exceção em `main.py`, try/except em torno do upsert no Pinecone em `root_upload.py` e da conexão MCP no startup em `lifespan.py`. `busca_web.py`/`consulta_receita_federal.py` mantidos sem try/except de propósito — já seguem o padrão "levanta exceção nativa, chamador em `tools.py` traduz" |
| 11 | Sem autenticação nem limite de uso: usuário pode conversar (gastar tokens da OpenAI) indefinidamente | Alto | Confirmado: nenhum middleware, `Depends` de auth ou rate limiter em `app/`. Backlog V2: rate limiting/quota/timeout de conversa — ver seção "Controle de custo e limite de uso" |
