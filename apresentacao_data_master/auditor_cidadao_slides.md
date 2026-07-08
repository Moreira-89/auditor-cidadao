## Slide 1 - Capa
**Conteúdo do Slide:**
- Auditor Cidadão
- IA Generativa para auditoria de licitações públicas municipais
- Lucas M. A. Rodrigues · Data Master — Engenheiro de IA

**Sugestão visual:** print da tela inicial da plataforma publicada (`frontend/index.html` — hero da landing page).

---

## Slide 2 - Agenda
**Conteúdo do Slide:**
- O problema e a solução
- Arquitetura: agente, RAG, ferramentas
- Engenharia de prompt e segurança
- Avaliação de desempenho (com números reais)
- Ética, LGPD e limitações
- Próximos passos

**Sugestão visual:** nenhuma — slide de texto puro, mantenha limpo.

---

## Slide 3 - O problema
**Conteúdo do Slide:**
- Fiscalizar uma licitação municipal exige cruzar o edital com PNCP, Receita Federal e CEIS/CNEP manualmente
- Trabalho lento, técnico, fora do alcance da maioria dos cidadãos e jornalistas
- Resultado: a maior parte das licitações municipais no Brasil nunca é auditada por ninguém fora do próprio órgão

**Sugestão visual:** diagrama simples (pode usar aqueles que estão em /docs) com um edital no centro e setas para as fontes que precisariam ser consultadas manualmente hoje: PNCP, Receita Federal, CEIS/CNEP.

---

## Slide 4 - A solução
**Conteúdo do Slide:**
- Upload do edital/contrato em PDF → indexação automática (RAG)
- Um agente de IA decide sozinho quais fontes oficiais consultar
- Varre 9 categorias de anomalias e entrega um laudo estruturado, em streaming
- **O sistema sinaliza padrões para investigação humana — não substitui uma auditoria formal**

**Sugestão visual:** print dos 3 cards "feature-step" do `frontend/index.html` (01 Upload → 02 O agente investiga → 03 Receba o laudo) — já existem prontos na landing page.

---

## Slide 5 - O que a banca espera ver (requisitos do case)
**Conteúdo do Slide:**
| # | Requisito | Onde tratamos |
|---|---|---|
| T1 | Modelo de IA | Bloco 2 |
| T2 | Prompts + orquestração | Bloco 2/3 |
| T3 | Uso de dados (RAG) | Bloco 3 |
| T4 | Estratégia de modelo + avaliação | Bloco 4 |
| T5 | Arquitetura com agentes | Bloco 2/5 |
| T6 | Ética, privacidade, responsabilidade | Bloco 5 |

**Sugestão visual:** nenhuma — a tabela já é o conteúdo visual do slide.

---

## Slide 6 - Stack e arquitetura macro
**Conteúdo do Slide:**
- Backend: FastAPI + LangGraph (orquestração do agente)
- LLM: OpenAI `gpt-4o-mini` · Embeddings: `text-embedding-3-small`
- Banco vetorial: Pinecone · Ferramentas externas via MCP (PNCP)
- Deploy: um único container Docker no Railway

**Sugestão visual:** diagrama Mermaid de topologia de infraestrutura, já pronto em `docs/operacional/index.md` (Railway → FastAPI+MCP → OpenAI/Pinecone/CGU/BrasilAPI/Tavily/PNCP). Exporte o Mermaid como imagem.

---

## Slide 7 - T1: Por que `gpt-4o-mini`?
**Conteúdo do Slide:**
- Papel do agente: orquestrar ferramentas e redigir laudo — não exige raciocínio de fronteira
- Chamado a cada turno de cada usuário → custo importa
- Contexto de 128k tokens, suficiente para múltiplos resultados de tool por turno
- `gpt-4o` (mais caro) reservado só para o juiz da avaliação, nunca em produção

**Sugestão visual:** tabela simples com os 4 modelos usados no projeto e seus papéis (agente, extrator, embeddings, juiz RAGAS) — está em `docs/ia/modelos_prompts.md`, dá pra recriar como tabela no slide.

