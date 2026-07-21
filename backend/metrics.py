"""
Prometheus metrics exporter for Flask.
Exposes /api/metrics endpoint for Prometheus scraping.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import Response
import time

# ── Metrics ───────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    'flask_request_count', 'Total request count',
    ['method', 'endpoint', 'status_code']
)
REQUEST_LATENCY = Histogram(
    'flask_request_latency_seconds', 'Request latency in seconds',
    ['method', 'endpoint']
)
ACTIVE_SESSIONS = Gauge(
    'baiyun_active_sessions', 'Number of active QA sessions'
)
LLM_REQUEST_COUNT = Counter(
    'baiyun_llm_request_count', 'LLM API calls',
    ['model', 'status']
)
LLM_LATENCY = Histogram(
    'baiyun_llm_latency_seconds', 'LLM API latency',
    ['model']
)
DB_CONNECTION_GAUGE = Gauge(
    'baiyun_db_connections', 'Active DB connections'
)


def register_metrics_route(app):
    @app.route('/api/metrics')
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


def observe_request(method, endpoint, status_code, latency):
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)


def observe_llm(model, status, latency_seconds):
    LLM_REQUEST_COUNT.labels(model=model, status=status).inc()
    LLM_LATENCY.labels(model=model).observe(latency_seconds)
