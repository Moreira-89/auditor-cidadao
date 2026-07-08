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

## O nome do usuário deixou de ser coletado

Uma decisão explícita de minimização de dados: a coleta do nome do usuário foi **removida de ponta a
ponta** — do schema de requisição (`PerguntaRequest`), dos endpoints, do `SYSTEM_PROMPT` e do
formulário do frontend. O `PerguntaRequest` hoje (`app/models/pergunta_request.py`) carrega apenas
`pergunta`, `estado`, `municipio`, `lista_cnpjs` e `thread_id` — nenhum campo identifica a pessoa que
está usando o sistema. Isso reduz a superfície de dado pessoal coletado ao mínimo necessário para a
função.

## Retenção de editais no Pinecone: decisão deliberada

Os editais indexados permanecem no banco vetorial (Pinecone) por tempo indeterminado — e isso é uma
decisão consciente, não um descuido. O racional:

- O conteúdo de um edital é documento público; não há dado pessoal sensível envolvido.
- A retenção viabiliza o **cruzamento histórico** planejado para a V2 (ex.: uma tool
  `buscar_historico_empresa` que cruza uma empresa sancionada em um município com um padrão
  semelhante em outro) — ver [Próximos Passos](limitacoes.md).

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

!!! info "Requisitos cobertos por este pilar"
    | Requisito | O que esta seção resolve |
    |---|---|
    | **T6** — Ética, privacidade e responsabilidade (LGPD) | Minimização de dados, retenção deliberada |
