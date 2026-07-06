# Variáveis de ambiente

Referência completa de cada chave usada pelo Auditor Cidadão. O template versionado está em
`.env.example`, na raiz do repositório — copie para `.env` e preencha antes de rodar o projeto
(veja [Setup local](setup_local.md)).

## LLM

| Variável | Obrigatória | Default | Descrição |
|---|---|---|---|
| `LLM_MODEL` | Não | `openai:gpt-4o-mini` | Modelo do agente principal, no formato `provider:model-name`. Trocável para `groq:llama-3.3-70b-versatile` ou `google_genai:gemini-2.0-flash` sem mudar código — o provider precisa ter a chave correspondente preenchida e o pacote `langchain-<provider>` instalado |
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

| Variável | Obrigatória | Descrição |
|---|---|---|
| `PINECONE_API_KEY` | **Sim** | Índice utilizado: `auditor-cidadao`, criado automaticamente pelo Pinecone se não existir |

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
    da aplicação são `OPENAI_API_KEY` e `PINECONE_API_KEY`.
