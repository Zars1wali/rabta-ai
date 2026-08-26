FROM node:20-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package files and install dependencies
COPY package.json package-lock.json ./
RUN npm ci --only=production

# Copy application source
COPY server.js ./
COPY approved_numbers.json ./

# Prepare auth_session directory
RUN mkdir -p /app/auth_session && chmod 777 /app/auth_session

# The auth_session directory is mounted as a named volume in compose
VOLUME ["/app/auth_session"]

EXPOSE 3001

# Health check — gateway /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:3001/health || exit 1

CMD ["node", "server.js"]