---

## Slide 8 - T2: Engenharia de prompt
**Conteúdo do Slide:**
- `SYSTEM_PROMPT`: identidade do agente + catálogo de anomalias + regras de segurança
- Catálogo de anomalias é **uma única constante**, reusada no prompt do agente e no prompt do extrator
- Regra dura: "nunca invente dados" — campo não verificado vira "não verificável", nunca suposição
- Hierarquia de evidências: dado oficial de API > texto do edital > busca web > inferência própria

**Sugestão visual:** print de um trecho curto do `app/core/prompt.py` (a constante `CATALOGO_ANOMALIAS` ou a regra de "vocabulário emprestado") — mostra código real, reforça credibilidade técnica sem precisar ler o arquivo inteiro.

---

## Slide 9 - T5: Arquitetura do agente — o grafo
**Conteúdo do Slide:**
- `StateGraph` (LangGraph): dois nós, `call_llm` e `tool_node`
- Um `router` decide o próximo passo checando se a última mensagem tem `tool_calls` pendentes
- `InMemorySaver` mantém histórico por `thread_id` (conversas com múltiplos turnos)
- Ciclo ReAct: LLM decide → ferramenta executa → resultado volta ao LLM → repete até responder

**Sugestão visual:** diagrama Mermaid do ciclo do agente, já pronto em `docs/arquitetura/visao_geral.md` (`ENTRADA → call_llm → router → tool_node/fim`). Este é provavelmente o diagrama mais importante da apresentação — capriche na exportação (boa resolução).

---

## Slide 10 - Ferramentas do agente e o protocolo MCP
**Conteúdo do Slide:**
- 4 ferramentas nativas: Receita Federal, RAG do edital, sanções (CEIS/CNEP), busca web
- 11 ferramentas de PNCP consumidas via **MCP** (`@licinexusbr/mcp`) — zero linha de integração própria com o PNCP
- Trade-off: reuso de 11 ferramentas validadas × dependência de subprocesso Node.js em produção
- Cache TTL de 24h (`cachetools.TTLCache`) sobre todas as tools, nativas e MCP

**Sugestão visual:** diagrama Mermaid do carregamento das tools MCP no startup, já pronto em `docs/arquitetura/protocolo_mcp.md` (Startup → NPX → MultiServerMCPClient → filtro whitelist → patch → cache → merge → grafo).

---

## Slide 11 - T3: Pipeline de dados — RAG do edital
**Conteúdo do Slide:**
- Upload do PDF → extração de texto (`pdfplumber`) → chunking → embeddings → Pinecone
- Chunks de 2000 caracteres, overlap de 200, separadores hierárquicos (parágrafo → linha → frase)
- Busca semântica filtrada por `estado` + `município`, `top_k=3`
- RAG em vez de fine-tuning: editais mudam a cada upload, não existem no treino de nenhum modelo

**Sugestão visual:** diagrama Mermaid de ingestão do edital, já pronto em `docs/arquitetura/fluxo_dados.md` (Upload → pdfplumber → chunking → embeddings → Pinecone → extração de CNPJs).

---

## Slide 12 - O bug de produção que a avaliação encontrou
**Conteúdo do Slide:**
- `[metadados] * len(chunks)` cria N referências ao **mesmo** dicionário, não N cópias
- Resultado: todo chunk indexado — de qualquer edital, inclusive de usuários reais — era salvo com o texto do **último** chunk do documento
- Os embeddings continuavam corretos → o bug ficava mascarado atrás de scores de similaridade plausíveis
- Corrigido com `[dict(metadados) for _ in chunks]`; banco de produção já estava limpo

**Sugestão visual:** print do diff/trecho de código do `app/services/gerenciadorvetorial.py` mostrando a linha errada (`[metadados] * len(lista_chunks)`) ao lado da corrigida (`[dict(metadados) for _ in lista_chunks]`) — contraste visual direto ajuda a plateia a entender o bug em segundos, mesmo sem saber Python a fundo.

