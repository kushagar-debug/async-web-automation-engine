# ==============================================================================
# Async Web Automation Engine - Production Dockerfile
# ==============================================================================
# Multi-stage container build optimized for security and minimal image size.
# Includes headless Chromium dependencies for Playwright automation.

FROM python:3.12-slim-bookworm AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system utilities and runtime libraries required by headless Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps chromium

# Copy application source code
COPY config/ ./config/
COPY core/ ./core/
COPY handlers/ ./handlers/
COPY utils/ ./utils/
COPY main.py run.py sync_token.py .env.example ./

# Create non-root user for security best practices
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app appuser && \
    mkdir -p /app/logs /app/.sessions && \
    chown -R appuser:appgroup /app

USER appuser

# Healthcheck to verify CLI responsiveness
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python main.py --help || exit 1

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
