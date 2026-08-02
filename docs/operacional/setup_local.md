# Setup local

!!! tip "Prefere não instalar nada?"
    A forma mais recomendada de acessar o Auditor Cidadão é pela instância já publicada em produção:
    **[Plataforma Auditor Cidadão](https://auditor-cidadao-production.up.railway.app/)**.
    O setup local abaixo é voltado para quem quer inspecionar o código, rodar o framework de
    avaliação ou contribuir com o projeto.

Passo a passo para rodar o Auditor Cidadão diretamente na sua máquina, sem Docker. Se preferir isolar o ambiente, veja [Docker & Deploy](docker.md).

## Pré-requisitos

| Ferramenta | Versão | Por quê |
|---|---|---|
| Python | 3.12+ | Runtime da aplicação FastAPI |
| Node.js | 20 LTS | O agente carrega as 11 ferramentas do PNCP via MCP, que sobe um subprocesso `npx @licinexusbr/mcp` — **sem Node.js instalado, o boot da aplicação falha ao conectar no MCP** |
| Redis | — | Persiste o histórico de conversa (`AsyncRedisSaver`), conta requisições do rate limiter e guarda o cache de ferramentas (TTL 24h) — **sem um Redis acessível, o boot também falha**. Não vem embutido no `Dockerfile`; ver o passo 4.1 abaixo |
| Chaves de API | — | OpenAI (obrigatória), Pinecone (obrigatória), CGU e Tavily (obrigatórias para as tools nativas de sanções e busca web) — ver [Variáveis de ambiente](variaveis_ambiente.md) |

## 1. Clonar o repositório

```bash
git clone https://github.com/Moreira-89/auditor-cidadao
cd auditor-cidadao
```

## 2. Criar e ativar o ambiente virtual

```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

## 3. Instalar dependências Python

```bash
pip install -r requirements.txt
```

## 4. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Preencha o `.env` com suas chaves reais. Todos os campos e seus efeitos estão documentados em [Variáveis de ambiente](variaveis_ambiente.md) — os obrigatórios para o boot
funcionar são `OPENAI_API_KEY`, `PINECONE_API_KEY` e um `REDIS_URI` que aponte para um Redis de
verdade (ver 4.1 abaixo). Em dev local, confira também que `AMBIENTE_PRODUCAO=False` — com `True`
(o default), o cookie de sessão usado pelo rate limiter não persiste em `http://localhost` sem TLS.

!!! warning "Nunca versione o `.env` real"
    Ele já está listado no `.gitignore`. Só `.env.example` (sem chaves reais) deve ir para o Git.

### 4.1. Subir um Redis local

Sem Docker instalado, dá para baixar o Redis nativamente (`apt`, `brew`, etc.) e rodar `redis-server`.
Com Docker, é mais simples:

```bash
docker run -d --name redis-auditor -p 6379:6379 redis:latest
```

Isso sobe um Redis em `redis://localhost:6379` — que já é o default de `REDIS_URI` se você não
sobrescrever no `.env`.

## 5. Subir a aplicação

```bash
uvicorn main:app --reload --port 8000
```

A aplicação sobe em `http://localhost:8000`. O `lifespan` (`app/services/lifespan.py`) conecta ao
MCP, inicializa o grafo do agente e o modelo extrator antes de aceitar requisições — se alguma
chave obrigatória estiver ausente, o erro aparece nos logs de boot, não numa requisição.

## 6. Verificar que está no ar

- Interface web: `http://localhost:8000` (upload de edital + chat)
- Health/rota de teste: `http://localhost:8000/docs` (Swagger UI gerado pelo FastAPI)

## Rodando a documentação (este site)

```bash
pip install mkdocs mkdocs-material   # já incluídos no requirements.txt
mkdocs serve
```

Sobe em `http://localhost:8000` por padrão — **se a aplicação principal já estiver rodando nessa
porta, use** `mkdocs serve -a localhost:8001`.