---

## Slide 13 - Catálogo de anomalias (A–I)
**Conteúdo do Slide:**
- 9 categorias: Sobrepreço, Direcionamento, Fracionamento, Cartel/Conluio, Empresa recém-criada, Prazo insuficiente, Reincidência, Sanção vigente, Incompatibilidade de atividade
- Anomalia H (sanção vigente) é a mais crítica: proibição legal expressa (Lei 14.133, art. 14)
- Uma constante única (`CATALOGO_ANOMALIAS`) alimenta tanto o agente quanto o extrator de JSON

**Sugestão visual:** print dos cards de anomalia da seção `#anomalias` do `frontend/index.html` (cards A–I com `anomalia-letra`, `anomalia-titulo`, `anomalia-criterio`) — já existe pronto e com bom design, aproveite em vez de recriar uma tabela.

---

## Slide 14 - Cobertura real hoje
**Conteúdo do Slide:**
- 6 das 9 anomalias são verificáveis hoje com as fontes integradas (C, E, F, G, H, I)
- Sobrepreço (A) e Cartel/Conluio (D) dependem de bases ainda não integradas
- Quando uma anomalia não pode ser verificada, o score mínimo aplicado é **MÉDIO** — nunca "limpo"

**Sugestão visual:** tabela de cobertura já pronta em `docs/ia/anomalias.md` (coluna Anomalia / Fonte principal / Verificável hoje) — reaproveite direto, já está no formato certo para um slide.

---

## Slide 15 - Guardrails de segurança
**Conteúdo do Slide:**
- **Anti-injeção de prompt:** todo campo do usuário passa por `escape_xml()`, não só a pergunta
- Conteúdo entre tags (`<DOCUMENTO>`, `<METADADOS>`) é tratado como dado bruto, nunca instrução
- Tentativa de manipulação no documento vira **achado de auditoria**, não é obedecida
- **Anti-alucinação:** proibição de "vocabulário emprestado" — nenhum campo pode ser inferido de uma tool que não foi chamada naquele turno

**Sugestão visual:** nenhum print necessário — se quiser reforçar visualmente, um ícone simples de "escudo" ao lado de cada guardrail (anti-injeção / anti-alucinação) já comunica bem.

---

## Slide 16 - T4: Metodologia de avaliação
**Conteúdo do Slide:**
- Golden dataset: 11 casos reais + sintéticos (sanção ativa, prazo irregular, caso controle, caso conversacional)
- 3 famílias de métrica independentes:
  - `aderencia_tools` — comparação determinística, sem LLM
  - `recall_anomalias` — reusa o extrator de produção sobre o laudo gerado
  - RAGAS (`faithfulness`, `context_recall`) — juiz `gpt-4o`, mede alucinação e cobertura de contexto

**Sugestão visual:** tabela das 3 métricas já pronta em `docs/ia/avaliacao.md` (Métrica / Como é medida / Usa LLM?) — reaproveite direto.

---

## Slide 17 - T4: Resultados da avaliação
**Conteúdo do Slide:**
| Métrica | Limiar | Resultado | Veredito |
|---|---|---|---|
| `aderencia_tools` | ≥ 0.70 | **1.00** estável | ✅ |
| `recall_anomalias` | ≥ 0.80 | **1.00** estável | ✅ |
| `faithfulness` | ≥ 0.85 | 0.79–0.88 oscilante | ⚠️ |
| `context_recall` | ≥ 0.75 | **0.60** estável | ❌ |
- Veredito geral: **reprovado**, por causa isolada de `context_recall`

**Sugestão visual:** a tabela em si já é o visual principal — considere um gráfico de barras simples (métrica × limiar × resultado) para reforçar visualmente onde passou e onde reprovou. Pode ser feito direto no PowerPoint/Excel a partir dos números acima.

---

