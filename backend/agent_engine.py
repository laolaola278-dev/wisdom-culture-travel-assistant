import json
import jieba
import jieba.analyse
from config import Config

AGENT_DESCRIPTIONS = {
    "culture": {
        "name": "文化传承Agent",
        "description": "处理非遗、历史、民俗、文化背景类问题",
        "keywords": ["非遗", "文化遗产", "历史", "传统", "民俗", "文化", "舞火龙",
                     "三元里抗英", "广绣", "珐琅", "木雕", "龙舟", "乞巧", "粤剧",
                     "醒狮", "传承", "典故", "由来", "起源", "背景"],
    },
    "route": {
        "name": "行程规划Agent",
        "description": "处理路线规划、行程安排、游览顺序类问题",
        "keywords": ["路线", "路线规划", "行程", "规划", "怎么走", "先去", "再去",
                     "顺序", "一日游", "半日游", "游览", "路线推荐", "途经",
                     "出行", "交通", "怎么去", "到达", "从", "出发"],
    },
    "nearby": {
        "name": "附近推荐Agent",
        "description": "处理附近景点、周边设施、关联推荐类问题",
        "keywords": ["附近", "周边", "旁边", "邻近", "附近有", "周围", "毗邻",
                     "推荐", "还有", "还有什么", "配套", "服务设施"],
    },
    "general": {
        "name": "通用问答Agent",
        "description": "处理景点信息、地址、开放时间等事实类问题",
        "keywords": ["在哪里", "地址", "开放时间", "电话", "门票", "价格",
                     "景点", "公园", "图书馆", "酒店", "民宿", "充电站",
                     "是什么", "有哪些", "介绍"],
    },
}


class BaseAgent:
    def __init__(self, agent_id, config, kg, rag_engine, data_cleaner, planner):
        self.id = agent_id
        self.config = config
        self.kg = kg
        self.rag = rag_engine
        self.data_cleaner = data_cleaner
        self.planner = planner
        self.name = config["name"]
        self.keywords = config["keywords"]

    def match_score(self, question):
        matched = 0
        for kw in self.keywords:
            if kw in question:
                matched += 1
        return matched / max(len(self.keywords), 1)

    def process(self, question, user_context=None):
        raise NotImplementedError


class CultureAgent(BaseAgent):
    def __init__(self, kg, rag_engine, data_cleaner, planner):
        super().__init__("culture", AGENT_DESCRIPTIONS["culture"],
                         kg, rag_engine, data_cleaner, planner)

    def process(self, question, user_context=None):
        result = self.rag.query(question)
        enriched = self._enrich_culture_context(question, result)
        result["agent"] = "culture"
        result["agent_name"] = self.name
        result["enriched_context"] = enriched
        result["answer"] = self._build_culture_answer(question, result, enriched)
        return result

    def _enrich_culture_context(self, question, result):
        enriched = []
        heritage_items = self.data_cleaner.get_intangible_heritage()
        for item in heritage_items:
            name = str(item.get('项目名称', ''))
            if any(kw in question for kw in [name, name[:2]]):
                enriched.append({
                    "name": name,
                    "category": str(item.get('类别', '')),
                    "level": str(item.get('级别', '')),
                    "protector": str(item.get('项目保护单位', '')),
                })
        return enriched[:3]

    def _build_culture_answer(self, question, result, enriched):
        base_answer = result.get('answer', '')
        if enriched and len(base_answer) < 100:
            extra = "\n\n🏮 **相关非遗项目**:\n"
            for item in enriched:
                extra += f"- {item['name']} ({item['category']}, {item['level']})\n"
            return base_answer + extra
        return base_answer


