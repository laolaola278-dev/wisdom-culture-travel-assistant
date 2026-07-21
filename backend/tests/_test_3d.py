"""临时测试 3D 实体数据"""
import requests
from collections import Counter

try:
    r = requests.get('http://127.0.0.1:5000/api/map/3d/entities', timeout=10)
    print('HTTP', r.status_code)
    d = r.json()
    ents = d.get('entities', [])
    print('total:', d.get('total'))
    print('实体数:', len(ents))
    print('---前 15 个实体---')
    for e in ents[:15]:
        print(f'  {e["id"]} | type={e["type"]} | {e["display_name"]}')
    print('---类型分布---')
    c = Counter(e['type'] for e in ents)
    for t, n in c.most_common():
        print(f'  {t}: {n}')

    # 对比前端过滤条件
    front_filter = ['星级酒店', '图书馆', '文化站', '旅行社', '民宿', 'A级景区/旅游景点', '公园']
    matched = [e for e in ents if e['type'] in front_filter]
    print(f'\n---前端过滤匹配---')
    print(f'前端过滤类型: {front_filter}')
    print(f'匹配建筑数: {len(matched)} / {len(ents)}')
    if not matched and ents:
        print('!!! 类型完全不匹配，这就是建筑不显示的原因 !!!')
except Exception as e:
    print(f'错误: {e}')
