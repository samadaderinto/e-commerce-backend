FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json ./
COPY client/package.json ./client/package.json
RUN --mount=type=cache,target=/root/.npm \
    npm ci --workspace=client --no-audit --prefer-offline

FROM node:22-alpine AS builder
RUN apk add --no-cache libc6-compat
WORKDIR /app
ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID
ARG NEXT_PUBLIC_APPLE_CLIENT_ID
ENV NEXT_TELEMETRY_DISABLED=1 \
    DOCKER_BUILD=true \
    NODE_ENV=production \
    NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID \
    NEXT_PUBLIC_APPLE_CLIENT_ID=$NEXT_PUBLIC_APPLE_CLIENT_ID
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY client/package.json client/tsconfig.json client/next.config.ts ./client/
COPY client/public ./client/public
COPY client/src ./client/src
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=cache,target=/app/client/.next/cache \
    npm run build --workspace=client

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /app/client/public ./client/public
COPY --from=builder --chown=nextjs:nodejs /app/client/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/client/.next/static ./client/.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "client/server.js"]