class RouteAgent(BaseAgent):
    def __init__(self, kg, rag_engine, data_cleaner, planner):
        super().__init__("route", AGENT_DESCRIPTIONS["route"],
                         kg, rag_engine, data_cleaner, planner)

    def process(self, question, user_context=None):
        entities = self._extract_entities_for_route(question)
        if entities:
            start = entities[0]
            end = entities[1] if len(entities) > 1 else None
            route_result = self.planner.plan_route(start, end)
            # 规划失败（起点无法解析等）时回退 RAG，避免返回空答案
            if route_result.get('success') and route_result.get('route_plan'):
                return {
                    "question": question,
                    "answer": route_result['route_plan'],
                    "agent": "route",
                    "agent_name": self.name,
                    "route_result": route_result,
                    "waypoints": route_result.get('waypoints_count', 0),
                    "source": "route_agent"
                }
        result = self.rag.query(question)
        result["agent"] = "route"
        result["agent_name"] = self.name
        return result

    def _extract_entities_for_route(self, question):
        entities = []
        keywords = jieba.analyse.extract_tags(question, topK=5)
        for kw in keywords:
            matches = self.kg.search_entities(kw, top_k=3)
            for name, score in matches:
                if name not in entities:
                    entities.append(name)
        return entities[:3]


class NearbyAgent(BaseAgent):
    def __init__(self, kg, rag_engine, data_cleaner, planner):
        super().__init__("nearby", AGENT_DESCRIPTIONS["nearby"],
                         kg, rag_engine, data_cleaner, planner)

    def process(self, question, user_context=None):
        entities = self._extract_entities_for_nearby(question)
        nearby_results = []
        for entity in entities[:2]:
            try:
                nearby = self.planner.get_nearby_attractions(entity, max_distance=3, max_results=8)
                if nearby:
                    nearby_results.append({
                        "entity": entity,
                        "nearby": nearby
                    })
            except Exception:
                continue

        if nearby_results:
            answer = self._build_nearby_answer(nearby_results)
            return {
                "question": question,
                "answer": answer,
                "agent": "nearby",
                "agent_name": self.name,
                "nearby_results": nearby_results,
                "source": "nearby_agent"
            }

        result = self.rag.query(question)
        result["agent"] = "nearby"
        result["agent_name"] = self.name
        return result

    def _extract_entities_for_nearby(self, question):
        entities = []
        keywords = jieba.analyse.extract_tags(question, topK=5)
        for kw in keywords:
            matches = self.kg.search_entities(kw, top_k=3)
            for name, score in matches:
                if name not in entities:
                    entities.append(name)
        return entities[:3]

    def _build_nearby_answer(self, nearby_results):
        parts = ["📍 **附近推荐结果**:\n"]
        for nr in nearby_results:
            parts.append(f"\n**{nr['entity']}** 附近有:")
            for n in nr['nearby'][:5]:
                depth_tag = "⭐" if n.get('depth', 99) <= 1 else "📍"
                parts.append(f"  {depth_tag} [{n['type']}] {n['name']}")
                via = n.get('via', '')
                if via:
                    parts.append(f"     └ 关联: {via}")
        parts.append("\n💡 点击任意推荐可查看详情")
        return "\n".join(parts)


class GeneralAgent(BaseAgent):
    def __init__(self, kg, rag_engine, data_cleaner, planner):
        super().__init__("general", AGENT_DESCRIPTIONS["general"],
                         kg, rag_engine, data_cleaner, planner)

    def process(self, question, user_context=None):
        result = self.rag.query(question)
        result["agent"] = "general"
        result["agent_name"] = self.name
        if user_context and user_context.get('history'):
            result["personalized"] = True
        return result


class AgentOrchestrator:
    def __init__(self, kg, rag_engine, data_cleaner, planner):
        self.agents = {
            "culture": CultureAgent(kg, rag_engine, data_cleaner, planner),
            "route": RouteAgent(kg, rag_engine, data_cleaner, planner),
            "nearby": NearbyAgent(kg, rag_engine, data_cleaner, planner),
            "general": GeneralAgent(kg, rag_engine, data_cleaner, planner),
        }

    def route_query(self, question, user_context=None):
        scores = []
        for agent_id, agent in self.agents.items():
            score = agent.match_score(question)
            if score > 0:
                scores.append((agent_id, score))

        if not scores:
            return self.agents["general"].process(question, user_context)

        scores.sort(key=lambda x: x[1], reverse=True)
        best_agent_id = scores[0][0]

        result = self.agents[best_agent_id].process(question, user_context)
        result["routed_agent"] = best_agent_id
        result["confidence"] = scores[0][1]
        return result

    def get_agent_info(self):
        return [
            {
                "id": aid,
                "name": a.name,
                "description": a.config["description"],
                "keywords": a.keywords,
            }
            for aid, a in self.agents.items()
        ]
