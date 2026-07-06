# Setup local

!!! tip "Prefere não instalar nada?"
    A forma mais recomendada de acessar o Auditor Cidadão é pela instância já publicada em produção:
    **[auditor-cidadao-production.up.railway.app](https://auditor-cidadao-production.up.railway.app/)**.
    O setup local abaixo é voltado para quem quer inspecionar o código, rodar o framework de
    avaliação ou contribuir com o projeto.

Passo a passo para rodar o Auditor Cidadão diretamente na sua máquina, sem Docker. Se preferir
isolar o ambiente, veja [Docker & Deploy](docker.md).

## Pré-requisitos

| Ferramenta | Versão | Por quê |
|---|---|---|
| Python | 3.12+ | Runtime da aplicação FastAPI |
| Node.js | 20 LTS | O agente carrega as 11 ferramentas do PNCP via MCP, que sobe um subprocesso `npx @licinexusbr/mcp` — **sem Node.js instalado, o boot da aplicação falha ao conectar no MCP** |
| Chaves de API | — | OpenAI (obrigatória), Pinecone (obrigatória), CGU e Tavily (obrigatórias para as tools nativas de sanções e busca web) — ver [Variáveis de ambiente](variaveis_ambiente.md) |

## 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
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

Preencha o `.env` com suas chaves reais. Todos os campos e seus efeitos estão documentados em
[Variáveis de ambiente](variaveis_ambiente.md) — os únicos realmente obrigatórios para o boot
funcionar são `OPENAI_API_KEY` e `PINECONE_API_KEY`.

!!! warning "Nunca versione o `.env` real"
    Ele já está listado no `.gitignore`. Só `.env.example` (sem chaves reais) deve ir para o Git.

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
