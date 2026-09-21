# Roteiro — Apresentação Auditor Cidadão

> Guia rápido pra não se perder na hora. Não é pra ler na tela — é pra consultar de relance entre
> um slide e outro. 19 slides + demo ao vivo, pensados pra caber em **~51 min**, deixando **~30 min**
> de folga pra perguntas dentro de 1h30 total. Banca técnica — pode (e deve) usar nome de campo,
> função e classe real em vez de parafrasear.

## Antes de começar

- [ ] Edital de exemplo já baixado no celular (ou confirme que o QR do slide 8 está funcionando)
- [ ] Plataforma publicada no ar (`auditor-cidadao-production.up.railway.app`) — dá uma conferida rápida antes
- [ ] Internet estável no local — a demo depende disso
- [ ] Celular no modo "não perturbe", pra não travar no meio do QR code

---

## Bloco 1 — Abertura (≈ 9 min)

### 1. Capa — 0:30
Só se apresentar. Nome, "Data Master — Engenheiro de IA", nome do projeto.

### 2. Agenda — 1 min
Passar rápido pelos 6 blocos. Não detalhar — é só o mapa. Avisar aqui que vai ter uma pausa pra
demo ao vivo no meio.

### 3. O problema — 2 min
**Antes de entrar no problema, contextualize em 1 frase o que é uma licitação** (parte da banca pode
não ser da área): é o processo pelo qual um órgão público (prefeitura, governo) é obrigado por lei a
comprar um bem ou contratar um serviço — a empresa que vence é escolhida por critérios definidos em
edital, não por escolha livre do gestor. É aí que mora o risco de fraude: alguém pode desenhar o
edital ou o processo pra favorecer uma empresa específica.

**Ponto central:** fiscalizar uma licitação hoje exige cruzar manualmente PNCP, Receita Federal e
CEIS/CNEP — trabalho de especialista, fora do alcance de cidadão comum e jornalista.
**Fechar com:** a maior parte das licitações municipais no Brasil nunca é auditada por ninguém.

### 4. Como funciona, na teoria — 2 min
Os 3 passos: upload → agente investiga → laudo com evidências, fontes e score, em streaming.
**Não esquecer a ressalva:** o sistema sinaliza padrões pra investigação humana, não substitui
auditoria formal — essa frase volta em outros pontos da apresentação, vale repetir aqui a primeira vez.

### 5. Por que não ChatGPT ou Claude direto — 2:30
**A pergunta que a banca já está pensando — responda antes que perguntem.**
ChatGPT/Claude não têm acesso direto às APIs oficiais (PNCP, Receita, CEIS/CNEP) — no máximo
direcionam, não confirmam com dado real. Replicar isso manualmente exige conhecimento técnico que
jornalista/cidadão comum não tem.
**Frase de efeito:** "não é sobre o modelo ser melhor — é sobre ter acesso automatizado às
ferramentas certas."

### 6. Stack — 1:30
Rápido, sem se alongar: FastAPI + LangGraph, Maritaca Sabiá-4 + embeddings da OpenAI, MongoDB Atlas
+ Redis, Docker no Railway. Não precisa justificar cada escolha aqui — isso vem depois, se perguntarem.

---

## Bloco 2 — Domínio de conhecimento (≈ 2 min)

### 7. Catálogo de anomalias — 2 min
Passar pelas 9 letras rápido — não precisa ler todos os critérios em voz alta, a banca consegue ler.
**Fechar com:** 7 das 9 já são verificáveis hoje; as 2 que faltam (sobrepreço e cartel) dependem de
integrações futuras (catálogo de preços e quadro societário).

---

## Pausa — Demonstração ao vivo (≈ 12–15 min)

### 8. Slide de pausa (QR codes)
Passo 1: quem não tiver um edital em mãos escaneia o primeiro QR e baixa o PDF de exemplo do Drive.
Passo 2: todo mundo escaneia o segundo QR e acessa a plataforma.

