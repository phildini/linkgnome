FROM python:3.12-slim

RUN apt-get update && apt-get install -y nodejs npm sqlite3 ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt linkgnome

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

RUN npx tailwindcss -i static/src/input.css -o static/css/output.css --minify

RUN python manage.py collectstatic --noinput

RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]

EXPOSE 8080
