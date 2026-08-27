# Variáveis de ambiente

Referência completa de cada chave usada pelo Auditor Cidadão. O template versionado é o `.env.example` na raiz do repositório — copie para `.env` e preencha antes de rodar (veja [Setup local](setup_local.md)).

Todas são lidas uma única vez em [`app/config/settings.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/config/settings.py), que aplica os defaults e os casts. Esse módulo não abre conexão nem instancia cliente: importar configuração é barato e livre de efeito colateral.

## LLM

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `LLM_MODEL` | Não | `openai:gpt-4o-mini` | Modelo do agente principal, no formato `provider:model-name`. Trocável para `groq:gpt-oss-120b` ou `google_genai:gemini-2.0-flash` sem mudar código — o provider precisa ter a chave correspondente preenchida e o pacote `langchain-<provider>` instalado |
| `LLM_TEMPERATURE` | Não | `0.1` | Temperatura do agente principal |
| `LLM_MAX_TOKENS` | Não | `4096` | Limite de tokens de saída do agente principal |
| `LLM_TIMEOUT_SEGUNDOS` | Não | `60` | Timeout por chamada ao LLM — sem ele, uma resposta lenta da OpenAI pode segurar o turno (e o streaming SSE) indefinidamente. Reusado pelo extrator (ver abaixo) |
| `LLM_MAX_RETRIES` | Não | `2` | Nº de retries por chamada ao LLM — menor que o default da lib (6) de propósito: no caminho síncrono de resposta ao usuário, falhar mais rápido (e deixar o evento `error` do SSE avisar) é preferível a segurar a requisição por vários minutos de retry. Reusado pelo extrator |
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
| `PINECONE_API_KEY` | **Sim** | — | Chave de acesso ao Pinecone |
| `PINECONE_INDEX_NAME` | Não | `auditor-cidadao` | Índice usado pelo `GerenciadorVetorial` ([`app/storage/vetorial.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/storage/vetorial.py)) e pelo job de limpeza. Criado automaticamente pelo Pinecone se não existir |
| `PINECONE_NAMESPACE` | Não | `production` | Namespace do Pinecone usado para indexar e buscar editais. Permite isolar conjuntos de dados (ex.: um namespace de testes) sem tocar no índice de produção |
| `PINECONE_RETENCAO_DIAS` | Não | `7` | Dias de retenção antes de um registro com `origem: "upload_usuario"` ser apagado pelo job de limpeza ([`app/jobs/limpeza_pinecone.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/jobs/limpeza_pinecone.py), ver [Uso de Dados e RAG](../ia/rag_dados.md#limpeza-de-dados-expirados)). Não afeta registros com outra origem |
| `TOP_K_EDITAL` | Não | `3` | Quantos trechos do edital a busca semântica (RAG) traz por pergunta — ver a tool [`buscar_contexto_edital`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/tools/contexto_edital.py) |

## Redis (checkpointer do grafo + rate limiting + cache de ferramentas)

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `REDIS_URI` | **Sim** | `redis://localhost:6379` | Precisa de uma instância Redis acessível (local, Docker ou gerenciada) — sem ela o **boot falha**. Duas conexões independentes usam essa mesma URI: o `AsyncRedisSaver` do histórico de conversa ([`app/storage/checkpointer.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/storage/checkpointer.py)) e um client `Redis` ([`app/storage/redis.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/storage/redis.py)) compartilhado entre o rate limiter ([`app/api/rate_limiter.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/rate_limiter.py)) e o cache de ferramentas ([`app/agents/tools/cache.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/agents/tools/cache.py), ver [Protocolo MCP](../arquitetura/protocolo_mcp.md#cache-das-ferramentas-aplicar_cache)) |
| `TTL_CHECKPOINT_MINUTOS` | Não | `1440` (24h) | Minutos de **inatividade** até o histórico de uma conversa expirar no Redis. Não é um TTL fixo desde a criação: cada leitura renova a contagem (`refresh_on_read=True`), então uma conversa em uso nunca expira no meio — só threads abandonadas são limpas. Use `-1` para desativar a expiração |

!!! note "Redis não vem embutido no container"
    O `Dockerfile` não instala Redis — é um serviço externo à aplicação (container separado
    localmente, add-on gerenciado no Railway). Ver [Setup local](setup_local.md) para como subir um
    Redis local rapidamente, e [Docker & Deploy](docker.md#deploy-em-producao-railway) para o passo
    a passo de provisionar o add-on no Railway (esquecer `REDIS_URI` lá gera um crash-loop
    característico no boot, documentado nessa página).

## Segurança: cookie de identificação de cliente

Usado para reconhecer o mesmo navegador entre requisições sem exigir login, como base do rate
limiting (ver [`app/api/cookies.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/cookies.py) e [`app/api/dependencies.py`](https://github.com/Moreira-89/auditor-cidadao/blob/main/backend/app/api/dependencies.py)).

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `COOKIE_SECRET_KEY` | **Sim, em produção** | chave aleatória gerada em memória no boot | Assina o cookie httpOnly `auditor_client_id`. Sem essa env var definida, cada processo gera sua própria chave aleatória no boot — em produção, com as 2 réplicas ativas hoje (ver [Docker & Deploy](docker.md#escalonamento-replicas-e-limites-de-recurso)), isso quebra a validação do cookie de forma intermitente, dependendo de qual réplica atende a requisição, sem sticky sessions no Railway. Defina sempre em produção |
| `AMBIENTE_PRODUCAO` | Não | `True` | Controla as flags `secure` e `samesite` do cookie. `True` (HTTPS, produção) usa `secure=True, samesite="none"` — necessário porque frontend e backend são serviços/domínios separados no Railway, o que torna a chamada do frontend uma requisição cross-site. Em dev local (`uvicorn` sem TLS), **precisa ser `False`** (`secure=False, samesite="lax"`) — com `True` fixo, o cookie nunca persiste entre requisições em `http://localhost`, e o rate limiter nunca reconhece o mesmo cliente duas vezes (bug silencioso: nenhum erro aparece, o limite simplesmente nunca dispara) |
| `CORS_ORIGINS` | **Sim, em produção** | vazio (nenhuma origem cross-site liberada) | URL(s) pública(s) do serviço de frontend no Railway autorizadas a chamar a API, separadas por vírgula (ex.: `https://auditor-cidadao.up.railway.app`). Sem essa variável, o navegador bloqueia toda chamada do frontend por CORS — a API só responde a requisições same-origin (dev local) |

## Fontes de dados oficiais (tools nativas)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `TAVILY_API_KEY` | Sim (para busca web) | Usada pela tool `buscar_informacao_web` |
| `CGU_API_KEY` | Sim (para sanções) | Usada pela tool `consultar_sancoes_empresa` (CEIS/CNEP). Obtida em `api.portaldatransparencia.gov.br/swagger-ui.html` |

!!! note "O que acontece se uma chave opcional faltar?"
    A aplicação sobe normalmente, mas a tool correspondente retorna um erro estruturado
    (`{"error": ...}`) em vez de derrubar a resposta inteira — o agente é instruído a tratar fonte
    indisponível como "não verificado", nunca como "sem irregularidades" (ver
    [Guardrails](../governanca/guardrails.md)). As únicas chaves cuja ausência impede o **boot**
    da aplicação são `OPENAI_API_KEY`, `PINECONE_API_KEY` e `REDIS_URI` (esta última tem um default
    válido para uso local, `redis://localhost:6379`, mas precisa de um Redis de verdade escutando
    nesse endereço).

## Frontend

O template versionado é [`frontend/.env.example`](https://github.com/Moreira-89/auditor-cidadao/blob/main/frontend/.env.example) — só uma variável, lida pelo Vite em **tempo de build**, não de runtime.

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `VITE_API_BASE_URL` | Não | `http://localhost:8000` | URL do backend que o app chama (upload + streaming SSE). Em produção, definida no serviço de frontend no Railway com a URL pública do serviço de backend — repassada como build arg ao `Dockerfile` (ver [Docker & Deploy](docker.md#frontend--build-da-imagem)) |
