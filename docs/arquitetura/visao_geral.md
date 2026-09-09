# Arquitetura do Sistema

Este pilar cobre a topologia **lógica** do Auditor Cidadão: como a pergunta de um usuário vira um
laudo de auditoria — o grafo do agente, o estado que ele carrega e as ferramentas que pode acionar.
Se você procura *onde* cada peça roda (Railway, container, serviços externos), isso está no pilar
[Operacional](../operacional/index.md); aqui o foco é o **raciocínio**, não a infraestrutura.

Todo o código do agente vive em
[`backend/app/agents/`](https://github.com/Moreira-89/auditor-cidadao/tree/main/backend/app/agents).

## O grafo do agente

O núcleo é um `StateGraph` do LangGraph montado explicitamente em
[`app/agents/graph.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/graph.py):
dois nós e uma aresta condicional entre eles, compilados uma vez no startup.

```python title="app/agents/graph.py:41-53"
grafo.add_node("agente", criar_no_agente(modelo))
# ToolNode executa a tool pedida e é quem injeta o ToolRuntime nas que o declaram.
grafo.add_node("ferramentas", ToolNode(tools))

grafo.add_edge(START, "agente")
# tools_condition devolve "tools" quando a última AIMessage traz tool_calls; o dict
# traduz esse retorno para o nome que o nó tem aqui.
grafo.add_conditional_edges(
    "agente", tools_condition, {"tools": "ferramentas", END: END}
)
grafo.add_edge("ferramentas", "agente")

return grafo.compile(checkpointer=checkpointer)
```

```mermaid
---
config:
  layout: dagre
  theme: redux-dark
  look: handDrawn
  fontFamily: '''Source Code Pro Variable'', monospace'
  themeVariables:
    fontFamily: '''Source Code Pro Variable'', monospace'
    fontSize: 25px
---
flowchart LR
    ENTRADA(["Pergunta do usuário"]) ==> LLM["agente"]
    LLM -- tem tool_calls? --> ROUTER{"tools_condition"}
    ROUTER -- sim --> TOOLS["ferramentas"]
    ROUTER -- não --> FIM(["__end__ → SSE"])
    TOOLS -- resultado da ferramenta --> LLM
```

É o ciclo **ReAct**: o modelo decide, as ferramentas executam, o modelo lê o resultado e decide de
novo, até responder sem pedir mais nada. `recursion_limit=50` (definido na chamada em
[`conversa.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/conversa.py))
é o teto que impede um loop infinito entre os dois nós.

O desenho completo dos dois pipelines ponta a ponta está em [Fluxo de Dados](fluxo_dados.md).

### O nó `agente`

