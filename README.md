<div align="center">

# 🏛️ Auditor Cidadão

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.137-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![LangGraph](https://img.shields.io/badge/LangGraph-agentic-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/) [![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

**[🚀 Testar a aplicação](https://auditor-cidadao-production.up.railway.app/)** · **[📚 Documentação técnica](https://moreira-89.github.io/auditor-cidadao/)**

</div>

## 📋 O caso

Fiscalizar licitações municipais no Brasil exige cruzar um edital em PDF com meia dúzia de bases
públicas diferentes (PNCP, Receita Federal, CEIS/CNEP) — um trabalho manual, lento e que a maioria
dos cidadãos e jornalistas não tem tempo ou conhecimento técnico para fazer.

O **Auditor Cidadão** automatiza essa varredura: recebe o edital em PDF, indexa seu conteúdo com RAG
(busca semântica) e disponibiliza um agente de IA que decide sozinho quais fontes oficiais consultar
para investigar **9 categorias de anomalias** — de sobrepreço a empresas sancionadas. Ao concluir a
indexação, já entrega sozinho um laudo inicial completo com evidências e nível de risco, sem esperar
o usuário perguntar nada; a conversa segue dali em diante, em streaming, em tempo real.

O sistema **sinaliza padrões para investigação humana — não acusa nem substitui uma auditoria formal.**

---

## ✨ Destaques

| | |
|---|---|
| 📄 | **Upload + relatório automático** — indexa o edital no Pinecone e já devolve um laudo inicial completo mais sugestões de pergunta, sem esperar o usuário perguntar nada |
| 🤖 | **Agente de auditoria (LangGraph)** — decide sozinho quais fontes oficiais consultar (Receita Federal, CEIS/CNEP, PNCP, busca web) para investigar 9 categorias de anomalia |
| ⚡ | **Streaming em tempo real** — resposta token a token via SSE, com memória conversacional persistida em Redis |
| 🛡️ | **Guardrails** — proteção contra prompt injection, rate limiting por cliente e laudo sempre tratado como indício, nunca veredito |

Lista completa de ferramentas, catálogo de anomalias e trade-offs de engenharia:
**[📚 Documentação técnica](https://moreira-89.github.io/auditor-cidadao/)**.

---

## 🛠️ Stack tecnológica

| Categoria | Tecnologia |
|---|---|
| Framework web | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| Orquestração agêntica | [LangGraph](https://langchain-ai.github.io/langgraph/) via `langchain.agents.create_agent` |
| LLM (padrão) | OpenAI `gpt-4o-mini` — trocável (Groq, Google Gemini) |
| Banco vetorial | [Pinecone](https://www.pinecone.io/) |
| Persistência / rate limiting | [Redis](https://redis.io/) |
| Dados de licitação | [PNCP](https://pncp.gov.br/) via MCP (`@licinexusbr/mcp`) |
| Sanções / cadastro | Portal da Transparência (CEIS/CNEP) + BrasilAPI |
| Avaliação automatizada | [RAGAS](https://docs.ragas.io/) — golden dataset + pipeline de métricas |

Versões exatas em [`requirements.txt`](./requirements.txt) e [`requirements-dev.txt`](./requirements-dev.txt).

---

## ⚙️ Rodando localmente

Pré-requisitos: **Python 3.12+**, **Node.js 20 LTS** (tools de PNCP via MCP) e **Redis** acessível
(sem ele o boot falha). Chaves obrigatórias: OpenAI, Pinecone, Tavily e Portal da Transparência/CGU.

```bash
git clone https://github.com/Moreira-89/auditor-cidadao.git
cd auditor-cidadao

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

docker run -d --name redis-auditor -p 6379:6379 redis:latest

cp .env.example .env   # preencha suas chaves
uvicorn main:app --reload
```

A aplicação sobe em `http://127.0.0.1:8000` (`/chat` para a interface, `/docs` para o Swagger).
Passo a passo detalhado, todas as variáveis de ambiente e instruções de Docker/deploy:
[Setup local](https://moreira-89.github.io/auditor-cidadao/operacional/setup_local/) ·
[Docker & Deploy](https://moreira-89.github.io/auditor-cidadao/operacional/docker/) ·
[Variáveis de ambiente](https://moreira-89.github.io/auditor-cidadao/operacional/variaveis_ambiente/).

---

## 📚 Documentação completa

Este README é só a porta de entrada — a documentação técnica de verdade (arquitetura, engenharia de
prompt, RAG, avaliação, governança, referência de API, estrutura do repositório) vive em
**[moreira-89.github.io/auditor-cidadao](https://moreira-89.github.io/auditor-cidadao/)**:

- **[Codemap](https://moreira-89.github.io/auditor-cidadao/codemap/)** — mapa de navegação do repositório
- **[Referência de API](https://moreira-89.github.io/auditor-cidadao/operacional/api/)** — endpoints, exemplos de request/response, eventos SSE
- **[Arquitetura](https://moreira-89.github.io/auditor-cidadao/arquitetura/visao_geral/)** — ciclo do agente, fluxo de dados, protocolo MCP
- **[Engenharia de IA](https://moreira-89.github.io/auditor-cidadao/ia/modelos_prompts/)** — prompts, RAG, relatório automático, avaliação (RAGAS)
- **[Governança](https://moreira-89.github.io/auditor-cidadao/governanca/lgpd/)** — LGPD, guardrails e limitações conhecidas

---

## 📄 Licença

Distribuído sob a **Apache License 2.0**. Consulte [`LICENSE`](./LICENSE) para o texto completo.
