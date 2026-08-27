# Docker & Deploy

O `Dockerfile` fica em
[`backend/`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/Dockerfile) e é o mesmo
artefato usado em desenvolvimento containerizado e em produção (Railway) — não há Dockerfile por
ambiente.

## Build da imagem

O contexto de build é a pasta `backend/`, não a raiz do repositório:

```bash
cd backend
docker build -t auditor-cidadao .
```

Pontos da imagem que valem explicação:

- **Base `python:3.12-slim`** — reduz o tamanho final eliminando ferramentas de compilação
  desnecessárias ao runtime.
- **Node.js 20 LTS instalado via NodeSource, na mesma imagem** — o agente carrega as ferramentas do
  PNCP através do MCP, que roda como subprocesso `npx @licinexusbr/mcp`. Sem essa camada o
  container sobe, mas o `lifespan` aborta ao conectar no MCP.
- **`COPY requirements.txt .` antes de `COPY . .`** — aproveita o cache de camadas: se as
  dependências não mudarem, a camada de `pip install` não é reconstruída a cada build.
- **`ENV NO_UPDATE_NOTIFIER=1`** — silencia o aviso de atualização do `npm` nos logs.
- **`CMD` com `${PORT:-8000}`** — em produção o Railway injeta `PORT`; localmente cai no padrão.

!!! info "A imagem contém só o backend"
    Com o contexto de build em `backend/`, a pasta `frontend/` fica de fora — assim como `docs/` e
    o roadmap. O container serve a API; o frontend é publicado como serviço próprio (ver abaixo).

## Rodando o container

O Redis **não** está embutido na imagem — precisa de um container separado no ar antes:

```bash
docker run -d --name redis-auditor -p 6379:6379 redis:latest
docker run -p 8000:8000 --env-file ../.env \
  --add-host=host.docker.internal:host-gateway auditor-cidadao
```

Se `REDIS_URI` apontar para `localhost`, ajuste para `host.docker.internal` (ou coloque os dois
containers na mesma rede com `docker network create`) — de dentro do container da aplicação,
`localhost` é o próprio container, não o host.

!!! warning "`--env-file` lê do host, não da imagem"
    O `.dockerignore` exclui `.env` da imagem, mas isso não afeta o `--env-file` do `docker run`:
    essa flag lê o arquivo do host na hora de subir. Ao criar variações locais (ex.: `.env.docker`),
    garanta que também estejam cobertas pelo `.dockerignore` antes de qualquer build publicável.

## Deploy em produção (Railway)

O repositório é um monorepo, e cada pasta vira um serviço no mesmo projeto do Railway, distinguidos
pelo **Root Directory**:

| Serviço | Root Directory | O que faz |
|---|---|---|
| Backend | `/backend` | Builda o `Dockerfile` e sobe a API |
| Frontend | `/frontend` | Serve os arquivos estáticos |

Ambos os serviços acompanham a mesma branch — a separação é por diretório, não por branch, o que
mantém um histórico único no Git. **Watch Paths** evita que um commit em `docs/` dispare rebuild do
backend.

As variáveis de ambiente são cadastradas no painel do Railway (mesmas chaves de
[Variáveis de ambiente](variaveis_ambiente.md)), nunca commitadas, e a plataforma injeta `PORT`
dinamicamente.

### Provisionar o Redis

Uma peça não vem pronta. Diferente do ambiente local, em produção é preciso criar o serviço:

1. No projeto do Railway: **"+ New" → "Database" → "Add Redis"**.
2. No serviço da API, defina `REDIS_URI` referenciando a variável do outro serviço em vez de colar
   a URL fixa: `REDIS_URI=${{Redis.REDIS_URL}}` (o nome `Redis` precisa bater com o nome do serviço
   no painel).

!!! danger "Sintoma de esquecer esse passo: crash-loop no boot"
    Sem `REDIS_URI`, a aplicação cai no default `redis://localhost:6379` — que dentro do container
    não tem nada escutando. O resultado é um loop de reinício a cada poucos segundos:

    ```
    redis.exceptions.ConnectionError: Error Multiple exceptions: [Errno 111] Connect call failed
    ('::1', 6379, 0, 0), [Errno 111] Connect call failed ('127.0.0.1', 6379) connecting to
    localhost:6379.
    ```

    Se aparecer isso, o Redis do projeto não existe ou `REDIS_URI` não está configurada — não é bug
    de código.

## Escalonamento: réplicas e limites de recurso

A aplicação roda com **2 réplicas** (Railway, região US East), sem multi-região, e **1 worker por
réplica** — o `CMD` não passa `--workers` ao `uvicorn`, de propósito.

- **Por que 2 réplicas:** elimina o ponto único de falha e valida em produção a premissa de que
  todo o estado vive fora da RAM local — checkpointer de conversa, contador de rate limit e cache de
  tools estão no Redis. Sem sticky sessions no Railway, qualquer uma dessas peças em memória local
  quebraria silenciosamente com múltiplas réplicas.
- **Por que 1 worker por réplica:** a carga é dominada por I/O (LLM, PNCP, Pinecone) e por rede, não
  por CPU — mais workers por processo trariam ganho marginal. Manter um eixo de escala só (réplicas)
  facilita depurar.
- **Teto de 4 vCPU / 4 GB por réplica** (Replica Limits) **+ Usage Limit no workspace** como
  proteção agregada de custo. Dado real de ~3 meses mostrou pico de 1,38 GB de RAM e CPU próxima de
  zero; 4/4 dá margem de ~3× sobre o pico e funciona como disjuntor contra anomalia (bug, loop), não
  como limite de operação normal.

!!! warning "Números calibrados com tráfego de um único usuário"
    O pico de 1,38 GB usado acima vem de ~3 meses de uso, mas **todo esse uso é do próprio autor**
    testando o sistema. Número de réplicas, tetos de recurso e Usage Limit são um ponto de partida
    seguro, não uma capacidade testada sob carga real — reavaliar depois dos primeiros dias com
    usuários simultâneos.
