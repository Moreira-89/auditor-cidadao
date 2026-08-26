# Operacional & Reprodução

Este pilar cobre a reprodução exata do ambiente do **Auditor Cidadão**: como clonar, configurar e
rodar o projeto — localmente ou via Docker — em qualquer máquina, sem depender de conhecimento
prévio sobre o código.

## Onde e como isso roda em produção

O diagrama abaixo mostra a topologia de hospedagem — quem fala com quem e onde cada peça está
implantada. Ele é sobre **infraestrutura**, não sobre o raciocínio do agente.

```mermaid
---
config:
  layout: dagre
  theme: redux-dark
  look: handDrawn
  fontFamily: '''Source Code Pro Variable'', monospace'
  themeVariables:
    fontFamily: '''Source Code Pro Variable'', monospace'
    fontSize: '28px'
---
flowchart TB
 subgraph railway["Railway — um projeto, dois serviços"]
    direction TB
        front["Serviço frontend<br>Root Directory /frontend"]
        fastapi["Serviço backend<br>FastAPI + Uvicorn (Dockerfile)"]
        mcp["Subprocesso Node.js 20<br>npx @licinexusbr/mcp"]
  end
 subgraph external["Serviços externos gerenciados"]
    direction TB
        openai["OpenAI<br>LLM + embeddings"]
        pinecone[("Pinecone<br>banco vetorial")]
        redis[("Redis<br>histórico + rate limit + cache")]
        cgu["Portal da Transparência / CGU<br>CEIS · CNEP"]
        receita["BrasilAPI<br>Receita Federal"]
        tavily["Tavily<br>busca web"]
        pncp["PNCP<br>licitações, contratos, atas"]
  end
    fastapi <-- MCP via stdio --> mcp
    browser["Navegador do usuário"] <-- HTTPS --> front
    browser <-- HTTPS --> fastapi
    fastapi --> openai & pinecone & redis & cgu & receita & tavily
    mcp --> pncp
```

Pontos que valem destaque:

- **Monorepo, dois serviços.** `backend/` e `frontend/` são publicados separadamente, distinguidos
  pelo **Root Directory** de cada serviço no Railway, ambos acompanhando a mesma branch — a
  separação é por diretório, não por branch, o que mantém um histórico único no Git. Ver
  [Docker & Deploy](docker.md#deploy-em-producao-railway).
- **Dois processos dentro do serviço de backend** — o FastAPI e o subprocesso Node.js do MCP, que o
  `lifespan` sobe no startup para carregar as 11 ferramentas do PNCP.
- **Redis é o único estado próprio da aplicação.** Não vem embutido no container: é um add-on
  gerenciado, provisionado à parte. Guarda três coisas independentes — o histórico de conversa por
  `thread_id`, a contagem do rate limiter e o cache de ferramentas (TTL 24h). É esse estado
  externalizado que viabiliza as 2 réplicas em produção, já que o Railway não oferece sticky
  sessions (ver [Docker & Deploy](docker.md#escalonamento-replicas-e-limites-de-recurso)).
- **Pinecone guarda os editais indexados**, consultados sob demanda pela tool de RAG — o conteúdo do
  edital nunca é pré-carregado no contexto do agente.
- **Variáveis de ambiente** são cadastradas diretamente no painel do Railway (mesmas chaves de
  [Variáveis de ambiente](variaveis_ambiente.md)), nunca commitadas.

## Acesse essas páginas para saber mais

- **[Setup local](setup_local.md)** — clonar o repositório, criar o ambiente virtual, instalar
  dependências e subir a aplicação com `uvicorn`.
- **[Referência de API](api.md)** — exemplos reais de request/response dos dois endpoints
  (`curl` para upload e para o streaming SSE de conversa).
- **[Docker & Deploy](docker.md)** — build e execução via container, e como o mesmo Dockerfile é
  usado em produção (Railway).
- **[Variáveis de ambiente](variaveis_ambiente.md)** — referência completa de cada chave exigida
  ou opcional, o que ela controla e onde obtê-la.
