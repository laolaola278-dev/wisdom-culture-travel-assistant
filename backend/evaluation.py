import os
import json
import time
import jieba
import numpy as np
from config import Config


DEFAULT_EVAL_QUESTIONS = [
    {"question": "白云山风景名胜区在哪里？", "expected_entities": ["白云山风景名胜区"], "category": "景点"},
    {"question": "白云区有哪些非物质文化遗产？", "expected_entities": ["非物质文化遗产"], "category": "非遗"},
    {"question": "白云区有哪些图书馆？", "expected_entities": ["图书馆"], "category": "图书馆"},
    {"question": "白云区有哪些星级酒店？", "expected_entities": ["酒店"], "category": "酒店"},
    {"question": "白云山附近有什么公园？", "expected_entities": ["白云山", "公园"], "category": "关联"},
    {"question": "三元里有什么历史事件？", "expected_entities": ["三元里抗英"], "category": "历史"},
    {"question": "白云区有哪些充电站？", "expected_entities": ["充电站"], "category": "设施"},
    {"question": "白云区有哪些A级景区？", "expected_entities": ["A级景区"], "category": "景点"},
    {"question": "白云区有哪些民宿推荐？", "expected_entities": ["民宿"], "category": "住宿"},
    {"question": "白云区舞火龙是什么级别的非遗？", "expected_entities": ["舞火龙", "非遗"], "category": "非遗"},
]


class Evaluator:
    def __init__(self, rag_engine, kg):
        self.rag_engine = rag_engine
        self.kg = kg
        self.questions = self._load_questions()

    def _load_questions(self):
        path = Config.EVAL_QUESTIONS_PATH
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_EVAL_QUESTIONS

    def _entity_recall(self, answer, expected_entities):
        if not answer:
            return 0.0
        found = 0
        for entity in expected_entities:
            if entity in answer:
                found += 1
        return found / len(expected_entities) if expected_entities else 0.0

    def _source_groundedness(self, answer):
        keywords = ['位于', '地址', '开放时间', '级别', '类别', '类型', '非遗', '景点', '公园', '图书馆']
        return 1.0 if any(kw in answer for kw in keywords) else 0.0

    def _answer_completeness(self, answer):
        if not answer:
            return 0.0
        length = len(answer)
        if length > 200:
            return 1.0
        elif length > 100:
            return 0.7
        elif length > 50:
            return 0.4
        else:
            return 0.2

    def _has_hallucination(self, answer, context):
        if not answer or not context:
            return False
        context_lower = context.lower()
        answer_sentences = [s.strip() for s in answer.replace('。', '.').split('.') if len(s.strip()) > 10]
        suspicious = 0
        total = 0
        for sent in answer_sentences:
            total += 1
            # check if key claims in the sentence appear in context
            # 必须先分词——直接迭代字符串得到单字符，len(w)>1 恒假会使检测永远失效
            words = [w for w in jieba.lcut(sent) if len(w) > 1 and w.isalpha()]
            key_terms = [w for w in words if w in context_lower]
            if len(words) > 0 and len(key_terms) / len(words) < 0.2:
                suspicious += 1
        if total == 0:
            return False
        return (suspicious / total) > 0.7

    def evaluate(self, verbose=False):
        results = []
        total_recall = 0.0
        total_grounded = 0.0
        total_complete = 0.0
        hallucination_count = 0

        print(f"\n{'='*60}")
        print(f"  评估开始: {len(self.questions)} 个问题")
        print(f"{'='*60}")

        for i, item in enumerate(self.questions):
            question = item['question']
            expected = item.get('expected_entities', [])
            category = item.get('category', '')

            t0 = time.time()

            query_result = self.rag_engine.query(question)
            answer = query_result.get('answer', '')
            context = query_result.get('context', '')
            elapsed = time.time() - t0

            recall = self._entity_recall(answer, expected)
            grounded = self._source_groundedness(answer)
            complete = self._answer_completeness(answer)
            hallucination = self._has_hallucination(answer, context)

            if hallucination:
                hallucination_count += 1

            total_recall += recall
            total_grounded += grounded
            total_complete += complete

            result = {
                "question": question,
                "category": category,
                "recall": round(recall, 3),
                "groundedness": round(grounded, 3),
                "completeness": round(complete, 3),
                "hallucination": hallucination,
                "latency_seconds": round(elapsed, 2),
                "answer_length": len(answer),
            }
            results.append(result)

            if verbose:
                status = "✅" if recall > 0.5 and not hallucination else "⚠️"
                print(f"  {status} [{category:4s}] {question[:30]:30s} "
                      f"召回={recall:.2f} 幻觉={'是' if hallucination else '否'} "
                      f"{elapsed:.1f}s")

        n = len(self.questions)
        avg_recall = total_recall / n if n > 0 else 0
        avg_grounded = total_grounded / n if n > 0 else 0
        avg_complete = total_complete / n if n > 0 else 0
        hallucination_rate = hallucination_count / n if n > 0 else 0

        summary = {
            "total_questions": n,
            "avg_entity_recall": round(avg_recall, 3),
            "avg_groundedness": round(avg_grounded, 3),
            "avg_completeness": round(avg_complete, 3),
            "hallucination_rate": round(hallucination_rate, 3),
            "avg_latency_seconds": round(
                np.mean([r['latency_seconds'] for r in results]), 2
            ) if results else 0,
            "details": results,
        }

        print(f"\n{'='*60}")
        print(f"  评估汇总")
        print(f"{'='*60}")
        print(f"  实体召回率 (Entity Recall):     {avg_recall:.1%}")
        print(f"  来源归因率 (Groundedness):       {avg_grounded:.1%}")
        print(f"  答案完整度 (Completeness):        {avg_complete:.1%}")
        print(f"  幻觉率 (Hallucination Rate):     {hallucination_rate:.1%}")
        print(f"  平均响应延迟:                    {summary['avg_latency_seconds']:.1f}s")
        print(f"{'='*60}\n")

        self._save_report(summary)
        return summary

    def _save_report(self, summary):
        report_dir = os.path.join(Config.GRAPH_DATA_DIR, '..', 'eval_reports')
        os.makedirs(report_dir, exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        path = os.path.join(report_dir, f'eval_report_{timestamp}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"[Evaluator] 评估报告已保存: {path}")

    def compare_baseline(self, baseline_report_path=None):
        latest = self._find_latest_report()
        if not latest and not baseline_report_path:
            print("[Evaluator] 无历史报告可对比")
            return

        path = baseline_report_path or latest
        with open(path, 'r', encoding='utf-8') as f:
            baseline = json.load(f)

        current = self.evaluate(verbose=False)
        print(f"\n{'='*60}")
        print(f"  对比: 基线 vs 当前")
        print(f"{'='*60}")
        metrics = ['avg_entity_recall', 'avg_groundedness', 'avg_completeness', 'hallucination_rate']
        for m in metrics:
            b = baseline.get(m, 0)
            c = current.get(m, 0)
            delta = c - b
            arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
            print(f"  {m:25s}: {b:.1%} → {c:.1%}  {arrow}")
        print(f"{'='*60}\n")

    def _find_latest_report(self):
        report_dir = os.path.join(Config.GRAPH_DATA_DIR, '..', 'eval_reports')
        if not os.path.exists(report_dir):
            return None
        reports = sorted(
            [f for f in os.listdir(report_dir) if f.startswith('eval_report_')],
            reverse=True
        )
        return os.path.join(report_dir, reports[0]) if reports else None
