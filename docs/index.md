# Auditor Cidadão — Documentação Técnica

Seja bem-vindo à documentação oficial do **Auditor Cidadão**, uma solução funcional de Inteligência Artificial Generativa voltada para a **auditoria de licitações públicas municipais**. 

Este projeto foi desenvolvido sob a trilha de *Assistência e Interação* combinada com *Automação e Extração de Conhecimento*, com foco em escalabilidade, segurança e eficiência.

---

## 🎯 Objetivo do Projeto
O Auditor Cidadão rompe o paradigma tradicional de simples validação cadastral para se tornar uma plataforma inteligente capaz de:

* **Cruzar múltiplas fontes oficiais:** Dados do PNCP, Receita Federal, CEIS/CNEP (Portal da Transparência) e consultas direcionadas à Web.
* **Detectar padrões anômalos:** Análise automatizada baseada em um catálogo rigoroso de anomalias de contratação.
* **Emitir laudos estruturados:** Geração automática de relatórios técnicos em formato JSON e Markdown para apoiar a investigação humana.

---

## 🗺️ Guia de Navegação
Esta documentação está dividida em 4 pilares estratégicos para facilitar a avaliação:

1. **[Operacional & Reprodução](operacional/setup_local.md):** Instruções passo a passo para clonar, configurar as variáveis de ambiente e rodar o projeto localmente ou via Docker.
2. **[Arquitetura do Sistema](arquitetura/visao_geral.md):** Desenho do pipeline de dados, o funcionamento do grafo do LangGraph, protocolo MCP e streaming via SSE.
3. **[Engenharia de IA](ia/modelos_prompts.md):** Justificativas dos modelos de LLM escolhidos, engenharia de prompts, extração de JSON e o framework de avaliação automatizado com RAGAS.
4. **[Governança e Ética](governanca/seguranca_guardrails.md):** Tratamento de dados sob a LGPD, mitigação de alucinações e guardrails de segurança contra injeção de prompts.