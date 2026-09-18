# Limitações e Próximos Passos

Documentar honestamente o que o sistema **não** faz é parte da responsabilidade do projeto. Esta
página reúne as limitações conhecidas da entrega atual (V1) e o backlog planejado para a V2.

## O princípio fundamental: indício, não veredito

Antes de qualquer limitação técnica, a limitação de escopo mais importante é conceitual: **o Auditor
Cidadão sinaliza padrões para investigação humana — não acusa nem emite sentenças.** O laudo é um
indício que sempre recomenda checagem manual, nunca uma decisão final. Esse framing é explícito no
`SYSTEM_PROMPT` — que proíbe declarar o edital "em conformidade com a lei" e exige score
conservador sem piso fixo quando uma verificação não pôde ser concluída (ver
[Guardrails](guardrails.md#distincao-entre-nao-verificado-e-sem-irregularidade)) —, na documentação
e deve ser reforçado em qualquer apresentação do produto.

## Limitações conhecidas da V1

### Cobertura parcial do catálogo de anomalias
Nem todas as 9 anomalias são verificáveis com as fontes integradas hoje — a Anomalia A (sobrepreço)
depende de um catálogo de preços ainda não integrado, e a D (cartel) depende do quadro societário
(QSA), ainda não capturado. Ver a [tabela de cobertura](../ia/anomalias.md#cobertura-real-hoje). O
sistema é transparente sobre isso: anomalias não verificáveis vão para "Verificações Não Concluídas"
e recebem score conservador.

### Rate limiting por cookie, não por identidade real
`/upload/` (5 requisições/dia) e `/conversar-com-auditor/` (50 requisições/dia) são limitados por
cliente via um cookie httpOnly assinado ([`app/api/rate_limiter.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/rate_limiter.py), [`app/api/cookies.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/cookies.py)),
não por conta de usuário — o projeto não tem autenticação. Isso resolve manipulação (o usuário não
edita o valor via DevTools, já que é assinado com uma chave secreta do servidor), mas resolve só
metade do problema de custo: **não impede reset**. Limpar cookies, aba anônima ou trocar de
navegador geram um `client_id` novo e, portanto, uma quota nova. Aceitável para o escopo atual (não
protege contra um atacante sofisticado, só eleva o custo do abuso casual) — autenticação mínima
(mesmo que só um token de acesso) é o pré-requisito para um limite que resista a esse reset,
planejado para a V2.

### Sem autenticação de usuário
Não há login nem conta de usuário — qualquer visitante pode usar a aplicação livremente, dentro dos
limites de taxa acima. Autenticação mínima está no backlog V2, tanto como valor em si quanto como
pré-requisito para o rate limiting acima resistir ao reset de cookie.

### Dependência de APIs externas
O sistema depende de BrasilAPI, Portal da Transparência, PNCP e Tavily. Falhas isoladas são tratadas
(cada fonte retorna erro estruturado, sem derrubar o turno), mas a qualidade da auditoria degrada
quando uma fonte está indisponível. O PNCP em especial tem rate limit agressivo, mitigado por cache
de 24h — ver [Protocolo MCP](../arquitetura/protocolo_mcp.md).

## Backlog V2

### Escalabilidade e persistência
| Componente | V1 (atual) | V2 (alvo) |
|---|---|---|
| Histórico de conversas | `AsyncRedisSaver` (Redis) — já persistente e compartilhado entre as 2 réplicas em produção | — (resolvido) |
| Controle de custo | Rate limiting por cookie ([`app/api/rate_limiter.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/rate_limiter.py)), sem resistência a reset de cookie | Autenticação mínima, para que a quota resista a limpeza de cookie/aba anônima |
| Cache de ferramentas | Redis compartilhado (TTL 24h) — resolvido, ver [Protocolo MCP](../arquitetura/protocolo_mcp.md#cache-das-ferramentas-aplicar_cache) | — (resolvido) |
| Infraestrutura de hospedagem | Railway (serviços gerenciados, sem GPU dedicada) | Avaliar migração para uma nuvem maior (AWS, Azure ou GCP) — ferramental de engenharia de IA mais maduro e a opção de hospedar GPU dedicada no mesmo provedor, se o projeto precisar rodar modelo próprio no futuro |

O Railway resolveu bem a V1 (deploy simples, sem gerenciar infraestrutura), mas escala menos que um
provedor de nuvem completo. A ideia para V2 é migrar para AWS, Azure ou GCP — com preferência por
GCP, tanto por familiaridade prévia quanto pela oferta de hospedagem rápida de aplicação e, no
mesmo provedor, GPU dedicada — útil caso o projeto passe a rodar algum modelo próprio em vez de
depender só de APIs de terceiros.

### Indexação automática via PNCP (Fase 7)
Eliminar o upload manual: o agente busca, baixa e indexa o PDF a partir de uma conversa
("Analise licitações de TI em SP desta semana"). Junto, os campos do chunk migram de
`municipio`/`estado` para `cnpjs` extraídos automaticamente — habilitando o cruzamento
cross-município.

### Controle de contexto
A V1 não aplica nenhum controle ou limite de contexto — o objetivo desta entrega é validar a ideia,
não otimizar custo de token ainda. Ideia em estudo para uma próxima versão: sumarização de contexto
via um modelo auxiliar (menor/mais barato) antes de repassar ao modelo principal, em vez de mandar o
texto recuperado (ver [padrão pai-filho](../ia/rag_dados.md#padrao-pai-filho-descartado-uma-vez-reintroduzido-depois))
integralmente a cada chamada. Complementa o item já registrado em
[Uso de Dados e RAG](../ia/rag_dados.md#limitacoes-conhecidas-do-retrieval) sobre gerenciamento de
contexto mais sofisticado.

### Tokenização real no fatiamento de chunks
O corte de parágrafo longo antes do embedding (`_fatiar_filhos`, `app/storage/vetorial.py`) hoje usa
`str.split()` por espaço em branco — um limite de "200 palavras", não de tokens de verdade. Como
nenhum tokenizador (`tiktoken`, o mesmo que o `text-embedding-3-small` usa por baixo) entra nessa
conta, o número real de tokens por chunk varia com o texto — termos técnicos/jurídicos longos podem
gerar bem mais tokens do que o esperado pelo corte por palavra. Trocar por contagem real de tokens
via `tiktoken` é candidato de próxima versão; complementa o item de "texto cru, sem o caminho da
seção" já registrado em [Uso de Dados e RAG](../ia/rag_dados.md#limitacoes-conhecidas-do-retrieval).

### Reescrever `RecallAnomaliasMetric` como G-Eval
Hoje a métrica é regex determinístico sobre o Markdown do laudo — rápido e sem custo de LLM, mas
frágil a variação de formato (foi a causa de uma reprovação intermitente contornada apertando o
prompt em vez de tornar a métrica mais tolerante, ver [Avaliação](../ia/avaliacao.md)). Uma versão
G-Eval extrairia os achados por julgamento semântico em vez de padrão fixo — mais robusta a
parafraseio, ao custo de uma chamada de LLM a mais por caso e da mesma variância entre rodadas que
já motivou trocar RAGAS por G-Eval na métrica de Fidelidade.

### Ampliação da cobertura de anomalias
Boa parte reaproveita dado que a BrasilAPI já devolve mas hoje é descartado (`capital_social`,
`cnaes_secundarios`, `qsa`, endereço completo): reforço da Anomalia E com data de fundação, da I com
CNAEs secundários, da D com quadro societário, e busca web direcionada por endereço (indício de sede
"fachada"). Integração nova prevista: catálogo de preços (Anomalia A) e dados do IBGE (contexto
fiscal do município).

### Revisão periódica do catálogo de anomalias
O catálogo atual (9 categorias, A–I) foi construído a partir de pesquisa de campo — reportagens,
casos documentados por órgãos de controle e padrões da literatura sobre fraude em compras públicas
— não de uma lista oficial fechada (ver [de onde veio esse catálogo](../ia/anomalias.md#de-onde-veio-esse-catalogo)).
Fica como item recorrente de V2 revisitar essa pesquisa periodicamente, verificando se surgiram
novos padrões de irregularidade que mereçam virar uma 10ª categoria (ou mais), em vez de tratar o
catálogo como definitivo.

### Observabilidade e avaliação contínua em produção
Hoje a avaliação (golden dataset + G-Eval, ver [Avaliação](../ia/avaliacao.md)) só roda sob demanda,
manualmente, quando alguém decide validar uma mudança antes de subir pra produção — não há nada que
rode o mesmo tipo de checagem contra o tráfego real depois que o sistema já está no ar. Ideia em
estudo para uma próxima versão: um sistema (próprio ou uma ferramenta de observabilidade de LLM já
existente no mercado) que centralize, num único lugar, consumo de tokens por conversa, volume de
requisições por ferramenta/fonte externa, logs do agente e — o ponto mais importante — a capacidade
de rodar avaliação de qualidade continuamente contra o modelo **em produção**, não só contra o
golden dataset local. Ainda não há desenho de arquitetura definido; fica registrado aqui como
direção, não como especificação.

### Frontend dedicado
Migração do frontend estático servido pelo FastAPI para uma stack dedicada (React), separando
frontend e backend em dois serviços — ver [Operacional](../operacional/index.md).

### Módulos futuros da plataforma
Auditor de contratos (aditivos suspeitos), monitor de fornecedores por município, alertas
automáticos, auditoria estadual e uma API pública de laudos para jornalistas e ONGs.