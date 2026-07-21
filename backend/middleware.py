"""
Production middleware: rate limiting, input sanitization, audit logging,
structured error responses, and security headers.
"""
import time
import logging
from functools import wraps

from flask import request, g, jsonify
import bleach

from config import Config
from database import get_db_session
from models import AuditLog

logger = logging.getLogger("baiyun.middleware")

_TRUSTED_PROXIES = {p.strip() for p in Config.TRUSTED_PROXIES if p.strip()}


def get_client_ip() -> str:
    """真实客户端 IP：仅当直连方是可信代理时才解析 X-Forwarded-For。

    采用 rightmost-untrusted 算法：从右向左跳过可信代理，取第一个
    不可信地址。nginx 的 proxy_add_x_forwarded_for 是追加语义——
    客户端伪造的条目位于最左侧，取首元素会让伪造值胜出，必须从右侧解析。
    """
    remote = request.remote_addr or 'unknown'
    if not (_TRUSTED_PROXIES and remote in _TRUSTED_PROXIES):
        return remote
    xff = request.headers.get('X-Forwarded-For', '')
    if not xff:
        return remote
    hops = [h.strip() for h in xff.split(',') if h.strip()]
    for hop in reversed(hops):
        if hop not in _TRUSTED_PROXIES:
            return hop
    # 全部条目均为可信代理（异常配置），回落直连地址
    return remote


# ── Input Sanitization ────────────────────────────────────────────

ALLOWED_TAGS = []
ALLOWED_ATTRIBUTES = {}


def sanitize(text):
    """Strip HTML and limit length."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    return text[:8192]


def sanitize_dict(data, max_depth=3):
    """Recursively sanitize a dict/list, stripping HTML from all strings."""
    if max_depth <= 0:
        return data
    if isinstance(data, dict):
        return {k: sanitize_dict(v, max_depth - 1) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_dict(v, max_depth - 1) for v in data]
    if isinstance(data, str):
        return sanitize(data)
    return data


# ── Audit Logging ─────────────────────────────────────────────────

def log_audit(action: str, resource_type: str, resource_id: str = None, details: dict = None):
    """Fire-and-forget audit log entry."""
    try:
        user_id = getattr(g, 'current_user_id', None)
        ip = get_client_ip()
        ua = request.user_agent.string if request.user_agent else ''
        with get_db_session() as db:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip,
                user_agent=ua[:512],
                details=details or {},
            )
            db.add(entry)
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")


def audit_after(action: str, resource_type: str, resource_id_key: str = None):
    """Decorator to auto-log after a view function succeeds."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.time()
            response = fn(*args, **kwargs)
            latency = int((time.time() - start) * 1000)
            rid = kwargs.get(resource_id_key) if resource_id_key else None
            log_audit(action, resource_type, rid, {"latency_ms": latency})
            return response
        return wrapper
    return decorator


# ── Request Timing & Context ──────────────────────────────────────

def setup_request_context():
    g.start_time = time.time()
    g.request_id = request.headers.get('X-Request-ID', '')


def teardown_request_context(response):
    """Add security headers and log slow requests."""
    duration = (time.time() - getattr(g, 'start_time', 0)) * 1000
    if duration > 5000:
        logger.warning(f"Slow request {request.path}: {duration:.0f}ms")

    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


# ── Structured Error Responses ────────────────────────────────────

def make_error(message: str, code: int = 400, error_type: str = "bad_request"):
    response = jsonify({
        "error": message,
        "error_type": error_type,
        "status_code": code,
    })
    response.status_code = code
    return response


# ── Validation Helpers ────────────────────────────────────────────

def validate_required(data: dict, fields: list) -> tuple:
    """Return (ok, error_response) tuple."""
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return False, make_error(f"缺少必填字段: {', '.join(missing)}")
    return True, None


def validate_length(value: str, max_len: int, field_name: str = "字段") -> tuple:
    if value and len(value) > max_len:
        return False, make_error(f"{field_name} 超过最大长度 {max_len}")
    return True, None
