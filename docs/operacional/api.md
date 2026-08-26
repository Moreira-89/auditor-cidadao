# Referência de API

Os dois endpoints que o frontend consome, com exemplo real de request/response para cada um.
Referência interativa completa (gerada automaticamente pelo FastAPI a partir dos schemas
Pydantic): `http://localhost:8000/docs` (Swagger UI) depois de subir a aplicação — ver
[Setup local](setup_local.md).

Os exemplos de `curl` abaixo assumem a aplicação rodando em `http://localhost:8000`. Contra a
instância publicada, troque o host.

## `POST /upload/` — indexar um edital

Recebe um PDF, extrai o texto, indexa no Pinecone e devolve os CNPJs encontrados.

| | |
|---|---|
| Rate limit | 5 requisições/dia por `client_id` (cookie) |
| Corpo | `multipart/form-data`: `file` (PDF), `estado`, `municipio`, `thread_id` |

`thread_id` é gerado pelo frontend (UUID) antes do upload e identifica a conversa que vai receber o
relatório automático como primeiro turno — a mesma thread deve ser reenviada em
`/conversar-com-auditor/` para que as perguntas seguintes continuem essa conversa em vez de começar
uma nova.

```bash
curl -X POST http://localhost:8000/upload/ \
  -F "file=@edital_saoluis.pdf" \
  -F "estado=Maranhão (MA)" \
  -F "municipio=São Luís" \
  -F "thread_id=3fa85f64-5717-4562-b3fc-2c963f66afa6" \
  -c cookies.txt
```

`-c cookies.txt` salva o cookie `auditor_client_id` que o servidor emite — reenvie-o
(`-b cookies.txt`) nas próximas chamadas para o rate limiting contar como o mesmo cliente
(ver [Guardrails](../governanca/guardrails.md) e [LGPD](../governanca/lgpd.md)).

**Resposta em sucesso (`200`):**

```json
{
  "mensagem": "Edital indexado!",
  "cnpjs": ["38504819000169"],
  "relatorio_inicial": {
    "texto": "## Resumo Executivo\n[...]",
    "laudo": {
      "cnpjs_analisados": ["38504819000169"],
      "anomalias": [],
      "nivel_risco_geral": "MÉDIO",
      "resumo_executivo": "[...]",
      "recomendacoes": ["[...]"]
    },
    "sugestoes_perguntas": [
      "Existe alguma sanção vigente para a empresa 38.504.819/0001-69?",
      "Qual o prazo entre a publicação do edital e a abertura das propostas?"
    ]
  }
}
```

O frontend guarda a lista de `cnpjs` e a reenvia em `lista_cnpjs` a cada pergunta subsequente — o
backend não os re-extrai do texto a cada turno. `relatorio_inicial` traz o primeiro laudo completo
da conversa, gerado automaticamente a partir do edital recém-indexado (ver
[Relatório Automático e Extração de Laudo](../ia/extracao_laudo.md)); pode vir `null` se a geração
falhar — o upload em si não falha por causa disso, e o frontend cai de volta no estado vazio normal.

**Respostas de erro:**

| Status | Quando | Corpo |
|---|---|---|
| `415` | `Content-Type` não é `application/pdf` | `{"detail": "Formato inválido: '...'. Apenas arquivos PDF são aceitos."}` |
| `413` | Arquivo maior que 20 MB | `{"detail": "Arquivo muito grande: N bytes. O limite é de 20971520 bytes."}` |
| `422` | PDF corrompido ou protegido por senha | `{"detail": "Não foi possível ler o PDF. O arquivo pode estar corrompido ou protegido por senha."}` |
| `429` | Rate limit excedido (5/dia) | `{"detail": "Você excedeu o limite de upload diário. Volte em ..."}` |
| `502` | Falha ao indexar no Pinecone | `{"detail": "Falha ao indexar o edital no banco vetorial. Tente novamente em instantes."}` |

## `POST /conversar-com-auditor/` — perguntar sobre o edital

Recebe a pergunta e devolve a resposta do agente em **streaming SSE** (Server-Sent Events) — o
corpo da resposta não é um JSON único, é uma sequência de eventos `data: {...}\n\n`.

| | |
|---|---|
| Rate limit | 50 requisições/dia por `client_id` (cookie) |
| Corpo | JSON: `pergunta`, `estado`, `municipio`, `lista_cnpjs`, `thread_id` (opcional) |
| `Content-Type` da resposta | `text/event-stream` |

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

Esse endpoint nunca emite laudo estruturado — o único laudo estruturado de uma thread é o
[relatório automático](../ia/extracao_laudo.md) devolvido por `/upload/`, uma única vez. Toda
resposta aqui, mesmo que o usuário peça explicitamente outra auditoria, chega só como Markdown em
streaming (`token`(s), o(s) `status` de qualquer tool chamada, e `done` no final) — sem chamada
extra de extração por turno.

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
