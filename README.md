# Auditor Cidadão 🕵️‍♂️🇧🇷

O **Auditor Cidadão** é um sistema inteligente desenvolvido para auxiliar cidadãos, jornalistas e órgãos de controle na fiscalização de gastos públicos. A plataforma permite o upload de editais de licitação, contratos e diários oficiais em PDF e utiliza Inteligência Artificial avançada (Arquitetura RAG + Loop Agêntico) para analisar os dados, recuperar contextos e identificar potenciais irregularidades com base em consultas em tempo real.

---

## 🚀 Como o Sistema Funciona (Arquitetura RAG + Agent)

O projeto é dividido em dois grandes passos:

### 1. Ingestão e Indexação (Endpoint: `/upload/`)
- **Extração de Texto:** Recebe um arquivo PDF e extrai todo o texto utilizando a biblioteca `pdfplumber`.
- **Extração de Entidades (Regex):** Varre o documento em busca de todos os CNPJs citados para análises futuras.
- **Chunkização:** Pega esse texto gigante e o divide em fatias menores (chunks) mantendo o sentido das frases (via `RecursiveCharacterTextSplitter` do LangChain).
- **Vetorização (Embeddings):** Transforma essas fatias de texto em vetores matemáticos usando o `sentence-transformers`.
- **Armazenamento:** Salva os vetores em um banco de dados especializado ([Pinecone](https://www.pinecone.io/)), associando metadados importantes (como "Estado" e "Município") para filtros rápidos posteriores.

### 2. Conversa e Auditoria (Endpoint: `/conversar-com-auditor/`)
- **Busca Semântica (Retrieval):** Quando o usuário faz uma pergunta, transformamos a pergunta em vetor e buscamos no Pinecone apenas os 3 pedaços de texto do edital mais relevantes matematicamente.
- **Agente de Inteligência Artificial (Generation):** Passamos esse contexto enxuto e a lista de CNPJs para um Agente Inteligente, movido pelo modelo **Llama 3.3 70B** (via [Groq](https://groq.com/)).
- **Loop Agêntico:** Diferente de um LLM normal, nosso Agente pensa antes de responder. Se ele identifica os CNPJs, ele pausa a resposta e aciona a ferramenta interna (`consultar_receita_federal`). Nosso sistema faz um `GET` na BrasilAPI, captura dados em tempo real da empresa (CNAE, Status, Razão Social) e devolve para o Agente. Só depois de cruzar o edital com os dados concretos é que o Agente formula a resposta final.

---

## 🛠️ Tecnologias Utilizadas

- **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **IA/LLM:** [Groq](https://groq.com/) (Llama 3.3 70B Versatile)
- **Vector Database:** [Pinecone](https://www.pinecone.io/)
- **Embeddings & RAG:** [LangChain](https://python.langchain.com/) + [HuggingFace](https://huggingface.co/)
- **Validação de Dados:** [Pydantic V2](https://docs.pydantic.dev/)
- **Integração Externa:** [BrasilAPI](https://brasilapi.com.br/) (Consulta de CNPJ)

---

## 📂 Estrutura do Projeto

```text
/auditor-cidadao
├── /app
│   ├── /api          # Rotas e Endpoints (FastAPI)
│   │   ├── root_upload.py       # (Recebe PDF e indexa no Pinecone)
│   │   └── root_perguntar.py    # (Faz busca vetorial e chama a IA)
│   ├── /core         # Configurações globais e cliente Groq
│   ├── /models       # Schemas de validação e Pydantic
│   ├── /services     # Lógica de negócio (Gerenciador Vetorial, Agentic Loop, Tools)
│   └── /utils        # Funções auxiliares (Extração de CNPJ)
├── main.py           # Ponto de entrada (Entry Point) da aplicação
├── .env              # Variáveis de ambiente (Groq API, Pinecone API)
└── requirements.txt  # Dependências do projeto
```

## Arquitetura do Projeto

```Mermaid
stateDiagram
  direction TB

  [*] --> Usuario
  
  state "Hospedagem (Render/Railway)" as Hospedagem {
    direction LR

    Usuario --> RootUpload: Acessa plataforma Auditor Cidadão
    
    state "Rota /upload" as RootUpload {
      direction TB
      Entrada : Usuário informa estado e cidade, depois faz o upload do edital

      Entrada --> GerenciadorVetorial : Usuário clica no botão "Upload"
      
      state "Classe Gerenciador Vetorial" as GerenciadorVetorial {
        direction TB
        Processo : Importa modelo embedding, faz chunking, gera vetores e salva no Pinecone
      }
    }

    RootUpload --> RootPerguntar : Redireciona usuário para o chat

    state "Rota /conversar-com-auditor" as RootPerguntar {
      direction LR
      
        Usuario_Pergunta 

      Usuario_Pergunta --> buscar_contexto

      state "Função buscar_contexto acionada" as buscar_contexto{
          processo: Consulta Pinecone + Consolidação das informações
      }

      buscar_contexto --> run_agent

      state "Auditor Cidadão" as run_agent{
        direction LR

        start --> node_call_lmm

        node_call_lmm --> node_call_tools: faz chamada as funções

        node_call_tools --> node_call_lmm: retorna resultado das funções

        node_call_lmm --> end

        end --> [*]

      }


     

    }
  }
```

---

## ⚙️ Configuração e Instalação

### Pré-requisitos
- Python 3.10+
- Chave de API da [Groq](https://console.groq.com/)
- Chave de API da [Pinecone](https://app.pinecone.io/)

### Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/auditor-cidadao.git
   cd auditor-cidadao
   ```

2. Crie e ative um ambiente virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # ou
   .venv\Scripts\activate     # Windows
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente:
   Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:
   ```env
   GROQ_API_KEY=sua_chave_groq_aqui
   PINECONE_API_KEY=sua_chave_pinecone_aqui
   ```

---

## 🖥️ Como Executar

Inicie o servidor de desenvolvimento:
```bash
uvicorn main:app --reload
```
A API estará disponível em `http://127.0.0.1:8000`.

Você pode testar todos os endpoints diretamente pela documentação interativa (Swagger UI) acessando:
👉 **`http://127.0.0.1:8000/docs`**
