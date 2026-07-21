"""
QA feedback & rating system.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import get_db_session
from models import QAHistory, QASession
from middleware import make_error

bp = Blueprint('feedback', __name__, url_prefix='/api/v2')


@bp.route('/feedback', methods=['POST'])
@jwt_required(optional=True)
def submit_feedback():
    data = request.get_json() or {}
    try:
        history_id = int(data.get('history_id'))
        rating = int(data.get('rating'))
    except (TypeError, ValueError):
        return make_error("history_id 与 rating 须为整数", 400)
    comment = str(data.get('comment', ''))
    if not (1 <= rating <= 5):
        return make_error("评分范围 1-5", 400)
    user_id = get_jwt_identity()
    fp = request.headers.get('X-Device-Fingerprint')
    with get_db_session() as db:
        h = db.query(QAHistory).filter_by(id=history_id).first()
        if not h:
            return make_error("记录不存在", 404)
        # 所有权校验：该条历史所属会话须归当前用户/设备
        s = db.query(QASession).filter_by(id=h.session_id).first()
        owned = False
        if s is not None:
            if user_id is not None:
                owned = s.user_id == int(user_id)
            elif fp:
                owned = s.user_id is None and s.device_fingerprint == fp
        if not owned:
            return make_error("无权评价此记录", 403, "forbidden")
        h.rating = rating
        # Store comment in sources metadata for simplicity
        sources = list(h.sources or [])
        sources.append({"type": "user_feedback", "comment": comment[:500], "rating": rating})
        h.sources = sources
        return jsonify({"message": "感谢反馈"})


@bp.route('/feedback/stats', methods=['GET'])
@jwt_required()
def feedback_stats():
    """Admin only: aggregate feedback statistics."""
    from auth import require_admin
    err = require_admin()
    if err:
        return err
    with get_db_session() as db:
        from sqlalchemy import func
        total = db.query(QAHistory).filter(QAHistory.rating.isnot(None)).count()
        avg_rating = db.query(func.avg(QAHistory.rating)).scalar() or 0
        distribution = db.query(QAHistory.rating, func.count(QAHistory.id)).group_by(QAHistory.rating).all()
        return jsonify({
            "total_rated": total,
            "average_rating": round(float(avg_rating), 2),
            "distribution": {str(r): c for r, c in distribution},
        })
