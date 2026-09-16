# Catálogo de Anomalias

O núcleo do conhecimento de auditoria do Auditor Cidadão é um catálogo de 9 categorias de anomalia,
de A a I. Ele vive numa única constante de texto (`CATALOGO_ANOMALIAS`, em `app/agents/prompt.py`)
que é injetada dentro do `SYSTEM_PROMPT` — é o critério, letra por letra, que o agente usa pra saber
o que procurar em cada edital e como classificar o que encontra. Não existe um catálogo duplicado em
outro lugar do código: o mesmo texto que o agente lê é o mesmo que a avaliação usa como referência
pra validar o gabarito dos casos de teste (ver [Avaliação](avaliacao.md)), e os códigos que o agente
aponta no Markdown final são lidos direto por regex, sem passar por um segundo LLM extrator.

## As 9 categorias

### A — Sobrepreço
Valor unitário de um item superior em mais de 30% à mediana de preços praticados para o mesmo
item/serviço nos últimos 12 meses. Verificação depende de um catálogo de preços de referência.

### B — Direcionamento
Especificação técnica excessivamente restritiva (marca específica, modelo único, dimensões fora de
padrão) que reduza artificialmente a competição. Sinais: "marca X ou similar superior", combinações
de requisitos que só um fornecedor conhecido atende.

### C — Fracionamento Irregular
Possível divisão artificial de contratações para evitar o procedimento ou limite aplicável —
verificado cruzando objetos comparáveis, datas próximas e valores no histórico de contratações do
órgão. O prompt não cita artigo de lei nem fixa um percentual: exige explicitamente que compras
semelhantes não sejam tratadas como fracionamento por si só (podem ser independentes, emergenciais,
sazonais ou de unidades distintas) e que o agente informe exatamente quais contratações comparou.

### D — Cartel / Conluio
Empresas "concorrentes" com sócios em comum, mesmo endereço, ou histórico de revezamento de
vitórias. Verificação depende de cruzar quadro societário e endereços das participantes.

### E — Empresa Recém-Criada
CNPJ com data de início de atividade inferior a 12 meses antes da licitação, vencendo contrato de
valor significativo. Bandeira vermelha quando combinado com objeto técnico complexo.

### F — Prazo Insuficiente
Intervalo entre a publicidade do instrumento convocatório e a apresentação/abertura de propostas
que pareça inferior ao prazo legal aplicável. O prompt **evita deliberadamente** fixar um número de
dias ou artigo de lei: instrui o agente a identificar objeto, modalidade, critério de julgamento e
regime de execução antes de calcular, porque "o prazo aplicável depende das características da
contratação previstas na legislação e no edital" — e proíbe "declarar conformidade jurídica",
limitando o achado ao intervalo calculado e à regra de comparação usada.

### G — Reincidência Suspeita
Mesma empresa vencendo proporção elevada (>50%) das licitações do mesmo órgão em um período de 12
meses.

### H — Sanção com Possível Impacto na Participação
Empresa vencedora com registro de sanção em CEIS/CNEP que possa afetar sua participação ou
contratação. **Não é automática**: o prompt exige que o agente diferencie tipo de sanção (multa,
suspensão, declaração de inidoneidade, publicação extraordinária...), use o campo `vigente`
(já calculado contra a data de hoje pela fonte, não recalculado pelo modelo) e avalie se o alcance
da sanção se aplica ao órgão/ente da contratação antes de confirmar.

!!! warning "H só vira RISCO CRÍTICO com sanção vigente e impacto confirmados"
    O prompt diz explicitamente: "registro de sanção não significa automaticamente impedimento
    para qualquer contratação ou em qualquer ente federativo" e "registro de multa ou publicação
    extraordinária, isoladamente, não deve ser convertido automaticamente em proibição de
    contratar". H só é marcada como RISCO CRÍTICO quando os dados confirmam sanção vigente **com
    impacto na participação ou contratação daquele caso específico** — registro presente mas com
    vigência, alcance ou tipo insuficiente vira INDÍCIO ou NÃO CONCLUÍDO, nunca impedimento legal
    afirmado direto.

### I — Compatibilidade Cadastral da Atividade
Verifica se o CNAE principal da empresa tem relação objetiva com o objeto licitado (ex.: "comércio
de material de limpeza" não cobre "prestação de serviço de limpeza com mão de obra"). Ausência de
relação vira INDÍCIO, nunca CONFIRMADO — o prompt é explícito que isso não prova incapacidade
técnica, fraude ou irregularidade jurídica, só é sinal para conferência humana, e que CNAE não deve
ser confundido com habilitação técnica, registro profissional ou experiência anterior.

## Cobertura real hoje

Nem todas as 9 anomalias são verificáveis com as fontes atualmente integradas — e o sistema é
transparente sobre isso. Anomalias que dependem de uma base não integrada (ex.: **A**, que exige um
catálogo de preços de referência) vão para a seção "Verificações Não Concluídas" do laudo, sem
score numérico atribuído (o `SYSTEM_PROMPT` proíbe atribuir score quando não há dados suficientes
para justificá-lo). Reforços e novas integrações para ampliar essa cobertura estão mapeados no
roadmap (ver [Próximos Passos](../governanca/limitacoes.md)).

| Anomalia | Fonte principal | Verificável hoje? |
|---|---|---|
| A — Sobrepreço | Catálogo de preços de referência | ❌ base não integrada |
| B — Direcionamento | Texto do edital (RAG) | ⚠️ parcial (análise textual) |
| C — Fracionamento | Histórico PNCP | ✅ |
| D — Cartel/Conluio | Quadro societário | ❌ QSA ainda não capturado |
| E — Empresa recém-criada | Receita Federal (data de fundação) | ✅ |
| F — Prazo insuficiente | Texto do edital + datas | ✅ |
| G — Reincidência | Histórico PNCP | ✅ |
| H — Sanção com impacto | CEIS/CNEP | ✅ |
| I — Compatibilidade cadastral | Receita Federal (CNAE) | ✅ |