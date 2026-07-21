import os
import json
import jieba
import jieba.analyse
import requests
from config import Config

EXPLORE_SYSTEM_PROMPT = """你是"白云文化文旅探索助手"，专注于提供广州市白云区文旅景点的深度信息检索和智能推荐。
你的职责包括：
1. 提供景点的详细背景信息、文化历史渊源、特色亮点
2. 根据用户查询智能推荐相关的附近景点、文化活动和非遗项目
3. 规划最佳游览路线，综合考虑距离、时间、开放时间等因素
4. 语言亲切自然，像本地资深导游一样提供实用游览建议

回答要求：
- 必须基于检索到的知识图谱数据，不得编造不存在的信息
- 如果没有足够数据，诚实提示用户并建议查询其他内容
- 提供的信息应结构化清晰，包含游览建议"""

ROUTE_SYSTEM_PROMPT = """你是"白云文化智慧出行助手"，专注于为游客规划广州市白云区的最佳游览路线。
你的职责包括：
1. 基于知识图谱中的实体关系，推荐从起点到终点的最佳游览路径
2. 智能安排途经景点顺序，优化游览效率
3. 考虑景点间的距离、交通便利性、开放时间
4. 标注沿途可用的充电站、住宿、餐饮等配套设施
5. 提供时间和里程估算

回答要求：
- 路线规划必须基于知识图谱中真实存在的景点和设施
- 不得编造不存在的景点或路线
- 给出清晰的步聚和层次结构
- 语言亲和且实用，像有经验的旅游规划师"""


