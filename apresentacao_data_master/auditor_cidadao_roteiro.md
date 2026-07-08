# Auditor Cidadão — Roteiro de Fala
> 24 slides · ~44 min de fala + ~15 min de perguntas ≈ 1h
> Uso em conjunto com `auditor_cidadao_slides.md` (mesma numeração e títulos)

---

## Slide 1 - Capa
**Roteiro (falar por ~1 min):**
Abertura rápida: nome do projeto, o que ele faz em uma frase, e quem está apresentando. Não se demore — a plateia quer contexto, não uma introdução longa. "Nos próximos 45 minutos vou mostrar o problema que resolvemos, como a arquitetura funciona de ponta a ponta, e os resultados reais da nossa avaliação — inclusive onde ela reprovou, porque isso faz parte do processo."

---

## Slide 2 - Agenda
**Roteiro (falar por ~1 min):**
Passe rápido pelos blocos, sem detalhar. O objetivo aqui é dar um mapa mental de 6 blocos para a banca acompanhar. Avise que perguntas podem ficar para o final, mas que você pode pausar se algo for crítico.

---

## Slide 3 - O problema
**Roteiro (falar por ~2 min):**
Conte o problema como uma história curta: um jornalista ou cidadão recebe um edital de 40 páginas e, para saber se está tudo certo, precisaria abrir seis abas diferentes, cruzar CNPJ por CNPJ, e ainda saber interpretar juridicamente o que está vendo. Isso não escala. É por isso que a fiscalização social — que devia ser uma camada de controle real sobre gasto público — praticamente não acontece na prática, principalmente em municípios pequenos.

---

## Slide 4 - A solução
**Roteiro (falar por ~2 min):**
Essa última frase do slide é importante — diga-a em voz alta, com ênfase. É a postura ética do projeto e volta a aparecer no bloco de governança. Explique o fluxo em uma frase: "o cidadão faz upload, o agente investiga sozinho, e ele recebe um laudo com evidências e nível de risco — sem precisar saber nada de auditoria pública."

---

## Slide 5 - O que a banca espera ver (requisitos do case)
**Roteiro (falar por ~2 min):**
Mostre esse slide como um "mapa de conformidade" — deixa claro que você sabe exatamente o que está sendo avaliado e onde cada requisito é respondido na apresentação. Isso tira qualquer ambiguidade da banca sobre "onde ele vai falar sobre X" e passa organização.

---

## Slide 6 - Stack e arquitetura macro
**Roteiro (falar por ~2 min):**
Visão de 30 mil pés antes de entrar em detalhe. Diga que cada uma dessas escolhas tem uma justificativa específica, que você vai detalhar peça por peça nos próximos slides — não é só "usamos X porque é popular".

---

## Slide 7 - T1: Por que `gpt-4o-mini`?
**Roteiro (falar por ~2 min):**
Frame como decisão de custo-benefício, não de limitação técnica. Seja honesto: mencione que o benchmark contra outros modelos (Sabiá, Claude, Gemini, DeepSeek-R1) está no backlog — isso mostra maturidade, não fraqueza. "Escolhemos com critério de custo-benefício para V1; comparação formal via golden dataset é próximo passo, não suposição."

---

## Slide 8 - T2: Engenharia de prompt
**Roteiro (falar por ~2 min):**
Destaque a decisão de ter uma única fonte de verdade para o catálogo de anomalias — foi o que corrigiu um bug real (conte isso rapidamente ou reserve para o slide do bug, sua escolha). O ponto pedagógico aqui: orquestração consistente não vem só do modelo, vem de como o prompt é estruturado e reusado.

---

## Slide 9 - T5: Arquitetura do agente — o grafo
**Roteiro (falar por ~3 min):**
Este é o slide de arquitetura mais técnico — vá com calma. Desenhe o ciclo verbalmente enquanto aponta o diagrama: "o usuário pergunta, o LLM decide se precisa de uma ferramenta, se precisar o `tool_node` executa e devolve o resultado, e isso se repete até o modelo ter informação suficiente para responder sem pedir mais nada." Seja transparente sobre a simplicidade proposital: hoje são só dois nós, e já existe uma expansão planejada para separar decisão, geração final e processamento determinístico em nós próprios — decisão de manutenibilidade, não limitação atual.

