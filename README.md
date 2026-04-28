# Auditor Cidadão 🕵️‍♂️🇧🇷

O **Auditor Cidadão** é um sistema inteligente desenvolvido para auxiliar cidadãos, jornalistas e órgãos de controle na fiscalização de gastos públicos. A plataforma permite o upload de editais de licitação, contratos e diários oficiais em PDF, utilizando Inteligência Artificial de ponta para cruzar dados e identificar anomalias ou indícios de irregularidades.

## 🚀 Funcionalidades

- **Extração Inteligente:** Extração de texto e tabelas de arquivos PDF complexos utilizando `pdfplumber`.
- **Detecção Automática de CNPJ:** Identificação automática de todas as empresas mencionadas no documento via Regex.
- **Validação em Tempo Real:** Consulta automática à base da Receita Federal (via BrasilAPI) para verificar a situação cadastral, razão social e CNAE das empresas.
- **Agente de IA Auditor:** Utiliza o modelo **Llama 3.3 70B** (via Groq) para realizar um raciocínio crítico sobre o documento, comparando os dados extraídos com as normas vigentes e informações oficiais.
- **Loop Agêntico:** O sistema opera em um ciclo de "pensamento" e "ação", onde a IA decide quais ferramentas (como a consulta de CNPJ) deve utilizar antes de entregar o relatório final.

## 🛠️ Tecnologias Utilizadas

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **IA/LLM:** [Groq](https://groq.com/) (Llama 3.3 70B Versatile)
- **Processamento de PDF:** [pdfplumber](https://github.com/jsvine/pdfplumber)
- **Validação de Dados:** [Pydantic V2](https://docs.pydantic.dev/)
- **Integração:** [BrasilAPI](https://brasilapi.com.br/) (Consulta de CNPJ)

## 📂 Estrutura do Projeto

```text
/auditor-cidadao
├── /app
│   ├── /api          # Definição de rotas e endpoints (FastAPI)
│   ├── /core         # Configurações globais e inicialização de clientes (Groq)
│   ├── /models       # Schemas de validação e tipagem (Pydantic)
│   └── /services     # Lógica de negócio: Motor da IA (Agentic Loop) e Ferramentas
├── main.py           # Ponto de entrada da aplicação
├── .env              # Variáveis de ambiente (API Keys)
└── requirements.txt  # Dependências do projeto
```

## ⚙️ Configuração e Instalação

### Pré-requisitos
- Python 3.10+
- Uma chave de API da [Groq](https://console.groq.com/)

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
   GROQ_API_KEY=sua_chave_aqui
   ```

## 🖥️ Como Executar

Inicie o servidor de desenvolvimento:
```bash
uvicorn main:app --reload
```
A API estará disponível em `http://127.0.0.1:8000`.
Você pode acessar a documentação interativa (Swagger UI) em `http://127.0.0.1:8000/docs`.

## 📡 Endpoints Principais

### `POST /analisar-edital/`
Recebe um arquivo PDF e retorna uma análise detalhada realizada pelo Agente Auditor.

**Exemplo de Resposta:**
```json
{
  "resultado_analise": "O edital apresenta a empresa [RAZÃO SOCIAL] com CNPJ [XX.XXX.XXX/XXXX-XX]. Em consulta à Receita Federal, verificou-se que a empresa possui situação cadastral ATIVA, porém seu CNAE principal não condiz com o objeto da licitação..."
}
```
