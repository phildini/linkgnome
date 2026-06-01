FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm sqlite3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt linkgnome
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npx tailwindcss -i static/src/input.css -o static/css/output.css --minify && \
    mkdir -p /data && python manage.py collectstatic --noinput
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "-"]
