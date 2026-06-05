FROM python:3.12-slim

RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy entire repo (context must be repo root)
COPY pyproject.toml README.md LICENSE uv.lock* /app/
COPY src/ /app/src/
COPY web/ /app/web/

WORKDIR /app/web

# Remove host .venv so uv creates a fresh one
RUN rm -rf .venv

# Install deps
RUN uv sync --no-dev

# Build Tailwind CSS
RUN npm install && npm run build

# Collect static files
RUN uv run python manage.py collectstatic --noinput

# Ensure cache directory exists (for XDG_CACHE_HOME fallback)
RUN mkdir -p /data/cache

EXPOSE 8080

COPY web/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]