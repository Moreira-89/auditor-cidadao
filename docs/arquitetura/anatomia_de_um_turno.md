# Anatomia de um turno

Esta página rastreia **uma requisição real de ponta a ponta**, citando arquivo e linha a cada salto.
As outras páginas de arquitetura explicam *por que* cada peça é como é; esta responde *onde estou* e
*para onde isso vai em seguida* — é a que se lê primeiro ao reabrir o projeto depois de um tempo.

Os caminhos são relativos a `backend/`, salvo quando começam por `frontend/`.

---

## Fluxo 1 — uma pergunta no chat

O usuário digita "Essa empresa tem sanção?" e aperta Enter.

### 1. Navegador → HTTP

`frontend/js/chat.js:761` monta o `fetch` para `POST /conversar-com-auditor/` com `pergunta`,
`estado`, `municipio`, `lista_cnpjs` e `thread_id`. O `API_BASE` é `''` (linha 10): URL relativa,
mesma origem — é isso que faz o cookie de sessão viajar sozinho.

### 2. FastAPI resolve as dependencies **antes** de entrar no endpoint

O router está registrado em `main.py:39`. Antes de `executar_pergunta` rodar, o FastAPI resolve, em
ordem:

| Ordem | O quê | Onde |
|---|---|---|
| 1 | `PerguntaRequest` valida o corpo | `app/api/schemas/pergunta.py` |
| 2 | `get_client_id` lê ou emite o cookie assinado | `app/api/dependencies.py:28` → `app/api/cookies.py` |
| 3 | `RateLimiter` conta a requisição no Redis | `app/api/rate_limiter.py:167` |

Se qualquer uma falhar, o endpoint **nunca executa** — o `429` do rate limiter e o `422` de
validação saem daqui, não do agente. Os handlers em `main.py:65-88` garantem que um cookie recém-
emitido não se perca junto com a resposta de erro.

### 3. O endpoint monta o streaming e sai da frente

`app/api/endpoints/chat.py:105` devolve um `StreamingResponse` envolvendo `_stream_sse(run_agent(...))`.
Repare que ele **não executa nada ainda**: `run_agent` é um gerador assíncrono, e só começa a rodar
quando o Starlette puxa o primeiro item para enviar ao navegador.

### 4. `run_agent` prepara o turno

`app/agents/conversa.py:61`, na ordem:

1. **Escapa todos os campos do cliente** (linhas 71-73) via `escape_xml` — `pergunta`, `estado` e
   `municipio`. É o guardrail contra injeção de tag XML no `PROMPT_DINAMICO`.
2. **Pega o grafo** (linha 85) com `get_graph()`. O grafo não é construído aqui: já existe desde o
   startup, ver o salto 8 abaixo.
3. **Lê o estado da thread** (linha 86) com `grafo.aget_state(config)` — é o checkpointer no Redis
   respondendo o que já aconteceu nessa conversa.
4. **Cura histórico interrompido** (linha 88). Se o turno anterior parou no meio de uma `tool_call`,
   injeta `ToolMessage`s sintéticas; sem isso a OpenAI rejeita o turno com `400`.
5. **Decide o que enviar** (linhas 90-102): thread nova recebe o envelope completo
   (`montar_primeiro_turno`, em `app/agents/envelope.py`); thread existente recebe só
   `<PERGUNTA>...</PERGUNTA>`, porque o histórico vem do checkpointer.

### 5. Entra no grafo

`app/agents/conversa.py:107` chama `grafo.astream_events(...)` passando `messages`, `estado` e
`municipio`. **`estado` e `municipio` vão em todo turno**, não só no primeiro: o checkpointer só
persiste as chaves declaradas no schema, e as tools precisam lê-las do estado ativo.

### 6. O nó `agente` chama o LLM

`app/agents/nodes/agente.py:17`. Uma linha: prepõe a `SystemMessage` com o `SYSTEM_PROMPT` e chama
`modelo.ainvoke`. O modelo já veio com `bind_tools` aplicado lá no `build_graph`
(`app/agents/graph.py:38`).

O prompt **não** fica no histórico — é preposto a cada chamada. Por isso alterar o
`SYSTEM_PROMPT` vale imediatamente até para conversas em andamento.

### 7. O roteamento decide: ferramenta ou fim

`app/agents/graph.py:48`. O `tools_condition` olha a última `AIMessage`: se ela traz `tool_calls`,
vai para o nó `ferramentas`; senão, `END`.

**No nó `ferramentas` está a armadilha nº 1 do projeto.** A função executada **não** é a que você lê
em `app/agents/tools/sancoes.py`. No startup, `aplicar_cache` (`app/agents/tools/registry.py:156`)
reconstruiu cada tool trocando a coroutine por um wrapper (`app/agents/tools/cache.py:60`). O que
roda é:

```
ToolNode → coroutine_com_cache        (cache.py:60)
             ├── HIT  → devolve do Redis, a tool nunca é chamada
             └── MISS → chama a tool de verdade (sancoes.py:120) e grava o resultado
```

Se um `print` dentro da tool não aparece, ou se o comportamento não bate com o código que você
está lendo, **é cache**. A chave é `mcp_cache:{tool}_{MD5(args)}`, com TTL de 24h.

O `ToolNode` também é quem injeta o `ToolRuntime` nas tools que declaram esse parâmetro — é assim
que `estado`/`municipio` chegam em `app/agents/tools/contexto_edital.py:29`.

Terminada a ferramenta, a aresta `ferramentas → agente` (`graph.py:51`) devolve o controle ao passo
6. O ciclo repete até o modelo responder sem pedir ferramenta, com teto de `recursion_limit=50`.

