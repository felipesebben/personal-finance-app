# web/Dockerfile: the Svelte frontend, built once and served by nginx.
#
# Stage 1 builds the static files with Node; stage 2 is a small nginx that
# serves them on 8501 (the address phones already use) and forwards /api/ to
# the backend, so the browser talks to one origin and needs no CORS.
# After editing web/src, rebuild: docker compose up -d --build web
# (or run `npm run dev` on the host for hot reload, see CLAUDE.md).

FROM node:22.15.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27.5-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8501