---

## Slide 10 - Ferramentas do agente e o protocolo MCP
**Roteiro (falar por ~2 min):**
Explique o MCP em uma frase para quem não conhece: "é um protocolo aberto que permite a um agente consumir ferramentas prontas de terceiros, como se fossem plugins." O ganho real foi de escopo — não precisamos reimplementar paginação, schemas e tratamento de erro de uma API pública inteira. O custo foi arquitetural: o container agora roda Node.js 20 além de Python, e se o `npx` falhar, o boot falha de propósito (fail-fast).

---

## Slide 11 - T3: Pipeline de dados — RAG do edital
**Roteiro (falar por ~3 min):**
Justifique RAG vs fine-tuning de forma direta: fine-tuning ensinaria um estilo, não um documento específico, e teria que ser refeito a cada edital novo — inviável. RAG ancora a resposta em texto real recuperado, o que reduz alucinação e permite responder sobre um documento que o modelo nunca viu. Seja honesto sobre o `top_k=3` e os valores de chunking: foram escolhas de boa prática de mercado, não empiricamente ajustadas neste projeto — e a avaliação (próximo bloco) mostrou que isso é uma alavanca real, não só teórica.

---

## Slide 12 - O bug de produção que a avaliação encontrou
**Roteiro (falar por ~2 min):**
Este é o slide de maior impacto de storytelling da apresentação — não tenha pressa nele. Conte como uma investigação de instabilidade de métrica no framework de avaliação (não um teste manual) revelou um defeito que afetava usuários reais em produção. É a resposta direta para "como a avaliação ajudou a encontrar problemas reais, não só medir números" — cite isso explicitamente se a banca perguntar sobre T4.

---

## Slide 13 - Catálogo de anomalias (A–I)
**Roteiro (falar por ~2 min):**
Não leia as 9 categorias uma a uma — cite 2 ou 3 exemplos concretos (sobrepreço, direcionamento, sanção vigente) e diga que o catálogo completo está na documentação. O ponto técnico a reforçar: ter uma única fonte de verdade para os critérios evitou divergência entre o que o agente investiga e o que o extrator classifica — foi exatamente a ausência dessa unificação que causou um dos bugs encontrados na avaliação.

---

## Slide 14 - Cobertura real hoje
**Roteiro (falar por ~1 min):**
Transparência rápida: nem tudo que o catálogo promete está 100% coberto hoje, e isso é intencional e documentado — o sistema nunca declara um edital totalmente limpo, porque sempre existe algo fora do alcance das fontes atuais.

---

## Slide 15 - Guardrails de segurança
**Roteiro (falar por ~2 min):**
Este slide responde a uma pergunta óbvia da banca: "um edital malicioso poderia manipular o agente?" A resposta é sim, se não houvesse esses guardrails — e o projeto trata isso com camadas: escape de todos os campos do cliente (não só o "óbvio"), isolamento estrutural via tags, e uma regra anti-alucinação bem específica descoberta em teste real de log, não teórica.

---

## Slide 16 - T4: Metodologia de avaliação
**Roteiro (falar por ~2 min):**
Justifique o desvio do plano original (um único LLM-juiz caseiro) para RAGAS + comparação determinística: foi decisão consciente de engenharia — determinístico é mais confiável que julgamento subjetivo quando dá para medir sem LLM, e RAGAS é uma biblioteca validada pela comunidade em vez de reinventar a métrica. Isso responde bem a "por que a implementação diverge do plano original?"

---