## Slide 18 - Streaming e extração estruturada
**Conteúdo do Slide:**
- Resposta via Server-Sent Events: tokens em tempo real + status de ferramenta em execução
- **Buffer-then-commit**: texto só entra no laudo final quando confirmado que a mensagem do LLM não pediu mais ferramenta
- Segunda chamada ao LLM (temperatura 0) converte o Markdown final em JSON estruturado para o frontend

**Sugestão visual:** print/gif do chat da plataforma em funcionamento (streaming de tokens acontecendo em tempo real) — se der para gravar uma tela curta antes da apresentação, é mais forte que qualquer diagrama aqui.

---

## Slide 19 - T5: Infraestrutura e deploy
**Conteúdo do Slide:**
- Um único container Docker (Python 3.12 + Node.js 20) publicado no Railway
- Mesmo Dockerfile em dev local e produção — zero divergência de ambiente
- FastAPI serve frontend estático e API na mesma porta
- Limitação conhecida: histórico de conversa em memória (`InMemorySaver`) — se perde a cada restart

**Sugestão visual:** o mesmo diagrama Mermaid de topologia do Slide 6 (`docs/operacional/index.md`) pode ser reaproveitado aqui, ou dividido: use uma versão simplificada no Slide 6 e a versão completa (com os 6 serviços externos) aqui.

---

## Slide 20 - T6: Ética, LGPD e responsabilidade
**Conteúdo do Slide:**
- Dados tratados: apenas informação pública (CNPJ, editais, bases governamentais)
- Nome do usuário não é mais coletado — reduz superfície de dado pessoal
- O laudo é um **indício para investigação humana**, nunca uma acusação ou decisão final
- Retenção indefinida de editais no Pinecone é decisão deliberada (sem dado pessoal sensível envolvido)

**Sugestão visual:** nenhum print necessário — slide de texto/princípios, mantenha limpo e direto para dar peso à mensagem.

---

## Slide 21 - Decisões e trade-offs (resumo)
**Conteúdo do Slide:**
- RAG vs fine-tuning → RAG venceu por não exigir retrain a cada edital novo
- MCP vs integração própria com PNCP → reuso de 11 tools validadas, custo de dependência Node.js
- RAGAS + determinístico vs LLM-juiz único → mais confiável para métricas que não exigem julgamento subjetivo
- Buffer-then-commit vs heurística por regex → delega a decisão "isso é um laudo?" ao próprio LLM extrator, não a um padrão de texto frágil

**Sugestão visual:** nenhuma — slide de recapitulação, pode ser só as 4 linhas em formato de tabela "Decisão / Trade-off aceito".

---

## Slide 22 - Limitações conhecidas e próximos passos
**Conteúdo do Slide:**
- `context_recall` abaixo do limiar → aumentar `top_k` ou reranking
- Histórico de conversa em memória → migrar para `PostgresSaver`
- Indexação hoje é manual → Fase 7: indexação automática via busca no PNCP
- Expansão do golden dataset para 30+ casos cobrindo as 9 categorias
- Backlog de módulos futuros: Auditor de Contratos, Monitor de Fornecedores, Alertas Automáticos, API pública

**Sugestão visual:** tabela de "Módulos futuros" já pronta no roadmap (Módulo / Descrição) — reaproveite direto se sobrar espaço no slide.

---

## Slide 23 - Conclusão
**Conteúdo do Slide:**
- Solução funcional, reproduzível e documentada, ponta a ponta
- Arquitetura de agente com ferramentas, RAG e guardrails de segurança
- Avaliação real, com resultados honestos — inclusive onde reprovou
- Próximo passo natural: fechar os gaps de `context_recall` e ampliar cobertura de anomalias

**Sugestão visual:** nenhuma — feche em texto limpo, sem poluir a última mensagem.

---

## Slide 24 - Perguntas
**Conteúdo do Slide:**
- Obrigado!
- Link da plataforma publicada
- Repositório / documentação

**Sugestão visual:** QR code para a plataforma publicada (`https://auditor-cidadao-production.up.railway.app/`) e para o repositório — facilita quem quiser testar durante as perguntas.
