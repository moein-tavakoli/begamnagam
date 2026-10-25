FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --fetch-retries=5 --fetch-timeout=300000

FROM node:24-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 BUILD_STANDALONE=1
ARG INTERNAL_API_URL=http://backend:8000
ARG APP_BASE_URL=http://localhost:3000
ARG SEO_INDEXABLE=0
# Public metadata, robots and sitemap are generated for this origin at build time.
ENV INTERNAL_API_URL=$INTERNAL_API_URL APP_BASE_URL=$APP_BASE_URL SEO_INDEXABLE=$SEO_INDEXABLE
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S app && adduser -S app -G app
COPY --from=builder --chown=app:app /app/public ./public
COPY --from=builder --chown=app:app /app/.next/standalone ./
COPY --from=builder --chown=app:app /app/.next/static ./.next/static
USER app
EXPOSE 3000
CMD ["node", "server.js"]
