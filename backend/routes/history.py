"""
QA History & Session persistence routes.
Replaces in-memory session with PostgreSQL-backed storage.
"""
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from database import get_db_session
from models import QASession, QAHistory
from middleware import sanitize, make_error

bp = Blueprint('history', __name__, url_prefix='/api/v2')


def _get_client_ip():
    from middleware import get_client_ip
    return get_client_ip()


def _check_session_owner(s, user_id):
    """所有权校验：登录用户比对 user_id；匿名请求比对设备指纹。
    返回 None 表示有权访问，否则返回错误响应。"""
    if user_id is not None:
        if s.user_id != int(user_id):
            return make_error("无权访问此会话", 403, "forbidden")
        return None
    fp = request.headers.get('X-Device-Fingerprint')
    if fp and s.device_fingerprint == fp and s.user_id is None:
        return None
    return make_error("无权访问此会话", 403, "forbidden")


def _create_db_session(user_id=None):
    sid = str(uuid.uuid4())[:16]
    with get_db_session() as db:
        s = QASession(
            session_id=sid,
            user_id=user_id,
            device_fingerprint=request.headers.get('X-Device-Fingerprint'),
            ip_address=_get_client_ip(),
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24),
        )
        db.add(s)
        db.flush()
        return s.to_dict() if hasattr(s, 'to_dict') else {"session_id": sid}


@bp.route('/sessions', methods=['GET'])
@jwt_required(optional=True)
def list_sessions():
    """List user's QA sessions (or anonymous by fingerprint)."""
    user_id = get_jwt_identity()
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))
    with get_db_session() as db:
        query = db.query(QASession)
        if user_id:
            query = query.filter_by(user_id=int(user_id))
        else:
            fp = request.headers.get('X-Device-Fingerprint')
            if fp:
                query = query.filter_by(device_fingerprint=fp)
            else:
                return jsonify({"sessions": [], "total": 0})
        total = query.count()
        sessions = query.order_by(QASession.updated_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        # 一次分组查询取消息数，避免逐会话 N+1
        from sqlalchemy import func
        counts = {}
        if sessions:
            ids = [s.id for s in sessions]
            rows = (db.query(QAHistory.session_id, func.count(QAHistory.id))
                    .filter(QAHistory.session_id.in_(ids))
                    .group_by(QAHistory.session_id).all())
            counts = dict(rows)
        return jsonify({
            "sessions": [
                {
                    "id": s.session_id,
                    "title": s.title or f"会话 {s.id}",
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "message_count": counts.get(s.id, 0),
                }
                for s in sessions
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        })


@bp.route('/sessions/<session_id>', methods=['GET'])
@jwt_required(optional=True)
def get_session(session_id):
    user_id = get_jwt_identity()
    with get_db_session() as db:
        s = db.query(QASession).filter_by(session_id=session_id).first()
        if not s:
            return make_error("会话不存在", 404, "not_found")
        err = _check_session_owner(s, user_id)
        if err:
            return err
        return jsonify({
            "id": s.session_id,
            "title": s.title or f"会话 {s.id}",
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "messages": [
                {
                    "id": h.id,
                    "question": h.question,
                    "answer": h.answer,
                    "agent_used": h.agent_used,
                    "sources": h.sources,
                    "rating": h.rating,
                    "created_at": h.created_at.isoformat(),
                }
                for h in s.histories
            ],
        })


@bp.route('/sessions/<session_id>', methods=['DELETE'])
@jwt_required(optional=True)
def delete_session(session_id):
    user_id = get_jwt_identity()
    with get_db_session() as db:
        s = db.query(QASession).filter_by(session_id=session_id).first()
        if not s:
            return make_error("会话不存在", 404, "not_found")
        err = _check_session_owner(s, user_id)
        if err:
            return err
        db.delete(s)
        return jsonify({"message": "已删除"})


@bp.route('/sessions/<session_id>/title', methods=['PUT'])
@jwt_required(optional=True)
def update_session_title(session_id):
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    title = sanitize(data.get('title', ''))
    if not title:
        return make_error("标题不能为空", 400)
    with get_db_session() as db:
        s = db.query(QASession).filter_by(session_id=session_id).first()
        if not s:
            return make_error("会话不存在", 404)
        err = _check_session_owner(s, user_id)
        if err:
            return err
        s.title = title[:255]
        return jsonify({"message": "已更新"})


def save_qa_to_db(session_id: str, question: str, answer: str, agent_used: str,
                  sources: list, latency_ms: int, tokens_used: int, model_name: str):
    """Called by the main app after LLM response."""
    with get_db_session() as db:
        s = db.query(QASession).filter_by(session_id=session_id).first()
        if not s:
            return
        # Auto-generate title from first question
        if not s.title and question:
            s.title = question[:100]
        h = QAHistory(
            session_id=s.id,
            question=question[:4000],
            answer=answer[:16000],
            agent_used=agent_used,
            sources=sources or [],
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            model_name=model_name,
        )
        db.add(h)