## Slide 17 - T4: Resultados da avaliação
**Roteiro (falar por ~3 min):**
Este é o slide mais importante da apresentação em termos de credibilidade técnica — não esconda o resultado reprovado, apresente-o com confiança. Explique a causa raiz do `context_recall` baixo: de 5 casos elegíveis, 2 têm o trecho-alvo posicionalmente distante no documento, fora do alcance de `top_k=3` mesmo testando até `top_k=50` — é limitação real de recuperação, endereçável com `top_k` maior ou reranking, já mapeada como próximo passo. Sobre `faithfulness`: oscila em torno do próprio limiar, hipótese não confirmada de que a `temperature=0.1` do agente (mesma configuração de produção) introduz variância — testável isolando a temperatura só na avaliação. Feche com a frase: "o framework existe para expor limitações, não para maquiar números — e foi isso que ele fez."

---

## Slide 18 - Streaming e extração estruturada
**Roteiro (falar por ~1 min):**
Rápido, mas mostra atenção a detalhe: se o laudo fosse acumulado direto no stream, texto de raciocínio intermediário do agente contaminaria o resultado final, porque o modelo pode emitir conteúdo parcial antes de o `tool_calls` daquele turno aparecer completo no chunk. O buffer resolve isso sem sacrificar a experiência em tempo real.

---

## Slide 19 - T5: Infraestrutura e deploy
**Roteiro (falar por ~2 min):**
Reforce reprodutibilidade (R1/R2/R3 do case): qualquer pessoa builda a mesma imagem localmente ou usa o Railway, sem configuração divergente. Seja direto sobre a limitação do `InMemorySaver` — é decisão consciente de simplicidade para o estágio atual, com migração para `PostgresSaver` já mapeada, e não afeta o único estado que realmente precisa persistir (o Pinecone, que é gerenciado externamente).

---

## Slide 20 - T6: Ética, LGPD e responsabilidade
**Roteiro (falar por ~2 min):**
Esse é o requisito T6 do case — trate como bloco próprio, não como rodapé. Deixe claro o princípio central do projeto, repita a frase do slide 4: "o sistema sinaliza padrões, não substitui uma auditoria formal." Sobre a retenção de editais: explique que é uma escolha deliberada e documentada, pensada para viabilizar cruzamento histórico numa V2 — não um descuido de privacidade, já que o dado em questão é público por natureza (edital municipal).

---

## Slide 21 - Decisões e trade-offs (resumo)
**Roteiro (falar por ~2 min):**
Consolide em um slide só as decisões já explicadas ao longo da apresentação — a banca valoriza ver que trade-off foi tratado como decisão de engenharia, não acidente. Não reexplique cada um em detalhe, só aponte e diga "já vimos o porquê de cada um".

---

## Slide 22 - Limitações conhecidas e próximos passos
**Roteiro (falar por ~2 min):**
Feche com uma leitura de maturidade: o projeto tem um roadmap real, não uma lista vaga de "melhorias futuras" — cada item nasceu de uma limitação identificada e documentada ao longo do próprio desenvolvimento e da avaliação, não de brainstorm solto.

---

## Slide 23 - Conclusão
**Roteiro (falar por ~1 min):**
Fechamento curto e direto. Não repita tudo — resuma em uma frase o valor entregue e abra para perguntas. "Entrego uma ferramenta que já funciona hoje, sei exatamente onde ela ainda falha, e tenho um plano concreto para cada uma dessas falhas."

---

## Slide 24 - Perguntas
**Roteiro (~15 min de perguntas):**
Abra o espaço e deixe a banca conduzir. Pontos que você já preparou respostas fortes para, caso perguntem: por que `gpt-4o-mini` e não outro modelo; por que `context_recall` reprovou e o que fazer a respeito; como os guardrails de segurança se comportam contra um edital malicioso; e por que a métrica de avaliação diverge do plano original do roadmap.

---

## Notas finais (não fazem parte do roteiro em si)
- **24 slides** é o número pensado para 1h — dá ~1,8 min médio por slide de conteúdo, com folga real para os slides mais técnicos (9, 12, 17) e ~15 min reservados para perguntas.
- O slide 17 (resultados da avaliação) é o que mais separa esse projeto de uma apresentação genérica — não tenha pressa nele.
- Revise comigo depois: posso ajustar tempos, cortar slides se sobrar tempo de fala, ou aprofundar algum bloco técnico específico antes de virar `.pptx`.
