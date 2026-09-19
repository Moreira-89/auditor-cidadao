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

## Bloco 1 — Abertura (≈ 8:30)

**Página:** `README.md` do repositório (github.com/Moreira-89/auditor-cidadao) — ou a home da doc
(`/`), que resume o mesmo conteúdo.

### O problema — 2:30
Não tem página própria — fale de cabeça, é a abertura, então merece estar bem mastigada.

**O que é uma licitação, em 1 frase** (parte da banca pode não ser da área): é o processo pelo qual
um órgão público — prefeitura, governo estadual, autarquia — é **obrigado por lei** (Lei
14.133/2021) a abrir concorrência antes de comprar um bem ou contratar um serviço, em vez de
escolher livremente um fornecedor. A empresa vencedora é definida por critérios fixados no
**edital** (o documento que rege aquela contratação específica): menor preço, melhor técnica, ou
uma combinação das duas.

**Onde mora o risco.** Justamente porque o processo é regrado, ele também pode ser manipulado por
dentro das próprias regras: um edital pode ser escrito com uma especificação técnica tão específica
que só uma empresa combinada de antemão consegue atender (direcionamento); o prazo entre a
publicação e a sessão pode ser curto demais de propósito, pra afastar concorrentes que não foram
avisados com antecedência; uma empresa pode vencer repetidamente contratos do mesmo órgão de forma
suspeita. Nada disso aparece como "ilegal" à primeira vista — precisa cruzar informação de várias
fontes pra enxergar o padrão.

**O problema prático.** Cruzar manualmente o edital com PNCP (histórico de contratações), Receita
Federal (dados cadastrais da empresa) e CEIS/CNEP (sanções) é trabalho de especialista — advogado,
auditor, jornalista investigativo com tempo disponível. **Fechar com:** a esmagadora maioria das
licitações municipais no Brasil nunca passa por esse crivo, simplesmente porque não há gente nem
tempo suficiente pra fazer isso em escala — são milhares de municípios publicando editais todo dia.

### Como funciona, na teoria — 2 min
Abra o README na seção **"📋 O caso"** e **"✨ Destaques"** — aponte a tabela de destaques sem ler
célula por célula, mas explique os 3 passos em voz alta enquanto aponta:

1. **Upload & indexação** — o usuário sobe o PDF do edital, o sistema indexa automaticamente em
   segundos (RAG).
2. **O agente investiga** — um agente de IA decide sozinho quais fontes oficiais consultar,
   varrendo as 9 categorias do catálogo de anomalias, sem um roteiro fixo de perguntas.
3. **Recebe o laudo** — estruturado, com evidência, fonte de cada afirmação e um score de risco,
   entregue em streaming (token a token, como um ChatGPT).

**Não esquecer a ressalva, repetir aqui pela primeira vez:** o sistema **sinaliza padrões pra
investigação humana** — não substitui auditoria formal, não acusa, não emite veredito. Essa frase
volta em outros pontos da apresentação, então plantar ela cedo ajuda.

### Por que não ChatGPT/Claude direto — 2:30
Não tem página própria na doc — fale direto, é o argumento mais "de venda" da apresentação, e o que
a banca provavelmente já está pensando antes de você falar.

**O que ChatGPT/Claude direto NÃO fazem:**
- Não têm acesso direto ao PNCP, à Receita Federal ou ao CEIS/CNEP — são APIs específicas, não algo
  que um chat genérico acessa sozinho.
- No máximo **direcionam** onde procurar ("consulte o portal da transparência") — não confirmam nem
  justificam um achado com dado oficial de verdade.
- Replicar esse cruzamento manualmente (abrir cada API/portal, extrair o dado, comparar) exige
  conhecimento técnico que um cidadão comum ou um jornalista sem formação em programação não tem.

**O que o Auditor Cidadão faz diferente:**
- Consulta as bases oficiais de verdade, em tempo real, dentro da própria conversa — o agente decide
  e chama a ferramenta certa sozinho.
- Cruza os resultados de várias fontes e devolve um laudo com evidência e fonte citada, não uma
  sugestão de busca.
- A única habilidade técnica exigida do usuário é saber fazer upload de um PDF.

