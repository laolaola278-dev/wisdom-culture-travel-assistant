"""
腾讯地图 API 代理 + 3D 地图数据服务
后端代理保护 API Key，聚合 3D 所需数据
"""
import json
import requests
from flask import Blueprint, request, jsonify, current_app
from config import Config

bp = Blueprint('map3d', __name__, url_prefix='/api/map')

# 白云区地标坐标（与 app.py 同步，避免循环导入）
BAIYUN_COORDINATES_3D = {
    "白云山风景名胜区": [113.2987, 23.1867],
    "白云山": [113.2987, 23.1867],
    "帽峰山": [113.4622, 23.2994],
    "白云湖": [113.2398, 23.2180],
    "南湖": [113.3397, 23.2256],
    "三元里抗英斗争纪念公园": [113.2607, 23.1558],
    "三元里": [113.2607, 23.1558],
    "广州市儿童公园": [113.2791, 23.1923],
    "白云公园": [113.2791, 23.1923],
    "云台花园": [113.2968, 23.1914],
    "广州体育馆": [113.2763, 23.1950],
    "白云国际会议中心": [113.2855, 23.1987],
    "广州白云站": [113.2470, 23.1734],
    "金沙洲": [113.2187, 23.1321],
    "同和": [113.3274, 23.1986],
    "永平": [113.3032, 23.2104],
    "三元里街": [113.2631, 23.1589],
    "景泰": [113.2688, 23.1691],
    "新市": [113.2570, 23.1899],
    "黄石": [113.2620, 23.2006],
    "棠景": [113.2544, 23.1684],
    "同德": [113.2328, 23.1642],
    "松洲": [113.2291, 23.1344],
    "石井": [113.2202, 23.2038],
    "石门": [113.2125, 23.2214],
    "均禾": [113.2692, 23.2470],
    "嘉禾": [113.2864, 23.2286],
    "鹤龙": [113.2845, 23.1720],
    "白云大道": [113.2890, 23.1910],
    "广州大道北": [113.3141, 23.1654],
    "白云新城": [113.2755, 23.1911],
}


def _infer_type(name):
    """根据名称推断实体类型"""
    if any(k in name for k in ['街', '镇']):
        return '街镇'
    if '公园' in name:
        return '公园'
    if '馆' in name:
        return '景点'
    if '站' in name or '中心' in name:
        return '景点'
    return '景点'

TENCENT_BASE = 'https://apis.map.qq.com'


def _tencent_request(endpoint, params):
    """统一腾讯地图 API 请求（配置 SECRET 时按官方规范计算 SN 签名）"""
    params = dict(params)
    params['key'] = Config.TENCENT_MAP_KEY
    if Config.TENCENT_MAP_SECRET:
        import hashlib
        sorted_qs = '&'.join(f'{k}={params[k]}' for k in sorted(params))
        raw = f'{endpoint}?{sorted_qs}{Config.TENCENT_MAP_SECRET}'
        params['sig'] = hashlib.md5(raw.encode('utf-8')).hexdigest()
    try:
        resp = requests.get(
            f'{TENCENT_BASE}{endpoint}',
            params=params,
            timeout=10,
        )
        return resp.json(), resp.status_code
    except Exception as e:
        return {'error': str(e), 'status': 'failed'}, 500


@bp.route('/proxy/geocoder', methods=['GET'])
def proxy_geocoder():
    """地理编码/逆地理编码代理"""
    address = request.args.get('address', '')
    location = request.args.get('location', '')
    if not address and not location:
        return jsonify({'error': '请提供 address 或 location'}), 400
    params = {}
    if address:
        params['address'] = address
    if location:
        params['location'] = location
    data, code = _tencent_request('/ws/geocoder/v1/', params)
    return jsonify(data), code


@bp.route('/proxy/place/search', methods=['GET'])
def proxy_place_search():
    """地点搜索代理"""
    keyword = request.args.get('keyword', '')
    boundary = request.args.get('boundary', 'region(白云区,0)')
    page_size = request.args.get('page_size', 20, type=int)
    if not keyword:
        return jsonify({'error': '请提供 keyword'}), 400
    params = {
        'keyword': keyword,
        'boundary': boundary,
        'page_size': min(page_size, 20),
        'output': 'json',
    }
    data, code = _tencent_request('/ws/place/v1/search', params)
    return jsonify(data), code


@bp.route('/proxy/direction', methods=['GET'])
def proxy_direction():
    """路线规划代理"""
    from_lat = request.args.get('from_lat', type=float)
    from_lng = request.args.get('from_lng', type=float)
    to_lat = request.args.get('to_lat', type=float)
    to_lng = request.args.get('to_lng', type=float)
    if any(v is None for v in (from_lat, from_lng, to_lat, to_lng)):
        return jsonify({'error': '请提供起终点坐标'}), 400
    params = {
        'from': f'{from_lat},{from_lng}',
        'to': f'{to_lat},{to_lng}',
        'output': 'json',
    }
    data, code = _tencent_request('/ws/direction/v1/driving/', params)
    return jsonify(data), code


@bp.route('/3d/entities', methods=['GET'])
def get_3d_entities():
    """获取 3D 地图标记实体（坐标来自硬编码地标 + 知识图谱类型）"""
    entities = []
    try:
        # 从知识图谱获取类型信息（可选）
        kg = getattr(current_app, 'extensions', {}).get('kg') if hasattr(current_app, 'extensions') else None

        for idx, (name, coords) in enumerate(BAIYUN_COORDINATES_3D.items(), 1):
            lng, lat = coords[0], coords[1]
            # 优先从知识图谱获取类型
            etype = None
            if kg and name in kg.graph:
                etype = kg.graph.nodes[name].get('type')
            if not etype:
                etype = _infer_type(name)
            entities.append({
                'id': idx,
                'name': name,
                'display_name': name,
                'type': etype,
                'lat': float(lat),
                'lng': float(lng),
                'address': '',
                'location': '',
            })
        return jsonify({'entities': entities, 'total': len(entities)})
    except Exception as e:
        return jsonify({'error': str(e), 'entities': []}), 500


@bp.route('/3d/config', methods=['GET'])
def get_3d_config():
    """获取 3D 地图前端配置。
    浏览器端 SDK 必须持有 key（应在腾讯控制台按域名白名单限制）——
    优先返回专用浏览器 key，避免泄露服务端签名 key。"""
    browser_key = getattr(Config, 'TENCENT_MAP_BROWSER_KEY', '') or Config.TENCENT_MAP_KEY or ''
    return jsonify({
        'tencent_map_key': browser_key,
        'enable_3d': Config.ENABLE_3D_MAP,
        'center': [113.285, 23.19],
        'zoom': 12,
        'building_lod_max_distance': Config.BUILDING_LOD_MAX_DISTANCE,
        'traffic_update_interval': Config.TRAFFIC_UPDATE_INTERVAL,
        'crowd_update_interval': Config.CROWD_UPDATE_INTERVAL,
    })