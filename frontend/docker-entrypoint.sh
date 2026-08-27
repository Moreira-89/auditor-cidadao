#!/bin/sh
set -e

# Só $PORT é substituído (explícito, em vez de deixar o envsubst padrão trocar
# TUDO que começa com $ no arquivo) — nginx.conf.template usa $uri, que é uma
# variável do PRÓPRIO nginx, não do shell; um envsubst sem essa lista viraria
# uma string vazia ali e quebraria o roteamento.
: "${PORT:=8080}"
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
