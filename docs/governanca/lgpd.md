# LGPD e Privacidade

O Auditor Cidadão lida com dados de empresas e de contratações públicas — a maioria é dado público
por natureza, mas isso não dispensa cuidado com privacidade. Esta página descreve o que é coletado,
o que **deixou de ser** coletado, e as decisões deliberadas de retenção.

## Que dados o sistema usa

| Dado | Natureza | Origem |
|---|---|---|
| Texto do edital (PDF) | Público (documento oficial de licitação) | Upload do usuário |
| CNPJ das empresas | Público | Extraído do edital / informado |
| Dados cadastrais (razão social, CNAE, endereço) | Público | Receita Federal via BrasilAPI |
| Sanções (CEIS/CNEP) | Público | Portal da Transparência |
| Licitações e contratos | Público | PNCP |

Todos os dados processados são de **pessoa jurídica** e de **acesso público** — não há coleta de
dado pessoal sensível de pessoa física no fluxo principal.

## Retenção do histórico de conversa: expira por inatividade, não fica indefinido

O histórico de uma conversa (`thread_id`, guardado no Redis via `AsyncRedisSaver`) expira
automaticamente após `TTL_CHECKPOINT_MINUTOS` minutos sem nenhuma leitura ou escrita nessa thread —
1440 minutos (24h) por padrão. Cada interação renova a contagem, então uma conversa em uso nunca é
apagada no meio; só threads abandonadas são limpas. Isso é uma prática de minimização de dados: o
sistema não acumula histórico de conversa indefinidamente sem necessidade, diferente da retenção
deliberadamente indeterminada do conteúdo dos editais no Pinecone (ver seção abaixo, que tem um
racional de retenção diferente e documentado à parte).

## O cookie de sessão é um identificador pseudônimo, não dado pessoal identificável

Desde a introdução do rate limiting (ver [Limitações conhecidas](limitacoes.md)), o navegador do
usuário recebe um cookie httpOnly (`auditor_client_id`, ver `app/utils/cookie_manager.py`) contendo
um UUID gerado aleatoriamente — sem relação com nome, e-mail, CPF ou qualquer outro dado que
identifique a pessoa diretamente. Ele existe só para contar requisições por navegador dentro de uma
janela de tempo (5/dia em `/upload/`, 50/dia em `/conversar-com-auditor/`) e expira em 30 dias.

Vale registrar por transparência, mesmo sendo um identificador de baixo risco:

- **Não é rastreamento entre sessões de navegação nem perfilamento** — o único uso é contagem de
  quota; nenhum outro dado é associado ao `client_id` (não há histórico de perguntas vinculado a
  ele, por exemplo — isso é associado ao `thread_id`, gerado à parte pelo frontend).
- **`httpOnly` e assinado** — JavaScript no navegador não lê o valor, e o servidor rejeita qualquer
  cookie adulterado (ver `verificar_cookie()`), então não há como um terceiro forjar a identidade de
  outro cliente através dele.
- **O usuário controla a retenção** — limpar cookies do navegador invalida o identificador
  imediatamente (efeito colateral: reseta a quota também, ver limitação correspondente).

## O nome do usuário deixou de ser coletado

Uma decisão explícita de minimização de dados: a coleta do nome do usuário foi **removida de ponta a
ponta** — do schema de requisição (`PerguntaRequest`), dos endpoints, do `SYSTEM_PROMPT` e do
formulário do frontend. O `PerguntaRequest` hoje (`app/models/pergunta_request.py`) carrega apenas
`pergunta`, `estado`, `municipio`, `lista_cnpjs` e `thread_id` — nenhum campo identifica a pessoa que
está usando o sistema. Isso reduz a superfície de dado pessoal coletado ao mínimo necessário para a
função.

## Retenção de editais no Pinecone: decisão deliberada, e agora com prazo configurável

Os editais indexados via upload (`origem: "upload_usuario"`) têm retenção configurável, não
indeterminada: `app/jobs/limpeza_pinecone.py`, rodado periodicamente (ex.: cron no Railway), apaga
os registros cujo `timestamp_indexacao` seja mais antigo que `PINECONE_RETENCAO_DIAS` (default 7
dias — ver [Variáveis de ambiente](../operacional/variaveis_ambiente.md)). O racional:

- O conteúdo de um edital é documento público; não há dado pessoal sensível envolvido — a limpeza
  é uma prática de minimização de dados, não uma exigência legal de anonimização.
- Um prazo curto (dias, não meses) é suficiente para o caso de uso principal: o cidadão analisa um
  edital específico dentro de uma janela curta de tempo; manter o vetor indexado indefinidamente
  depois disso não agrega valor e amplia a superfície de dado armazenado sem necessidade.
- O filtro do job usa também `origem: "upload_usuario"` — outras origens (ex.: uma futura
  indexação automática via PNCP, ver [Próximos Passos](limitacoes.md)) podem ter um racional de
  retenção diferente e não são afetadas por essa expiração.

!!! note "O que muda na V2 (e por que é relevante para a LGPD)"
    A migração planejada troca o metadado de indexação de `municipio`/`estado` (informados
    manualmente) para `cnpjs` (extraídos automaticamente). Como isso amplia o cruzamento por
    empresa, o roadmap prevê citar essa capacidade explicitamente na documentação de ética como
    parte da visão de produto — transparência sobre o que o sistema passará a correlacionar.

## Limite de coleta por requisição

O `PerguntaRequest.lista_cnpjs` tem um `field_validator` que corta a lista em 10 CNPJs e descarta os
matematicamente inválidos (via `validate-docbr`), logando tentativas de exceder o limite. Além de
controlar custo de token, isso limita quanto um cliente adulterado pode empurrar de dado numa única
requisição.
