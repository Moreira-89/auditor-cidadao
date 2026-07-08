# Docker & Deploy

O `Dockerfile` na raiz do projeto é o mesmo artefato usado em desenvolvimento local containerizado
e em produção (Railway) — não há um Dockerfile separado por ambiente.

## Build da imagem

```bash
docker build -t auditor-cidadao .
```

Pontos da imagem que valem explicação:

- **Base `python:3.12-slim`** — reduz o tamanho final eliminando ferramentas de compilação
  desnecessárias ao runtime.
- **Node.js 20 LTS instalado via NodeSource, dentro da mesma imagem** — necessário porque o agente
  carrega as ferramentas do PNCP através do MCP, que roda como subprocesso `npx @licinexusbr/mcp`.
  Sem essa camada, o container sobe mas o `lifespan` falha ao conectar no MCP.
- **`COPY requirements.txt .` antes de `COPY . .`** — aproveita o cache de camadas do Docker: se as
  dependências não mudarem, a camada de `pip install` não é reconstruída a cada build.
- **`ENV NO_UPDATE_NOTIFIER=1`** — silencia o aviso de atualização do `npm` nos logs do container.

## Rodando o container

```bash
docker run -p 8000:8000 --env-file .env auditor-cidadao
```

O comando de start (`CMD` do Dockerfile) usa `${PORT:-8000}` — em produção (Railway), a plataforma
injeta `PORT` automaticamente; localmente, cai no padrão `8000`.

!!! warning "`.env.docker` não é `.env`"
    O `.dockerignore` exclui `.env` da imagem, mas isso não afeta o `--env-file .env` usado no
    `docker run` — essa flag lê o arquivo do host na hora de subir o container, não o copia para
    dentro da imagem. Cuidado ao criar variações locais desse arquivo (ex.: `.env.docker`): garanta
    que elas também estejam cobertas pelo `.dockerignore` antes de fazer qualquer build que possa
    ser publicado.

## Deploy em produção (Railway)

O Railway builda a mesma imagem a partir do `Dockerfile` do repositório — não há configuração de
deploy divergente do ambiente local. As variáveis de ambiente são cadastradas diretamente no painel
do Railway (mesmas chaves de [Variáveis de ambiente](variaveis_ambiente.md)), e a plataforma injeta
`PORT` dinamicamente.
