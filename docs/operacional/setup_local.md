# Setup local

!!! tip "Prefere não instalar nada?"
    A forma mais rápida de conhecer o Auditor Cidadão é pela instância publicada:
    **[Plataforma Auditor Cidadão](https://auditor-cidadao-production.up.railway.app/)**. O setup
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
| Node.js | 20 LTS | O agente carrega 11 ferramentas do PNCP via MCP, que sobe um subprocesso `npx @licinexusbr/mcp` — **sem Node.js, o boot falha ao conectar no MCP** |
| Redis | — | Guarda o histórico de conversa, a contagem do rate limiter e o cache de ferramentas — **sem um Redis acessível, o boot também falha**. Ver o passo 4.1 |
| Chaves de API | — | OpenAI e Pinecone são obrigatórias; CGU e Tavily são exigidas pelas tools de sanções e busca web. Ver [Variáveis de ambiente](variaveis_ambiente.md) |

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

É um arquivo único: além das dependências de runtime da API, ele traz o `mkdocs`/`mkdocs-material`
usado para gerar esta documentação.

## 4. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Preencha o `.env` na raiz do repositório com suas chaves. Todos os campos estão documentados em
[Variáveis de ambiente](variaveis_ambiente.md); os obrigatórios para o boot são `OPENAI_API_KEY`,
`PINECONE_API_KEY` e um `REDIS_URI` apontando para um Redis de verdade.

Em desenvolvimento local, confira que **`AMBIENTE_PRODUCAO=False`**. Com `True` (o default), o
cookie de sessão sai com a flag `Secure` e o navegador nunca o reenvia em `http://localhost` — o
rate limiter deixa de reconhecer o mesmo cliente entre requisições, sem emitir erro nenhum.

!!! warning "Nunca versione o `.env` real"
    Ele já está no `.gitignore`. Só o `.env.example`, sem chaves reais, vai para o Git.

### 4.1. Subir um Redis local

Com Docker:

```bash
docker run -d --name redis-auditor -p 6379:6379 redis:latest
```

Isso sobe um Redis em `redis://localhost:6379`, que já é o default de `REDIS_URI`. Sem Docker, dá
para instalar nativamente (`apt`, `brew`, `dnf`) e rodar `redis-server`.

## 5. Subir a aplicação

Os comandos rodam **de dentro de `backend/`** — é a raiz do pacote Python, e é também o
diretório que o Railway usa como Root Directory do serviço:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

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
de status, ou um nome de whitelist que o servidor MCP não expôs.

## 6. Verificar que está no ar

- Interface web: `http://localhost:8000` (upload de edital + chat)
- Swagger UI: `http://localhost:8000/docs`

## Rodando os testes

De dentro de `backend/`:

```bash
pytest
```

A suíte roda **sem rede**: nenhuma chave de API, nenhum Redis, nenhum Pinecone. Isso é possível
porque nada abre conexão no import — o cliente do Pinecone só é criado na primeira busca, e o LLM é
substituído por um modelo falso nos testes do grafo.

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
