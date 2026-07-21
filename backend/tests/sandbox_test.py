"""
智慧文旅与交通建设 - 全功能沙盒模拟测试
系统性地验证所有功能模块的核心逻辑、组件交互、数据流程和异常处理
"""
import requests
import json
import time
import sys
import io
import os
from typing import Any

# 强制 stdout 使用 UTF-8 编码，避免 PowerShell GBK 编码无法输出 emoji
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

BASE = "http://127.0.0.1:5000/api"
PASS = 0
FAIL = 0
RESULTS = []
AUTH_TOKEN = None  # JWT token for authenticated endpoints


def get_auth_token() -> str:
    """注册测试用户并登录获取 JWT token"""
    global AUTH_TOKEN
    if AUTH_TOKEN:
        return AUTH_TOKEN
    test_user = f"testuser_{int(time.time())}"
    # 尝试注册
    try:
        requests.post(f"{BASE}/auth/register",
                      json={"username": test_user, "email": f"{test_user}@test.com", "password": "Test1234!"},
                      timeout=10)
    except Exception:
        pass
    # 登录
    try:
        r = requests.post(f"{BASE}/auth/login",
                          json={"username": test_user, "password": "Test1234!"},
                          timeout=10)
        if r.status_code == 200:
            AUTH_TOKEN = r.json().get("access_token")
    except Exception:
        pass
    return AUTH_TOKEN


