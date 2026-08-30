# Multi-stage production build for Nuncio / ZeroPointIntel Platform
FROM node:22-alpine AS builder

WORKDIR /app

# Enable pnpm via corepack
RUN corepack enable && corepack prepare pnpm@11.20.0 --activate

# Copy root manifests and workspace configs
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/types/package.json ./packages/types/
COPY packages/core/package.json ./packages/core/
COPY packages/web/package.json ./packages/web/
COPY packages/eval/package.json ./packages/eval/
COPY adapters/catalog-csv/package.json ./adapters/catalog-csv/
COPY adapters/catalog-json/package.json ./adapters/catalog-json/
COPY adapters/catalog-shopify/package.json ./adapters/catalog-shopify/
COPY adapters/catalog-woocommerce/package.json ./adapters/catalog-woocommerce/

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source trees
COPY . .

# Build all TypeScript packages
RUN pnpm build

# Production Runner Stage
FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

# Enable pnpm
RUN corepack enable && corepack prepare pnpm@11.20.0 --activate

# Copy built workspace and node_modules from builder
COPY --from=builder /app ./

EXPOSE 3000

# Start production server
CMD ["node", "demo_server.mjs"]