[`app/agents/nodes/agente.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/nodes/agente.py)
é o único ponto do projeto onde o modelo principal é invocado. É uma função-fábrica: recebe o
modelo já com `bind_tools` aplicado e devolve o nó, o que deixa a assinatura que o LangGraph
inspeciona reduzida a `(state)` e torna o nó testável passando qualquer modelo.

```python title="app/agents/nodes/agente.py:16-21"
async def no_agente(state: AgentState) -> dict:
    resposta = await modelo.ainvoke(
        [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    )
    return {"messages": [resposta]}
```

O `SYSTEM_PROMPT` é **preposto a cada chamada**, não gravado no histórico. Três consequências
diretas: ele não é persistido pelo checkpointer, não se duplica a cada turno, e uma alteração no
prompt vale imediatamente até para conversas já em andamento.

### O nó `ferramentas`

É o `ToolNode` de `langgraph.prebuilt`, sem customização. Além de executar a ferramenta pedida, é
ele quem **injeta o `ToolRuntime`** nas tools que declaram esse parâmetro — o mecanismo que leva o
contexto geográfico até a busca vetorial no MongoDB, descrito na seção seguinte.

## O estado do grafo (`AgentState`)

[`app/agents/state.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/state.py)
estende `MessagesState` do LangGraph — que já traz `messages` com o reducer `add_messages`, ou seja,
cada nó **anexa** ao histórico em vez de sobrescrevê-lo — com três chaves próprias:

```python title="app/agents/state.py"
class AgentState(MessagesState):
    """Estado compartilhado entre os nós do grafo durante um turno de conversa."""

    estado: str
    municipio: str
    thread_id: str
```

`estado` e `municipio` são o contexto geográfico do edital em análise; `thread_id` é o
identificador do edital (a thread é 1:1 com o edital). Nenhum dos três faz parte da conversa e o
LLM nunca os lê diretamente: quem os consome são as tools que declaram `runtime: ToolRuntime`,
lendo `runtime.state["estado"]` etc. É esse trio que filtra a busca semântica para o edital certo
(ver [Uso de Dados e RAG](../ia/rag_dados.md)).

Como o checkpointer só persiste as chaves declaradas no schema, e quem sabe estado/município/thread
é quem chama o grafo, os três são **reenviados a cada turno** —
[`conversa.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/conversa.py).

## Persistência da conversa (checkpointer)

Um `AsyncRedisSaver` guarda o histórico por `thread_id`, aberto em
[`app/storage/checkpointer.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/storage/checkpointer.py)
e mantido vivo pelo `lifespan` durante toda a execução do processo. Isso faz a conversa sobreviver a
restarts e ficar acessível às duas réplicas em produção
(ver [Docker & Deploy](../operacional/docker.md#escalonamento-replicas-e-limites-de-recurso)).

A persistência não é indefinida. Cada thread expira após `TTL_CHECKPOINT_MINUTOS` de
**inatividade** (default 24h), e `refresh_on_read=True` renova essa contagem a cada leitura — uma
conversa em uso nunca expira no meio, só threads abandonadas são limpas.

```python title="app/storage/checkpointer.py:21"
ttl_config = {"default_ttl": TTL_CHECKPOINT_MINUTOS, "refresh_on_read": True}
```

O grafo só pode ser compilado **dentro** desse contexto — é ali que a conexão existe. Por isso o
`lifespan` ([`app/api/lifespan.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/lifespan.py))
mantém o `async with` aberto envolvendo o `yield`:

```python title="app/api/lifespan.py"
async with abrir_client_redis() as redis_client:
    tools = await montar_tools(redis_client)
    inicializar_rate_limiter(redis_client)

    # Pré-aquece os dois DocumentConverter do Docling (com e sem OCR) — carga
    # pesada de modelo, em thread pra não travar o event loop no startup.
    await asyncio.to_thread(inicializar_converters)

    async with abrir_checkpointer() as checkpointer:
        initialize_graph(tools=tools, checkpointer=checkpointer)
        logger.info("Servidor pronto para receber requests.")

        yield
```

O `inicializar_converters()` ([`app/ingestion/pdf_hierarquico.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/ingestion/pdf_hierarquico.py))
cria e chama `initialize_pipeline` em dois `DocumentConverter`: um com `do_ocr=True`, outro com
`do_ocr=False`. Manter os dois quentes custa RAM fixa (dois conjuntos de modelo de layout/tabela,
mais o de OCR), mas nenhuma requisição de `/upload/` paga carga de modelo, e não é preciso
recriar um converter só pra alternar OCR. Ver [Uso de Dados e RAG](../ia/rag_dados.md#o-pipeline-de-indexacao).

## Ferramentas disponíveis ao agente

| Origem | Ferramenta | O que faz |
|---|---|---|
| Nativa | [`consultar_receita_federal`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/tools/receita_federal.py) | Situação cadastral, CNAE, data de fundação (BrasilAPI) |
| Nativa | [`buscar_contexto_edital`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/tools/contexto_edital.py) | Busca semântica no edital indexado (MongoDB Atlas) |
| Nativa | [`consultar_sancoes_empresa`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/tools/sancoes.py) | Sanções ativas no CEIS/CNEP (Portal da Transparência) |
| Nativa | [`buscar_informacao_web`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/tools/busca_web.py) | Contexto complementar via Tavily |
| MCP (`@licinexusbr/mcp`) | 11 tools de PNCP | Licitações, contratos, itens, resultados, atas de RP — ver [Protocolo MCP](protocolo_mcp.md) |

Cada tool nativa é **um arquivo só**, contendo as duas metades: o `@tool` que o LLM enxerga (schema
`Annotated`/`Field`, a docstring — que é o texto lido pelo modelo para decidir se chama a
ferramenta —, validação de CNPJ e a tradução de falhas) e, abaixo, a função de rede pura, que
levanta exceção nativa e não sabe o que é um LLM.

Nenhuma tool nativa deixa exceção subir crua: todas devolvem `{"error": ...}` estruturado para o
LLM decidir como reagir, em vez de derrubar o turno.

!!! warning "A função registrada no grafo não é a que está no arquivo da tool"
    Antes de chegarem ao grafo, todas as tools passam por `aplicar_cache()` em
    [`app/agents/tools/registry.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/tools/registry.py),
    e o que o agente executa é o wrapper resultante. Ao depurar o comportamento de uma ferramenta,
    o `registry.py` é o segundo arquivo a abrir — ver
    [Cache das ferramentas](protocolo_mcp.md#cache-das-ferramentas-aplicar_cache).

### Montagem: `montar_tools()`

`registry.py` é o único lugar que responde "quais ferramentas o agente tem". Ele reúne as nativas,
conecta ao MCP, filtra a whitelist, aplica o patch de schema e envolve tudo com cache:

```python title="app/agents/tools/registry.py:147-163"
async def montar_tools(redis_client: Redis) -> list[BaseTool]:
    tools_mcp = await _obter_tools_mcp()

    tools = aplicar_cache(
        tools=TOOLS_NATIVAS,
        redis_client=redis_client,
        ttl_segundos=TTL_CACHE_TOOLS_SEGUNDOS,
        normalizadores=CACHE_KEY_NORMALIZERS,
    ) + aplicar_cache(
        tools=tools_mcp,
        redis_client=redis_client,
        ttl_segundos=TTL_CACHE_TOOLS_SEGUNDOS,
    )

    _conferir_mensagens_de_status(tools)
    logger.info("Total de ferramentas disponíveis para o agente: %d", len(tools))
    return tools
```

Duas verificações rodam no startup e transformam falhas silenciosas em avisos no log:

- **`_conferir_mensagens_de_status`** (`registry.py:126`) compara os nomes das tools montadas com as
  chaves de
  [`app/config/tool_status_map.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/config/tool_status_map.py),
  nos dois sentidos. Sem ela, uma tool sem mensagem cai no fallback `"Analisando..."` do streaming
  sem que ninguém perceba, e uma entrada órfã no mapa fica invisível.
- **Whitelist MCP não atendida** (`registry.py:114`): se um nome de `TOOLS_MCP_SELECIONADAS` não
  vier do servidor — porque o pacote renomeou a ferramenta, por exemplo —, sai um `WARNING` com o
  nome exato. Sem isso, a ferramenta simplesmente desapareceria do agente.

## Um único fluxo chama o grafo

[`agents/conversa.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/conversa.py)
(`run_agent()`) é o único ponto de entrada do grafo, tanto para uma pergunta real do usuário quanto
para o relatório automático pós-upload — a diferença entre os dois é só qual texto vira a "pergunta"
(`PROMPT_RELATORIO_INICIAL` no automático, ver `app/api/endpoints/chat.py`), nunca o caminho de
código. O golden dataset da avaliação (`backend/evaluation/`) roda exatamente esse mesmo
`run_agent()`, pelo mesmo motivo.

[`agents/envelope.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/envelope.py)
tem `escape_xml()` (guardrail anti prompt-injection, ver [Guardrails](../governanca/guardrails.md))
e `montar_primeiro_turno()`, que monta o `PROMPT_DINAMICO` com CNPJs, estado, município e data — o
primeiro `HumanMessage` de toda thread nova, seja ela aberta por uma pergunta ou pelo relatório
automático.

### Streaming: eventos de domínio e o formato de fio

`run_agent()` consome `grafo.astream_events(version="v2")` e traduz o que acontece no grafo
em **eventos de domínio** — objetos que dizem o que aconteceu, sem saber como serão transmitidos.
O vocabulário está em
[`app/agents/eventos.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/eventos.py): `TokenGerado`, `FerramentaIniciada`,
`TurnoConcluido` e `ErroNoTurno`.

```python title="app/agents/conversa.py:116-129"
if evento["event"] == "on_chat_model_stream":
    # getattr com default: chunks intermediários podem não ter o atributo tool_calls
    chunk = evento["data"].get("chunk")
    if chunk is not None and chunk.content and not getattr(chunk, "tool_calls", None):
        yield TokenGerado(chunk.content)

elif evento["event"] == "on_tool_start":
    yield FerramentaIniciada(evento["name"])

yield TurnoConcluido()
```

O filtro `not getattr(chunk, "tool_calls", None)` é o que impede que fragmentos de uma chamada de
ferramenta apareçam como texto na tela. `evento["name"]`, no `on_tool_start`, é o nome técnico da
**tool**.

Quem transforma esses eventos em bytes é o endpoint,
[`app/api/endpoints/chat.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/endpoints/chat.py) — a única camada que sabe o que é
Server-Sent Events. É também onde o nome técnico vira o texto que o usuário lê:

```python title="app/api/endpoints/chat.py:43-54"
def _para_sse(evento: EventoDoTurno) -> str:
    match evento:
        case TokenGerado(texto):
            return _linha_sse("token", texto)
        case FerramentaIniciada(nome):
            # É aqui que o nome técnico da tool vira o texto que o usuário lê.
            return _linha_sse("status", TOOL_STATUS_MAP.get(nome, "Analisando..."))
        case TurnoConcluido():
            return _linha_sse("done")
        case ErroNoTurno():
            return _linha_sse("error", MENSAGEM_ERRO_GENERICA)
```

Essa fronteira é o que permite consumir o agente sem HTTP: um teste afirma
`FerramentaIniciada("buscar_contexto_edital")` em vez de comparar strings `data: ...`, e um
consumidor futuro (uma fila, um WebSocket) recebe objetos em vez de bytes de SSE.

Nenhum turno faz extração estruturada: a resposta sempre chega ao frontend como Markdown livre. O
relatório automático é só o primeiro turno da thread, disparado pelo frontend logo após o upload
(via `inicial: true`) e streamado como qualquer outro.

!!! note "Histórico interrompido no meio de uma `tool_call`"
    Se o usuário interromper a execução de uma ferramenta, o checkpointer fica com uma `AIMessage`
    cujos `tool_calls` nunca foram respondidos — e a OpenAI rejeita qualquer mensagem nova nessa
    thread com `400` enquanto isso não for corrigido.

    `_curar_tool_calls_pendentes()`
    ([`conversa.py:15`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/conversa.py))
    detecta esse estado no início do próximo turno: compara os `tool_calls` da última `AIMessage`
    com os `tool_call_id` já respondidos e injeta uma `ToolMessage` sintética
    (`"Chamada cancelada..."`) para cada pendência, via `grafo.aupdate_state()`. O histórico volta a
    ser válido sem descartar a conversa.

## Identificação do cliente: cookie assinado e CORS cross-site

O rate limiting (`app/api/rate_limiter.py`) precisa identificar o mesmo navegador entre
requisições. `get_client_id` (`app/api/dependencies.py`) faz isso com um cookie httpOnly
assinado (`auditor_client_id`) em vez de IP — IP é fraco para essa finalidade (troca com
rede móvel/VPN, e vários usuários atrás do mesmo NAT caem no mesmo limite). O cookie é
gerado na primeira visita e reconhecido nas seguintes; sendo assinado, o cliente não
consegue forjar nem adulterar o valor para escapar do limite.

**As três flags do cookie** (`response.set_cookie` em `dependencies.py`) variam com o
ambiente por um motivo concreto:

- `httponly=True` — impede um ataque XSS de ler ou forjar o cookie via JavaScript.
- `secure=AMBIENTE_PRODUCAO` — em produção, só HTTPS reenvia o cookie (comportamento
  desejado). Fixo em `True` quebraria o dev local: `uvicorn` sem TLS não teria o cookie
  reenviado nunca, e o rate limiter trataria toda requisição como um cliente novo — um
  bug silencioso, sem erro algum aparecendo.
- `samesite="none" if AMBIENTE_PRODUCAO else "lax"` — front e back são domínios separados
  no Railway, então toda chamada do frontend é cross-site em produção; `"lax"` bloquearia
  o cookie nela. `"none"` exige `Secure` (garantido pela flag acima) e `allow_credentials=True`
  no CORS (`main.py`) para o navegador aceitar enviar/receber o cookie entre origens
  diferentes. Em dev, front e back normalmente compartilham origem, então `"lax"` basta.

**Cookie perdido em resposta de erro.** Por padrão, o FastAPI descarta o `Response` que uma
dependency já tinha modificado sempre que uma exceção interrompe a requisição — junto vai
qualquer `Set-Cookie` gravado nele. Sem correção, um visitante novo cujo primeiro request
falhasse por qualquer motivo (415, 422, 429...) nunca receberia o cookie, e seguiria sendo
tratado como "visitante novo" a cada tentativa. `get_client_id` guarda uma cópia do header
em `request.state.cookie_pendente`; os exception handlers centrais em `main.py`
(`_reaplicar_cookie_pendente`) reaplicam esse cookie em qualquer resposta de erro da
requisição, não só a do rate limiter.

### O contador atômico do rate limiter (script Lua no Redis)

`app/api/rate_limiter.py` conta requisições por `client_id` num script Lua, executado
**dentro** do Redis (`EVAL`/`EVALSHA`) em vez de em Python:

```lua
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('GET', key)

if current and tonumber(current) >= limit then
    return -1
else
    local count = redis.call('INCR', key)
    if count == 1 then
        redis.call('EXPIRE', key, window)
    end
    return count
end
```

`KEYS[1]` é a chave do contador (`"<prefixo>:<client_id>"`, ex.: `"upload:abc123"`);
`ARGV[1]`/`ARGV[2]` são o limite e a duração da janela em segundos. Por que Lua e não um
`GET` + `INCR` em Python: entre ler o valor atual e decidir se incrementa, duas
requisições concorrentes do mesmo cliente poderiam ler o mesmo contador "quase no limite"
e as duas passarem — o script roda como uma unidade atômica dentro do Redis, sem essa
janela de corrida.

Passo a passo do script:

1. Lê o contador atual (`GET`) — pode não existir ainda (primeira requisição do cliente).
2. Se já atingiu o limite, devolve `-1` **sem incrementar** — o contador não sobe
   indefinidamente enquanto o cliente insiste dentro da mesma janela.
3. Caso contrário, incrementa (`INCR` cria a chave com valor 1 se não existir) e, só na
   primeira requisição da janela (`count == 1`), define o TTL (`EXPIRE`). O Redis apaga a
   chave sozinho quando o TTL expira — reinicia a contagem sem limpeza manual.
4. Devolve o contador pós-incremento, para `RateLimiter.__call__` logar o consumo sem
   precisar de um segundo round-trip (`GET`) só para isso.

`inicializar_rate_limiter` registra esse script uma vez no startup
(`redis_client.register_script`); a lib então usa `EVALSHA` (reenvia só o hash do script)
nas chamadas seguintes, em vez do texto completo.

## Limitações conhecidas

As limitações desta arquitetura — incluindo o alcance real do rate limiting e o que o sistema
sinaliza mas não prova — estão consolidadas em
[Limitações conhecidas](../governanca/limitacoes.md), junto das demais.
