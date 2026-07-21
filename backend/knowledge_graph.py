import os
import json
import jieba
import jieba.analyse
import networkx as nx
from config import Config


# ── Domain‑specific dictionary terms for jieba ─────────────────────────
BAIYUN_DOMAIN_TERMS = [
    # 非遗项目
    "三元里抗英", "舞火龙", "广式红木宫灯", "广式硬木家具", "广式烧卖", "广式肠粉",
    "广式月饼", "广州珐琅", "广州木雕", "广州玉雕", "广州榄雕", "广州灰塑",
    "广州砖雕", "广州彩瓷", "广州刺绣", "广州戏服", "广州箫笛", "广州狮舞",
    "竹料鸡公狮", "白眉拳", "蔡李佛拳", "洪拳", "莫家拳", "咏春拳",
    "粤剧", "醒狮", "龙舟", "乞巧节", "郑仙诞",
    # 地名/景点
    "白云山", "帽峰山", "南湖", "白云湖", "金沙洲", "同和", "永平",
    "三元里", "景泰", "新市", "黄石", "棠景", "同德", "松洲",
    "石井", "石门", "均禾", "嘉禾", "鹤龙", "白云大道", "广州大道北",
    "白云新城", "广州白云站", "白云国际机场",
    # 文化名词
    "非物质文化遗产", "知识图谱", "文旅融合", "乡村旅游", "红色旅游",
    "智慧旅游", "全域旅游", "文创产品", "文旅产业",
    # 机构/设施
    "供电局", "充电站", "文化站", "图书馆", "档案馆", "少年宫",
    "旅行社", "民宿", "星级酒店",
]

BAIYUN_DISAMBIG_MAP = {
    "白云山": [
        ("风景名胜区", "景区"),
        ("街道", "街镇"),
        ("社区", "社区"),
    ],
    "三元里": [
        ("街道", "街镇"),
        ("抗英", "非遗项目"),
        ("社区", "社区"),
    ],
}

def _init_jieba_domain_dict():
    """Add domain‑specific words to jieba's dictionary for better tokenization."""
    for term in BAIYUN_DOMAIN_TERMS:
        jieba.add_word(term)


