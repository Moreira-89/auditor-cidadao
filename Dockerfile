# Imagem base: Python 3.12 slim (Debian Bookworm)
# "slim" reduz o tamanho final eliminando ferramentas de compilação desnecessárias
FROM python:3.12-slim

# Evita que o Python bufferize stdout/stderr
# Isso garante que os logs apareçam em tempo real no Railway/Docker
ENV PYTHONUNBUFFERED=1
ENV NO_UPDATE_NOTIFIER=1

# Instala Node.js 20 LTS via NodeSource
# Node.js é necessário para o subprocess do MCP LiciNexus (npx @licinexusbr/mcp)
# curl é necessário para baixar o script de instalação do NodeSource
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    # Limpa cache do apt para reduzir o tamanho da imagem final
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia e instala dependências Python ANTES de copiar o código
# Isso aproveita o cache de camadas do Docker:
# se requirements.txt não mudar, essa camada não é reconstruída
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação
COPY . .

# Expõe a porta que o uvicorn vai escutar
EXPOSE 8000

# Comando de inicialização do servidor
# --host 0.0.0.0 é obrigatório em containers — sem isso, o servidor
# escuta só em localhost e não recebe tráfego externo
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]