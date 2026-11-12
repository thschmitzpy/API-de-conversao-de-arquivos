# Etapa 1: build estático do React.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY public ./public
COPY src ./src
RUN npm run build

# Etapa 2: nginx servindo o build e fazendo proxy de /api para a API.
# Variante sem root (UID 101); por isso escuta em 8080 em vez de 80.
FROM nginxinc/nginx-unprivileged:stable-alpine
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 8080