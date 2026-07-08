# Fluxo de Dados

Esta página detalha, ponta a ponta, os dois pipelines de dados do Auditor Cidadão: a ingestão de
um edital (upload) e a conversa com o agente (pergunta → laudo).

## Ingestão do edital (`POST /upload/`)

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
    U["Usuário"] -->|"Upload do PDF + estado/município"| UP["POST /upload/"]
    UP --> PDF["pdfplumber extrai texto"]
    PDF --> CHUNK["RecursiveCharacterTextSplitter<br>chunks de 2000 chars, overlap 200"]
    CHUNK --> EMB["OpenAI text-embedding-3-small"]
    EMB --> PC[("Pinecone<br>index auditor-cidadao")]
    PDF --> CNPJ["Regex + validate-docbr<br>extrai CNPJs do texto"]
    CNPJ --> U
```

O PDF é lido inteiro em memória (sem tocar disco), rejeitado com `415`/`413` se não for PDF ou
passar de 20 MB (`app/api/root_upload.py`), e tem o texto extraído via `pdfplumber`. O
`GerenciadorVetorial` chunkiza o texto (separadores hierárquicos: parágrafo → linha → frase →
palavra), gera os embeddings e faz o upsert no Pinecone com `estado`/`municipio`/`arquivo`
replicados como metadado em cada chunk — é esse metadado que permite filtrar a busca por edital
depois. Os CNPJs do texto são extraídos por regex e devolvidos ao frontend, que os reenvia em
cada pergunta subsequente.

## Conversa com o agente (`POST /conversar-com-auditor/`)

Esse fluxo é dividido em dois diagramas: o **caminho da requisição** (a "casca" — como a pergunta
entra e a resposta sai) e o **leque de ferramentas** que o agente pode acionar por dentro dela.
Juntos num diagrama só, ficavam grandes demais para ler; separados, cada um cabe numa leitura só.

### O caminho da requisição

```mermaid
---
config:
  layout: dagre
  theme: redux-dark
  look: handDrawn
  fontFamily: '''Source Code Pro Variable'', monospace'
  themeVariables:
    fontFamily: '''Source Code Pro Variable'', monospace'
    fontSize: '32px'
---
flowchart LR
    U["Usuário"] -->|"Pergunta sobre o edital"| CHAT["POST /conversar-com-auditor/"]
    CHAT --> AGENTE["Loop do agente<br>call_llm ↔ tool_node"]
    AGENTE --> SSE["StreamingResponse (SSE)"]
    SSE -->|"tokens + status + laudo_estruturado + done"| U
```

A resposta é transmitida via Server-Sent Events (SSE): tokens de texto conforme são gerados,
mensagens de status quando uma ferramenta é acionada (ex.: "Consultando Receita Federal..."), e
ao final o laudo estruturado em JSON — ver o trade-off do **buffer-then-commit** em
[Visão Geral](visao_geral.md#streaming-por-que-o-laudo-nao-e-preenchido-direto-no-stream) para
entender por que o laudo não é montado direto durante o streaming.

### O que o agente pode acionar dentro do loop

```mermaid
---
config:
  layout: dagre
  theme: redux-dark
  look: handDrawn
  fontFamily: '''Source Code Pro Variable'', monospace'
  themeVariables:
    fontFamily: '''Source Code Pro Variable'', monospace'
    fontSize: '30px'
---
flowchart TB
    AGENTE["Loop do agente<br>call_llm ↔ tool_node"] --> RF["consultar_receita_federal"]
    AGENTE --> RAG["buscar_contexto_edital"]
    AGENTE --> SANC["consultar_sancoes_empresa"]
    AGENTE --> WEB["buscar_informacao_web"]
    AGENTE --> MCP["11 tools PNCP via MCP"]
    RAG -.->|"similarity_search<br>filtro estado+município"| PC[("Pinecone")]
```

O `StateGraph` decide sozinho quais dessas ferramentas chamar, em qualquer ordem e quantas vezes
forem necessárias, antes de responder — o funcionamento interno desse loop de decisão (`call_llm`
↔ `tool_node` ↔ `router`) está detalhado em
[Visão Geral](visao_geral.md#o-ciclo-de-decisao-do-agente).
