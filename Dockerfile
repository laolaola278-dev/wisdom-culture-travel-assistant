FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY deploy/ ./deploy/
COPY 智慧文旅与交通建设数据/ ./智慧文旅与交通建设数据/
COPY frontend/dist/ ./frontend/

ENV PYTHONPATH=/app
ENV FLASK_ENV=production
ENV GUNICORN_WORKERS=2

# Railway provides PORT env var, default to 5000
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-5000}/api/health')" || exit 1

CMD gunicorn -c deploy/gunicorn.conf.py backend.app:create_app() --bind 0.0.0.0:${PORT:-5000}