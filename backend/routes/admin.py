"""
Admin dashboard APIs: user management, audit logs, system settings.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from database import get_db_session
from models import User, AuditLog, SystemSetting
from auth import get_current_user, require_admin, ROLE_HIERARCHY
from middleware import make_error, sanitize

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# 保留原名，模块内及 feedback.py 的既有调用不变
_require_admin = require_admin


@bp.route('/users', methods=['GET'])
@jwt_required()
def list_users():
    err = _require_admin()
    if err:
        return err
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 20, type=int)))
    with get_db_session() as db:
        total = db.query(User).count()
        users = db.query(User).order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return jsonify({
            "users": [
                {
                    "id": str(u.public_id),
                    "username": u.username,
                    "email": u.email,
                    "role": u.role,
                    "is_active": u.is_active,
                    "last_login": u.last_login_at.isoformat() if u.last_login_at else None,
                    "created_at": u.created_at.isoformat(),
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        })


@bp.route('/users/<public_id>/role', methods=['PUT'])
@jwt_required()
def update_user_role(public_id):
    err = _require_admin()
    if err:
        return err
    current = get_current_user()
    data = request.get_json() or {}
    new_role = data.get('role')
    if new_role not in ROLE_HIERARCHY:
        return make_error("无效角色", 400)
    # 禁止授予不低于自身层级的角色（仅 superadmin 可任命 admin，无人可通过 API 任命 superadmin）
    if ROLE_HIERARCHY[new_role] >= ROLE_HIERARCHY[current.role]:
        return make_error("不能授予不低于自身层级的角色", 403, "forbidden")
    with get_db_session() as db:
        user = db.query(User).filter_by(public_id=public_id).first()
        if not user:
            return make_error("用户不存在", 404)
        # 禁止修改层级不低于自己的用户
        if ROLE_HIERARCHY.get(user.role, 0) >= ROLE_HIERARCHY[current.role]:
            return make_error("不能修改同级或更高级用户", 403, "forbidden")
        user.role = new_role
        return jsonify({"message": "已更新"})


@bp.route('/users/<public_id>/status', methods=['PUT'])
@jwt_required()
def update_user_status(public_id):
    err = _require_admin()
    if err:
        return err
    data = request.get_json() or {}
    is_active = data.get('is_active')
    if is_active is None:
        return make_error("缺少 is_active", 400)
    with get_db_session() as db:
        user = db.query(User).filter_by(public_id=public_id).first()
        if not user:
            return make_error("用户不存在", 404)
        user.is_active = bool(is_active)
        return jsonify({"message": "已更新", "is_active": user.is_active})


@bp.route('/audit-logs', methods=['GET'])
@jwt_required()
def list_audit_logs():
    err = _require_admin()
    if err:
        return err
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(200, max(1, request.args.get('per_page', 50, type=int)))
    action = request.args.get('action')
    with get_db_session() as db:
        query = db.query(AuditLog)
        if action:
            query = query.filter_by(action=action)
        total = query.count()
        logs = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        return jsonify({
            "logs": [
                {
                    "id": l.id,
                    "action": l.action,
                    "resource_type": l.resource_type,
                    "resource_id": l.resource_id,
                    "ip_address": l.ip_address,
                    "details": l.details,
                    "created_at": l.created_at.isoformat(),
                }
                for l in logs
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        })


@bp.route('/settings', methods=['GET'])
@jwt_required()
def get_settings():
    err = _require_admin()
    if err:
        return err
    with get_db_session() as db:
        settings = db.query(SystemSetting).all()
        return jsonify({s.key: s.value for s in settings})


@bp.route('/settings', methods=['PUT'])
@jwt_required()
def update_settings():
    err = _require_admin()
    if err:
        return err
    data = request.get_json() or {}
    with get_db_session() as db:
        for key, value in data.items():
            s = db.query(SystemSetting).filter_by(key=key).first()
            if s:
                s.value = value
            else:
                db.add(SystemSetting(key=key, value=value))
        return jsonify({"message": "已更新"})
