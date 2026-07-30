# Variáveis de ambiente

Referência completa de cada chave usada pelo Auditor Cidadão. O template versionado está em `.env.example`, na raiz do repositório — copie para `.env` e preencha antes de rodar o projeto (veja [Setup local](setup_local.md)).

## LLM

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `LLM_MODEL` | Não | `openai:gpt-4o-mini` | Modelo do agente principal, no formato `provider:model-name`. Trocável para `groq:gpt-oss-120b` ou `google_genai:gemini-2.0-flash` sem mudar código — o provider precisa ter a chave correspondente preenchida e o pacote `langchain-<provider>` instalado |
| `LLM_TEMPERATURE` | Não | `0.1` | Temperatura do agente principal |
| `LLM_MAX_TOKENS` | Não | `4096` | Limite de tokens de saída do agente principal |
| `EXTRATOR_MODEL` | Não | `openai:gpt-4o-mini` | Modelo usado só para extrair o laudo estruturado (JSON) a partir do Markdown já gerado. Separado do `LLM_MODEL` para permitir trocar um sem afetar o outro |
| `EXTRATOR_TEMPERATURE` | Não | `0.0` | Temperatura do extrator — fixa em zero porque a tarefa é extração determinística, não geração criativa |

## Chaves de API dos provedores de LLM

| Variável | Obrigatória | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | **Sim, sempre** | Mesmo que `LLM_MODEL`/`EXTRATOR_MODEL` usem outro provider, os embeddings do RAG (`text-embedding-3-small`) sempre passam pela OpenAI |
| `GROQ_API_KEY` | Só se usar Groq | Obrigatória apenas se `LLM_MODEL` ou `EXTRATOR_MODEL` apontarem para `groq:...` |
| `GOOGLE_API_KEY` | Só se usar Gemini | Obrigatória apenas se `LLM_MODEL` ou `EXTRATOR_MODEL` apontarem para `google_genai:...` |

## Banco de dados vetorial

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `PINECONE_API_KEY` | **Sim** | — | Índice utilizado: `auditor-cidadao`, criado automaticamente pelo Pinecone se não existir |
| `PINECONE_NAMESPACE` | Não | `production` | Namespace usado para indexar/buscar editais. O framework de avaliação sobrescreve essa env var em tempo de execução para isolar dados de teste do namespace de produção |
| `TOP_K_EDITAL` | Não | `3` | Quantos trechos do edital a busca semântica (RAG) traz por pergunta — ver a tool `buscar_contexto_edital` em `app/services/tools.py` |

## Redis (checkpointer do grafo + rate limiting)

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `REDIS_URI` | **Sim** | `redis://localhost:6379` | Precisa de uma instância Redis acessível (local, Docker ou gerenciada) — sem ela o **boot falha**. Duas conexões independentes usam essa mesma URI: o `AsyncRedisSaver` (histórico de conversa por `thread_id`, ver `app/services/lifespan.py`) e o rate limiter (contagem de requisições por cliente, ver `app/services/rate_limiter.py`) |
| `TTL_CHECKPOINT_MINUTOS` | Não | `1440` (24h) | Minutos de **inatividade** até o histórico de uma conversa expirar no Redis. Não é um TTL fixo desde a criação: cada leitura renova a contagem (`refresh_on_read=True`), então uma conversa em uso nunca expira no meio — só threads abandonadas são limpas. Use `-1` para desativar a expiração |

!!! note "Redis não vem embutido no container"
    O `Dockerfile` não instala Redis — é um serviço externo à aplicação (container separado
    localmente, add-on gerenciado no Railway). Ver [Setup local](setup_local.md) para como subir um
    Redis local rapidamente.

## Segurança: cookie de identificação de cliente

Usado para reconhecer o mesmo navegador entre requisições sem exigir login, como base do rate
limiting (ver `app/utils/cookie_manager.py` e `app/api/dependencies_http.py`).

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `COOKIE_SECRET_KEY` | Recomendada | chave aleatória gerada em memória no boot | Assina o cookie httpOnly `auditor_client_id`. Sem essa env var definida, a chave muda a cada restart do processo (ou entre workers, se houver mais de um) e os cookies emitidos antes deixam de ser válidos — defina sempre em produção |
| `AMBIENTE_PRODUCAO` | Não | `True` | Controla a flag `secure` do cookie. `True` (HTTPS, produção) faz o navegador só reenviar o cookie em conexões seguras. Em dev local (`uvicorn` sem TLS), **precisa ser `False`** — com `True` fixo, o cookie nunca persiste entre requisições em `http://localhost`, e o rate limiter nunca reconhece o mesmo cliente duas vezes (bug silencioso: nenhum erro aparece, o limite simplesmente nunca dispara) |

## Fontes de dados oficiais (tools nativas)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `TAVILY_API_KEY` | Sim (para busca web) | Usada pela tool `buscar_informacao_web` |
| `CGU_API_KEY` | Sim (para sanções) | Usada pela tool `consultar_sancoes_empresa` (CEIS/CNEP). Obtida em `api.portaldatransparencia.gov.br/swagger-ui.html` |

## Avaliação (RAGAS)

Usadas apenas pelo framework de avaliação (`evaluation/pipeline_avaliacao.py`), fora do caminho de
boot da API principal.

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `AVALIADOR_MODEL` | Não | `openai:gpt-4o-mini` | Modelo usado pelo RAGAS para julgar as métricas do golden dataset |
| `AVALIADOR_TEMPERATURE` | Não | `0.0` | Temperatura do avaliador — fixa em zero pelo mesmo motivo do extrator: julgamento determinístico |

!!! note "O que acontece se uma chave opcional faltar?"
    A aplicação sobe normalmente, mas a tool correspondente retorna um erro estruturado
    (`{"error": ...}`) em vez de derrubar a resposta inteira — o agente é instruído a tratar fonte
    indisponível como "não verificado", nunca como "sem irregularidades" (ver
    [Guardrails](../governanca/guardrails.md)). As únicas chaves cuja ausência impede o **boot**
    da aplicação são `OPENAI_API_KEY`, `PINECONE_API_KEY` e `REDIS_URI` (esta última tem um default
    válido para uso local, `redis://localhost:6379`, mas precisa de um Redis de verdade escutando
    nesse endereço).
