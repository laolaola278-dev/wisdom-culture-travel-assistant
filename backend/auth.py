"""
Authentication & Authorization layer.
JWT tokens, password hashing, RBAC decorators.
"""
import datetime
from functools import wraps

from flask import request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    get_jwt_identity, jwt_required, get_jwt,
    verify_jwt_in_request,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db_session
from models import User, RefreshToken


# ── Roles & Permissions ───────────────────────────────────────────

ROLE_HIERARCHY = {
    'guest': 0,
    'user': 1,
    'moderator': 2,
    'admin': 3,
    'superadmin': 4,
}


def hash_password(password: str) -> str:
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def create_tokens(user_id: int, fresh: bool = False) -> dict:
    access = create_access_token(identity=str(user_id), fresh=fresh)
    refresh = create_refresh_token(identity=str(user_id))
    # 登记 refresh jti（revoked=False），使 logout/封禁可按用户撤销全部 refresh token
    try:
        from flask_jwt_extended import decode_token
        payload = decode_token(refresh)
        with get_db_session() as db:
            db.add(RefreshToken(
                jti=payload['jti'],
                user_id=user_id,
                revoked=False,
                expires_at=datetime.datetime.fromtimestamp(payload['exp']),
            ))
    except Exception:
        # 登记失败不阻断登录；该 refresh token 将无法被按用户批量撤销
        pass
    return {"access_token": access, "refresh_token": refresh}


def revoke_token(jti: str, user_id: int, expires_at: datetime.datetime):
    with get_db_session() as db:
        existing = db.query(RefreshToken).filter_by(jti=jti).first()
        if existing:
            existing.revoked = True
            return
        rt = RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at, revoked=True)
        db.add(rt)


def revoke_all_user_tokens(user_id: int):
    """撤销该用户全部已登记的 token（登出/封禁时调用）。

    注：refresh token 签发时不入库，此处只能撤销已见过的 jti；
    彻底失效由 logout 端点显式登记当前 refresh jti 保证。"""
    with get_db_session() as db:
        db.query(RefreshToken).filter_by(user_id=user_id, revoked=False).update(
            {"revoked": True}, synchronize_session=False
        )


def is_token_revoked(jwt_payload: dict) -> bool:
    jti = jwt_payload.get('jti')
    if not jti:
        return True
    with get_db_session() as db:
        token = db.query(RefreshToken).filter_by(jti=jti, revoked=True).first()
        return token is not None


def get_current_user():
    identity = get_jwt_identity()
    if not identity:
        return None
    with get_db_session() as db:
        return db.query(User).filter_by(id=int(identity)).first()


def require_admin():
    """视图内管理员检查（需已通过 @jwt_required）。有权限返回 None，否则返回 403 响应。"""
    user = get_current_user()
    if not user or user.role not in ('admin', 'superadmin'):
        return jsonify({"error": "需要管理员权限"}), 403
    return None


# ── RBAC Decorators ───────────────────────────────────────────────

def require_role(*roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user or not user.is_active:
                return jsonify({"error": "用户已被禁用或不存在"}), 403
            if user.role not in roles and user.role not in ['admin', 'superadmin']:
                return jsonify({"error": "权限不足"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_auth(optional: bool = False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request(optional=optional)
            except Exception:
                if not optional:
                    return jsonify({"error": "未登录或Token无效"}), 401
            return fn(*args, **kwargs)
        return wrapper
    return decorator