### 8. De onde veio o grafo, afinal

Do startup, não da requisição. `app/api/lifespan.py:15` roda uma vez antes do primeiro request:

```
abrir_client_redis()      storage/redis.py         → client compartilhado
  montar_tools()          agents/tools/registry.py → nativas + MCP, todas com cache
  inicializar_rate_limiter()
  abrir_checkpointer()    storage/checkpointer.py  → AsyncRedisSaver
    initialize_graph()    agents/graph.py:56       → compila e guarda no singleton
    yield                 ← a aplicação atende requisições aqui dentro
```

O `yield` está **dentro** dos dois `async with`. Não é estilo: o grafo só pode existir enquanto a
conexão do checkpointer existir.

### 9. Eventos de domínio saem do agente

De volta em `app/agents/conversa.py:116-129`, o loop traduz o que o grafo emite:

| Evento do LangGraph | Vira | Linha |
|---|---|---|
| `on_chat_model_stream` (com conteúdo, sem `tool_calls`) | `TokenGerado(texto)` | 124 |
| `on_tool_start` | `FerramentaIniciada(nome_tecnico)` | 127 |
| fim do stream | `TurnoConcluido()` | 129 |
| exceção | `ErroNoTurno()` | 133 |

O filtro `not getattr(chunk, "tool_calls", None)` (linha 122) é o que impede fragmentos de chamada
de ferramenta de vazarem como texto na tela.

`run_agent` **não sabe o que é SSE**. Ele emite objetos declarados em `app/agents/eventos.py`.

### 10. O endpoint traduz para bytes

`app/api/endpoints/chat.py:43`, `_para_sse`. É aqui — e só aqui — que:

- o vocabulário vira o formato de fio: `data: {"type": "token", ...}\n\n`;
- o **nome técnico da tool vira o texto que o usuário lê**, pelo `TOOL_STATUS_MAP`
  (`app/config/tool_status_map.py`). Tool sem entrada no mapa cai em `"Analisando..."` — e o
  `registry.py:126` avisa isso no log do startup.

### 11. De volta ao navegador

`frontend/js/chat.js:810-826` faz `JSON.parse` de cada linha `data: ` e despacha por `type`:
`token` acumula e re-renderiza o Markdown, `status` adiciona um passo no accordion de raciocínio,
`done` encerra o loop, `error` vira a bolha de erro com botão de tentar novamente.

O `leftover` (linhas 787-805) trata a linha SSE cortada pela fronteira do chunk de rede — sem isso,
um pedaço de JSON vazaria como texto na resposta.

---

## Fluxo 2 — o upload de um edital

`frontend/js/chat.js:438` envia `POST /upload/` como `multipart/form-data`. Em
`app/api/endpoints/upload.py`:

| Passo | O quê | Linha |
|---|---|---|
| 1 | Valida tipo e tamanho (20 MB) → `415` / `413` | 78-87 |
| 2 | `extrair_texto_pdf` (pdfplumber) | 97 |
| 3 | `extrair_cnpj` (regex + validate-docbr) | `app/ingestion/cnpj.py` |
| 4 | Indexa no Pinecone via `get_gerenciador().executar` | 114 |
| 5 | `gerar_relatorio_inicial` — **um turno completo do agente** | 151 |
| 6 | Responde com CNPJs + `relatorio_inicial` | 163 |

O passo 4 usa `asyncio.to_thread` porque o cliente do Pinecone é síncrono e bloquearia o event loop
— toda outra requisição em andamento travaria junto.

O passo 5 é o mais caro de todo o sistema: `app/agents/relatorio.py:68` chama `grafo.ainvoke()`
(sem streaming, ao contrário do fluxo 1) e, na sequência, `relatorio.py:82` faz uma **segunda**
chamada ao LLM com `with_structured_output(RelatorioInicial)` para transformar o Markdown em JSON.
São duas chamadas de LLM no melhor caso, mais as ferramentas que o agente decidir usar — tudo
dentro do request HTTP, com o cliente esperando.

Se qualquer coisa falhar aí, `relatorio.py` devolve `None` e o upload **continua bem-sucedido** com
`relatorio_inicial: null` — o relatório é um bônus de UX, não um requisito da indexação. No
frontend, `renderRelatorioInicial` (`chat.js:474`) simplesmente não desenha nada.

---

## Três coisas que não estão onde parecem

**1. A tool que executa não é a do arquivo da tool.** Passa por `aplicar_cache` no `registry.py`.
Ao depurar comportamento de ferramenta, abra `agents/tools/registry.py` e `agents/tools/cache.py`
antes de suspeitar da tool.

**2. O grafo não é construído na requisição.** É um singleton compilado no `lifespan`
(`agents/graph.py:19`). `get_graph()` levanta `RuntimeError` se for chamado fora do ciclo de vida do
FastAPI — é o que acontece ao importar um módulo e chamar o agente num script solto.

**3. O `SYSTEM_PROMPT` não está no histórico.** Ao inspecionar o checkpointer no Redis, você não vai
encontrá-lo: ele é preposto a cada chamada em `nodes/agente.py:17`.

---

## Como confirmar tudo isso sem subir nada

A suíte em `backend/tests/` percorre esses mesmos caminhos com um modelo falso e sem rede:

```bash
cd backend && pytest
```

`tests/test_grafo.py` cobre os passos 6 e 7 (ciclo ReAct, `SYSTEM_PROMPT`, injeção do
`ToolRuntime`), `tests/test_conversa.py` cobre os passos 4 e 9, e `tests/test_sse.py` cobre o
passo 10.
