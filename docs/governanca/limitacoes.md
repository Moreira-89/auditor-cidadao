# Limitações e Próximos Passos

Documentar honestamente o que o sistema **não** faz é parte da responsabilidade do projeto. Esta
página reúne as limitações conhecidas da entrega atual (V1) e o backlog planejado para a V2.

## O princípio fundamental: indício, não veredito

Antes de qualquer limitação técnica, a limitação de escopo mais importante é conceitual: **o Auditor
Cidadão sinaliza padrões para investigação humana — não acusa nem emite sentenças.** O laudo é um
indício que sempre recomenda checagem manual, nunca uma decisão final. Esse framing é explícito no
`SYSTEM_PROMPT` (que proíbe "laudo limpo total" e exige score conservador), na documentação e deve
ser reforçado em qualquer apresentação do produto.

## Limitações conhecidas da V1

### Cobertura parcial do catálogo de anomalias
Nem todas as 9 anomalias são verificáveis com as fontes integradas hoje — a Anomalia A (sobrepreço)
depende de um catálogo de preços ainda não integrado, e a D (cartel) depende do quadro societário
(QSA), ainda não capturado. Ver a [tabela de cobertura](../ia/anomalias.md#cobertura-real-hoje). O
sistema é transparente sobre isso: anomalias não verificáveis vão para "Verificações Não Concluídas"
e recebem score conservador.

### Retrieval limitado por `top_k=3`
Em editais grandes, o trecho relevante pode estar posicionalmente distante e fora do alcance da
busca (`context_recall = 0.60` na avaliação, ver [Avaliação](../ia/avaliacao.md)). Endereçável com
`top_k` maior ou reranking na V2.

### Rate limiting por cookie, não por identidade real
`/upload/` (5 requisições/dia) e `/conversar-com-auditor/` (50 requisições/dia) são limitados por
cliente via um cookie httpOnly assinado (`app/services/rate_limiter.py`, `app/utils/cookie_manager.py`),
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

### Uma ferramenta de PNCP implementada mas desativada
`buscar_contratos_fornecedor_pncp` está pronta mas fora do agente: a varredura de todas as
modalidades de um órgão pode levar minutos sob o rate limit do PNCP, e o streaming SSE não emite
eventos durante a execução de uma tool, arriscando timeout de proxy. Documentada como limitação
consciente em vez de arriscar quebrar o streaming.

## Backlog V2

### Escalabilidade e persistência
| Componente | V1 (atual) | V2 (alvo) |
|---|---|---|
| Histórico de conversas | `AsyncRedisSaver` (Redis) — já persistente e compartilhado entre as 2 réplicas em produção | — (resolvido) |
| Controle de custo | Rate limiting por cookie (`app/services/rate_limiter.py`), sem resistência a reset de cookie | Autenticação mínima, para que a quota resista a limpeza de cookie/aba anônima |
| Cache de ferramentas | Redis compartilhado (TTL 24h) — resolvido, ver [Protocolo MCP](../arquitetura/protocolo_mcp.md#cache-das-ferramentas-aplicar_cache) | — (resolvido) |

### Indexação automática via PNCP (Fase 7)
Eliminar o upload manual: o agente busca, baixa e indexa o PDF a partir de uma conversa
("Analise licitações de TI em SP desta semana"). Junto, o metadado do Pinecone migra de
`municipio`/`estado` para `cnpjs` extraídos automaticamente — habilitando o cruzamento
cross-município.

### Ampliação da cobertura de anomalias
Boa parte reaproveita dado que a BrasilAPI já devolve mas hoje é descartado (`capital_social`,
`cnaes_secundarios`, `qsa`, endereço completo): reforço da Anomalia E com data de fundação, da I com
CNAEs secundários, da D com quadro societário, e busca web direcionada por endereço (indício de sede
"fachada"). Integração nova prevista: catálogo de preços (Anomalia A) e dados do IBGE (contexto
fiscal do município).

### Frontend dedicado
Migração do frontend estático servido pelo FastAPI para uma stack dedicada (React), separando
frontend e backend em dois serviços — ver [Operacional](../operacional/index.md).

### Módulos futuros da plataforma
Auditor de contratos (aditivos suspeitos), monitor de fornecedores por município, alertas
automáticos, auditoria estadual e uma API pública de laudos para jornalistas e ONGs.