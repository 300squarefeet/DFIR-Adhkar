# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS deps
RUN corepack enable && corepack prepare pnpm@9 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM deps AS dev
COPY . .
ENV NODE_ENV=development
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

FROM deps AS build
COPY . .
ENV NODE_ENV=production
RUN pnpm build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s CMD wget -qO- http://localhost/ >/dev/null || exit 1