**Roteiro da demo:**
1. Sobe o PDF na plataforma.
2. Mostra a indexação acontecendo (barra de progresso).
3. Deixa o relatório automático ser gerado — chama atenção pro streaming em tempo real e pros
   status de ferramenta aparecendo ("consultando Receita Federal...", etc.).
4. Faz 1-2 perguntas de acompanhamento ao vivo (ex.: "essa empresa tem sanção?").
5. Volta pra apresentação de onde parou.

**Atenção:** isso é a parte de maior risco de "enrolar" — combine com você mesmo um teto de tempo
(ex.: 15 min) e corte pra continuar mesmo se a demo não sair 100% redonda.

---

## Bloco 3 — Arquitetura, RAG e ferramentas (≈ 12:30)

### 9. Arquitetura do agente — o grafo — 2:30
O ciclo ReAct: `agente` decide → `router` (`tools_condition`) confere se pediu ferramenta →
`ferramentas` executa → volta pro `agente` → repete até responder. `AsyncRedisSaver` guarda o
histórico por `thread_id`, expira após 24h de inatividade.

### 10. Ferramentas & protocolo MCP — 2 min
4 ferramentas nativas (Receita Federal, RAG do edital, sanções, busca web) + 11 de PNCP herdadas
via protocolo MCP — zero linha de integração própria com o PNCP. Cache no Redis (TTL 24h) sobre
quase tudo, compartilhado entre réplicas.

### 11. RAG — indexação e recuperação — 2:30
Slide dividido: de um lado o pipeline de indexação (Docling → chunk filho → embedding →
MongoDB), do outro um **exemplo real** de documento gravado em `chunks_edital` — mostra o campo
`secao_ordem` (chave do dedup) e `secao_texto_completo` (o pai inteiro, sem embedding próprio).
Embaixo, a recuperação condensada: `$vectorSearch` com `top_k=3`, filtro por `edital_id` +
`estado` + `município`, dedup por `secao_ordem` e por thread (`secoes_vistas`, via `Command` do
LangGraph). **Não precisa ler o JSON linha por linha** — é pra banca técnica olhar enquanto você
fala do padrão pai-filho.

### 12. Persistência e limpeza de dados — 2:30
**Pergunta que a banca provavelmente vai fazer — responda antes.** Sim, o MongoDB guarda os
editais indexados — mostra o diagrama de topologia (navegador → Railway com FastAPI/MCP/Redis →
serviços externos, MongoDB Atlas em destaque). Mas não fica pra sempre: chunk é apagado quando
`origem == "upload_usuario"` **e** mais velho que `MONGO_RETENCAO_DIAS` (default 2 dias). Job
standalone (`limpeza_mongo.py`), pensado pra cron, termina com erro explícito se falhar — nunca
em silêncio. **Detalhe que vale citar:** outras origens (ex.: futura indexação via PNCP) não são
afetadas por essa expiração.

### 13. Anatomia de um turno — 2:30
Slide dividido: upload (validação → Docling → indexação → SSE) de um lado, turno de conversa (as
6 paradas: navegador → FastAPI/cookie/cota → stream devolvido → `run_agent` monta o turno → ciclo
ReAct → eventos viram SSE) do outro. **Ponto que costuma gerar pergunta:** o `SYSTEM_PROMPT` nunca
fica salvo no histórico do Redis — é preposto a cada chamada. E o grafo é montado uma vez só, no
startup.

**Por que SSE no upload** (callout do slide): a indexação leva ~2 min — um request síncrono
estourava timeout de conexão ociosa (`Failed to fetch` no navegador, mesmo com o backend terminando
certo). `progress`/`heartbeat` mantêm a conexão viva durante esse tempo todo.

---

## Bloco 4 — Guardrails e avaliação (≈ 8:30)

