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

O Redis **não** está embutido nessa imagem — precisa de um container separado rodando antes de
subir a aplicação (ver [Setup local](setup_local.md#41-subir-um-redis-local)):

```bash
docker run -d --name redis-auditor -p 6379:6379 redis:latest
docker run -p 8000:8000 --env-file .env --add-host=host.docker.internal:host-gateway auditor-cidadao
```

Se `REDIS_URI` no `.env` apontar para `localhost`, ajuste para `host.docker.internal` (ou coloque
os dois containers na mesma rede Docker com `docker network create`) — de dentro do container da
aplicação, `localhost` se refere ao próprio container, não ao host.

O comando de start (`CMD` do Dockerfile) usa `${PORT:-8000}` — em produção (Railway), a plataforma
injeta `PORT` automaticamente; localmente, cai no padrão `8000`.

!!! warning "`.env.docker` não é `.env`"
    O `.dockerignore` exclui `.env` da imagem, mas isso não afeta o `--env-file .env` usado no
    `docker run` — essa flag lê o arquivo do host na hora de subir o container, não o copia para
    dentro da imagem. Cuidado ao criar variações locais desse arquivo (ex.: `.env.docker`): garanta
    que elas também estejam cobertas pelo `.dockerignore` antes de fazer qualquer build que possa
    ser publicado.

## Deploy em produção (Railway)

O Railway builda a mesma imagem a partir do `Dockerfile` do repositório — a aplicação em si não tem
configuração de deploy divergente do ambiente local. As variáveis de ambiente são cadastradas
diretamente no painel do Railway (mesmas chaves de [Variáveis de ambiente](variaveis_ambiente.md)),
e a plataforma injeta `PORT` dinamicamente.

Uma peça, porém, **não** vem pronta: o Redis. Diferente do ambiente local (onde você mesmo sobe um
container, ver acima), em produção é preciso provisionar o serviço explicitamente:

1. No projeto do Railway, **"+ New" → "Database" → "Add Redis"** — sobe um serviço Redis gerenciado
   dentro do mesmo projeto.
2. No serviço da API, defina `REDIS_URI` apontando para esse Redis. O jeito robusto é referenciar a
   variável do outro serviço em vez de colar a URL fixa: `REDIS_URI=${{Redis.REDIS_URL}}` (o nome
   `Redis` precisa bater com o nome do serviço que aparece no painel).

!!! danger "Sintoma de esquecer esse passo: crash-loop no boot"
    Sem `REDIS_URI` definida, a aplicação cai no default `redis://localhost:6379` — que dentro do
    container do Railway não tem nada escutando. O resultado é um loop de reinício a cada poucos
    segundos, com esse erro nos logs:

    ```
    redis.exceptions.ConnectionError: Error Multiple exceptions: [Errno 111] Connect call failed
    ('::1', 6379, 0, 0), [Errno 111] Connect call failed ('127.0.0.1', 6379) connecting to
    localhost:6379.
    ```

    Se aparecer isso, o Redis do projeto não existe ou `REDIS_URI` não está configurada no serviço
    da API — não é um bug de código.

## Escalonamento: réplicas e limites de recurso

A aplicação roda em produção com **2 réplicas** (Railway, região US East), sem multi-região, e
**1 worker por réplica** — o `CMD` do `Dockerfile` não passa `--workers` para o `uvicorn`, de
propósito.

- **Por que 2 réplicas, e não 1 ou mais:** elimina o ponto único de falha e valida em produção a
  premissa de que o estado da aplicação vive fora da RAM local (Redis, ver
  [Variáveis de ambiente](variaveis_ambiente.md#seguranca-cookie-de-identificacao-de-cliente) e
  [Visão geral da arquitetura](../arquitetura/visao_geral.md)) — sem exigir mais infraestrutura do
  que o estágio atual de tráfego (divulgação orgânica) justifica.
- **Por que 1 worker por réplica, e não vários:** a carga é dominada por I/O (chamadas a
  LLM/PNCP/Pinecone) e pela velocidade de rede, não por CPU — múltiplos workers por processo
  trariam ganho marginal. As réplicas do Railway já são o eixo de escala escolhido; manter os dois
  eixos (réplicas vs. workers por processo) simples facilita depurar.
- **Teto de 4 vCPU / 4 GB por réplica** (Replica Limits do Railway) **+ Usage Limit no workspace**
  como proteção agregada de custo: dado real de ~3 meses de uso mostrou pico de 1,38 GB de RAM e
  CPU próxima de zero — o teto de 8 vCPU/8 GB do plano era o máximo técnico disponível, não
  refletia uso real algum. 4/4 dá margem de ~3x sobre o pico observado, funcionando como disjuntor
  contra anomalia (bug/loop), não como limite de operação normal.
- **Pré-requisito que viabilizou essas decisões sem risco:** a migração de todo estado que antes
  vivia só na RAM de um processo (checkpointer de conversa, contador de rate limit, cache de
  tools) para o Redis — sem sticky sessions no Railway, qualquer uma dessas peças em memória local
  quebraria silenciosamente com múltiplas réplicas.

!!! warning "Configuração validada com tráfego de 1 usuário (autor, ambiente de testes)"
    O dado de pico (1,38 GB RAM, CPU ~zero) usado para calibrar os tetos acima vem de ~3 meses de
    uso, mas **todo esse uso é do próprio autor** testando o sistema — tanto localmente quanto em
    produção —, não de múltiplos usuários reais e simultâneos. Número de réplicas, tetos de
    recurso e o Usage Limit de custo são um **ponto de partida seguro**, não uma capacidade testada
    sob carga real. Reavaliar todos esses números depois dos primeiros dias de uso com múltiplos
    usuários reais (quando o link for compartilhado publicamente) — os padrões de tráfego
    (concorrência, tamanho de picos, distribuição ao longo do dia) só existem daí em diante.
