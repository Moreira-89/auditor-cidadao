# auditor-cidadao
Auditor Cidadão é um sistema inteligente onde um cidadão ou jornalista pode fazer o upload de editais de licitação, contratos públicos e diários oficiais (em formato PDF) de uma prefeitura, e interagir com um Agente que cruza esses dados para encontrar anomalias.


## Arquitetura pastas: 

```
/auditor-cidadao
├── /app
│   ├── /api          # Apenas as rotas da API (ex: rotas para o frontend chamar)
│   ├── /core         # Configurações globais, chaves de API, variáveis de ambiente
│   ├── /models       # Schemas de validação e tipagem (Pydantic)
│   └── /services     # O "cérebro": lógica de negócio, chamadas LLM, RAG, Tools
├── .env              # Variáveis sensíveis (NÃO vai pro GitHub)
├── .gitignore
├── requirements.txt
└── main.py           # Ponto de entrada do FastAPI (uvicorn)
```