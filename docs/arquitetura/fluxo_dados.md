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
    U["Usuário"] -->|"Upload do PDF + estado/município + thread_id"| UP["POST /upload/"]
    UP --> PDF["pdfplumber extrai texto"]
    PDF --> CHUNK["RecursiveCharacterTextSplitter<br>chunks de 2000 chars, overlap 200"]
    CHUNK --> EMB["OpenAI text-embedding-3-small"]
    EMB --> PC[("Pinecone<br>index auditor-cidadao")]
    PDF --> CNPJ["Regex + validate-docbr<br>extrai CNPJs do texto"]
    CNPJ --> REL["Relatório automático<br>(1º turno da thread)"]
    REL --> U
```

O PDF é lido inteiro em memória (sem tocar disco), rejeitado com `415`/`413` se não for PDF ou
passar de 20 MB (`app/api/root_upload.py`), e tem o texto extraído via `pdfplumber`. O
`GerenciadorVetorial` chunkiza o texto (separadores hierárquicos: parágrafo → linha → frase →
palavra), gera os embeddings e faz o upsert no Pinecone com `estado`/`municipio`/`arquivo`
replicados como metadado em cada chunk — é esse metadado que permite filtrar a busca por edital
depois. Os CNPJs do texto são extraídos por regex e devolvidos ao frontend, que os reenvia em
cada pergunta subsequente.

Com a indexação concluída, `gerar_relatorio_inicial()` roda como o **primeiro turno** da thread
identificada pelo `thread_id` recebido no upload — sem esperar nenhuma pergunta do usuário — e
devolve um laudo completo já estruturado (ver
[Relatório Automático e Extração de Laudo](../ia/extracao_laudo.md)). Perguntas seguintes do usuário
em `/conversar-com-auditor/` reusam esse mesmo `thread_id` e continuam a mesma conversa no
checkpointer, em vez de começar do zero. Exemplo real de request/response (`curl`):
[Referência de API](../operacional/api.md#post-upload-indexar-um-edital).

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
    CHAT --> AGENTE["Loop do agente<br>model ↔ tools (create_agent)"]
    AGENTE --> SSE["StreamingResponse (SSE)"]
    SSE -->|"tokens + status + done"| U
```

A resposta é transmitida via Server-Sent Events (SSE): tokens de texto conforme são gerados, e
mensagens de status quando uma ferramenta é acionada (ex.: "Consultando Receita Federal..."). Não há
extração estruturada nem card de laudo nessa conversa — o único laudo estruturado da thread é o
[relatório automático](../ia/extracao_laudo.md) gerado uma vez, logo após o upload; ver também
[Visão Geral](visao_geral.md#streaming-o-que-sai-pelo-sse-de-conversa). Exemplo real do stream de
eventos (`curl -N` + o JSON completo de cada tipo de evento):
[Referência de API](../operacional/api.md#post-conversar-com-auditor-perguntar-sobre-o-edital).

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
    AGENTE["Loop do agente<br>model ↔ tools (create_agent)"] --> RF["consultar_receita_federal"]
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