**Frase de efeito pra fechar:** "não é sobre o modelo de IA ser 'melhor' — é sobre ter acesso
automatizado às ferramentas certas." É esse acesso automatizado, não o modelo em si, que é o
diferencial real.

### Stack — 1:30
README, seção **"🛠️ Stack tecnológica"** — a tabela já está pronta, só apontar. Rápido: FastAPI +
LangGraph no backend, Maritaca Sabiá-4 como LLM principal (embeddings via OpenAI), MongoDB Atlas +
Redis pros dados, Docker no Railway. Não justificar cada escolha aqui — se quiser aprofundar o
porquê do Sabiá-4 especificamente, a razão está em `ia/modelos_prompts.md` (especialização em
domínio jurídico-administrativo brasileiro + custo sustentável num agente que faz várias chamadas
de LLM por turno), mas só abra essa página se sobrar tempo — não é bloco planejado.

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

## Bloco 3 — Arquitetura, RAG e persistência (≈ 12:30)

### Arquitetura do agente — o grafo — 2:30
**Página:** `arquitetura/visao_geral.md`, seção **"O grafo do agente"**.
Mostre o diagrama Mermaid do ciclo — é o padrão **ReAct**: o modelo decide se precisa de uma
ferramenta, o `router` (`tools_condition`) checa se a última resposta trouxe uma chamada de
ferramenta, se sim executa e volta pro agente decidir de novo, até responder sem pedir mais nada.
`recursion_limit=50` é o teto que impede um loop infinito entre os dois nós — vale citar, é o tipo
de detalhe que mostra cuidado de engenharia. Mostre o trecho de código do `graph.py` logo acima do
diagrama. Fale do `AsyncRedisSaver` (seção **"Persistência da conversa"** mais abaixo na mesma
página) — histórico por thread, expira em 24h de **inatividade** (não é um teto fixo — uma conversa
em uso nunca expira no meio).

### Ferramentas & protocolo MCP — 2 min
**Página:** mesma (`visao_geral.md`), seção **"Ferramentas disponíveis ao agente"** — a tabela já
lista as 4 nativas (Receita Federal, RAG do edital, sanções CEIS/CNEP, busca web) + as 11 de PNCP
via **MCP** (Model Context Protocol) — um pacote npm de terceiro entrega essas 11 ferramentas
prontas, zero linha de integração própria com a API do PNCP. Cite o cache: quase todas as tools
passam por Redis com TTL de 24h, compartilhado entre as réplicas — uma consulta repetida ao mesmo
CNPJ no mesmo dia não gera tráfego novo pra fonte externa. Se quiser aprofundar o *como* o MCP
carrega, pule pra `arquitetura/protocolo_mcp.md` (diagrama de carregamento no startup) — mas só se
sobrar tempo.

### RAG — indexação e recuperação — 3 min
**Página:** `ia/rag_dados.md`.

**Por que RAG e não fine-tuning, em 1 frase se perguntarem:** o edital é um documento novo a cada
upload, que não existe no treino de nenhum modelo — fine-tuning ensinaria estilo, não o conteúdo
específico daquele documento, e teria que ser refeito a cada edital novo.

Abra em **"O pipeline de indexação"** — explique o padrão **pai-filho** (small-to-big): o Docling
extrai texto + estrutura de seções (diferente de um extrator de texto plano, reconhece tabela e
hierarquia); só o parágrafo pequeno (filho, até 200 palavras) vira embedding, mas quem é gravado
junto — sem embedding próprio — é o texto da seção inteira (pai). Mostre o exemplo real de
documento gravado (o bloco de código JSON com `secao_ordem`, `secao_texto_completo`) logo abaixo do
texto sobre Docling.

Desça até **"O pipeline de busca"** pra mostrar o código do `$vectorSearch`: busca vetorial sobre o
filho (é ele que compete por similaridade), mas devolve a seção-pai inteira pro agente, com
`top_k=3` e filtro obrigatório por `edital_id`+`estado`+`município` (nunca mistura dois editais).
Cite o dedup por `secao_ordem` — a mesma seção não volta duas vezes na mesma busca, nem se repete
se já apareceu numa pergunta anterior da conversa. **Não precisa ler o código Python linha por
linha** — aponte os nomes de campo enquanto fala do conceito.

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

