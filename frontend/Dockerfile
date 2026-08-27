# Build multi-stage: gera o bundle estático (Vite) numa imagem com Node, depois
# serve só o resultado (dist/) numa imagem nginx enxuta — a imagem final não
# carrega node_modules nem o toolchain de build.

FROM node:22-alpine AS build
WORKDIR /app

# ARG (não ENV) porque o valor só precisa existir durante o `npm run build` —
# o Vite embute VITE_API_BASE_URL no bundle nesse momento (import.meta.env),
# não é lido em runtime pelo container final. O Railway injeta variáveis do
# serviço como build args automaticamente quando declaradas com ARG aqui —
# configure VITE_API_BASE_URL nas variáveis do serviço de frontend, com a URL
# pública do serviço de backend (ver docs/operacional/docker.md).
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Copia e instala dependências antes do código: aproveita o cache de camadas
# do Docker — se package*.json não mudar, `npm ci` não roda de novo.
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Sem valor fixo: o Railway injeta PORT em runtime. 8080 é só o fallback para
# rodar localmente com `docker run` sem passar -e PORT=...
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
