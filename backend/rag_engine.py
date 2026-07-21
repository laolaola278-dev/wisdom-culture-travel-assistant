import os
import json
import jieba
import jieba.analyse
import requests
import numpy as np
from config import Config

SYSTEM_PROMPT = """你是"白云文化智能问答助手"，专门回答广州市白云区的文旅相关问题。
你的回答必须基于提供的知识图谱检索结果、向量检索结果和相关数据记录，不得编造不存在的信息。
如果检索结果中没有相关信息，请诚实回答"抱歉，我目前没有关于这个问题的数据"。
回答时请做到：
1. 准确引用检索到的事实，注明信息来源
2. 语言亲切自然，像本地导游一样
3. 适当补充实用建议（如交通、开放时间等）
4. 如果信息不完整，说明已知信息并建议用户进一步查询"""


def reciprocal_rank_fusion(ranked_lists, k=60):
    scores = {}
    for lst in ranked_lists:
        for rank, item_id in enumerate(lst, 1):
            scores[item_id] = scores.get(item_id, 0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _item_id(seg):
    return seg.get('name', '') + '||' + seg.get('text', '')[:80]


class RAGEngine:
    def __init__(self, knowledge_graph, data_cleaner, vector_store=None):
        self.kg = knowledge_graph
        self.data_cleaner = data_cleaner
        self.vector_store = vector_store
        self.text_segments = []
        self.segment_index = {}

    def build_index(self):
        self.text_segments = self.data_cleaner.get_all_text_segments()
        for i, seg in enumerate(self.text_segments):
            self.segment_index[i] = seg
        if self.vector_store:
            cached = self.vector_store.load_cache()
            if cached and len(self.vector_store.segments) >= len(self.text_segments) * 0.9:
                print(f"[RAGEngine] 向量缓存已加载: {len(self.vector_store.segments)}条")
            else:
                print(f"[RAGEngine] 构建向量索引 ({len(self.text_segments)}条)...")
                self.vector_store.build_index(self.text_segments)
        print(f"[RAGEngine] 索引就绪: {len(self.text_segments)}条文本段")

    # ═══════════════════════════════════════════════════════════════
    #  三路检索
    # ═══════════════════════════════════════════════════════════════

    def _keyword_search(self, query, top_k=None):
        if top_k is None:
            top_k = Config.KEYWORD_TOP_K
        query_keywords = set(jieba.analyse.extract_tags(query, topK=10))
        if not query_keywords:
            query_keywords = set(query)

        category_map = {
            '景区': '景区', '景点': '景区', '旅游': '景区', 'A级': '景区',
            '公园': '公园', '绿地': '公园',
            '图书馆': '图书馆', '借书': '图书馆', '阅读': '图书馆',
            '非遗': '非遗', '文化遗产': '非遗', '传统': '非遗', '民俗': '非遗',
            '酒店': '酒店', '星级': '酒店', '住宿': '酒店',
            '民宿': '民宿', '客栈': '民宿',
            '旅行社': '旅行社', '旅游公司': '旅行社',
            '文化站': '文化站', '文化中心': '文化站',
            '充电': '充电站', '电车': '充电站', '新能源': '充电站',
            '旅馆': '旅馆', '宾馆': '旅馆',
            '活动': '活动', '讲座': '活动', '展览': '活动',
            '供电': '供电', '电费': '供电', '营业厅': '供电',
            '服务点': '服务点',
            '档案馆': '档案馆', '档案': '档案馆',
            '少年宫': '少年宫',
        }
        target_categories = set()
        for kw in query_keywords | {query}:
            for key, cat in category_map.items():
                if key in kw or kw in key:
                    target_categories.add(cat)

        scored = []
        for i, seg in enumerate(self.text_segments):
            text = seg['text']
            category = seg.get('category', '')
            score = 0

            seg_keywords = set(jieba.analyse.extract_tags(text, topK=15))
            overlap = len(query_keywords & seg_keywords)
            score += overlap * 2

            if target_categories and category in target_categories:
                score += 5

            name = seg.get('name', '')
            if name and (name in query or query in name):
                score += 5

            if score > 0:
                scored.append((i, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [self.text_segments[i] for i, _ in scored[:top_k]]

    def _graph_search(self, query, top_k=None):
        if top_k is None:
            top_k = Config.GRAPH_TOP_K
        matched_entities = self.kg.search_entities(query, top_k=top_k)
        results = []
        for entity_name, score in matched_entities:
            details = self.kg.get_entity_details(entity_name)
            if details:
                rel_texts = []
                for rel in details['relations'][:10]:
                    rel_texts.append(f"{details['entity']} {rel['relation']} {rel['tail']}")
                results.append({
                    "entity": entity_name,
                    "type": details['type'],
                    "score": score,
                    "facts": rel_texts,
                    "location": details.get('location', ''),
                })
        return results

    def _vector_search(self, query, top_k=None):
        if top_k is None:
            top_k = Config.VECTOR_TOP_K
        if not self.vector_store:
            return []
        return self.vector_store.search(query, top_k=top_k)

    # ═══════════════════════════════════════════════════════════════
    #  RRF 融合
    # ═══════════════════════════════════════════════════════════════

    def _hybrid_retrieve(self, query):
        if not Config.ENABLE_HYBRID_SEARCH:
            keyword_results = self._keyword_search(query, top_k=Config.HYBRID_TOP_K)
            graph_results = self._graph_search(query, top_k=Config.HYBRID_TOP_K)
            return keyword_results, graph_results, []

        keyword_results = self._keyword_search(query, top_k=Config.HYBRID_TOP_K * 2)
        graph_results = self._graph_search(query, top_k=Config.HYBRID_TOP_K * 2)
        vector_results = self._vector_search(query, top_k=Config.HYBRID_TOP_K * 2)

        if not vector_results:
            return keyword_results[:Config.HYBRID_TOP_K], graph_results[:Config.HYBRID_TOP_K], []

        all_text_items = {}
        for seg in self.text_segments:
            all_text_items[_item_id(seg)] = seg

        kw_ranked = []
        seen_kw = set()
        for seg in keyword_results:
            iid = _item_id(seg)
            if iid not in seen_kw:
                seen_kw.add(iid)
                kw_ranked.append(iid)

        vec_ranked = []
        seen_vec = set()
        for r in vector_results:
            seg = r['segment']
            iid = _item_id(seg)
            if iid not in seen_vec:
                seen_vec.add(iid)
                vec_ranked.append(iid)

        fused = reciprocal_rank_fusion([kw_ranked, vec_ranked], k=Config.RRF_K)

        final_texts = []
        seen_final = set()
        for iid, score in fused:
            if len(final_texts) >= Config.HYBRID_TOP_K:
                break
            if iid not in seen_final and iid in all_text_items:
                seen_final.add(iid)
                seg = all_text_items[iid]
                seg['_fusion_score'] = round(score, 4)
                final_texts.append(seg)

        for seg in keyword_results:
            iid = _item_id(seg)
            if iid not in seen_final and len(final_texts) < Config.HYBRID_TOP_K:
                seen_final.add(iid)
                final_texts.append(seg)

        graph_top = graph_results[:Config.HYBRID_TOP_K]
        return final_texts, graph_top, vector_results

    # ═══════════════════════════════════════════════════════════════
    #  上下文组装
    # ═══════════════════════════════════════════════════════════════

    def _build_context(self, query):
        text_results, graph_results, vector_results = self._hybrid_retrieve(query)

        context_parts = []

        if graph_results:
            context_parts.append("【知识图谱检索结果】")
            for gr in graph_results:
                context_parts.append(f"- 实体: {gr['entity']} (类型: {gr['type']})")
                for fact in gr['facts']:
                    context_parts.append(f"  · {fact}")

        if text_results:
            context_parts.append("\n【相关数据记录】")
            for tr in text_results:
                label = f"[{tr.get('category', '')}]"
                if '_fusion_score' in tr:
                    label += f"[融合分:{tr['_fusion_score']}]"
                context_parts.append(f"- {label} {tr['text']}")

        if vector_results and Config.ENABLE_HYBRID_SEARCH:
            context_parts.append("\n【语义向量匹配】")
            for vr in vector_results[:3]:
                cat = vr['segment'].get('category', '')
                context_parts.append(f"- [{cat}] {vr['segment']['text'][:120]}... (相似度:{vr['score']:.3f})")

        context = "\n".join(context_parts)
        if len(context) > Config.MAX_CONTEXT_LENGTH:
            context = context[:Config.MAX_CONTEXT_LENGTH] + "..."
        return context

    # ═══════════════════════════════════════════════════════════════
    #  LLM 调用 (多模型回退)
    # ═══════════════════════════════════════════════════════════════

    def _build_payload(self, query, context, stream=False):
        user_prompt = (
            "基于以下检索到的白云区文旅知识，回答用户问题。\n\n"
            f"检索到的知识：\n{context}\n\n"
            f"用户问题：{query}\n\n"
            "请基于以上知识给出准确回答："
        )
        return {
            "model": Config.LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
            "stream": stream,
        }

    def _auth_headers(self):
        return {
            "Authorization": f"Bearer {Config.LLM_API_KEY}",
            "Content-Type": "application/json",
        }

    def _call_llm(self, query, context):
        if not Config.LLM_API_KEY:
            return self._fallback_generate(query, context)

        payload = self._build_payload(query, context, stream=False)
        model_type = self._detect_model_type(Config.LLM_API_URL)

        if model_type == 'ollama':
            return self._call_ollama(query, context)

        try:
            response = requests.post(
                Config.LLM_API_URL,
                headers=self._auth_headers(),
                json=payload,
                timeout=30,
            )
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return self._handle_model_fallback(query, context)
        except Exception:
            return self._handle_model_fallback(query, context)

    def _detect_model_type(self, url):
        if 'ollama' in url.lower() or '11434' in url:
            return 'ollama'
        return 'openai'

    def _call_ollama(self, query, context):
        ollama_url = f"{Config.OLLAMA_BASE_URL}/api/chat"
        user_prompt = (
            "基于以下检索到的白云区文旅知识，回答用户问题。\n\n"
            f"检索到的知识：\n{context}\n\n"
            f"用户问题：{query}\n\n"
            "请基于以上知识给出准确回答："
        )
        try:
            response = requests.post(
                ollama_url,
                json={
                    "model": Config.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
                timeout=60,
            )
            if response.status_code == 200:
                return response.json()['message']['content']
        except Exception:
            pass
        return self._fallback_generate(query, context)

    def _handle_model_fallback(self, query, context):
        if Config.OLLAMA_ENABLED:
            print("[RAGEngine] DeepSeek API 失败, 回退到 Ollama...")
            ollama_result = self._call_ollama(query, context)
            if ollama_result and "抱歉" not in ollama_result[:10]:
                return ollama_result
        return self._fallback_generate(query, context)

    def _fallback_generate(self, query, context):
        # 1. 解析已有 context 中的检索结果
        graph_lines = []
        data_lines = []
        current_section = None
        for line in context.split('\n'):
            if '【知识图谱检索结果】' in line:
                current_section = 'graph'
                continue
            elif '【相关数据记录】' in line or '【语义向量匹配】' in line:
                current_section = 'data'
                continue
            if current_section == 'graph':
                graph_lines.append(line)
            elif current_section == 'data':
                data_lines.append(line)

        # 2. 直接从知识图谱拿 Top-3 实体详情（保证有真实内容）
        kg_results = self._graph_search(query, top_k=3)
        entity_details = []
        for gr in kg_results:
            detail = self.kg.get_entity_details(gr['entity'])
            if detail:
                entity_details.append(detail)

        # 3. 真正空时退化为引导提示
        if not entity_details and not graph_lines and not data_lines:
            return (
                "抱歉，我目前没有关于这个问题的数据。"
                "您可以尝试询问白云区的景点、非遗项目、图书馆、酒店等方面的信息。\n\n"
                "💡 提示：如需更智能的语义理解回答，"
                "请在 .env 中配置 DEEPSEEK_API_KEY 后重启服务。"
            )

        # 4. 构造基于真实图谱的回答
        answer_parts = []

        if entity_details:
            answer_parts.append("根据白云区文旅知识库，为您找到以下相关信息：\n")
            for i, detail in enumerate(entity_details[:3], 1):
                name = detail.get('display_name') or detail.get('entity')
                etype = detail.get('type', '未知')
                location = detail.get('location', '')
                relations = detail.get('relations', [])

                answer_parts.append(f"{i}. 📍 **{name}**（{etype}）")
                if location:
                    answer_parts.append(f"   📫 地址：{location}")

                # 展示前 5 条关键关系（只展示语义化的关系，跳过 _反向）
                shown = 0
                for rel in relations:
                    relation = rel.get('relation', '')
                    tail = rel.get('tail', '')
                    if not tail or '_反向' in relation:
                        continue
                    if relation in ('属于类型',):
                        answer_parts.append(f"   🏷️ 类别：{tail}")
                    elif relation in ('位于', '所在地'):
                        answer_parts.append(f"   📍 位置：{tail}")
                    elif relation in ('所属街镇', '所在街镇', '所在地区'):
                        answer_parts.append(f"   🏘️ 所属：{tail}")
                    elif relation in ('开放时间',):
                        answer_parts.append(f"   🕐 {tail}")
                    elif relation in ('联系电话', '电话'):
                        answer_parts.append(f"   ☎️ {tail}")
                    else:
                        answer_parts.append(f"   • {relation}：{tail}")
                    shown += 1
                    if shown >= 5:
                        break
                answer_parts.append("")

        if data_lines:
            answer_parts.append("📋 相关数据记录：")
            shown = 0
            for line in data_lines:
                line = line.strip()
                if line.startswith('- ['):
                    answer_parts.append(f"  {line}")
                    shown += 1
                    if shown >= 5:
                        break
            answer_parts.append("")

        if graph_lines:
            answer_parts.append("📌 知识图谱检索片段：")
            shown = 0
            for line in graph_lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('- 实体:'):
                    answer_parts.append(f"  🔹 {line.replace('- 实体:', '').strip()}")
                elif line.startswith('·'):
                    answer_parts.append(f"    → {line.replace('·', '').strip()}")
                shown += 1
                if shown >= 6:
                    break
            answer_parts.append("")

        answer_parts.append(
            "💡 以上信息来源于白云区文旅知识图谱（"
            f"{len(entity_details)} 个相关实体）。\n"
            "   如需更智能的自然语言回答，请在 .env 中配置 "
            "DEEPSEEK_API_KEY 后重启服务。"
        )
        return "\n".join(answer_parts)

    # ═══════════════════════════════════════════════════════════════
    #  公开 API (非流式 / 流式)
    # ═══════════════════════════════════════════════════════════════

    def query(self, question):
        context = self._build_context(question)
        answer = self._call_llm(question, context)
        graph_results = self._graph_search(question, top_k=3)
        related_entities = [
            {"name": gr["entity"], "type": gr["type"]} for gr in graph_results
        ]
        return {
            "question": question,
            "answer": answer,
            "context": context,
            "related_entities": related_entities,
            "source": "hybrid_rag_v2",
            "fusion_enabled": Config.ENABLE_HYBRID_SEARCH,
        }

    # ═══════════════════════════════════════════════════════════════
    #  流式接口 (DeepSeek → Ollama → 本地)
    # ═══════════════════════════════════════════════════════════════

    def _call_llm_stream(self, query, context):
        if not Config.LLM_API_KEY:
            # 本地兜底返回完整字符串——整段 yield 一次，
            # 严禁 for 迭代（会把 str 拆成逐字符 SSE 事件）
            yield self._fallback_generate(query, context)
            return

        model_type = self._detect_model_type(Config.LLM_API_URL)
        if model_type == 'ollama':
            for chunk in self._call_ollama_stream(query, context):
                yield chunk
            return

        payload = self._build_payload(query, context, stream=True)

        try:
            response = requests.post(
                Config.LLM_API_URL,
                headers=self._auth_headers(),
                json=payload,
                timeout=Config.STREAM_TIMEOUT_SECONDS,
                stream=True,
            )
        except Exception:
            for chunk in self._stream_fallback_handler(query, context):
                yield chunk
            return

        if response.status_code != 200:
            for chunk in self._stream_fallback_handler(query, context):
                yield chunk
            return

        accumulated = ""
        try:
            for raw_line in response.iter_lines(decode_unicode=True, chunk_size=1):
                if not raw_line:
                    continue
                if raw_line.startswith("data: "):
                    data_str = raw_line[len("data: "):]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        accumulated += content
                        yield content
        except Exception:
            # 中途断流：已输出的内容客户端已收到，不能重发 accumulated（会整段重复）；
            # 无任何输出时才走兜底
            if not accumulated:
                for chunk in self._stream_fallback_handler(query, context):
                    yield chunk
            return

    def _call_ollama_stream(self, query, context):
        ollama_url = f"{Config.OLLAMA_BASE_URL}/api/chat"
        user_prompt = (
            "基于以下检索到的白云区文旅知识，回答用户问题。\n\n"
            f"检索到的知识：\n{context}\n\n"
            f"用户问题：{query}\n\n"
            "请基于以上知识给出准确回答："
        )
        try:
            response = requests.post(
                ollama_url,
                json={
                    "model": Config.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": True,
                    "options": {"temperature": 0.3},
                },
                stream=True,
                timeout=Config.STREAM_TIMEOUT_SECONDS,
            )
        except Exception:
            # 连接失败（未输出任何内容）：整段 yield 本地兜底
            yield self._fallback_generate(query, context)
            return
        emitted = False
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    content = data.get('message', {}).get('content', '')
                    if content:
                        emitted = True
                        yield content
                except json.JSONDecodeError:
                    continue
        except Exception:
            # 中途断流：已有部分输出则直接结束，避免拼接完整兜底造成内容重复
            if not emitted:
                yield self._fallback_generate(query, context)

    def _stream_fallback_handler(self, query, context):
        if Config.OLLAMA_ENABLED:
            fallback_gen = self._call_ollama_stream(query, context)
            first = True
            for chunk in fallback_gen:
                if first and not chunk:
                    continue
                yield chunk
                first = False
            if not first:
                return
        yield self._fallback_generate(query, context)

    def query_stream(self, question):
        context = self._build_context(question)
        graph_results = self._graph_search(question, top_k=3)
        related_entities = [
            {"name": gr["entity"], "type": gr["type"]} for gr in graph_results
        ]

        yield json.dumps({
            "type": "meta",
            "question": question,
            "context": context,
            "related_entities": related_entities,
            "source": "hybrid_rag_v2_stream",
            "fusion_enabled": Config.ENABLE_HYBRID_SEARCH,
        }, ensure_ascii=False)

        for chunk in self._call_llm_stream(question, context):
            yield json.dumps({"type": "delta", "content": chunk},
                             ensure_ascii=False)

        yield json.dumps({"type": "done"}, ensure_ascii=False)

    # ═══════════════════════════════════════════════════════════════
    #  热门问题
    # ═══════════════════════════════════════════════════════════════

    def get_hot_questions(self):
        return [
            "白云山风景名胜区在哪里？",
            "白云区有哪些非物质文化遗产？",
            "白云区有哪些图书馆？",
            "白云区有哪些星级酒店？",
            "白云区有哪些公园？",
            "白云区有哪些民宿？",
            "三元里有什么文化特色？",
            "白云区有哪些充电站？",
            "白云区有哪些旅行社？",
            "白云区有哪些文化站？",
        ]