## Bloco 4 — Guardrails e avaliação (≈ 9:30)

### Guardrails de segurança — 2:30
**Página:** `governanca/guardrails.md`.

Dois escudos, dois riscos diferentes: **injeção de prompt** (o documento ou um campo do usuário
tentando reprogramar o agente) e **alucinação** (o agente afirmando algo que não verificou).

A página já tem o exemplo real pronto — seção **"Exemplo real: uma tentativa de injeção via
`municipio`"**, com o antes/depois do `escape_xml()`: um valor malicioso tentando fechar a tag
`<METADADOS>` e injetar uma instrução falsa, neutralizado porque `<`/`>` viram `&lt;`/`&gt;` antes
de entrar no prompt. Abra direto nela, é mais forte que descrever de memória — mostra o guardrail
funcionando na prática, não só descrito.

Complemente com **"Anti-alucinação"** mais abaixo: a regra de **"vocabulário emprestado"** proíbe o
agente de inferir um campo a partir de uma fonte que não foi chamada naquele turno (ex.: afirmar
situação cadastral usando só o resultado de sanções, sem ter chamado a Receita Federal) — foi
descoberta em teste real, via análise de log, não é uma regra teórica. E a hierarquia de evidências:
API oficial > texto do edital > busca web > inferência própria, sempre sinalizada como tal.

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

### Custo real do MVP — 2 min
**Sem página própria na doc — fale direto, os números estão aqui:**

| Serviço | Uso | Gasto |
|---|---|---|
| Maritaca AI | LLM do agente — API, desde o início do projeto | R$ 40,00 |
| OpenAI | Embeddings (RAG) — API | R$ 103,05 |
| MongoDB Atlas | Banco vetorial — plano free | R$ 0,00 |
| Railway | Hospedagem — plano "Hobby" (US$5/mês) | R$ 77,28 |
| **Total** | | **R$ 220,33** |

**Por que a OpenAI custou mais que a Maritaca**, se a Maritaca é o LLM principal: embeddings são
gerados a cada chunk indexado (todo o RAG passa por lá), enquanto o LLM principal só é chamado por
turno de conversa — volume de chamada diferente.

**Por que Railway e não MongoDB/Maritaca pagos:** os planos free de MongoDB Atlas e Maritaca
cobriram a demanda de um MVP em validação; a hospedagem (Railway) é o único item realmente pago
porque não existe "plano free" viável pra manter o serviço no ar 24/7.

**Frase de efeito pra fechar:** é um MVP pra validar a ideia, não a arquitetura final — o próprio
Railway descreve o plano usado como "para projetos hobby". Migrar pra uma nuvem maior (AWS, Azure
ou GCP) é o primeiro passo antes de pensar em escala real, o que puxa direto pro próximo bloco.

---

## Bloco 5 — Fechamento (≈ 3 min)

### Limitações e próximos passos — 2:30
**Página:** `governanca/limitacoes.md`.

Antes do backlog, vale citar o princípio que abre a página — **"indício, não veredito"**: o laudo
sempre recomenda checagem manual, nunca é decisão final. É o fechamento natural pra retomar a
ressalva do início da apresentação.

Role até **"Backlog V2"** — não leia a lista inteira, escolha 2-3 pra destacar em voz alta:
- **Escalabilidade e persistência** — migrar do Railway pra uma nuvem maior (GCP como preferência,
  por hospedagem rápida de configurar + opção de GPU dedicada se o projeto rodar modelo próprio).
- **Fase 7** — indexação automática via PNCP, eliminando o upload manual.
- **Autenticação** — hoje a cota é por cookie de sessão, não por identidade; resolve só metade do
  problema de custo (não impede reset de cookie/aba anônima).

Os itens mais recentes — **controle de contexto** (sumarização com modelo auxiliar, hoje inexistente
porque a V1 é só validação), **tokenização real** (troca do `split()` por `tiktoken` no fatiamento
de chunk) e a ideia de **observabilidade** (centralizar tokens/requisições/logs, com avaliação
contínua em produção) — também estão nessa página, cada um com sua própria seção, casos a banca
pergunte por detalhe.

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
