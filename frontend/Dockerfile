# Etapa 1: build estático do React.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY public ./public
COPY src ./src
RUN npm run build


FROM nginxinc/nginx-unprivileged:stable-alpine
# Sem proxy confiável por padrão; o deploy atrás de Caddy/balanceador sobrescreve.
ENV TRUSTED_PROXY_CIDR=127.0.0.1/32
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 8080