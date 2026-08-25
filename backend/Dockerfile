# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — install Python dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /install

# Install build dependencies for asyncpg and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install/deps -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runner — minimal production image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runner

WORKDIR /app

# Runtime libraries only (no gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install/deps /usr/local

# Copy application source
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check (Docker uses this to decide if the container is ready)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn — 2 workers, appropriate for 2vCPU VPS
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info"]
