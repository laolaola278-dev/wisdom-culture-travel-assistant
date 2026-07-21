FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY deploy/ ./deploy/
COPY 智慧文旅与交通建设数据/ ./智慧文旅与交通建设数据/
COPY frontend/dist/ ./frontend/

ENV PYTHONPATH=/app
ENV FLASK_ENV=production
ENV GUNICORN_WORKERS=4

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

CMD ["gunicorn", "-c", "deploy/gunicorn.conf.py", "backend.app:create_app()"]
