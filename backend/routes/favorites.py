"""
User favorites: bookmark entities and QA answers.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import get_db_session
from models import User
from middleware import sanitize, make_error

bp = Blueprint('favorites', __name__, url_prefix='/api/v2')

# Simple in-favorite tracking table (since we didn't create a dedicated model)
# We'll use a lightweight approach: store in user.extra_data or system_settings
# For production, a dedicated favorites table is better.


@bp.route('/favorites', methods=['GET'])
@jwt_required()
def list_favorites():
    user_id = get_jwt_identity()
    with get_db_session() as db:
        user = db.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return make_error("用户不存在", 404)
        favs = (user.extra_data or {}).get('favorites', [])
        return jsonify({"favorites": favs})


@bp.route('/favorites', methods=['POST'])
@jwt_required()
def add_favorite():
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    item_type = data.get('type')  # 'entity' | 'qa'
    item_id = sanitize(data.get('id', ''))
    name = sanitize(data.get('name', ''))
    if not item_type or not item_id:
        return make_error("缺少 type 或 id", 400)
    with get_db_session() as db:
        user = db.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return make_error("用户不存在", 404)
        extra = dict(user.extra_data or {})
        favs = list(extra.get('favorites', []))
        # Prevent duplicates
        if any(f['id'] == item_id and f['type'] == item_type for f in favs):
            return jsonify({"message": "已收藏"}), 200
        favs.append({
            "type": item_type,
            "id": item_id,
            "name": name,
        })
        extra['favorites'] = favs
        user.extra_data = extra
        return jsonify({"message": "收藏成功"}), 201


@bp.route('/favorites', methods=['DELETE'])
@jwt_required()
def remove_favorite():
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    item_type = data.get('type')
    # 与 add_favorite 保持同一 sanitize 规则，否则清洗后的存储 id 永远匹配不上
    item_id = sanitize(data.get('id', ''))
    with get_db_session() as db:
        user = db.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return make_error("用户不存在", 404)
        extra = dict(user.extra_data or {})
        favs = list(extra.get('favorites', []))
        favs = [f for f in favs if not (f['id'] == item_id and f['type'] == item_type)]
        extra['favorites'] = favs
        user.extra_data = extra
        return jsonify({"message": "已取消收藏"})
