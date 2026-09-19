# Roteiro v2 — Apresentação guiada pela documentação

> Formato diferente do v1 (`roteiro.md`, feito pro deck HTML): aqui **a documentação publicada é a
> apresentação**. Duas telas — nesta (o roteiro) você lê o que dizer e até onde ir; na outra, a
> documentação (`https://moreira-89.github.io/auditor-cidadao/`) aberta na página indicada.
>
> **Regra de ouro, porque a doc é longa:** você nunca lê a página em voz alta. Você abre a seção
> certa, aponta, e fala o que já sabe — o parágrafo cheio existe pra quem quiser conferir depois,
> não pra você recitar. Se sentir que está entrando fundo demais numa seção, é sinal de parar e
> passar pra próxima.
>
> Mesmo orçamento de tempo do v1: **~50 min de fala + demo**, deixando **~30 min** de perguntas
> dentro de 1h30 total. Banca técnica — pode nomear campo, classe e função reais.

## Antes de começar

- [ ] Duas telas configuradas: uma com este arquivo (ou impresso), outra com o navegador na doc
- [ ] Edital de exemplo baixado (você mesmo decide como compartilhar o link/QR na hora)
- [ ] Plataforma publicada no ar (`auditor-cidadao-production.up.railway.app`) — conferida antes
- [ ] Internet estável — tanto a doc quanto a demo dependem disso
- [ ] Abas do navegador pré-abertas nas páginas abaixo, na ordem, pra não perder tempo navegando

---

## Bloco 1 — Abertura (≈ 9 min)

**Página:** `README.md` do repositório (github.com/Moreira-89/auditor-cidadao) — ou a home da doc
(`/`), que resume o mesmo conteúdo.

### O problema — 2 min
Fale de cabeça, sem precisar de página aberta ainda: fiscalizar uma licitação exige cruzar
manualmente PNCP, Receita Federal e CEIS/CNEP — trabalho de especialista. **Antes disso**,
contextualize em 1 frase o que é uma licitação (parte da banca pode não ser da área): processo
pelo qual um órgão público é obrigado por lei a comprar/contratar, empresa vencedora escolhida por
critério do edital — é aí que mora o risco de fraude.

### Como funciona, na teoria — 2 min
Abra o README na seção **"📋 O caso"** e **"✨ Destaques"** — aponte a tabela de destaques (upload +
relatório automático, agente de auditoria, streaming, guardrails) sem ler célula por célula.

### Por que não ChatGPT/Claude direto — 2:30
Não tem página própria na doc — fale direto, é o argumento mais "de venda" da apresentação:
ChatGPT/Claude não acessam PNCP/Receita/CEIS-CNEP de verdade, só direcionam. Replicar isso manual
exige conhecimento técnico que jornalista/cidadão comum não tem. **Frase de efeito:** "não é sobre
o modelo ser melhor — é sobre ter acesso automatizado às ferramentas certas."

### Stack — 1:30
README, seção **"🛠️ Stack tecnológica"** — a tabela já está pronta, só apontar. Não justificar cada
escolha aqui.

---

## Bloco 2 — Catálogo de anomalias (≈ 2 min)

**Página:** `ia/anomalias.md`

Abra direto na seção **"As 9 categorias"** — passe rápido pelas letras A–I sem ler os critérios
completos (a banca lê sozinha se quiser). Feche apontando a tabela **"Cobertura real hoje"** no fim
da página: 7 das 9 já verificáveis, sobrepreço e cartel ainda dependem de integração futura.

---

## 🛑 PAUSA — DEMONSTRAÇÃO AO VIVO (≈ 12–15 min)

**Aqui você para de navegar a documentação.** Este é o momento de sair da doc, compartilhar o link
ou QR code da plataforma do jeito que preferir, e subir um edital real com a banca acompanhando.
(Como compartilhar o acesso fica com você — só o gancho de quando parar está aqui.)

**Roteiro sugerido da demo** (mesmo do v1):
1. Sobe o PDF na plataforma.
2. Mostra a indexação acontecendo.
3. Deixa o relatório automático ser gerado — chama atenção pro streaming e pros status de
   ferramenta aparecendo.
4. Faz 1-2 perguntas de acompanhamento ao vivo.
5. Fecha a demo e volta pra documentação, retomando no Bloco 3 abaixo.

**Atenção:** combine um teto de tempo com você mesmo (ex.: 15 min) — se a demo não sair redonda,
corte e continue. É a parte de maior risco de esticar o tempo total.

---

## Bloco 3 — Arquitetura, RAG e persistência (≈ 13 min)

### Arquitetura do agente — o grafo — 2:30
**Página:** `arquitetura/visao_geral.md`, seção **"O grafo do agente"**.
Mostre o diagrama Mermaid do ciclo (`agente` → `router` → `ferramentas` → volta) e o trecho de
código do `graph.py` logo acima. Fale do `AsyncRedisSaver` (seção **"Persistência da conversa"**
mais abaixo na mesma página) — histórico por thread, expira em 24h de inatividade.

### Ferramentas & protocolo MCP — 2 min
**Página:** mesma (`visao_geral.md`), seção **"Ferramentas disponíveis ao agente"** — a tabela já
lista as 4 nativas + as 11 de PNCP via MCP. Se quiser aprofundar o *como* o MCP carrega, pule pra
`arquitetura/protocolo_mcp.md` (diagrama de carregamento no startup) — mas só se sobrar tempo.

