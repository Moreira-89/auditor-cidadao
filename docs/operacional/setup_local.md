# Setup local

!!! tip "Prefere não instalar nada?"
    A forma mais rápida de conhecer o Auditor Cidadão é pela instância publicada:
    **[Plataforma Auditor Cidadão](https://auditorcidadao.up.railway.app/)**. O setup
    abaixo é para quem quer inspecionar o código ou contribuir.

Passo a passo para rodar na sua máquina, sem Docker. Para o caminho containerizado, veja
[Docker & Deploy](docker.md).

## Estrutura do repositório

O repositório é um monorepo com duas partes independentes, cada uma publicada como um serviço
próprio:

```
auditor-cidadao/
├── backend/          # FastAPI + agente — é aqui que os comandos abaixo rodam
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── app/
├── frontend/         # HTML/CSS/JS servido como estático
├── docs/             # esta documentação (MkDocs)
└── mkdocs.yml
```

## Pré-requisitos

| Ferramenta | Versão | Por quê |
|---|---|---|
| Python | 3.12+ | Runtime da aplicação FastAPI |
| Node.js | 20 LTS | (1) o agente carrega 11 ferramentas do PNCP via MCP (`npx @licinexusbr/mcp`) — **sem Node.js, o boot falha ao conectar no MCP**; (2) o frontend é um app Vite separado (`npm run dev`) |
| Redis | — | Histórico de conversa, rate limiter e cache de ferramentas — **sem um Redis acessível, o boot falha**. Ver o passo 4.1 |
| MongoDB Atlas | — | Guarda e busca os chunks do edital (RAG). O `lifespan` faz `ping` no boot — **sem `MONGODB_URI` válida, o boot falha**. **Precisa ser um cluster Atlas** (tier gratuito M0 serve) — Vector Search não existe em Mongo self-hosted/local, então um container Docker de Mongo não funciona aqui. Ver o passo 4.1 |
| Chaves de API | — | OpenAI é obrigatória; CGU e Tavily são exigidas pelas tools de sanções e busca web. Ver [Variáveis de ambiente](variaveis_ambiente.md) |

## 1. Clonar o repositório

```bash
git clone https://github.com/Moreira-89/auditor-cidadao
cd auditor-cidadao
```

## 2. Criar e ativar o ambiente virtual

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

## 3. Instalar dependências

```bash
pip install -r backend/requirements.txt
```

Um arquivo único: runtime da API, MkDocs (esta documentação), testes (`pytest`) e a
avaliação (`deepeval`) — tudo na mesma imagem/ambiente.

## 4. Configurar variáveis de ambiente

```bash
cd backend
cp .env.example .env
```

Preencha o `.env` em `backend/` com suas chaves. Todos os campos estão documentados em
[Variáveis de ambiente](variaveis_ambiente.md); os obrigatórios para o boot são `OPENAI_API_KEY`,
`MONGODB_URI` e um `REDIS_URI` apontando para um Redis de verdade.

Em desenvolvimento local, confira que **`AMBIENTE_PRODUCAO=False`**:

- o cookie de sessão sai sem a flag `Secure`, senão o navegador nunca o reenvia em `http://localhost`
  e o rate limiter deixa de reconhecer o mesmo cliente entre requisições (sem erro nenhum);
- o backend libera automaticamente o CORS de `http://localhost:5173` (o Vite do frontend). Não
  precisa mexer em `CORS_ORIGINS` em dev — sem CORS liberado, o frontend recebe `Failed to fetch`
  mesmo com o backend processando o request normalmente.

!!! warning "Nunca versione o `.env` real"
    Ele já está no `.gitignore`. Só o `.env.example`, sem chaves reais, vai para o Git.

### 4.1. Subir Redis local e criar o cluster MongoDB Atlas

Redis pode rodar em Docker:

```bash
docker run -d --name redis-auditor -p 6379:6379 redis:latest
```

Fica em `redis://localhost:6379` (já é o default de `REDIS_URI`).

**MongoDB não roda em Docker local aqui** — o RAG usa `$vectorSearch` (Atlas Search), recurso que
só existe em cluster **Atlas**, não num `mongo:latest` self-hosted. Crie um cluster gratuito (tier
M0) em [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas), copie a connection string
(`mongodb+srv://…`) para `MONGODB_URI` no `.env`, e crie o índice vetorial na coleção
`chunks_edital` (banco `auditor_cidadao`) — ver o schema e a definição do índice em
[Uso de Dados e RAG](../ia/rag_dados.md).

!!! tip "Uma UI para inspecionar o Redis"
    A imagem `redis:latest` não tem interface. Para ver as chaves (`quota_upload:*`, `mcp_cache:*`,
    os checkpoints do LangGraph), TTLs e rodar comandos, troque pela `redis-stack`, que embute o
    **RedisInsight** (UI web) no mesmo container:

    ```bash
    docker rm -f redis-auditor
    docker run -d --name redis-auditor -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
    ```

    Redis continua em `6379` (o `REDIS_URI` não muda); a UI fica em `http://localhost:8001`. Se a
    `8001` bater com o `mkdocs serve`, remapeie (`-p 8002:8001`). Sem UI, o CLI direto:
    `docker exec -it redis-auditor redis-cli` (depois `KEYS *`, `TTL <chave>`, `MONITOR`).

## 5. Subir o backend

Os comandos rodam **de dentro de `backend/`** — é a raiz do pacote Python, e é também o
diretório que o Railway usa como Root Directory do serviço:

```bash
cd backend
uvicorn main:app --port 8000
```

!!! warning "Evite `--reload` para testar upload"
    O `--reload` do uvicorn observa `backend/` e reinicia o processo a qualquer arquivo salvo — se
    isso acontecer durante um upload (a extração com Docling leva ~2 min), o request é morto no
    meio. Para desenvolvimento normal `--reload` é ok; para testar o fluxo de upload, rode sem ele.

O `lifespan`
([`app/api/lifespan.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/lifespan.py))
conecta ao Redis, monta as ferramentas e compila o grafo antes de aceitar requisições. Se uma chave
obrigatória faltar, o erro aparece nos logs de boot, não numa requisição. Um startup saudável
termina assim:

```
INFO | Client Redis (rate limiter + cache de ferramentas) conectado.
INFO | npx encontrado em: /usr/local/bin/npx
INFO | MCP conectado — 11/18 ferramentas selecionadas para o agente.
INFO | Total de ferramentas disponíveis para o agente: 15
INFO | Checkpointer Redis pronto (TTL=1440 min).
INFO | Servidor pronto para receber requests.
INFO | Application startup complete.
```

Qualquer `WARNING` entre essas linhas aponta uma divergência de configuração — uma tool sem mensagem
de status, ou um nome de whitelist que o servidor MCP não expôs. O startup também pré-aquece os dois
`DocumentConverter` do Docling (baixa ~1 GB de modelos na primeira vez) e faz `ping` no MongoDB.

## 6. Subir o frontend

O frontend é um app Vite separado (não é mais servido pelo backend). Em outro terminal:

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000 já é o default
npm run dev
```

O Vite sobe em `http://localhost:5173`. Toda chamada dele para o backend (`:8000`) é cross-site — o
CORS já é liberado automaticamente em dev (passo 4, `AMBIENTE_PRODUCAO=False`).

## 7. Verificar que está no ar

- Interface web: `http://localhost:5173` (upload de edital + chat)
- API / Swagger UI: `http://localhost:8000/docs`

## Rodando os testes

De dentro de `backend/`:

```bash
pytest
```

A suíte roda **sem rede**: nenhuma chave de API, nenhum Redis, nenhum MongoDB. Isso é possível
porque nada abre conexão no import — a conexão com o Mongo só é aberta na primeira busca/indexação,
e o LLM é substituído por um modelo falso nos testes do grafo.

O que ela cobre: montagem do grafo e o ciclo ReAct completo (incluindo a injeção do `ToolRuntime`
nas tools), os eventos emitidos por `run_agent()`, a tradução desses eventos para SSE, a cura de
histórico interrompido, os normalizadores da chave de cache, o filtro de resultados da busca web e a
consistência entre as tools registradas e o `TOOL_STATUS_MAP`.

## Rodando esta documentação

O `mkdocs` já veio no `requirements.txt` do passo 3. Da raiz do repositório:

```bash
mkdocs serve -a localhost:8001
```

A porta `8001` evita conflito com a aplicação, que usa a `8000` por padrão.
