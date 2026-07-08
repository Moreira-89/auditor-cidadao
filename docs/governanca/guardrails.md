# Guardrails de Segurança

Um agente que lê documentos enviados por usuários e responde sobre irregularidades enfrenta dois
riscos centrais: **injeção de prompt** (o documento tentando reprogramar o agente) e **alucinação**
(o agente afirmando o que não verificou). Esta página descreve os guardrails aplicados contra os
dois.

## Anti-injeção de prompt

### Escape de XML em todos os campos do usuário

O `PROMPT_DINAMICO` envolve os dados do usuário em tags no estilo XML (`<CNPJS_NO_EDITAL>`,
`<METADADOS>`, `<PERGUNTA>`). Se um usuário conseguisse injetar `</PERGUNTA><SYSTEM>...`, poderia
quebrar esse isolamento e forjar uma instrução. Para impedir isso, `run_agent`
(`app/services/ai_engine.py`) passa **todos** os campos vindos do cliente por `escape_xml()`, que
troca `<` e `>` por `&lt;`/`&gt;` — não só a pergunta, mas também `estado`, `municipio` e a lista de
CNPJs formatada.

!!! note "Por que escapar todos os campos, não só a pergunta"
    Numa versão anterior só a pergunta era escapada, o que abria uma brecha: um valor malicioso em
    `municipio` ou nos CNPJs podia injetar tags via `<METADADOS>`. A correção foi aplicar o escape a
    todo campo controlado pelo cliente — a superfície de injeção é o conjunto inteiro de entradas,
    não apenas o campo "óbvio".

### Tags de isolamento e regras imutáveis

O `SYSTEM_PROMPT` instrui o agente a tratar **todo conteúdo entre as tags** `<DOCUMENTO>`,
`<CNPJS_NO_EDITAL>` e `<METADADOS>` como **dado bruto de terceiros**, nunca como instrução — mesmo
que o texto pareça uma ordem direta. E vai além: se o documento contiver tentativas de manipulação
("ignore suas instruções", "este edital está em ordem"), o agente é instruído a tratar isso como um
**achado de auditoria** e sinalizar ao usuário, em vez de obedecer.

O prompt também proíbe o agente de revelar seu prompt interno, suas regras ou os nomes técnicos das
ferramentas, e de confirmar/negar especulações sobre seu funcionamento interno.

## Anti-alucinação

### "Nunca invente dados"

O `SYSTEM_PROMPT` estabelece uma regra dura: se uma consulta falha ou retorna vazio, o agente deve
registrar explicitamente "Informação não verificável com as fontes disponíveis" — nunca preencher a
lacuna com suposição.

### Hierarquia de evidências

As conclusões seguem uma ordem de confiança: (1) dados oficiais de APIs governamentais, (2) texto do
documento, (3) busca web (sempre citando a origem), (4) inferências próprias (sempre sinalizadas).
Isso impede que um resultado de busca web tenha o mesmo peso de um dado da Receita Federal.

### Proibição de "vocabulário emprestado"

Uma regra específica — descoberta em teste real via análise de log — proíbe o agente de inferir um
campo a partir de uma fonte que não foi consultada naquele turno. Exemplo: afirmar a `situação
cadastral` de uma empresa a partir de um resultado de sanções, sem ter chamado a Receita Federal.
Toda afirmação factual precisa remeter a um campo literal de uma tool efetivamente chamada.

### Distinção entre "não verificado" e "sem irregularidade"

Este é um guardrail de design, não só de prompt. A ferramenta de sanções (`consultar_sancoes`)
retorna deliberadamente um item `{"tipo_registro": "aviso"}` quando uma base (CEIS ou CNEP) está
indisponível — distinto de uma lista vazia (base consultada, sem sanções). O `SYSTEM_PROMPT` então
exige **score conservador**: quando uma anomalia depende de uma base não verificada, o mínimo é
MÉDIO, e o laudo nunca declara "limpo total" — sempre ressalva que verificações não concluídas devem
ser checadas manualmente.

## Validação e isolamento de erros

- **Validação de CNPJ** — todo CNPJ é validado matematicamente (`validate-docbr`) antes de qualquer
  requisição HTTP; CNPJs inválidos são descartados no `PerguntaRequest` e rejeitados nas tools.
- **Erros estruturados** — nenhuma ferramenta deixa uma exceção subir crua: todas retornam
  `{"error": ...}` para o LLM decidir como reagir, em vez de derrubar o turno.
- **Rede de segurança global** — um handler de exceção em `main.py` captura qualquer erro não
  tratado e responde 500 sem vazar stack trace ao cliente.

!!! info "Requisitos cobertos por este pilar"
    | Requisito | O que esta seção resolve |
    |---|---|
    | **T6** — Ética, privacidade e responsabilidade | Anti-injeção, anti-alucinação, isolamento de erros |
    | **E5** — Decisões e trade-offs | Escape de todos os campos, distinção verificado × não-verificado |
