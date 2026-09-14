# Referência de API

Os dois endpoints que o frontend consome, com exemplo real de request/response para cada um.
Referência interativa completa (gerada automaticamente pelo FastAPI a partir dos schemas
Pydantic): `http://localhost:8000/docs` (Swagger UI) depois de subir a aplicação — ver
[Setup local](setup_local.md).

Os exemplos de `curl` abaixo assumem a aplicação rodando em `http://localhost:8000`. Contra a
instância publicada, troque o host.

## `POST /upload/` — indexar um edital

Recebe um PDF, extrai a estrutura (Docling) e indexa (MongoDB). A resposta é um
**stream SSE** — a extração + indexação levam ~2 min, e um request síncrono todo esse tempo era
derrubado por timeout de conexão ociosa (`Failed to fetch` no navegador, mesmo com o backend
terminando bem).

| | |
|---|---|
| Rate limit | 5 requisições/dia por `client_id` (cookie) |
| Corpo | `multipart/form-data`: `file` (PDF), `estado`, `municipio`, `thread_id` |
| `Content-Type` da resposta | `text/event-stream` (após as validações de tipo/tamanho) |

`thread_id` é gerado pelo frontend (UUID) antes do upload e identifica a conversa que vai receber o
relatório automático como primeiro turno — a mesma thread deve ser reenviada em
`/conversar-com-auditor/` para que as perguntas seguintes continuem essa conversa em vez de começar
uma nova. Como cada thread recebe exatamente um edital, o `thread_id` também é gravado como
`edital_id` em cada chunk indexado e usado para filtrar a busca RAG por aquele edital (ver
[RAG e dados](../ia/rag_dados.md)).

```bash
curl -N -X POST http://localhost:8000/upload/ \
  -F "file=@edital_saoluis.pdf" \
  -F "estado=Maranhão (MA)" \
  -F "municipio=São Luís" \
  -F "thread_id=3fa85f64-5717-4562-b3fc-2c963f66afa6" \
  -c cookies.txt
```

`-N` desativa o buffer do `curl` (o mesmo do endpoint de chat). `-c cookies.txt` salva o cookie
`auditor_client_id` que o servidor emite — reenvie-o (`-b cookies.txt`) nas próximas chamadas para o
rate limiting contar como o mesmo cliente (ver [Guardrails](../governanca/guardrails.md) e
[LGPD](../governanca/lgpd.md)).

**O stream de eventos** (cada linha `data: {...}\n\n`):

```text
data: {"type": "progress", "content": "Extraindo a estrutura do documento…", "pct": 35}

data: {"type": "heartbeat"}

data: {"type": "progress", "content": "Indexando as seções e os trechos…", "pct": 82}

data: {"type": "done", "cnpjs": ["38504819000169"]}
```

- **`progress`** — troca de etapa; `pct` é uma dica para a barra de progresso do frontend.
- **`heartbeat`** — emitido a cada ~3 s enquanto uma etapa longa (Docling) roda numa thread; só
  serve para manter a conexão viva.
- **`done`** — fim do processamento, com a lista de CNPJs. O frontend guarda e reenvia em
  `lista_cnpjs` a cada pergunta seguinte.
- **`error`** — `{"type": "error", "content": "..."}` para PDF ilegível ou falha de indexação
  (MongoDB). Substitui os antigos `422`/`502` — a resposta já começou com `200`.

O **relatório automático não sai daqui**. No `done`, o frontend leva o usuário ao chat e dispara o
primeiro turno via `POST /conversar-com-auditor/` com `inicial: true` (ver abaixo).

**Respostas de erro (antes do stream começar):**

| Status | Quando | Corpo |
|---|---|---|
| `415` | `Content-Type` não é `application/pdf` | `{"detail": "Formato inválido: '...'. Apenas arquivos PDF são aceitos."}` |
| `413` | Arquivo maior que 20 MB | `{"detail": "Arquivo muito grande: N bytes. O limite é de 20971520 bytes."}` |
| `429` | Rate limit excedido (5/dia) | `{"detail": "Você excedeu o limite de upload diário. Volte em ..."}` |

PDF ilegível e falha de indexação viram um evento `error` no stream, não um status HTTP.

## `POST /conversar-com-auditor/` — perguntar sobre o edital

Recebe a pergunta e devolve a resposta do agente em **streaming SSE** (Server-Sent Events) — o
corpo da resposta não é um JSON único, é uma sequência de eventos `data: {...}\n\n`.

| | |
|---|---|
| Rate limit | 50 requisições/dia por `client_id` (cookie) |
| Corpo | JSON: `pergunta`, `estado`, `municipio`, `lista_cnpjs`, `thread_id` (opcional), `inicial` (opcional, default `false`) |
| `Content-Type` da resposta | `text/event-stream` |

Com `inicial: true`, o backend ignora `pergunta` e roda o **relatório automático** como primeiro
turno da thread (usa `PROMPT_RELATORIO_INICIAL` internamente). É o que o frontend chama logo após o
upload; o `thread_id` deve ser o mesmo passado no `/upload/`.

```bash
curl -N -X POST http://localhost:8000/conversar-com-auditor/ \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "pergunta": "Audite essa empresa e verifique se há alguma sanção que a impeça de contratar com o poder público.",
    "estado": "Maranhão (MA)",
    "municipio": "São Luís",
    "lista_cnpjs": ["38504819000169"],
    "thread_id": null
  }'
```

`-N` desativa o buffer do `curl` — sem isso, você só veria a resposta inteira de uma vez ao
final, em vez do streaming token a token. `thread_id: null` no primeiro turno faz o backend gerar
um UUID novo; turnos seguintes da mesma conversa devem reenviar o `thread_id` recebido para o
LangGraph recuperar o histórico (ver [Arquitetura](../arquitetura/visao_geral.md)).

**O stream de eventos** (cada linha é um evento SSE — tipos definidos em [`app/agents/conversa.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/conversa.py)):

```text
data: {"type": "status", "content": "⚖️ Verificando sanções da empresa nos cadastros CEIS e CNEP..."}

data: {"type": "token", "content": "A"}

data: {"type": "token", "content": " empresa"}

data: {"type": "token", "content": " vencedora"}

[... um evento "token" por fragmento de texto gerado, até a resposta terminar ...]

data: {"type": "done"}
```

Nenhum turno emite laudo estruturado — nem as perguntas comuns nem o relatório automático (o turno
com `inicial: true`). Toda resposta chega como Markdown em streaming (`token`(s), o(s) `status` de
qualquer tool chamada, e `done` no final). A extração de códigos de anomalia (para a métrica de
avaliação) lê esse mesmo Markdown por regex — ver [Avaliação](../ia/avaliacao.md).

**Se algo falhar no meio do streaming:**

```text
data: {"type": "error", "content": "Ocorreu um erro ao processar sua pergunta. Tente novamente."}
```

Esse evento substitui o `done` (não emitidos juntos) — o frontend trata os dois como sinal de "a
resposta terminou", um com sucesso e outro com falha.

**Erro antes do streaming começar (`429`, rate limit):** como o corpo da resposta normal já é
`text/event-stream`, um 429 vem como resposta HTTP comum (não SSE), igual ao `/upload/`:

```json
{"detail": "Você excedeu o limite de perguntas diárias ao auditor. Volte em ..."}
```