def _jaccard_similarity(a, b):
    """Calculate Jaccard similarity between two strings based on character bigrams."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    def _bigrams(s):
        s = s.lower().replace(' ', '')
        return set(s[i:i + 2] for i in range(len(s) - 1))
    set_a = _bigrams(a)
    set_b = _bigrams(b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


class KnowledgeGraph:
    def __init__(self):
        _init_jieba_domain_dict()
        self.graph = nx.DiGraph()
        self.entity_index = {}
        self.keyword_index = {}
        self.triples = []
        self.graph_data_dir = Config.GRAPH_DATA_DIR
        os.makedirs(self.graph_data_dir, exist_ok=True)
        self._entity_context_cache = {}

    def build_from_data(self, data_cleaner):
        # 重建到全新影子实例，完成后原子换引用：
        # 1) 避免在已有图上追加导致三元组/关系每次同步翻倍并持久化；
        # 2) 请求线程迭代旧结构时不会碰到构建中的字典（threaded 服务 + 后台同步）。
        builder = KnowledgeGraph.__new__(KnowledgeGraph)
        builder.graph = nx.DiGraph()
        builder.entity_index = {}
        builder.keyword_index = {}
        builder.triples = []
        builder.graph_data_dir = self.graph_data_dir
        builder._entity_context_cache = {}

        builder._build_scenic_graph(data_cleaner.get_scenic_spots())
        builder._build_park_graph(data_cleaner.get_parks())
        builder._build_library_graph(data_cleaner.get_libraries())
        builder._build_heritage_graph(data_cleaner.get_intangible_heritage())
        builder._build_hotel_graph(data_cleaner.get_hotels())
        builder._build_homestay_graph(data_cleaner.get_homestays())
        builder._build_travel_agency_graph(data_cleaner.get_travel_agencies())
        builder._build_culture_station_graph(data_cleaner.get_culture_stations())
        builder._build_charging_graph(data_cleaner.get_charging_stations()[:200])
        builder._build_activity_graph(data_cleaner.get_library_activities()[:300])
        builder._build_hostel_graph(data_cleaner.get_hostels()[:200])
        builder._build_power_graph(data_cleaner.get_power_stations())
        builder._build_service_point_graph(data_cleaner.get_library_service_points())
        builder._build_cross_relations()
        builder._build_keyword_index()

        # 原子换引用（CPython 属性赋值原子；读方拿到的是旧或新完整结构）
        self.graph = builder.graph
        self.entity_index = builder.entity_index
        self.keyword_index = builder.keyword_index
        self.triples = builder.triples
        self._entity_context_cache = {}

        self._save_graph()
        print(f"知识图谱构建完成: {self.graph.number_of_nodes()}个节点, {self.graph.number_of_edges()}条边, {len(self.triples)}条三元组")

    def _add_triple(self, head, relation, tail, extra_attrs=None):
        head = str(head).strip()
        tail = str(tail).strip()
        relation = str(relation).strip()
        if not head or not tail or not relation:
            return
        if head == tail:
            return
        # 同一构建内去重（跨关系构建可能重复产生同一三元组）
        if not hasattr(self, '_triple_seen'):
            self._triple_seen = set()
        key = (head, relation, tail)
        if key in self._triple_seen:
            return
        self._triple_seen.add(key)
        self.graph.add_edge(head, tail, relation=relation)
        if extra_attrs:
            for k, v in extra_attrs.items():
                self.graph.nodes[head][k] = self.graph.nodes[head].get(k, v)
                self.graph.nodes[tail][k] = self.graph.nodes[tail].get(k, v)
        self.triples.append({"head": head, "relation": relation, "tail": tail})
        if head not in self.entity_index:
            self.entity_index[head] = []
        self.entity_index[head].append({"relation": relation, "tail": tail})
        if tail not in self.entity_index:
            self.entity_index[tail] = []
        self.entity_index[tail].append({"relation": f"{relation}_反向", "tail": head})

        relation_type_map = {
            '位于': '地址', '所在街镇': '街镇', '申报地区': '地区',
            '属于类别': '类别', '级别': '级别', '保护单位': '机构',
            '公布时间': '时间', '开放时间': '时间', '营业时间': '时间',
            '联系电话': '联系方式', '属于类型': '类型',
        }
        if relation in relation_type_map:
            if 'type' not in self.graph.nodes[tail]:
                self.graph.nodes[tail]['type'] = relation_type_map[relation]

    def _set_entity_type(self, entity, entity_type):
        if entity in self.graph:
            self.graph.nodes[entity]['type'] = entity_type

    def _build_scenic_graph(self, spots):
        for item in spots:
            name = str(item.get('名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '属于类型', str(item.get('类型', '')))
            self._add_triple(name, '位于', str(item.get('地址', '')))
            town = str(item.get('所在街镇', '')).strip()
            if town:
                self._add_triple(name, '所在街镇', town)
                self._add_triple(town, '包含景点', name)
            self._set_entity_type(name, '景点')

    def _build_park_graph(self, parks):
        for item in parks:
            name = str(item.get('名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('地址', '')))
            self._add_triple(name, '开放时间', str(item.get('开放时间', '')))
            note = str(item.get('简介或备注', '')).strip()
            if note:
                self._add_triple(name, '备注', note)
            self._set_entity_type(name, '公园')

    def _build_library_graph(self, libraries):
        for item in libraries:
            name = str(item.get('图书馆', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('地址', '')))
            self._add_triple(name, '开放时间', f"{item.get('开放时间', '')} {item.get('开放时间点', '')}")
            self._set_entity_type(name, '图书馆')

    def _build_heritage_graph(self, items):
        for item in items:
            name = str(item.get('项目名称', '')).strip()
            if not name:
                continue
            category = str(item.get('类别', '')).strip()
            level = str(item.get('级别', '')).strip()
            area = str(item.get('申报地区或单位', '')).strip()
            protector = str(item.get('项目保护单位', '')).strip()
            pub_time = str(item.get('公布时间', '')).strip()
            if category:
                self._add_triple(name, '属于类别', category)
            if level:
                self._add_triple(name, '级别', level)
            if area:
                self._add_triple(name, '申报地区', area)
                self._add_triple(area, '拥有非遗', name)
            if protector:
                self._add_triple(name, '保护单位', protector)
            if pub_time:
                self._add_triple(name, '公布时间', pub_time)
            self._set_entity_type(name, '非遗项目')

    def _build_hotel_graph(self, hotels):
        for item in hotels:
            name = str(item.get('名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '属于类型', str(item.get('类型', '')))
            self._add_triple(name, '位于', str(item.get('地址', '')))
            town = str(item.get('所在镇街', '')).strip()
            if town:
                self._add_triple(name, '所在镇街', town)
                self._add_triple(town, '拥有酒店', name)
            self._set_entity_type(name, '酒店')

    def _build_homestay_graph(self, homestays):
        for item in homestays:
            name = str(item.get('名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('地址', '')))
            town = str(item.get('所在街镇', '')).strip()
            if town:
                self._add_triple(name, '所在街镇', town)
                self._add_triple(town, '拥有民宿', name)
            self._set_entity_type(name, '民宿')

    def _build_travel_agency_graph(self, agencies):
        for item in agencies:
            name = str(item.get('名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('地址', '')))
            self._set_entity_type(name, '旅行社')

    def _build_culture_station_graph(self, stations):
        for item in stations:
            name = str(item.get('名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('详细地址', '')))
            self._add_triple(name, '开放时间', str(item.get('开放时间', '')))
            level = str(item.get('文化站级别', '')).strip()
            if level:
                self._add_triple(name, '级别', level)
            self._set_entity_type(name, '文化站')

    def _build_charging_graph(self, stations):
        for item in stations:
            name = str(item.get('企业（单位）名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('地址', '')))
            town = str(item.get('镇街', '')).strip()
            if town:
                self._add_triple(name, '所在街镇', town)
            self._set_entity_type(name, '充电站')

    def _build_activity_graph(self, activities):
        for item in activities:
            name = str(item.get('活动名称', '')).strip()
            if not name:
                continue
            category = str(item.get('活动类别', '')).strip()
            location = str(item.get('活动地点', '')).strip()
            branch = str(item.get('分馆名称', '')).strip()
            if category:
                self._add_triple(name, '活动类别', category)
            if location:
                self._add_triple(name, '活动地点', location)
            if branch:
                self._add_triple(name, '举办分馆', branch)
                self._add_triple(branch, '举办活动', name)
            self._set_entity_type(name, '活动')

    def _build_hostel_graph(self, hostels):
        for item in hostels:
            name = str(item.get('现外挂酒店招牌名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('经营地址', '')))
            town = str(item.get('所属镇街', '')).strip()
            if town:
                self._add_triple(name, '所属镇街', town)
            self._set_entity_type(name, '旅馆')

    def _build_power_graph(self, stations):
        for item in stations:
            name = str(item.get('营业网点', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('地址', '')))
            self._add_triple(name, '营业时间', str(item.get('营业时间', '')))
            self._set_entity_type(name, '供电网点')

    def _build_service_point_graph(self, points):
        for item in points:
            name = str(item.get('服务点名称', '')).strip()
            if not name:
                continue
            self._add_triple(name, '位于', str(item.get('地址', '')))
            phone = str(item.get('服务电话', '')).strip()
            if phone:
                self._add_triple(name, '联系电话', phone)
            self._add_triple(name, '开放时间', str(item.get('开放时间', '')))
            self._set_entity_type(name, '服务点')

    def _build_cross_relations(self):
        scenic_names = set()
        park_names = set()
        heritage_names = set()
        for n in self.graph.nodes():
            ntype = self.graph.nodes[n].get('type', '')
            if ntype == '景点':
                scenic_names.add(n)
            elif ntype == '公园':
                park_names.add(n)
            elif ntype == '非遗项目':
                heritage_names.add(n)

        for s in scenic_names:
            for p in park_names:
                if s in p or p in s:
                    self._add_triple(s, '关联公园', p)
                    self._add_triple(p, '关联景点', s)

        for h in heritage_names:
            for s in scenic_names:
                if h[:2] in s or s[:2] in h:
                    self._add_triple(h, '关联景点', s)

    def _build_keyword_index(self):
        all_texts = []
        for n in self.graph.nodes():
            ntype = self.graph.nodes[n].get('type', '')
            all_texts.append(f"{n} {ntype}")

        for text in all_texts:
            keywords = jieba.analyse.extract_tags(text, topK=10)
            for kw in keywords:
                if kw not in self.keyword_index:
                    self.keyword_index[kw] = []
                entity = text.split()[0]
                if entity not in self.keyword_index[kw]:
                    self.keyword_index[kw].append(entity)

    def _save_graph(self):
        triples_path = os.path.join(self.graph_data_dir, 'triples.json')
        with open(triples_path, 'w', encoding='utf-8') as f:
            json.dump(self.triples, f, ensure_ascii=False, indent=2)

        entity_path = os.path.join(self.graph_data_dir, 'entities.json')
        entities = {}
        for n in self.graph.nodes():
            entities[n] = dict(self.graph.nodes[n])
        with open(entity_path, 'w', encoding='utf-8') as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)

        keyword_path = os.path.join(self.graph_data_dir, 'keyword_index.json')
        with open(keyword_path, 'w', encoding='utf-8') as f:
            json.dump(self.keyword_index, f, ensure_ascii=False, indent=2)

        graphml_path = os.path.join(self.graph_data_dir, 'knowledge_graph.graphml')
        try:
            nx.write_graphml(self.graph, graphml_path)
        except Exception:
            pass

    def load_graph(self):
        triples_path = os.path.join(self.graph_data_dir, 'triples.json')
        keyword_path = os.path.join(self.graph_data_dir, 'keyword_index.json')
        entity_path = os.path.join(self.graph_data_dir, 'entities.json')

        if not os.path.exists(triples_path):
            return False

        with open(triples_path, 'r', encoding='utf-8') as f:
            raw_triples = json.load(f)
        # 去重加载：修复历史版本重复追加导致的 triples.json 污染
        seen = set()
        self.triples = []
        for t in raw_triples:
            key = (t['head'], t['relation'], t['tail'])
            if key in seen:
                continue
            seen.add(key)
            self.triples.append(t)
        for t in self.triples:
            self.graph.add_edge(t['head'], t['tail'], relation=t['relation'])
            self.entity_index.setdefault(t['head'], []).append({"relation": t['relation'], "tail": t['tail']})
            self.entity_index.setdefault(t['tail'], []).append({"relation": f"{t['relation']}_反向", "tail": t['head']})

        if os.path.exists(entity_path):
            with open(entity_path, 'r', encoding='utf-8') as f:
                entities = json.load(f)
            for name, attrs in entities.items():
                if name not in self.graph:
                    self.graph.add_node(name)
                for k, v in attrs.items():
                    self.graph.nodes[name][k] = v

        if os.path.exists(keyword_path):
            with open(keyword_path, 'r', encoding='utf-8') as f:
                self.keyword_index = json.load(f)

        return self.graph.number_of_nodes() > 0

    def search_entities(self, query, top_k=5):
        query_keywords = jieba.analyse.extract_tags(query, topK=10)
        if not query_keywords:
            query_keywords = list(query)

        scored_entities = {}
        for kw in query_keywords:
            if kw in self.keyword_index:
                for entity in self.keyword_index[kw]:
                    if entity not in scored_entities:
                        scored_entities[entity] = 0
                    scored_entities[entity] += 1

        jaccard_threshold = 0.35
        query_lower = query.lower()
        for entity_name in self.entity_index:
            name_lower = entity_name.lower()
            sim = _jaccard_similarity(query_lower, name_lower)
            if sim >= jaccard_threshold:
                if entity_name not in scored_entities:
                    scored_entities[entity_name] = 0
                scored_entities[entity_name] += sim * 8
            elif len(name_lower) >= 3 and name_lower in query_lower:
                if entity_name not in scored_entities:
                    scored_entities[entity_name] = 0
                scored_entities[entity_name] += 5
            elif len(query_lower) >= 3 and query_lower in name_lower:
                if entity_name not in scored_entities:
                    scored_entities[entity_name] = 0
                scored_entities[entity_name] += 3

        sorted_entities = sorted(scored_entities.items(), key=lambda x: x[1], reverse=True)
        return sorted_entities[:top_k]

    def get_entity_with_context(self, entity_name):
        details = self.get_entity_details(entity_name)
        if not details:
            return None
        location_info = self._resolve_entity_context(entity_name)
        result = dict(details)
        result['context'] = location_info
        return result

    def _resolve_entity_context(self, entity_name):
        if entity_name in self._entity_context_cache:
            return self._entity_context_cache[entity_name]

        context = {}
        name_base = entity_name
        for suffix in ['风景名胜区', '街道', '社区', '村', '镇']:
            if entity_name.endswith(suffix):
                name_base = entity_name[:-len(suffix)]
                break

        if name_base in BAIYUN_DISAMBIG_MAP:
            context['ambig_names'] = []
            seen = set()
            for ambig_suffix, cat in BAIYUN_DISAMBIG_MAP[name_base]:
                full_pattern = name_base + ambig_suffix
                for en in self.entity_index:
                    if en == entity_name or en in seen:
                        continue
                    if full_pattern in en or (ambig_suffix in en and name_base in en):
                        seen.add(en)
                        ctx_info = {
                            'name': en,
                            'type': self.graph.nodes[en].get('type', '未知'),
                            'category': cat
                        }
                        context['ambig_names'].append(ctx_info)

        entity_type = self.graph.nodes[entity_name].get('type', '')
        relations = self.entity_index.get(entity_name, [])
        for rel in relations:
            rel_key = rel['relation']
            if rel_key in ('位于', '所在街镇', '所在镇街', '所属镇街', '地址'):
                context['location'] = rel['tail']
                break

        if not context.get('location'):
            for rel in relations:
                if '地址' in rel['relation'] or '街' in rel['tail'] or '镇' in rel['tail']:
                    context['location'] = rel['tail']
                    break

        context['type'] = entity_type
        context['display_name'] = f"{entity_name}（{entity_type}）" if entity_type else entity_name

        self._entity_context_cache[entity_name] = context
        return context

    def get_entity_details(self, entity_name):
        if entity_name not in self.entity_index:
            return None
        relations = self.entity_index[entity_name]
        entity_type = self.graph.nodes[entity_name].get('type', '\u672A\u77E5')
        context = self._resolve_entity_context(entity_name)
        return {
            "entity": entity_name,
            "type": entity_type,
            "display_name": context.get('display_name', entity_name),
            "location": context.get('location', ''),
            "ambig_names": context.get('ambig_names', []),
            "relations": relations
        }

    def get_subgraph(self, entity_name, depth=2):
        if entity_name not in self.graph:
            return []
        visited = set()
        result_triples = []
        queue = [(entity_name, 0)]
        while queue:
            node, d = queue.pop(0)
            if node in visited or d > depth:
                continue
            visited.add(node)
            for _, neighbor, data in self.graph.edges(node, data=True):
                if (node, neighbor) not in visited:
                    result_triples.append({
                        "head": node,
                        "relation": data.get('relation', ''),
                        "tail": neighbor
                    })
                    if neighbor not in visited:
                        queue.append((neighbor, d + 1))
        return result_triples

    def get_graph_stats(self):
        return {
            "total_entities": self.graph.number_of_nodes(),
            "total_relations": self.graph.number_of_edges(),
            "total_triples": len(self.triples),
            "entity_types": self._count_entity_types()
        }

    def _count_entity_types(self):
        type_count = {}
        for n in self.graph.nodes():
            ntype = self.graph.nodes[n].get('type', '未知')
            type_count[ntype] = type_count.get(ntype, 0) + 1
        return type_count

    def get_all_entities_by_type(self, entity_type):
        result = []
        for n in self.graph.nodes():
            if self.graph.nodes[n].get('type', '') == entity_type:
                result.append({
                    "name": n,
                    "relations": self.entity_index.get(n, [])
                })
        return result

    def find_nearby_entities(self, entity_name, max_depth=3, entity_types=None):
        if entity_name not in self.graph:
            return []

        if entity_types is None:
            entity_types = {'景点', '公园', '非遗项目', '图书馆', '文化站',
                            '酒店', '民宿', '活动', '旅行社', '充电站'}

        source_type = self.graph.nodes[entity_name].get('type', '')
        source_attrs = {}
        for rel in self.entity_index.get(entity_name, []):
            key = rel['relation']
            val = rel['tail']
            source_attrs[key] = val

        results = []
        seen = {entity_name}

        for candidate in self.entity_index:
            if candidate == entity_name:
                continue
            if candidate in seen:
                continue
            ctype = self.graph.nodes[candidate].get('type', '')
            if ctype not in entity_types:
                continue

            distance = 99
            match_reason = ""
            for rel in self.entity_index.get(candidate, []):
                key = rel['relation']
                val = rel['tail']

                if (key == '位于' or key == '所在街镇' or key == '所在镇街' or
                    key == '所属镇街' or key == '申报地区'):
                    # same place → close
                    if (key in source_attrs and
                        (source_attrs[key] == val or
                         source_attrs[key] in val or
                         val in source_attrs[key])):
                        if 1 < distance:
                            distance = 1
                            match_reason = f"同在: {val}"
                if key == '属于类别':
                    if ('属于类别' in source_attrs and
                        source_attrs['属于类别'] == val):
                        if 2 < distance:
                            distance = 2
                            match_reason = f"同类: {val}"
                if key == '属于类型':
                    if ('属于类型' in source_attrs and
                        source_attrs['属于类型'] == val):
                        if 2 < distance:
                            distance = 2
                            match_reason = f"同类: {val}"

                if entity_name in val or val in entity_name:
                    if 1 < distance:
                        distance = 1
                        match_reason = f"关联: {key}={val}"

            if distance < 99:
                seen.add(candidate)
                results.append({
                    "name": candidate,
                    "type": ctype,
                    "depth": distance,
                    "via": match_reason,
                    "relations": self.entity_index.get(candidate, [])[:5]
                })

        results.sort(key=lambda x: x['depth'])
        return results

    def get_entity_with_context(self, entity_name):
        details = self.get_entity_details(entity_name)
        if not details:
            return None
        nearby = self.find_nearby_entities(
            entity_name,
            max_depth=3,
            entity_types={'景点', '公园', '非遗项目', '图书馆', '文化站',
                          '酒店', '民宿', '活动', '旅行社', '充电站'}
        )
        subgraph = self.get_subgraph(entity_name, depth=2)
        return {
            "entity": details['entity'],
            "type": details['type'],
            "relations": details['relations'],
            "subgraph": subgraph,
            "nearby": nearby[:10]
        }

    def search_by_location(self, location_query, top_k=10):
        location_keywords = jieba.analyse.extract_tags(location_query, topK=5)
        if not location_keywords:
            location_keywords = list(location_query)

        scored = []
        for n in self.graph.nodes():
            score = 0
            for kw in location_keywords:
                if kw in n:
                    score += 2
            ntype = self.graph.nodes[n].get('type', '')
            if ntype in ('地址', '街镇'):
                if location_query in n or any(k in n for k in location_keywords):
                    score += 3
            if score > 0:
                scored.append((n, self.graph.nodes[n].get('type', ''), score))
        scored.sort(key=lambda x: x[2], reverse=True)
        return [{"name": s[0], "type": s[1], "score": s[2]} for s in scored[:top_k]]

    def get_entities_with_coordinates(self):
        coords = {}
        for n in self.graph.nodes():
            ntype = self.graph.nodes[n].get('type', '')
            if ntype not in ('地址',):
                continue
            for entity, rels in self.entity_index.items():
                for rel in rels:
                    if n in rel.get('tail', ''):
                        etype = self.graph.nodes[entity].get('type', '')
                        valid = ('景点', '公园', '图书馆', '文化站', '非遗项目',
                                 '酒店', '民宿', '充电站')
                        if etype in valid:
                            if entity not in coords:
                                coords[entity] = {"address": n, "type": etype}
        return coords