### RAG — indexação e recuperação — 3 min
**Página:** `ia/rag_dados.md`.
Abra em **"O pipeline de indexação"** — mostre o exemplo real de documento gravado (o bloco de
código JSON com `secao_ordem`, `secao_texto_completo`) logo abaixo do texto sobre Docling. Desça até
**"O pipeline de busca"** pra mostrar o código do `$vectorSearch` com `top_k=3` e o dedup por
`secao_ordem`. **Não precisa ler o código Python linha por linha** — aponte os nomes de campo
enquanto fala do padrão pai-filho.

### Persistência e limpeza de dados — 2:30
**Pergunta que a banca provavelmente vai fazer — responda antes.**
**Página:** `operacional/index.md`, seção **"Onde e como isso roda em produção"**, pro diagrama de
topologia (mostra o MongoDB Atlas entre os serviços externos) — depois pule pra `governanca/lgpd.md`,
seção **"Retenção de editais (MongoDB)"**
pra regra real: chunk apagado quando `origem == "upload_usuario"` **e** mais antigo que
`MONGO_RETENCAO_DIAS` (2 dias por padrão), job `limpeza_mongo.py` pensado pra cron, termina com erro
explícito se falhar. Mencione que outras origens (indexação futura via PNCP) não são afetadas por
essa expiração.

### Anatomia de um turno — 2:30
**Página:** `arquitetura/anatomia_de_um_turno.md`.
Tem dois fluxos na página — role até **"Fluxo 1 — uma pergunta no chat, em 6 paradas"** pro diagrama
de sequência, e **"Fluxo 2 — o upload de um edital"** logo abaixo. Ponto que costuma gerar pergunta:
seção **"De volta à superfície: eventos viram SSE"** — o `SYSTEM_PROMPT` nunca fica salvo no
histórico do Redis, é preposto a cada chamada.

---

## Bloco 4 — Guardrails e avaliação (≈ 9 min)

### Guardrails de segurança — 2:30
**Página:** `governanca/guardrails.md`.
A página já tem o exemplo real pronto — seção **"Exemplo real: uma tentativa de injeção via
`municipio`"**, com o antes/depois do `escape_xml()`. Abra direto nela, é mais forte que descrever
de memória. Complemente com **"Anti-alucinação"** mais abaixo (vocabulário emprestado, hierarquia de
evidências).

### Metodologia de avaliação — 2:30
**Página:** `ia/avaliacao.md`.
Seção **"As quatro métricas"** tem a tabela (Tool Correctness, Argumentos, Fidelidade, Cobertura/
Recall) com limiar e se usa LLM. Se quiser mostrar a rubrica do juiz, está logo abaixo em
**"Fidelidade: como o juiz decide a nota"** — o bloco de código com as 5 notas. O exemplo de caso
**sintético** (H — sanção vigente) está na tabela de **"O golden dataset"**, mais acima na mesma
página; pra citar um caso **real** de exemplo, `caso_02_saoluis_sancao` aparece como exemplo de
comando na seção **"Rodando"**, mais abaixo.

### Resultados da avaliação — 2:30
**Página:** mesma (`avaliacao.md`), role até **"Estado atual do veredito"** — os dois admonitions
verdes (`real` 4/4, `sintético` 9/9 estável em 3 rodadas) são o "gráfico" desta versão.

**Se perguntarem por que Fidelidade (0,89–0,99) é mais baixa que as outras:** é a única métrica
semântica (G-Eval/juiz LLM), as outras são determinísticas ou recall binário — uma extrapolação
pequena de texto já custa ponto na rubrica.

### Custo real do MVP — 1:30
**Sem página própria na doc — fale direto, os números estão aqui:**
R$ 220,33 gastos até hoje: Maritaca AI R$ 40, OpenAI R$ 103,05, MongoDB Atlas free, Railway R$ 77,28
(plano "Hobby", US$5/mês). É um MVP pra validar a ideia, não a arquitetura final.

---

## Bloco 5 — Fechamento (≈ 3 min)

### Limitações e próximos passos — 2:30
**Página:** `governanca/limitacoes.md`.
Role até **"Backlog V2"** — não leia a lista inteira, escolha 2-3 pra destacar em voz alta (sugestão:
migração de nuvem em **"Escalabilidade e persistência"**, autenticação, indexação automática via
PNCP em **"Fase 7"**). Os itens mais recentes — controle de contexto, tokenização real, e a ideia de
observabilidade — também estão nessa página, cada um com sua própria seção.

### Obrigado — 0:30
Fechar e abrir pra perguntas.

---

## Se o tempo apertar

Corte nesta ordem:
1. Protocolo MCP (arquitetura/protocolo_mcp.md) — mencione que existe, sem abrir a página.
2. Detalhamento do catálogo de anomalias — mostre só a tabela de cobertura no fim da página.
3. Fluxo 2 (upload) em `anatomia_de_um_turno.md` — foque só no Fluxo 1 (a pergunta no chat).

**Nunca corte:** a diferenciação vs. ChatGPT/Claude, a demo ao vivo, guardrails (o exemplo de
injeção é forte), os resultados da avaliação e o custo real — são os pontos que mais seguram a
atenção e respondem o que a banca mais provavelmente vai perguntar.
