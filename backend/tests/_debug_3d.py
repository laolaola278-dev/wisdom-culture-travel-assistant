"""调试 3D 实体数据来源"""
import sys
sys.path.insert(0, '.')

# 测试 1: 知识图谱节点名称 vs BAIYUN_COORDINATES 匹配
from knowledge_graph import KnowledgeGraph
from app import BAIYUN_COORDINATES

kg = KnowledgeGraph()
kg.load_graph()
print(f"知识图谱节点数: {kg.graph.number_of_nodes()}")
print(f"BAIYUN_COORDINATES 数: {len(BAIYUN_COORDINATES)}")

print("\n--- BAIYUN_COORDINATES 的 key ---")
for k in BAIYUN_COORDINATES.keys():
    print(f"  '{k}'")

print("\n--- 知识图谱中匹配到坐标的节点 ---")
matched = 0
for name, data in kg.graph.nodes(data=True):
    if name in BAIYUN_COORDINATES:
        matched += 1
        print(f"  精确匹配: '{name}' type={data.get('type','?')}")

# 模糊匹配
fuzzy = 0
for name, data in kg.graph.nodes(data=True):
    if name not in BAIYUN_COORDINATES:
        for coord_name in BAIYUN_COORDINATES:
            if name in coord_name or coord_name in name:
                fuzzy += 1
                if fuzzy <= 10:
                    print(f"  模糊匹配: '{name}' ~ '{coord_name}' type={data.get('type','?')}")
                break

print(f"\n精确匹配: {matched}, 模糊匹配: {fuzzy}, 合计: {matched + fuzzy}")

if matched + fuzzy == 0:
    print("\n--- 知识图谱前 20 个节点名 ---")
    for i, (name, data) in enumerate(kg.graph.nodes(data=True)):
        if i >= 20:
            break
        print(f"  '{name}' type={data.get('type','?')}")
