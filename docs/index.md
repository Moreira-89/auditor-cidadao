# Auditor Cidadão — Documentação Técnica

Seja bem-vindo à documentação oficial do **Auditor Cidadão**, uma solução funcional de Inteligência Artificial Generativa voltada para a **auditoria de licitações públicas municipais**.

---

## O problema

Fiscalizar licitações municipais no Brasil exige cruzar um edital em PDF com meia dúzia de bases públicas diferentes — PNCP, Receita Federal, CEIS/CNEP — para identificar irregularidades como sobrepreço, direcionamento ou empresas sancionadas participando de uma disputa. É um trabalho manual e lento, que a maioria dos cidadãos e jornalistas não tem tempo nem conhecimento técnico para fazer sozinha. Na prática, isso significa que boa parte das licitações municipais do país nunca chega a ser auditada por ninguém fora do próprio órgão que a conduziu.

## A solução

O Auditor Cidadão automatiza essa varredura, tornando a fiscalização acessível a qualquer cidadão ou jornalista — sem exigir conhecimento técnico ou horas de trabalho manual. Basta fazer o upload do edital, contrato ou diário oficial de uma prefeitura (em PDF); o sistema indexa o conteúdo com RAG (busca semântica) e disponibiliza um agente de IA que decide sozinho quais fontes oficiais consultar para investigar 9 categorias de anomalias.

Concretamente, isso quer dizer que a plataforma:

* **Cruza múltiplas fontes oficiais** — PNCP, Receita Federal, CEIS/CNEP (Portal da Transparência) e consultas direcionadas à Web — sem exigir que o usuário abra uma aba para cada uma.
* **Detecta padrões anômalos** automaticamente, com base num catálogo rigoroso de 9 categorias de irregularidade em contratações públicas, de sobrepreço a empresas sancionadas.
* **Emite um laudo estruturado**, em streaming e tempo real, com evidências e nível de risco por anomalia — em Markdown e JSON, pronto para apoiar uma investigação humana (o sistema sinaliza padrões, não substitui uma auditoria formal).

---

## Acesse a plataforma

Faça um teste na nossa plataforma! A forma mais recomendada de conhecer o Auditor Cidadão é acessando a instância já publicada, sem precisar instalar nada:

**[Plataforma Auditor Cidadão](https://auditorcidadao.up.railway.app/)**

Rodar localmente ou via Docker (ver [Operacional & Reprodução](operacional/setup_local.md)) é recomendado para quem quer inspecionar o código ou contribuir com o projeto — não é pré-requisito para experimentar a solução.

---

## Guia de Navegação

Esta documentação está dividida em 4 pilares estratégicos para facilitar a avaliação:

1. **[Operacional & Reprodução](operacional/index.md):** instruções passo a passo para clonar, configurar as variáveis de ambiente e rodar o projeto localmente ou via Docker.
2. **[Arquitetura do Sistema](arquitetura/visao_geral.md):** o grafo do agente no LangGraph, o estado que ele carrega, as ferramentas disponíveis, o protocolo MCP e o streaming via SSE.
3. **[Engenharia de IA](ia/modelos_prompts.md):** justificativa dos modelos escolhidos, engenharia de prompts, catálogo de anomalias e a extração do laudo estruturado em JSON.
4. **[Governança e Ética](governanca/lgpd.md):** tratamento de dados sob a LGPD, mitigação de alucinações e guardrails de segurança contra injeção de prompts.
