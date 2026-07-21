"""直接用 Flask test client 测试 3D 实体（绕过 HTTP 服务器）"""
import sys
sys.path.insert(0, '.')

from app import create_app
app = create_app()

with app.test_client() as client:
    resp = client.get('/api/map/3d/entities')
    print(f"HTTP {resp.status_code}")
    import json
    data = json.loads(resp.data)
    print(f"total: {data.get('total')}")
    ents = data.get('entities', [])
    print(f"实体数: {len(ents)}")
    for e in ents[:10]:
        print(f"  {e['id']} | {e['type']} | {e['display_name']} ({e['lat']:.4f}, {e['lng']:.4f})")
    if 'error' in data:
        print(f"ERROR: {data['error']}")