### 14. Guardrails de segurança — 2:30
Dois escudos: anti-injeção (todo campo do usuário passa por `escape_xml()` — não só a pergunta —
tentativa de manipulação vira achado de auditoria) e anti-alucinação (proibição de "vocabulário
emprestado" — nenhum campo pode vir de uma fonte que não foi consultada naquele turno). O slide
mostra o envelope `PROMPT_DINAMICO` de verdade, com as tags `<CNPJS_NO_EDITAL>`/`<METADADOS>`/
`<PROMPT_USUARIO>`, e um exemplo de tentativa de injeção via `municipio` antes/depois do
`escape_xml()` — vale parar 1 segundo nesse antes/depois, é o tipo de coisa que a banca técnica
gosta de ver de verdade, não só descrito.

### 15. Metodologia de avaliação — 2:30
G-Eval em vez de nota livre — critério fixo pro juiz, não "opinião". 4 métricas, cada uma com sua
descrição no slide (Tool Correctness e Argumentos são determinísticas, sem LLM; Fidelidade e
Cobertura/Recall usam G-Eval). Golden dataset de 13 casos, rodando o mesmo código de produção
(`run_agent()`).

O slide agora tem uma nota sobre o **G-Eval** em si (Liu et al., 2023): em vez de pedir nota direta
à LLM juíza, o método força ela a seguir passos intermediários de raciocínio (*Evaluation Steps*,
técnica de Chain-of-Thought) antes de emitir o parecer — reduz aleatoriedade, aproxima da avaliação
humana. Implementado via a lib **deepeval**. Vale citar de cabeça, se quiser, os dois tipos de caso
do dataset: o **sintético** (ex.: H — sanção vigente) tem gabarito escrito antes do PDF existir,
cobra tool certa *e* anomalia certa; o **real** (`caso_02_saoluis_sancao`, edital verdadeiro de São
Luís) só cobra o objetivamente checável — achou o trecho certo, chamou a tool certa — porque nem um
humano especialista bateria o martelo com certeza absoluta sobre um edital real.

**Se perguntarem sobre a rubrica do juiz de Fidelidade** (não está no slide, mas pode vir):
G-Eval usa uma régua de nota 1 a 5 testada de propósito — um caso que extrapola a fonte dá 0.32, um
caso fiel dá 1.0. O critério: lista cada afirmação do laudo, checa se é sustentada pelas fontes,
marca sustentada ou não (extrapolação conta como não sustentada).

### 16. Resultados da avaliação — 2:30
**O número que importa:** real 4/4, sintético 9/9, estável em 3 rodadas seguidas sem mudar código.

**Se perguntarem por que Fidelidade (0,89–0,99) é mais baixa que as outras (1,00):** Fidelidade é a
única métrica semântica das quatro — julgamento de um LLM-juiz (G-Eval) sobre cada afirmação do
laudo, não uma checagem determinística como Tool Correctness/Argumentos, nem um recall binário como
Cobertura. Uma extrapolação pequena de texto já custa ponto na rubrica (ver slide 15). O caso mais
baixo do lote (0,889, edital de Belém) ainda carrega resquício do problema de retrieval documentado
na avaliação — não é uma falha de fidelidade em si, é limite de recuperação.

**Se perguntarem sobre erro de classificação:** existem 2 confusões conhecidas entre categorias
vizinhas do catálogo (ex.: E × I) — não reprovam, mas estão documentadas em `docs/ia/avaliacao.md`.
Não escondido, só tirado do slide pra não competir com o número principal.

### 17. Custo real do MVP — 1 min
R$ 220,33 gastos até hoje (Maritaca, OpenAI, MongoDB free, Railway).

---

## Bloco 5 — Fechamento (≈ 2:30)

### 18. Próximos passos — 2 min
Não ler todos os bullets — escolher 2-3 pra destacar em voz alta (sugestão: migração de nuvem,
autenticação, indexação automática via PNCP, controle de contexto) e deixar o resto como "está tudo
documentado, quem quiser ver depois pode conferir".

**Novo item — tokenização real no fatiamento de chunks:** hoje o corte de parágrafo longo antes do
embedding usa `split()` por espaço (limite de "200 palavras"), não um tokenizador de verdade.

**Pergunta provável — "aplicam alguma tokenização antes do embedding?" — resposta pronta:**
Não, hoje não. O texto do Docling vai só com `.strip()`, e o corte de parágrafo longo usa
`str.split()` por espaço (limite de 200 "palavras"), sem `tiktoken` — o mesmo tokenizador que o
`text-embedding-3-small` usa por baixo dos panos. Isso importa por 3 motivos, se pedirem pra
aprofundar:

1. **O modelo tem limite real de tokens** (8191 pro `text-embedding-3-small`), não de palavras —
   contar palavra é proxy ruim porque o tokenizador quebra em subpalavras, e termo jurídico
   longo/sigla/acentuação em português gera mais token por palavra que em inglês. Se estourar o
   limite real, a chamada falha ou trunca **silenciosamente** — perda de conteúdo sem aviso.
2. **É a unidade real de custo e de rate limit** — cobrança e cota são por token, não por palavra.
3. **Afeta a qualidade do embedding** — chunk maior que o ideal em tokens dilui o vetor (mistura
   tópico), chunk menor fragmenta contexto demais; o tamanho certo é decisão sobre tokens, porque é
   isso que o modelo de fato processa.

Registrado como próximo passo (trocar por `tiktoken`), tanto no slide 18 quanto em
`docs/governanca/limitacoes.md`.

### 19. Obrigado — 0:30
Fechar e abrir pra perguntas.

---

## Se o tempo apertar

Corte nesta ordem (do menos crítico pro mais crítico):
1. Slide 13 (Anatomia de um turno) — resumir em 1 frase o lado do upload, focar só no turno de conversa.
2. Detalhamento do catálogo de anomalias (slide 7) — mostrar só o callout final.
3. Exemplo JSON do slide 11 — mencionar que existe, sem parar pra ler os campos em voz alta.

**Nunca corte:** slides 5 (por que não ChatGPT), 8 (demo), 12 (persistência/limpeza — responde uma
pergunta certa da banca), 14 (guardrails com o exemplo de injeção), 16 (resultados) e 17 (custo) —
são os que mais seguram a atenção e respondem as perguntas que a banca mais provavelmente vai fazer.

---

## Respostas rápidas — perguntas prováveis da banca

Campo de consulta rápida. Não precisa decorar frase por frase — só ter o argumento na ponta da
língua.

**"A indexação do edital demora ~2 minutos. Isso não é um problema? E se no futuro o próprio agente
for indexar editais do PNCP automaticamente, não corre risco de timeout?"**
Sim, é um problema conhecido. O Docling ainda roda dentro do próprio request HTTP do upload hoje.
Já mitigamos o sintoma mais grave — trocamos pra streaming SSE com `progress`/`heartbeat`, porque
antes o request síncrono batia timeout de conexão ociosa (`Failed to fetch` no navegador mesmo com
o backend terminando certo). Mas isso resolve só o sintoma, não reduz o tempo de processamento em
si. O próximo passo, já registrado no roadmap, é mover o Docling pra um job assíncrono em
background: o `/upload/` responde em segundos e o status de indexação chega por outro mecanismo. E
esse desacoplamento é justamente pré-requisito pra Fase 7 (indexação automática via PNCP) — sem
isso, cada indexação automática multiplicaria o mesmo risco de timeout, então já sei que preciso
resolver essa base antes de construir aquela feature em cima.

**"Por que a métrica de Fidelidade tem nota mais baixa que as outras?"**
Porque é a única das 4 métricas que é semântica, julgada por LLM (G-Eval) — Tool Correctness e
Argumentos são determinísticas, comparação direta, não têm essa variância. Fidelidade compara o
texto gerado com a evidência recuperada, e isso é mais sensível a nuance de linguagem. Mesmo assim
ficou entre 0.89 e 0.99 nos 13 casos, estável em 3 rodadas.

**"Vocês têm casos onde o agente erra ou confunde categoria de anomalia?"**
Sim, documentamos 2 casos de confusão entre categorias próximas (ex.: E×I) — não são falhas no
sentido de quebrar o teste, mas ficam registrados como limitação conhecida porque as categorias têm
fronteira semântica próxima. O caso de Fidelidade mais baixa (0.889, Belém) está ligado a uma
limitação de recuperação (RAG trouxe o trecho certo mas não o mais completo), não a uma alucinação.

**"Vocês tokenizam o texto antes de gerar o embedding?"**
Não, hoje é um gap conhecido. O corte de chunk usa `str.split()` por espaço (~200 "palavras"), não
um tokenizador real. Isso importa por três motivos: (1) `text-embedding-3-small` tem limite real de
8191 tokens — estimativa por palavra é pouco confiável, principalmente em português jurídico, e pode
truncar silenciosamente; (2) token é a unidade real de custo e rate limit; (3) o tamanho certo do
chunk em tokens afeta a qualidade do embedding. Já está registrado como próximo passo, trocar por
`tiktoken`.

**"Por que gastou mais com OpenAI do que com o modelo de linguagem (Maritaca)?"**
Porque o LLM (Sabiá, via Maritaca) só processa quando o usuário faz uma pergunta, mas o embedding
roda toda vez que um documento novo é indexado — e cada edital vira dezenas de chunks. Uso de
embedding é mais frequente que uso de chat nesse estágio do projeto.

**"Por que só o Railway está pago, e o resto no free tier? Isso não é uma arquitetura de MVP frágil
pra produção?"**
É, e é assumido como tal. O objetivo aqui é validar a ideia com o menor custo possível antes de
investir em infra maior — o próprio Railway vende esse plano como "para projetos hobby". O primeiro
passo antes de qualquer escala real é migrar pra uma cloud maior (AWS/Azure/GCP — GCP é a preferida),
já registrado no roadmap.

**"Por que não usou o RAGAS pra avaliação, em vez do G-Eval/deepeval?"**
RAGAS é focado em pipelines RAG puros (métricas como context precision/recall, faithfulness sobre
chunk recuperado). O G-Eval via deepeval encaixou melhor porque a avaliação aqui não é só do RAG —
é do agente completo, incluindo decisão de qual tool chamar (Tool Correctness) e uso correto dos
argumentos, que não são o foco do RAGAS. O G-Eval também permite customizar os critérios e os steps
de raciocínio por métrica, o que deixou a nota mais alinhada com o que a banca de auditoria
realmente considera "certo" num laudo, e não só fidelidade textual ao chunk recuperado.

**"Como vocês lidam com dados pessoais / LGPD nos editais?"**
O sistema trabalha só com dados públicos de contratação (editais, CNPJs de empresas participantes,
sanções públicas) — não há coleta de dado pessoal sensível de cidadão. Detalhe completo está
documentado em `docs/governanca/lgpd.md`.

**"O sistema depende de um pacote de terceiros pro PNCP (`@licinexusbr/mcp`). Isso não é um risco?"**
É um risco real e assumido conscientemente pro MVP — evita reescrever integração com 11
ferramentas do zero. Se o pacote for descontinuado, o impacto fica isolado nas tools PNCP (as 4
tools nativas — Receita Federal, RAG do edital, sanções, busca web — continuam funcionando), e a
troca seria por uma integração própria ou outro provedor MCP compatível.

**"O rate limit por cookie não é fácil de burlar limpando o navegador?"**
Sim, é uma limitação conhecida do MVP — o objetivo hoje é conter abuso casual, não resistir a um
usuário malicioso decidido. Endurecer isso (ex.: rate limit por IP ou autenticação) é um ajuste de
próxima fase, não bloqueador pra validar a ideia.
