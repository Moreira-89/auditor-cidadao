# Operacional & Reprodução

Este pilar cobre a reprodução exata do ambiente do **Auditor Cidadão**: como clonar, configurar e
rodar o projeto — localmente ou via Docker — em qualquer máquina, sem depender de conhecimento
prévio sobre o código.

!!! info "Requisitos cobertos por este pilar"
    | Requisito | O que esta seção resolve |
    |---|---|
    | **E1** — Projeto funcional, empacotado e reprodutível | [Setup local](setup_local.md) e [Docker & Deploy](docker.md) |
    | **E3** — Instruções de execução | [Setup local](setup_local.md) |
    | **R1** — Reproduzível em outra máquina | [Docker & Deploy](docker.md) |
    | **R2** — Scripts de setup/execução no Git | `Dockerfile`, `.env.example`, `requirements.txt` (raiz do repo) |
    | **R3** — Instruções claras de configuração | [Variáveis de ambiente](variaveis_ambiente.md) |

## Páginas

- **[Setup local](setup_local.md)** — clonar o repositório, criar o ambiente virtual, instalar
  dependências e subir a aplicação com `uvicorn`.
- **[Docker & Deploy](docker.md)** — build e execução via container, e como o mesmo Dockerfile é
  usado em produção (Railway).
- **[Variáveis de ambiente](variaveis_ambiente.md)** — referência completa de cada chave exigida
  ou opcional, o que ela controla e onde obtê-la.