def auth_headers() -> dict:
    token = get_auth_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def log(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    status = "✅ PASS" if ok else "❌ FAIL"
    PASS += 1 if ok else 0
    FAIL += 0 if ok else 1
    line = f"{status} | {name}"
    if detail:
        line += f" | {detail}"
    print(line)
    RESULTS.append({"name": name, "ok": ok, "detail": detail})


def req(method: str, path: str, **kwargs) -> tuple[int, Any]:
    url = f"{BASE}{path}"
    try:
        r = requests.request(method, url, timeout=30, **kwargs)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return r.status_code, data
    except Exception as e:
        return -1, {"error": str(e)}


def section(title: str):
    print("\n" + "═" * 70)
    print(f"  {title}")
    print("═" * 70)


# ════════════════════════════════════════════════════════════════════
# 模块 1：系统健康检查 + LLM 状态
# ════════════════════════════════════════════════════════════════════
def test_health():
    section("模块 1：系统健康检查 + LLM 状态")
    code, data = req("GET", "/health")
    log("健康检查 HTTP 200", code == 200, f"实际: {code}")
    log("返回 status=ok", data.get("status") == "ok", f"实际: {data.get('status')}")
    log("包含知识图谱统计", "knowledge_graph" in data, f"实体数: {data.get('knowledge_graph', {}).get('entities')}")
    log("包含向量库统计", "vector_store" in data, f"段数: {data.get('vector_store', {}).get('segments')}")
    log("包含 llm_enabled 字段", "llm_enabled" in data, f"值: {data.get('llm_enabled')}")
    log("包含 llm_provider 字段", "llm_provider" in data, f"值: {data.get('llm_provider')}")
    log("包含 database 状态", data.get("database") == "ok", f"值: {data.get('database')}")
    log("包含 agents 配置", "agents" in data, f"值: {data.get('agents')}")
    return data


# ════════════════════════════════════════════════════════════════════
# 模块 2：智能问答（含 fallback 异常处理）
# ════════════════════════════════════════════════════════════════════
def test_qa():
    section("模块 2：智能问答（含 fallback 异常处理）")
    # 正常问答
    code, data = req("POST", "/v2/qa", json={"question": "白云山有哪些景点"})
    log("问答 HTTP 200", code == 200, f"实际: {code}")
    log("返回 answer 字段", "answer" in data and bool(data["answer"]), f"长度: {len(data.get('answer', ''))}")
    log("返回 question 字段", "question" in data, f"值: {data.get('question')}")
    log("返回 source 字段", "source" in data, f"值: {data.get('source')}")
    log("返回 related_entities", "related_entities" in data, f"数量: {len(data.get('related_entities', []))}")
    log("答案包含真实内容", "白云山" in data.get("answer", ""), "答案包含关键词")
    log("答案非空 fallback", "抱歉，我目前没有" not in data.get("answer", "")[:30], "非空兜底")

    # 空问题异常处理
    code, data = req("POST", "/v2/qa", json={"question": ""})
    log("空问题返回 4xx/2xx", code in (200, 400, 422), f"实际: {code}")

    # 无效 JSON 异常处理
    r = requests.post(f"{BASE}/v2/qa", data="invalid json", headers={"Content-Type": "application/json"}, timeout=30)
    log("无效 JSON 异常处理", r.status_code in (400, 422, 500), f"实际: {r.status_code}")

    # 第二个问题测试会话延续
    code, data = req("POST", "/v2/qa", json={"question": "三元里有什么文化特色"})
    log("第二个问题 HTTP 200", code == 200, f"实际: {code}")
    log("第二个问题答案非空", bool(data.get("answer")), "有答案")


# ════════════════════════════════════════════════════════════════════
# 模块 3：智能体路由 + 推荐系统
# ════════════════════════════════════════════════════════════════════
def test_agents():
    section("模块 3：智能体路由 + 推荐系统")
    code, data = req("GET", "/v2/agents")
    log("获取智能体列表 HTTP 200", code == 200, f"实际: {code}")
    log("返回 agents 数组", isinstance(data.get("agents"), list), f"数量: {len(data.get('agents', []))}")
    if data.get("agents"):
        a = data["agents"][0]
        log("智能体包含 name", "name" in a, f"值: {a.get('name')}")
        log("智能体包含 description", "description" in a, f"值: {a.get('description', '')[:30]}")

    code, data = req("GET", "/v2/recommend")
    log("推荐系统 HTTP 200", code == 200, f"实际: {code}")
    log("返回 recommendations", "recommendations" in data, f"数量: {len(data.get('recommendations', []))}")

    # 热门问题
    code, data = req("GET", "/hot-questions")
    log("热门问题 HTTP 200", code == 200, f"实际: {code}")
    log("返回 questions 数组", isinstance(data.get("questions"), list), f"数量: {len(data.get('questions', []))}")


# ════════════════════════════════════════════════════════════════════
# 模块 4：知识图谱检索
# ════════════════════════════════════════════════════════════════════
def test_graph():
    section("模块 4：知识图谱检索（搜索/实体/可视化/统计）")
    # 搜索
    code, data = req("GET", "/graph/search", params={"q": "白云山", "top_k": 5})
    log("图谱搜索 HTTP 200", code == 200, f"实际: {code}")
    log("返回 results 数组", isinstance(data.get("results"), list), f"数量: {len(data.get('results', []))}")
    if data.get("results"):
        r0 = data["results"][0]
        log("搜索结果包含 name", "name" in r0, f"值: {r0.get('name')}")

    # 实体详情
    code, data = req("GET", "/graph/entity/白云山风景名胜区")
    log("实体详情 HTTP 200", code == 200, f"实际: {code}")
    log("实体包含 entity 字段", "entity" in data, f"值: {data.get('entity')}")
    log("实体包含 type 字段", "type" in data, f"值: {data.get('type')}")
    log("实体包含 relations", "relations" in data, f"数量: {len(data.get('relations', []))}")

    # 可视化
    code, data = req("GET", "/graph/visualization", params={"limit": 50})
    log("图谱可视化 HTTP 200", code == 200, f"实际: {code}")
    log("返回 nodes 数组", isinstance(data.get("nodes"), list), f"数量: {len(data.get('nodes', []))}")
    log("返回 links/edges 数组", isinstance(data.get("links") or data.get("edges"), list), f"数量: {len(data.get('links', data.get('edges', [])))}")

    # 统计
    code, data = req("GET", "/graph/stats")
    log("图谱统计 HTTP 200", code == 200, f"实际: {code}")
    log("返回 total_entities", "total_entities" in data, f"值: {data.get('total_entities')}")
    log("返回 total_relations", "total_relations" in data, f"值: {data.get('total_relations')}")

    # 实体列表
    code, data = req("GET", "/graph/entities", params={"limit": 10})
    log("实体列表 HTTP 200", code == 200, f"实际: {code}")


# ════════════════════════════════════════════════════════════════════
# 模块 5：文旅探索
# ════════════════════════════════════════════════════════════════════
def test_explore():
    section("模块 5：文旅探索（分类/实体详情/附近/AI搜索）")
    # 分类
    code, data = req("GET", "/data/categories")
    log("分类列表 HTTP 200", code == 200, f"实际: {code}")
    log("返回 categories 数组", isinstance(data.get("categories"), list), f"数量: {len(data.get('categories', []))}")

    # 实体增强详情
    code, data = req("GET", "/explore/entity/白云山风景名胜区/enhanced")
    log("实体增强详情 HTTP 200", code == 200, f"实际: {code}")

    # 实体附近
    code, data = req("GET", "/explore/entity/白云山风景名胜区/nearby")
    log("实体附近 HTTP 200", code == 200, f"实际: {code}")
    log("返回 nearby 数组", isinstance(data.get("nearby"), list), f"数量: {len(data.get('nearby', []))}")

    # 实体上下文
    code, data = req("GET", "/explore/entity/白云山风景名胜区/context")
    log("实体上下文 HTTP 200", code == 200, f"实际: {code}")

    # AI 搜索
    code, data = req("POST", "/explore/ai-search", json={"query": "白云山历史文化", "search_type": "general"})
    log("AI 搜索 HTTP 200", code == 200, f"实际: {code}")
    log("AI 搜索返回结果", bool(data.get("answer") or data.get("result")), "有结果")


# ════════════════════════════════════════════════════════════════════
# 模块 6：路线规划 + 地图坐标
# ════════════════════════════════════════════════════════════════════
def test_route_map():
    section("模块 6：路线规划 + 地图坐标")
    # 路线规划
    code, data = req("POST", "/explore/route-plan", json={
        "start": "白云山风景名胜区",
        "preferences": ["文化体验", "风景名胜"]
    })
    log("路线规划 HTTP 200", code == 200, f"实际: {code}")
    log("返回 success 字段", "success" in data, f"值: {data.get('success')}")
    log("返回 route_plan", bool(data.get("route_plan")), "有路线方案")

    # 地图坐标
    code, data = req("GET", "/map/coordinates", params={"limit": 10})
    log("地图坐标 HTTP 200", code == 200, f"实际: {code}")
    log("返回 points 数组", isinstance(data.get("points"), list), f"数量: {len(data.get('points', []))}")
    if data.get("points"):
        p = data["points"][0]
        log("坐标点包含 lat", "lat" in p, f"值: {p.get('lat')}")
        log("坐标点包含 lng", "lng" in p, f"值: {p.get('lng')}")
        log("坐标点包含 name", "name" in p, f"值: {p.get('name')}")


# ════════════════════════════════════════════════════════════════════
# 模块 7：历史会话 + 收藏管理
# ════════════════════════════════════════════════════════════════════
def test_history_favorites():
    section("模块 7：历史会话 + 收藏管理")
    headers = auth_headers()
    log("获取鉴权 token", bool(AUTH_TOKEN), f"token: {AUTH_TOKEN[:20] if AUTH_TOKEN else 'None'}...")

    # 历史会话列表（需要鉴权）
    code, data = req("GET", "/v2/sessions", headers=headers)
    log("会话列表 HTTP 200", code == 200, f"实际: {code}")
    log("返回 sessions 数组", isinstance(data.get("sessions"), list), f"数量: {len(data.get('sessions', []))}")

    session_id = None
    if data.get("sessions"):
        session_id = data["sessions"][0].get("id")
        log("首个会话包含 id", session_id is not None, f"值: {session_id}")
        log("首个会话包含 title", "title" in data["sessions"][0], f"值: {data['sessions'][0].get('title')}")

    # 会话详情
    if session_id:
        code, data = req("GET", f"/v2/sessions/{session_id}", headers=headers)
        log("会话详情 HTTP 200", code == 200, f"实际: {code}")
        log("会话包含 messages", "messages" in data, f"数量: {len(data.get('messages', []))}")

    # 收藏列表（需要鉴权）
    code, data = req("GET", "/v2/favorites", headers=headers)
    log("收藏列表 HTTP 200", code == 200, f"实际: {code}")
    log("返回 favorites 数组", isinstance(data.get("favorites"), list), f"数量: {len(data.get('favorites', []))}")

    # 添加收藏（201 Created 也是成功）
    code, data = req("POST", "/v2/favorites", json={"type": "景点", "id": "test-fav-001", "name": "测试景点"}, headers=headers)
    log("添加收藏 HTTP 2xx", 200 <= code < 300, f"实际: {code}")

    # 删除收藏
    code, data = req("DELETE", "/v2/favorites", json={"type": "景点", "id": "test-fav-001"}, headers=headers)
    log("删除收藏 HTTP 200", code == 200, f"实际: {code}")


# ════════════════════════════════════════════════════════════════════
# 模块 8：数据统计 + 3D地图配置
# ════════════════════════════════════════════════════════════════════
def test_stats_map3d():
    section("模块 8：数据统计 + 3D地图配置")
    # 统计概览
    code, data = req("GET", "/stats/overview")
    log("统计概览 HTTP 200", code == 200, f"实际: {code}")
    log("返回统计数据", isinstance(data, dict) and len(data) > 0, f"字段数: {len(data) if isinstance(data, dict) else 0}")

    # 位置频次
    code, data = req("GET", "/stats/location-frequency")
    log("位置频次 HTTP 200", code == 200, f"实际: {code}")

    # 3D 地图配置
    code, data = req("GET", "/map/3d/config")
    log("3D 地图配置 HTTP 200", code == 200, f"实际: {code}")

    # 3D 地图实体
    code, data = req("GET", "/map/3d/entities")
    log("3D 地图实体 HTTP 200", code == 200, f"实际: {code}")
    log("返回实体数据", isinstance(data, dict) and len(data) > 0, "有数据")


# ════════════════════════════════════════════════════════════════════
# 模块 9：异常处理（无效输入/不存在的实体）
# ════════════════════════════════════════════════════════════════════
def test_error_handling():
    section("模块 9：异常处理（无效输入/不存在的实体）")
    # 不存在的实体
    code, data = req("GET", "/graph/entity/这个实体绝对不存在_xyz123")
    log("不存在实体 HTTP 状态码合理", code in (200, 404, 422), f"实际: {code}")

    # 不存在的会话
    code, data = req("GET", "/v2/sessions/nonexistent-session-id-12345")
    log("不存在会话 HTTP 状态码合理", code in (200, 404, 422, 500), f"实际: {code}")

    # 不存在的路由（SPA fallback 会返回 200 HTML，属于正常行为）
    code, data = req("GET", "/this-endpoint-does-not-exist")
    # 接受 404（无 SPA fallback）或 200（SPA fallback 返回 HTML）
    log("不存在路由返回 404 或 SPA fallback", code in (404, 200), f"实际: {code}")

    # 不存在的实体附近
    code, data = req("GET", "/explore/entity/不存在的实体_xyz/nearby")
    log("不存在实体附近 HTTP 状态码合理", code in (200, 404, 422), f"实际: {code}")

    # 空查询搜索
    code, data = req("GET", "/graph/search", params={"q": ""})
    log("空查询搜索 HTTP 状态码合理", code in (200, 400, 422), f"实际: {code}")


# ════════════════════════════════════════════════════════════════════
# 主函数
# ════════════════════════════════════════════════════════════════════
def main():
    print("╔" + "═" * 68 + "╗")
    print("║" + " 智慧文旅与交通建设 - 全功能沙盒模拟测试 ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    t0 = time.time()

    try:
        test_health()
    except Exception as e:
        log("模块1异常", False, str(e))

    try:
        test_qa()
    except Exception as e:
        log("模块2异常", False, str(e))

    try:
        test_agents()
    except Exception as e:
        log("模块3异常", False, str(e))

    try:
        test_graph()
    except Exception as e:
        log("模块4异常", False, str(e))

    try:
        test_explore()
    except Exception as e:
        log("模块5异常", False, str(e))

    try:
        test_route_map()
    except Exception as e:
        log("模块6异常", False, str(e))

    try:
        test_history_favorites()
    except Exception as e:
        log("模块7异常", False, str(e))

    try:
        test_stats_map3d()
    except Exception as e:
        log("模块8异常", False, str(e))

    try:
        test_error_handling()
    except Exception as e:
        log("模块9异常", False, str(e))

    elapsed = time.time() - t0
    print("\n" + "═" * 70)
    print(f"  测试完成 | 通过: {PASS} | 失败: {FAIL} | 耗时: {elapsed:.1f}s")
    print("═" * 70)

    # 输出失败项汇总
    failed = [r for r in RESULTS if not r["ok"]]
    if failed:
        print(f"\n失败项汇总 ({len(failed)} 项):")
        for f in failed:
            print(f"  ❌ {f['name']} | {f['detail']}")

    # 写入 JSON 结果文件（UTF-8 编码，便于其他工具读取）
    report = {
        "summary": {
            "total": PASS + FAIL,
            "passed": PASS,
            "failed": FAIL,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "all_passed": FAIL == 0,
        },
        "results": RESULTS,
    }
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sandbox_report.json")
    with open(report_path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)
    print(f"\n报告已写入: {report_path}")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
