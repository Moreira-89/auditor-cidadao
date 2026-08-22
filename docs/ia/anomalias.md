# Catálogo de Anomalias

O núcleo do conhecimento de auditoria do Auditor Cidadão é um catálogo de 9 categorias de anomalia
(A–I), definido em `app/core/prompt.py` na constante `CATALOGO_ANOMALIAS`. Esse catálogo é injetado
no `SYSTEM_PROMPT` (para o agente saber o que procurar) e no `PROMPT_EXTRATOR_INICIAL` (para
classificar cada anomalia no JSON estruturado do relatório automático, ver
[Relatório Automático e Extração do Laudo](extracao_laudo.md)) — e também no `PROMPT_EXTRATOR`, a
variante mais simples usada só pelo pipeline de avaliação. Uma constante única, reusada nos três,
para evitar divergência de texto entre eles.

!!! info "Uma constante, vários consumidores"
    O catálogo estar em um só lugar não é detalhe estético. Um dos bugs corrigidos durante a
    avaliação foi justamente o extrator ver *só* a lista de códigos válidos (`A`–`I`), sem os
    critérios de cada um — e por isso não conseguir mapear um texto de sanção para o código `H`. A
    correção foi extrair o catálogo completo (com critério por letra) para a constante única
    `CATALOGO_ANOMALIAS`, reaproveitada em todos os prompts que precisam dele.

## As 9 categorias

### A — Sobrepreço
Valor unitário de um item superior em mais de 30% à mediana de preços praticados para o mesmo
item/serviço nos últimos 12 meses. Verificação depende de um catálogo de preços de referência.

### B — Direcionamento
Especificação técnica excessivamente restritiva (marca específica, modelo único, dimensões fora de
padrão) que reduza artificialmente a competição. Sinais: "marca X ou similar superior", combinações
de requisitos que só um fornecedor conhecido atende.

### C — Fracionamento Irregular
Divisão do mesmo objeto em múltiplas contratações de menor valor para evitar a modalidade
licitatória mais rigorosa (Lei 14.133, art. 75). Verifica-se no histórico de contratações do órgão.

### D — Cartel / Conluio
Empresas "concorrentes" com sócios em comum, mesmo endereço, ou histórico de revezamento de
vitórias. Verificação depende de cruzar quadro societário e endereços das participantes.

### E — Empresa Recém-Criada
CNPJ com data de início de atividade inferior a 12 meses antes da licitação, vencendo contrato de
valor significativo. Bandeira vermelha quando combinado com objeto técnico complexo.

### F — Prazo Insuficiente
Prazo entre publicação do edital e abertura de propostas inferior ao mínimo legal (8 dias úteis para
Pregão; 10 para Concorrência de bens comuns; 25 para Concorrência de obras — Lei 14.133, art. 55).

### G — Reincidência Suspeita
Mesma empresa vencendo proporção elevada (>50%) das licitações do mesmo órgão em um período de 12
meses.

### H — Sanção Vigente (fato gravíssimo)
Empresa vencedora consta em CEIS, CNEP ou lista de inidôneos do TCU. É **proibição legal expressa**
(Lei 14.133, art. 14) e é sinalizada como RISCO CRÍTICO sempre que confirmada.

!!! warning "A Anomalia H depende de constar no cadastro, não do subtipo da penalidade"
    Qualquer registro retornado por uma consulta a CEIS ou CNEP caracteriza H — suspensão,
    impedimento, declaração de inidoneidade, multa, publicação extraordinária da decisão
    condenatória, etc. Registros acessórios (ex.: uma multa) não anulam nem diluem a caracterização
    de H trazida pelos demais registros do mesmo CNPJ. Essa regra é explicitada tanto no
    `SYSTEM_PROMPT` quanto no `PROMPT_EXTRATOR_INICIAL`, porque o modelo tendia a ignorar a
    anomalia quando os registros eram heterogêneos.

### I — Incompatibilidade de Atividade
CNAE principal da empresa não compatível com o objeto licitado (ex.: empresa cadastrada como
restaurante vencendo licitação de obra civil).

## Cobertura real hoje

Nem todas as 9 anomalias são verificáveis com as fontes atualmente integradas — e o sistema é
transparente sobre isso. Anomalias que dependem de uma base não integrada (ex.: **A**, que exige um
catálogo de preços de referência) vão para a seção "Verificações Não Concluídas" do laudo, e o
`SYSTEM_PROMPT` aplica um **score conservador** (mínimo MÉDIO) quando uma anomalia não pôde ser
verificada. Reforços e novas integrações para ampliar essa cobertura estão mapeados no roadmap (ver
[Próximos Passos](../governanca/limitacoes.md)).

| Anomalia | Fonte principal | Verificável hoje? |
|---|---|---|
| A — Sobrepreço | Catálogo de preços de referência | ❌ base não integrada |
| B — Direcionamento | Texto do edital (RAG) | ⚠️ parcial (análise textual) |
| C — Fracionamento | Histórico PNCP | ✅ |
| D — Cartel/Conluio | Quadro societário | ❌ QSA ainda não capturado |
| E — Empresa recém-criada | Receita Federal (data de fundação) | ✅ |
| F — Prazo insuficiente | Texto do edital + datas | ✅ |
| G — Reincidência | Histórico PNCP | ✅ |
| H — Sanção vigente | CEIS/CNEP | ✅ |
| I — Incompatibilidade | Receita Federal (CNAE) | ✅ |