class RoutePlanner:
    """AI-driven route planning and intelligent tourism recommendations."""

    def __init__(self, knowledge_graph, data_cleaner, rag_engine):
        self.kg = knowledge_graph
        self.data_cleaner = data_cleaner
        self.rag = rag_engine

    # ==================================================================
    #  Route Planning
    # ==================================================================

    def plan_route(self, start_query, end_query=None, preferences=None):
        start_entities = self._resolve_location(start_query)
        end_entities = self._resolve_location(end_query) if end_query else []

        if not start_entities:
            return {
                "success": False,
                "message": f"未在知识图谱中找到与'{start_query}'相关的起点",
                "routes": []
            }

        waypoints = self._collect_waypoints(start_entities, end_entities)
        route_context = self._build_route_context(
            start_entities, end_entities, waypoints, preferences or {}
        )
        route_plan = self._generate_route_via_llm(
            start_query, end_query or "周边游览", route_context,
            waypoints, preferences or {}
        )

        return {
            "success": True,
            "start": {"query": start_query, "matches": start_entities[:5]},
            "end": {"query": end_query or "自动推荐", "matches": end_entities[:5]} if end_entities else None,
            "waypoints_count": len(waypoints),
            "route_plan": route_plan,
            "nearby_services": self._collect_services(start_entities)
        }

    def _resolve_location(self, query):
        entities = self.kg.search_entities(query, top_k=10)
        resolved = []
        valid_types = ('景点', '公园', '图书馆', '文化站', '非遗项目', '街镇')
        for name, score in entities:
            etype = self.kg.graph.nodes[name].get('type', '未知')
            if etype not in valid_types:
                continue
            resolved.append({"name": name, "type": etype, "score": score})

        for name, idx in self.kg.entity_index.items():
            if query in name or name in query:
                etype = self.kg.graph.nodes[name].get('type', '未知')
                valid_types = ('景点', '公园', '图书馆', '文化站', '非遗项目', '街镇')
                if etype in valid_types:
                    already = any(r['name'] == name for r in resolved)
                    if not already:
                        resolved.append({"name": name, "type": etype, "score": 2})

        resolved.sort(key=lambda x: x['score'], reverse=True)
        return resolved[:5]

    def _collect_waypoints(self, start_entities, end_entities):
        waypoints = {}
        seen = set()

        for entity in start_entities[:3]:
            name = entity['name']
            if name in seen:
                continue
            seen.add(name)
            nearby = self.kg.find_nearby_entities(name, max_depth=2)
            for n in nearby:
                if n['name'] not in waypoints:
                    waypoints[n['name']] = {
                        "type": n['type'],
                        "relation": n.get('via', ''),
                        "connected_to": name
                    }

        for entity in end_entities[:3]:
            name = entity['name']
            if name in seen:
                continue
            seen.add(name)
            nearby = self.kg.find_nearby_entities(name, max_depth=2)
            for n in nearby:
                if n['name'] not in waypoints:
                    waypoints[n['name']] = {
                        "type": n['type'],
                        "relation": n.get('via', ''),
                        "connected_to": name
                    }

        return waypoints

    def _collect_services(self, entities):
        services = {"充电站": [], "酒店": [], "民宿": [], "旅行社": [], "图书馆": []}
        seen = set()
        for entity in entities[:3]:
            sub = self.kg.get_subgraph(entity['name'], depth=3)
            for t in sub:
                for node in (t['head'], t['tail']):
                    ntype = self.kg.graph.nodes[node].get('type', '')
                    if ntype in services and node not in seen:
                        seen.add(node)
                        services[ntype].append(node)
        return services

    def _build_route_context(self, start_entities, end_entities, waypoints, preferences):
        parts = []

        parts.append("【起点匹配】")
        for e in start_entities[:3]:
            parts.append(f"- {e['name']} (类型: {e['type']}, 相关度: {e['score']})")

        if end_entities:
            parts.append("\n【终点匹配】")
            for e in end_entities[:3]:
                parts.append(f"- {e['name']} (类型: {e['type']}, 相关度: {e['score']})")

        parts.append(f"\n【沿途可选景点/设施】共{len(waypoints)}个")
        types = {}
        for name, info in waypoints.items():
            types.setdefault(info['type'], []).append(name)
        for t, names in sorted(types.items()):
            parts.append(f"- {t}: {', '.join(names[:10])}")

        if preferences:
            parts.append(f"\n【用户偏好】")
            if isinstance(preferences, dict):
                for k, v in preferences.items():
                    parts.append(f"- {k}: {v}")
            elif isinstance(preferences, list):
                for item in preferences:
                    parts.append(f"- {item}")
            else:
                parts.append(f"- {preferences}")

        return "\n".join(parts)

    def _generate_route_via_llm(self, start, end, context, waypoints, preferences):
        user_prompt = (
            f"请基于以下白云区文旅知识图谱数据，为用户规划最佳游览路线。\n\n"
            f"路线数据：\n{context}\n\n"
            f"起点：{start}\n"
            f"终点：{end}\n"
            f"偏好：{json.dumps(preferences, ensure_ascii=False) if preferences else '无特殊偏好'}\n\n"
            f"请规划最佳路线，格式如下：\n"
            f"1. 路线概览（总览描述）\n"
            f"2. 推荐游览顺序（按站点编号列出）\n"
            f"3. 每个站点的推荐理由和预计游览时间\n"
            f"4. 配套设施标注（附近充电站、住宿等）\n"
            f"5. 实用小贴士"
        )

        if not Config.LLM_API_KEY:
            return self._local_route_plan(start, end, waypoints)

        try:
            response = requests.post(
                Config.LLM_API_URL,
                headers={
                    "Authorization": f"Bearer {Config.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": Config.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": ROUTE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1200,
                    "stream": False,
                },
                timeout=30,
            )
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            return self._local_route_plan(start, end, waypoints)
        except Exception:
            return self._local_route_plan(start, end, waypoints)

    def _local_route_plan(self, start, end, waypoints):
        types_order = ['景点', '公园', '非遗项目', '图书馆', '文化站', '酒店', '民宿']
        ordered = []
        for t in types_order:
            for name, info in waypoints.items():
                if info['type'] == t and name not in ordered:
                    ordered.append(name)
        for name in waypoints:
            if name not in ordered:
                ordered.append(name)

        lines = [
            f"📍 白云区游览路线规划\n",
            f"起点: {start}",
            f"终点: {end}\n",
            f"🗺️ 推荐游览顺序（共{len(ordered)}站）:"
        ]
        for i, name in enumerate(ordered[:15], 1):
            wp = waypoints[name]
            lines.append(f"   {i}. [{wp['type']}] {name}")
        lines.append("")
        lines.append("💡 温馨提示：以上路线基于知识图谱数据生成，建议结合实际交通情况调整。")
        return "\n".join(lines)

    # ==================================================================
    #  Nearby Attraction Recommendation
    # ==================================================================

    def get_nearby_attractions(self, entity_name, max_distance=3, max_results=10):
        nearby_entities = self.kg.find_nearby_entities(
            entity_name, max_depth=max_distance,
            entity_types={'景点', '公园', '非遗项目', '图书馆', '文化站',
                          '酒店', '民宿', '活动'}
        )
        return nearby_entities[:max_results]

    def _find_path(self, start, end, max_depth=10):
        if start not in self.kg.graph or end not in self.kg.graph:
            return []
        try:
            path = next(iter(
                self.kg.graph.neighbors(start) & self.kg.graph.neighbors(end)
            ), None)
            if path:
                return [start, path, end]
        except Exception:
            pass
        return [start, end]

    # ==================================================================
    #  AI-Enhanced Entity Detail
    # ==================================================================

    def get_enhanced_detail(self, entity_name):
        details = self.kg.get_entity_details(entity_name)
        if not details:
            return None
        nearby = self.get_nearby_attractions(entity_name, max_distance=3, max_results=5)
        subgraph = self.kg.get_subgraph(entity_name, depth=2)

        context = f"实体名称: {entity_name}\n类型: {details['type']}\n"
        for rel in details['relations'][:15]:
            context += f"- {details['entity']} {rel['relation']} {rel['tail']}\n"
        if nearby:
            context += "\n附近关联: " + ", ".join(
                f"{n['name']}({n['type']})" for n in nearby
            )

        description = self._generate_description_via_llm(entity_name, context)
        return {
            "entity": details['entity'],
            "type": details['type'],
            "relations": details['relations'],
            "subgraph": subgraph,
            "nearby_attractions": nearby,
            "ai_description": description,
        }

    def _generate_description_via_llm(self, entity_name, context):
        user_prompt = (
            f"请根据以下知识图谱数据，为'{entity_name}'提供详细的背景介绍。\n\n"
            f"数据：\n{context}\n\n"
            f"请包括：\n1. 基本信息和定位\n2. 文化历史背景（如适用）\n"
            f"3. 特色亮点\n4. 游览建议"
        )

        if not Config.LLM_API_KEY:
            return self._local_description(entity_name, context)

        try:
            response = requests.post(
                Config.LLM_API_URL,
                headers={
                    "Authorization": f"Bearer {Config.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": Config.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 800,
                    "stream": False,
                },
                timeout=30,
            )
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            return self._local_description(entity_name, context)
        except Exception:
            return self._local_description(entity_name, context)

    def _local_description(self, entity_name, context):
        lines = [f"📍 {entity_name}\n"]
        for line in context.split('\n'):
            line = line.strip()
            if line.startswith('- ') or line.startswith('·'):
                lines.append(f"  {line}")
        lines.append("\n💡 附近还有其他文旅资源可以探索。")
        return "\n".join(lines)

    # ==================================================================
    #  AI Intelligent Search
    # ==================================================================

    def ai_search(self, query, search_type="general", image_base64=None):
        graph_results = self.rag._graph_search(query, top_k=5)
        text_results = self.rag._keyword_search(query, top_k=5)

        context_parts = []
        if graph_results:
            context_parts.append("【知识图谱匹配】")
            for gr in graph_results:
                context_parts.append(f"- {gr['entity']} (类型: {gr['type']}, 相关度: {gr['score']})")
                for fact in gr['facts'][:5]:
                    context_parts.append(f"  · {fact}")
        if text_results:
            context_parts.append("\n【数据匹配】")
            for tr in text_results[:5]:
                context_parts.append(f"- [{tr.get('category', '')}] {tr['text']}")
        context = "\n".join(context_parts)

        image_analysis = None
        if image_base64:
            image_analysis = self._analyze_image(query, image_base64, context)
            if image_analysis:
                context_parts.append("\n【图片分析结果】")
                context_parts.append(image_analysis)
                context = "\n".join(context_parts)

        user_prompt = (
            f"请基于以下白云区文旅数据，回答用户的检索请求。\n\n"
            f"数据：\n{context}\n\n"
            f"用户查询：{query}\n"
            f"检索类型：{search_type}\n\n"
            f"请提供结构化的检索结果，包括："
            f"1. 核心匹配结果\n2. 相关拓展推荐\n3. 实用建议"
        )

        if not Config.LLM_API_KEY:
            result = {"answer": self._local_search_result(query, context),
                      "entities": graph_results, "source": "local"}
            if image_analysis:
                result["image_analysis"] = image_analysis
            return result

        try:
            response = requests.post(
                Config.LLM_API_URL,
                headers={
                    "Authorization": f"Bearer {Config.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": Config.LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.4,
                    "max_tokens": 1000,
                    "stream": False,
                },
                timeout=30,
            )
            if response.status_code == 200:
                result = response.json()
                rv = {
                    "answer": result['choices'][0]['message']['content'],
                    "entities": graph_results,
                    "source": "deepseek_v4"
                }
                if image_analysis:
                    rv["image_analysis"] = image_analysis
                return rv
            result = {"answer": self._local_search_result(query, context),
                      "entities": graph_results, "source": "local"}
            if image_analysis:
                result["image_analysis"] = image_analysis
            return result
        except Exception:
            result = {"answer": self._local_search_result(query, context),
                      "entities": graph_results, "source": "local"}
            if image_analysis:
                result["image_analysis"] = image_analysis
            return result

    def _analyze_image(self, query, image_base64, context):
        if not Config.LLM_API_KEY:
            return self._local_image_analysis(query, image_base64)

        analysis_prompt = (
            "你是一个白云区文旅AI助手。用户上传了一张图片，请结合图片信息分析以下内容：\n\n"
            f"用户查询: {query}\n"
            f"可参考的白云区知识: {context[:1500]}\n\n"
            "请分析:\n"
            "1. 图片中可能包含什么文旅相关内容\n"
            "2. 该内容与白云区文旅的关联\n"
            "3. 给用户提供相关的进一步建议"
        )

        try:
            messages = [
                {"role": "system", "content": EXPLORE_SYSTEM_PROMPT},
            ]
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": analysis_prompt},
                    {"type": "image_url", "image_url": {"url": image_base64}}
                ]
            })

            response = requests.post(
                Config.LLM_API_URL,
                headers={
                    "Authorization": f"Bearer {Config.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": Config.LLM_MODEL,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 600,
                    "stream": False,
                },
                timeout=30,
            )
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return content
            return self._local_image_analysis(query, image_base64)
        except Exception:
            return self._local_image_analysis(query, image_base64)

    def _local_image_analysis(self, query, image_base64):
        try:
            import base64
            import io
            img_data = base64.b64decode(image_base64.split(',')[1] if ',' in image_base64 else image_base64)
            from PIL import Image
            img = Image.open(io.BytesIO(img_data))
            info = (
                f"【本地图片分析】\n"
                f"- 图片格式: {img.format}\n"
                f"- 图片尺寸: {img.size[0]} × {img.size[1]} 像素\n"
                f"- 色彩模式: {img.mode}\n"
                f"- 用户查询: {query}\n\n"
                f"💡 提示: 已上传图片，请描述图片内容以获取更精准的文旅信息推荐。"
            )
            return info
        except Exception as e:
            return f"图片分析: 用户上传了一张图片（查询: {query}），请结合白云区文旅知识回答。"

    def _local_search_result(self, query, context):
        lines = ["📋 检索结果：\n"]
        for line in context.split('\n'):
            line = line.strip()
            if line.startswith('- ') or line.startswith('·'):
                lines.append(f"  {line}")
        lines.append("\n💡 建议使用具体景点名称进行更精准的检索。")
        return "\n".join(lines)
