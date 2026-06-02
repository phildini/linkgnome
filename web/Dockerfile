FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm sqlite3 ca-certificates fuse3 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY --from=flyio/litefs:0.5 /usr/local/bin/litefs /usr/local/bin/litefs

COPY web/litefs.yml /etc/litefs.yml

WORKDIR /app

COPY web/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN uv pip install --system --no-cache .

COPY web/package.json web/package-lock.json* ./
RUN npm install

COPY web/ .

RUN npx tailwindcss -i static/src/input.css -o static/css/output.css --minify

RUN python manage.py collectstatic --noinput

RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["litefs", "mount", "-config", "/etc/litefs.yml"]

EXPOSE 8080 8081
