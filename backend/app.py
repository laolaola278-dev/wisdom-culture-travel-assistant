import os
import re
import uuid
import time
import datetime
import warnings
import logging

# Load .env from project root
from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
if os.path.exists(_env_path):
    load_dotenv(_env_path, override=True)

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context, g
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token, create_refresh_token
from flask_limiter import Limiter
from flasgger import Swagger, swag_from

from data_cleaner import DataCleaner
from knowledge_graph import KnowledgeGraph
from rag_engine import RAGEngine
from route_planner import RoutePlanner
from vector_store import VectorStore
from data_sync import DataSync
from evaluation import Evaluator
from agent_engine import AgentOrchestrator
from recommendation import SessionManager, RecommendationEngine
from data_sources.amap_client import AmapPOIClient
from config import Config
from cache import make_cache, cached

# Production imports
from database import get_db_session, init_db
from models import User, QASession
from auth import hash_password, verify_password, create_tokens, get_current_user, require_role, ROLE_HIERARCHY
from middleware import (
    sanitize, sanitize_dict, setup_request_context, teardown_request_context,
    log_audit, validate_required, make_error, get_client_ip,
)
from metrics import register_metrics_route, observe_request
from content_moderation import check_question

# Blueprints
from routes import history, favorites, feedback, admin, map3d

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logger = logging.getLogger("baiyun.app")

FRONTEND_BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'frontend'
)
FRONTEND_DIR = os.path.join(FRONTEND_BASE, 'dist') if os.path.isdir(os.path.join(FRONTEND_BASE, 'dist')) else FRONTEND_BASE

# ── Baiyun District landmark coordinates (approximate, for map display) ──
BAIYUN_COORDINATES = {
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

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _load_or_create_secret(name: str) -> str:
    """加载或生成持久化随机密钥（多 worker/重启间稳定），杜绝硬编码密钥。

    O_EXCL 独占创建保证多 worker 并发冷启动时只有一个 worker 写入；
    落败的 worker 重读文件，全部 worker 收敛到同一密钥。"""
    import secrets
    import time as _time
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'.{name}')

    def _read() -> str:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except OSError:
            return ''

    existing = _read()
    if existing:
        return existing
    try:
        key = secrets.token_urlsafe(48)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(key)
        logger.warning(f"{name} 未配置，已生成随机密钥并保存至 {path}（生产环境请通过环境变量设置）")
        return key
    except FileExistsError:
        # 另一 worker 抢先创建：短暂等待其写入完成后读取
        for _ in range(50):
            existing = _read()
            if existing:
                return existing
            _time.sleep(0.1)
        logger.warning(f"{name} 密钥文件存在但为空，使用进程内随机密钥")
        return secrets.token_urlsafe(48)
    except OSError:
        # 文件系统只读等极端情况：进程内随机（重启后 token 失效）
        logger.warning(f"{name} 未配置且无法持久化，使用进程内随机密钥")
        return secrets.token_urlsafe(48)


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    # ── JWT ───────────────────────────────────────────────────────
    _secret_key = Config.SECRET_KEY or _load_or_create_secret('secret_key')
    _jwt_key = Config.JWT_SECRET_KEY or _secret_key
    app.config['SECRET_KEY'] = _secret_key
    app.config['JWT_SECRET_KEY'] = _jwt_key
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = Config.JWT_ACCESS_TOKEN_EXPIRES
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = Config.JWT_REFRESH_TOKEN_EXPIRES
    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_payload):
        from auth import is_token_revoked
        return is_token_revoked(jwt_payload)

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data.get('sub')
        if not identity:
            return None
        with get_db_session() as db:
            return db.query(User).filter_by(id=int(identity)).first()

    # ── Rate Limiter ──────────────────────────────────────────────
    _limiter_enabled = Config.RATE_LIMIT_ENABLED
    _storage_uri = Config.CELERY_BROKER_URL
    if _limiter_enabled:
        try:
            import redis as _redis
            _redis.Redis().ping()
        except Exception:
            logger.warning("Redis unavailable, disabling rate limiter")
            _limiter_enabled = False
    limiter = Limiter(
        key_func=get_client_ip,
        app=app,
        default_limits=["100 per minute"],
        storage_uri=_storage_uri,
        enabled=_limiter_enabled,
    )

    # Monkey-patch limiter.limit to no-op when disabled (avoids ReferenceError in test client)
    if not _limiter_enabled:
        _original_limit = limiter.limit
        def _noop_limit(*args, **kwargs):
            def decorator(fn):
                return fn
            return decorator
        limiter.limit = _noop_limit

    # ── CORS (tightened) ──────────────────────────────────────────
    CORS(app, resources={
        r"/api/*": {
            "origins": Config.ALLOWED_ORIGINS,
            "supports_credentials": True,
            "allow_headers": ["Content-Type", "Authorization", "X-Session-Id", "X-Request-ID", "X-Device-Fingerprint"],
            "expose_headers": ["X-Request-ID"],
        }
    })

    # ── Request hooks ─────────────────────────────────────────────
    @app.before_request
    def before_request():
        setup_request_context()
        if request.path.startswith('/api/'):
            # Set current user on g for audit logging
            # 必须先 verify 再取 identity（视图装饰器的验证在此钩子之后才执行）
            try:
                from flask_jwt_extended import verify_jwt_in_request
                verify_jwt_in_request(optional=True)
                identity = get_jwt_identity()
                g.current_user_id = int(identity) if identity else None
            except Exception:
                g.current_user_id = None

    @app.after_request
    def after_request(response):
        # Prometheus metrics
        if hasattr(g, 'start_time') and request.path.startswith('/api/'):
            latency = time.time() - g.start_time
            # 用路由模板而非原始路径作标签，避免 /entity/<名称> 造成标签基数爆炸
            endpoint = request.url_rule.rule if request.url_rule else 'unmatched'
            observe_request(request.method, endpoint, response.status_code, latency)
        return teardown_request_context(response)

    # ── Swagger ───────────────────────────────────────────────────
    swagger = Swagger(app, config={
        "headers": [],
        "specs": [{
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
        }],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/docs/",
        "title": "白云文化智能问答助手 API",
        "description": "基于知识图谱 + DeepSeek V4 RAG的白云区文旅智能问答系统",
        "version": "2.0.0",
        "uiversion": 3,
    })

    data_cleaner = DataCleaner()
    data_cleaner.load_all_data()

    kg = KnowledgeGraph()
    if not kg.load_graph():
        print("未找到缓存知识图谱，开始构建...")
        kg.build_from_data(data_cleaner)
    else:
        print(
            f"已加载缓存知识图谱: "
            f"{kg.graph.number_of_nodes()}个节点, "
            f"{kg.graph.number_of_edges()}条边"
        )

    # 暴露 kg 给蓝图（3D 地图等需要访问知识图谱实体）
    app.extensions['kg'] = kg

    vector_store = VectorStore()

    rag = RAGEngine(kg, data_cleaner, vector_store=vector_store)
    rag.build_index()

    planner = RoutePlanner(kg, data_cleaner, rag)

    data_sync = DataSync(data_cleaner, kg, vector_store, rag)
    if Config.DATA_SYNC_ENABLED:
        data_sync.start_auto_sync()

    evaluator = Evaluator(rag, kg) if Config.ENABLE_EVALUATION else None

    orchestrator = AgentOrchestrator(kg, rag, data_cleaner, planner) if Config.ENABLE_AGENTS else None

    session_manager = SessionManager(kg, max_sessions=Config.MAX_SESSIONS, ttl_seconds=Config.SESSION_TTL_SECONDS) if Config.ENABLE_RECOMMENDATION else None
    rec_engine = RecommendationEngine(kg, data_cleaner, session_manager) if session_manager else None

    amap_client = AmapPOIClient() if Config.ENABLE_REALTIME_DATA else None

    cache = make_cache(Config)

    if Config.CACHE_ENABLED:
        print(f"缓存已启用 (后端: {'Redis' if cache.__class__.__name__ != 'NullCache' else '内存'}"
              f", TTL={Config.CACHE_DEFAULT_TTL}s)")

    model_label = (
        f"DeepSeek V4 ({Config.LLM_MODEL})"
        if Config.LLM_API_KEY and "deepseek" in Config.LLM_API_URL
        else "本地知识图谱 (无API密钥)"
    )
    print(f"问答引擎已初始化: {model_label}")
    if not Config.LLM_API_KEY:
        print("━" * 60)
        print("⚠️  未配置 DEEPSEEK_API_KEY / LLM_API_KEY")
        print("   当前使用本地知识图谱兜底模式（仅返回结构化数据，无自然语言理解）")
        print("   启用方式：")
        print("   1) 编辑项目根目录 .env 文件")
        print("   2) 设置: DEEPSEEK_API_KEY=sk-你的真实密钥")
        print("   3) 重启后端服务")
        print("━" * 60)
    else:
        print(f"✅ DeepSeek API 已启用 (model={Config.LLM_MODEL})")

    # ==================================================================
    #  Health
    # ==================================================================

    # ──────────────────────────────────────────────────────────────────
    #  Non‑streaming QA  (backward‑compatible)
    # ──────────────────────────────────────────────────────────────────

    @app.route('/api/qa', methods=['POST'])
    @limiter.limit("10 per minute")
    def qa():
        """
        智能问答 (非流式)
        ---
        tags:
          - qa
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - question
              properties:
                question:
                  type: string
                  example: 白云山有什么历史？
        responses:
          200:
            description: 问答结果,含答案与上下文来源
        """
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "请提供question参数"}), 400
        question = data['question'].strip()
        if not question:
            return jsonify({"error": "问题不能为空"}), 400
        is_safe, block_reason = check_question(question)
        if not is_safe:
            log_audit("qa.blocked", "question", details={"reason": block_reason})
            return jsonify({"error": block_reason, "blocked": True}), 400
        result = rag.query(question)
        return jsonify(result)

    # ──────────────────────────────────────────────────────────────────
    #  Streaming QA  (DeepSeek V4 SSE)
    # ──────────────────────────────────────────────────────────────────

    @app.route('/api/qa/stream', methods=['POST'])
    @limiter.limit("10 per minute")
    def qa_stream():
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "请提供question参数"}), 400
        question = data['question'].strip()
        if not question:
            return jsonify({"error": "问题不能为空"}), 400
        is_safe, block_reason = check_question(question)
        if not is_safe:
            log_audit("qa.blocked", "question", details={"reason": block_reason})
            return jsonify({"error": block_reason, "blocked": True}), 400

        def generate():
            try:
                for event_json in rag.query_stream(question):
                    yield f"data: {event_json}{Config.STREAM_CHUNK_DELIMITER}"
            except GeneratorExit:
                pass
            except Exception:
                error_event = (
                    '{"type":"error","message":"'
                    '流式响应中断，请重试。'
                    '"}'
                )
                yield f"data: {error_event}{Config.STREAM_CHUNK_DELIMITER}"

        return Response(
            stream_with_context(generate()),
            headers=SSE_HEADERS,
        )

    # ──────────────────────────────────────────────────────────────────
    #  Graph  (unchanged)
    # ──────────────────────────────────────────────────────────────────

    @app.route('/api/graph/stats', methods=['GET'])
    def graph_stats():
        stats = kg.get_graph_stats()
        return jsonify(stats)

    @app.route('/api/graph/search', methods=['GET'])
    def graph_search():
        """
        知识图谱实体搜索
        ---
        tags:
          - graph
        parameters:
          - in: query
            name: q
            type: string
            required: true
          - in: query
            name: top_k
            type: integer
            default: 5
        responses:
          200:
            description: 搜索结果列表
        """
        query = request.args.get('q', '')
        top_k = int(request.args.get('top_k', 10))
        if not query:
            return jsonify({"error": "请提供查询参数q"}), 400
        entities = kg.search_entities(query, top_k=top_k)
        results = []
        for name, score in entities:
            details = kg.get_entity_details(name)
            if details:
                # 补充 name 和 score 字段，便于前端统一处理
                details["name"] = name
                details["score"] = float(score)
                results.append(details)
        return jsonify({"query": query, "results": results})

    @app.route('/api/graph/entity/<path:entity_name>', methods=['GET'])
    def entity_detail(entity_name):
        details = kg.get_entity_details(entity_name)
        if not details:
            # Fallback: try fuzzy search
            matches = kg.search_entities(entity_name, top_k=1)
            if matches:
                details = kg.get_entity_details(matches[0][0])
        if not details:
            return jsonify({"error": f"未找到实体: {entity_name}"}), 404
        subgraph = kg.get_subgraph(details['entity'], depth=2)
        details['subgraph'] = subgraph
        return jsonify(details)

    @app.route('/api/graph/entities', methods=['GET'])
    def entities_by_type():
        entity_type = request.args.get('type', '')
        limit = int(request.args.get('limit', 100))
        if not entity_type:
            # 不传 type 时返回所有实体类型分组统计
            stats = kg.get_graph_stats()
            type_dist = stats.get('type_distribution', {})
            return jsonify({
                "type": "all",
                "count": len(type_dist),
                "entities": [],
                "type_distribution": type_dist,
            })
        entities = kg.get_all_entities_by_type(entity_type)
        return jsonify({
            "type": entity_type,
            "count": len(entities),
            "entities": entities[:limit] if isinstance(entities, list) else entities
        })

    @app.route('/api/hot-questions', methods=['GET'])
    def hot_questions():
        questions = rag.get_hot_questions()
        return jsonify({"questions": questions})

    # ──────────────────────────────────────────────────────────────────
    #  System & Evaluation (v2.1)
    # ──────────────────────────────────────────────────────────────────

    @app.route('/api/system/stats', methods=['GET'])
    def system_stats():
        kg_stats = kg.get_graph_stats()
        vs_stats = vector_store.get_stats() if vector_store else {}
        ds_status = data_sync.get_sync_status() if data_sync else {}
        return jsonify({
            "graph": kg_stats,
            "vector_store": vs_stats,
            "data_sync": ds_status,
            "config": {
                "hybrid_search": Config.ENABLE_HYBRID_SEARCH,
                "embedding_model": Config.EMBEDDING_MODEL,
                "rrf_k": Config.RRF_K,
                "ollama_enabled": Config.OLLAMA_ENABLED,
                "ollama_model": Config.OLLAMA_MODEL,
            }
        })

    @app.route('/api/system/sync', methods=['POST'])
    @limiter.limit("5 per minute")
    @require_role('admin')
    def trigger_sync():
        force = request.args.get('force', 'false').lower() == 'true'
        synced = data_sync.sync(force=force)
        return jsonify({
            "synced": synced,
            "message": "数据已同步" if synced else "数据已是最新",
            "sync_status": data_sync.get_sync_status(),
        })

    @app.route('/api/eval/run', methods=['POST'])
    @limiter.limit("5 per hour")
    @require_role('admin')
    def run_evaluation():
        if not evaluator:
            return jsonify({"error": "评估模式未启用 (ENABLE_EVALUATION=false)"}), 400
        verbose = request.args.get('verbose', 'true').lower() == 'true'
        results = evaluator.evaluate(verbose=verbose)
        return jsonify(results)

    @app.route('/api/eval/compare', methods=['GET'])
    @require_role('admin')
    def eval_compare():
        if not evaluator:
            return jsonify({"error": "评估模式未启用"}), 400
        evaluator.compare_baseline()
        latest = evaluator._find_latest_report()
        return jsonify({"latest_report": latest})

    # ══════════════════════════════════════════════════════════════════
    #  Phase 2: Multi-Agent + Personalization + Real-time Data
    # ══════════════════════════════════════════════════════════════════

    def _get_or_create_session(request):
        if not session_manager:
            return None
        session_id = (request.args.get('session_id') or
                      request.headers.get('X-Session-Id') or
                      None)
        if session_id is None:
            body = request.get_json(silent=True)
            if isinstance(body, dict):
                session_id = body.get('session_id')
        return session_manager.get_or_create(session_id)

    @app.route('/api/v2/qa', methods=['POST'])
    @limiter.limit("10 per minute")
    @jwt_required(optional=True)
    def v2_qa():
        """智能问答 v2: 多智能体路由
        ---
        tags:
          - v2
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required: [question]
              properties:
                question: { type: string }
                session_id: { type: string }
        """
        import time as _time
        start_time = _time.time()
        data = request.get_json() or {}
        question = data.get('question', '').strip()
        if not question:
            return jsonify({"error": "请提供question参数"}), 400

        # Content moderation
        is_safe, block_reason = check_question(question)
        if not is_safe:
            log_audit("qa.blocked", "question", details={"reason": block_reason})
            return jsonify({"error": block_reason, "blocked": True}), 400

        current_user_id = get_jwt_identity()
        session = _get_or_create_session(request)
        use_agent = data.get('use_agent', True) and orchestrator is not None

        # 命中缓存（仅非 agent 路径写入，与下方写入逻辑对称）
        if Config.CACHE_ENABLED and not use_agent:
            cached_result = cache.get(f'qa:{question}')
            if cached_result is not None:
                # 浅拷贝：NullCache 返回存储对象本身，直接改写会污染缓存
                cached_result = dict(cached_result)
                # history_id 属于首个提问者的历史记录，命中者对其无所有权（无法评分），剔除
                cached_result.pop('history_id', None)
                cached_result['session_id'] = session.session_id if session else None
                cached_result['cached'] = True
                return jsonify(cached_result)

        if use_agent and orchestrator:
            result = orchestrator.route_query(question)
        else:
            result = rag.query(question)
            result['agent'] = 'direct'

        latency_ms = int((_time.time() - start_time) * 1000)
        session_id = session.session_id if session else None
        related = result.get('related_entities', []) or []

        # Persist to memory session manager (legacy)
        if session:
            session_manager.record(session_id, question, entities=related,
                                    agent=result.get('agent'))

        # Persist to PostgreSQL (production)
        from database import get_db_session
        from models import QASession as DBQASession, QAHistory
        try:
            with get_db_session() as db:
                db_session = None
                if session_id:
                    db_session = db.query(DBQASession).filter_by(session_id=session_id).first()
                if not db_session:
                    db_session = DBQASession(
                        session_id=session_id or str(uuid.uuid4())[:16],
                        user_id=int(current_user_id) if current_user_id else None,
                        title=question[:100],
                        device_fingerprint=request.headers.get('X-Device-Fingerprint'),
                        ip_address=get_client_ip(),
                    )
                    db.add(db_session)
                    db.flush()
                elif current_user_id and not db_session.user_id:
                    # 关联已有匿名会话到当前登录用户
                    db_session.user_id = int(current_user_id)
                qa = QAHistory(
                    session_id=db_session.id,
                    question=question[:4000],
                    answer=result.get('answer', '')[:16000],
                    agent_used=result.get('agent'),
                    sources=result.get('related_entities', []) or [],
                    latency_ms=latency_ms,
                    model_name=Config.LLM_MODEL,
                )
                db.add(qa)
                db.flush()
                result['history_id'] = qa.id
        except Exception as e:
            logger.warning(f"Failed to persist QA history: {e}")

        result['session_id'] = session_id
        result['version'] = '2.1'
        result['agents_enabled'] = use_agent and orchestrator is not None
        if Config.CACHE_ENABLED and not use_agent:
            cache.set(f'qa:{question}', result, ttl=Config.CACHE_QA_TTL)
        return jsonify(result)

    @app.route('/api/v2/recommend', methods=['GET'])
    def v2_recommend():
        session = _get_or_create_session(request)
        if not session or not rec_engine:
            return jsonify({"error": "推荐服务未启用", "recommendations": []})
        top_k = request.args.get('top_k', Config.RECOMMEND_TOP_K, type=int)
        recs = rec_engine.recommend_for_user(session.session_id, top_k=top_k)
        return jsonify({
            "session_id": session.session_id,
            "recommendations": recs,
            "user_profile": session.to_dict() if session else None,
        })

    @app.route('/api/v2/session', methods=['GET', 'POST'])
    def v2_session():
        if not session_manager:
            return jsonify({"error": "会话管理未启用"}), 400
        if request.method == 'POST':
            data = request.get_json() or {}
            session = session_manager.get_or_create(data.get('session_id'))
            return jsonify(session.to_dict())
        session = _get_or_create_session(request)
        if session:
            return jsonify(session.to_dict())
        return jsonify({"error": "无活跃会话"}), 404

    @app.route('/api/v2/agents', methods=['GET'])
    def v2_agents():
        if not orchestrator:
            return jsonify({"error": "智能体系统未启用", "agents": []})
        return jsonify({
            "agents": orchestrator.get_agent_info(),
            "active": True,
        })

    @app.route('/api/v2/poi/search', methods=['GET'])
    def v2_poi_search():
        if not amap_client:
            return jsonify({"error": "实时数据服务未启用"}), 400
        keywords = request.args.get('keywords', '')
        city = request.args.get('city', '广州')
        types = request.args.get('types')
        if not keywords:
            return jsonify({"error": "请提供keywords参数"}), 400
        results = amap_client.search_poi(keywords, city=city, types=types)
        return jsonify({"count": len(results), "results": results, "source": "amap"})

    @app.route('/api/v2/poi/nearby', methods=['GET'])
    def v2_poi_nearby():
        if not amap_client:
            return jsonify({"error": "实时数据服务未启用"}), 400
        lng = request.args.get('lng', type=float)
        lat = request.args.get('lat', type=float)
        radius = request.args.get('radius', 1000, type=int)
        types = request.args.get('types')
        if lng is None or lat is None:
            return jsonify({"error": "请提供lng和lat参数"}), 400
        results = amap_client.search_nearby(lng, lat, radius=radius, types=types)
        return jsonify({"count": len(results), "results": results, "source": "amap"})

    @app.route('/api/v2/weather', methods=['GET'])
    def v2_weather():
        if not amap_client:
            return jsonify({"error": "实时数据服务未启用"}), 400
        city = request.args.get('city', '440111')
        result = amap_client.get_weather(city)
        return jsonify(result)

    @app.route('/api/v2/itinerary', methods=['POST'])
    def v2_itinerary():
        """
        智能行程规划 v2: 生成带预算、时间线、交通建议的完整行程
        """
        data = request.get_json() or {}
        start = data.get('start', '').strip()
        end = data.get('end', '').strip() or None
        days = data.get('days', 1)
        budget = data.get('budget', 0)
        preferences = data.get('preferences', {})

        if not start:
            return jsonify({"error": "请提供起点start参数"}), 400

        route_result = planner.plan_route(start, end, preferences)
        timeline = _generate_timeline(route_result, days)

        return jsonify({
            "start": start,
            "end": end or "周边游览",
            "days": days,
            "budget": budget,
            "route_plan": route_result.get('route_plan', ''),
            "timeline": timeline,
            "waypoints_count": route_result.get('waypoints_count', 0),
            "nearby_services": route_result.get('nearby_services', {}),
        })

    def _generate_timeline(route_result, days):
        wc = route_result.get('waypoints_count', 0)
        if wc == 0:
            return []
        per_day = max(1, (wc + days - 1) // days)
        timeline = []
        for d in range(days):
            start_idx = d * per_day
            end_idx = min(start_idx + per_day, wc)
            if start_idx >= wc:
                break
            timeline.append({
                "day": d + 1,
                "label": f"第{d+1}天",
                "waypoints_count": end_idx - start_idx,
                "waypoints": [
                    {"index": i + 1, "name": f"景点{i+1}"}
                    for i in range(start_idx, end_idx)
                ],
            })
        return timeline

    @app.route('/api/data/categories', methods=['GET'])
    def data_categories():
        stats = kg.get_graph_stats()
        return jsonify({
            "categories": [
                {"key": "景点", "label": "A级景区/旅游景点",
                 "count": stats['entity_types'].get('景点', 0)},
                {"key": "公园", "label": "公园",
                 "count": stats['entity_types'].get('公园', 0)},
                {"key": "图书馆", "label": "图书馆",
                 "count": stats['entity_types'].get('图书馆', 0)},
                {"key": "非遗项目", "label": "非物质文化遗产",
                 "count": stats['entity_types'].get('非遗项目', 0)},
                {"key": "酒店", "label": "星级酒店",
                 "count": stats['entity_types'].get('酒店', 0)},
                {"key": "民宿", "label": "民宿",
                 "count": stats['entity_types'].get('民宿', 0)},
                {"key": "旅行社", "label": "旅行社",
                 "count": stats['entity_types'].get('旅行社', 0)},
                {"key": "文化站", "label": "文化站",
                 "count": stats['entity_types'].get('文化站', 0)},
                {"key": "充电站", "label": "充电站",
                 "count": stats['entity_types'].get('充电站', 0)},
                {"key": "旅馆", "label": "旅馆",
                 "count": stats['entity_types'].get('旅馆', 0)},
                {"key": "活动", "label": "图书馆活动",
                 "count": stats['entity_types'].get('活动', 0)},
                {"key": "供电网点", "label": "供电营业网点",
                 "count": stats['entity_types'].get('供电网点', 0)},
                {"key": "服务点", "label": "图书馆服务点",
                 "count": stats['entity_types'].get('服务点', 0)}
            ]
        })

    @app.route('/api/graph/visualization', methods=['GET'])
    def graph_visualization():
        entity_type = request.args.get('type', '')
        limit = int(request.args.get('limit', 50))
        nodes = []
        edges = []
        count = 0
        for n in kg.graph.nodes():
            if entity_type and kg.graph.nodes[n].get('type', '') != entity_type:
                continue
            if count >= limit:
                break
            ntype = kg.graph.nodes[n].get('type', '未知')
            nodes.append({"id": n, "label": n, "category": ntype})
            count += 1

        node_ids = {n['id'] for n in nodes}
        for u, v, data in kg.graph.edges(data=True):
            if u in node_ids and v in node_ids:
                edges.append({
                    "source": u,
                    "target": v,
                    "relation": data.get('relation', '')
                })

        return jsonify({"nodes": nodes, "edges": edges})

    # ──────────────────────────────────────────────────────────────────
    #  Map Data (Amap coordinates)
    # ──────────────────────────────────────────────────────────────────

    @app.route('/api/map/coordinates', methods=['GET'])
    def map_coordinates():
        """
        获取地图坐标数据
        ---
        tags:
          - map
        parameters:
          - in: query
            name: entity
            type: string
          - in: query
            name: type
            type: string
          - in: query
            name: limit
            type: integer
            default: 100
        responses:
          200:
            description: 坐标点列表
        """
        entity_name = request.args.get('entity', '')
        entity_type = request.args.get('type', '')
        limit = int(request.args.get('limit', 100))

        result = []
        for name, coord in BAIYUN_COORDINATES.items():
            if entity_name and entity_name not in name:
                continue
            details = kg.get_entity_details(name) or {}
            etype = details.get('type', '')
            if entity_type and etype != entity_type:
                continue
            if len(result) >= limit:
                break
            result.append({
                "name": name,
                "lng": coord[0],
                "lat": coord[1],
                "type": etype,
                "display_name": details.get('display_name', name),
                "location": details.get('location', ''),
            })
        return jsonify({
            "count": len(result),
            "points": result,
        })

    # ──────────────────────────────────────────────────────────────────
    #  AI-Enhanced Explore Endpoints (Route Planner + AI Search)
    # ──────────────────────────────────────────────────────────────────

    @app.route('/api/explore/ai-search', methods=['POST'])
    def explore_ai_search():
        """
        AI智能检索 (支持图片)
        ---
        tags:
          - explore
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - query
              properties:
                query:
                  type: string
                  example: 白云山有什么历史文化
                image:
                  type: string
                  description: 图片base64数据
                search_type:
                  type: string
                  default: general
        responses:
          200:
            description: AI分析结果+相关实体
        """
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({"error": "请提供query参数"}), 400
        query = data['query'].strip()
        if not query:
            return jsonify({"error": "查询不能为空"}), 400
        search_type = data.get('search_type', 'general')
        image_base64 = data.get('image', None)
        result = planner.ai_search(query, search_type, image_base64=image_base64)
        return jsonify(result)

    @app.route('/api/explore/route-plan', methods=['POST'])
    def explore_route_plan():
        """
        AI路线规划
        ---
        tags:
          - explore
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - start
              properties:
                start:
                  type: string
                  example: 白云山风景名胜区
                end:
                  type: string
                preferences:
                  type: object
        responses:
          200:
            description: 路线规划结果+途经点+沿途服务设施
        """
        data = request.get_json()
        if not data or 'start' not in data:
            return jsonify({"error": "请提供起点start参数"}), 400
        start = data['start'].strip()
        end = data.get('end', '').strip() or None
        preferences = data.get('preferences', {})
        if not start:
            return jsonify({"error": "起点不能为空"}), 400
        result = planner.plan_route(start, end, preferences)
        return jsonify(result)

    @app.route('/api/explore/entity/<path:entity_name>/enhanced', methods=['GET'])
    def explore_entity_enhanced(entity_name):
        result = planner.get_enhanced_detail(entity_name)
        if not result:
            matches = kg.search_entities(entity_name, top_k=1)
            if matches:
                result = planner.get_enhanced_detail(matches[0][0])
        if not result:
            return jsonify({"error": f"未找到实体: {entity_name}"}), 404
        return jsonify(result)

    @app.route('/api/explore/entity/<path:entity_name>/nearby', methods=['GET'])
    def explore_entity_nearby(entity_name):
        nearby = planner.get_nearby_attractions(entity_name, max_distance=3, max_results=15)
        if not nearby:
            matches = kg.search_entities(entity_name, top_k=1)
            if matches:
                nearby = planner.get_nearby_attractions(matches[0][0], max_distance=3, max_results=15)
                entity_name = matches[0][0]
        return jsonify({
            "entity": entity_name,
            "nearby": nearby
        })

    @app.route('/api/explore/entity/<path:entity_name>/context', methods=['GET'])
    def explore_entity_context(entity_name):
        result = kg.get_entity_with_context(entity_name)
        if not result:
            matches = kg.search_entities(entity_name, top_k=1)
            if matches:
                result = kg.get_entity_with_context(matches[0][0])
        if not result:
            return jsonify({"error": f"未找到实体: {entity_name}"}), 404
        return jsonify(result)

    # ──────────────────────────────────────────────────────────────────
    #  Statistics: Location frequency from QA answers
    # ──────────────────────────────────────────────────────────────────

    @app.route('/api/stats/location-frequency', methods=['GET'])
    def location_frequency():
        """分析智能问答回答中各地点的出现次数"""
        top_n = request.args.get('top_n', 30, type=int)
        import re
        from database import get_db_session
        from models import QAHistory, Entity

        # 1. 读取所有实体名作为地点词典
        location_dict = {}  # name -> {type, address}
        try:
            with get_db_session() as db:
                entities = db.query(Entity).all()
                for e in entities:
                    key = e.name.strip()
                    if len(key) >= 2:
                        location_dict[key] = {
                            'type': e.entity_type or '未知',
                            'address': e.address or e.location or '',
                            'display_name': e.display_name or key,
                        }
        except Exception as e:
            logger.warning(f"加载实体词典失败: {e}")

        # 2. 读取所有 QA 回答并统计地点出现次数
        freq = {}  # name -> count
        try:
            with get_db_session() as db:
                histories = db.query(QAHistory).all()
                for h in histories:
                    answer = h.answer or ''
                    # 去除 HTML 标签
                    text = re.sub(r'<[^>]+>', '', answer)
                    for name, info in location_dict.items():
                        # 简单字符串匹配（实体名在回答中出现）
                        count = text.count(name)
                        if count > 0:
                            freq[name] = freq.get(name, 0) + count
        except Exception as e:
            logger.warning(f"统计问答地点失败: {e}")

        # 3. 按出现次数排序
        sorted_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]

        # 4. 按类型聚合
        type_dist = {}
        for name, count in sorted_items:
            t = location_dict.get(name, {}).get('type', '未知')
            type_dist[t] = type_dist.get(t, 0) + count

        # 5. 构建时间趋势（按天统计问答量）
        daily_trend = {}
        try:
            with get_db_session() as db:
                histories = db.query(QAHistory).all()
                for h in histories:
                    day = h.created_at.strftime('%Y-%m-%d') if h.created_at else 'unknown'
                    daily_trend[day] = daily_trend.get(day, 0) + 1
        except Exception as e:
            logger.warning(f"统计时间趋势失败: {e}")

        return jsonify({
            "total_qa": len(histories) if 'histories' in dir() else 0,
            "top_locations": [
                {
                    "name": name,
                    "display_name": location_dict.get(name, {}).get('display_name', name),
                    "count": count,
                    "type": location_dict.get(name, {}).get('type', '未知'),
                    "address": location_dict.get(name, {}).get('address', ''),
                }
                for name, count in sorted_items
            ],
            "type_distribution": [
                {"type": t, "count": c}
                for t, c in sorted(type_dist.items(), key=lambda x: x[1], reverse=True)
            ],
            "daily_trend": [
                {"date": d, "count": c}
                for d, c in sorted(daily_trend.items())
            ],
        })

    @app.route('/api/stats/overview', methods=['GET'])
    def stats_overview():
        """系统整体数据概览"""
        from database import get_db_session
        from models import QAHistory, QASession, User, Entity
        try:
            with get_db_session() as db:
                qa_count = db.query(QAHistory).count()
                session_count = db.query(QASession).count()
                user_count = db.query(User).count()
                entity_count = db.query(Entity).count()
                return jsonify({
                    "qa_total": qa_count,
                    "session_total": session_count,
                    "user_total": user_count,
                    "entity_total": entity_count,
                })
        except Exception as e:
            logger.warning(f"统计概览失败: {e}")
            return jsonify({"qa_total": 0, "session_total": 0, "user_total": 0, "entity_total": 0})

    # ──────────────────────────────────────────────────────────────────
    # ── Custom Swagger UI fallback ──────────────────────────────────
    @app.route('/api/swagger', methods=['GET'])
    def swagger_ui():
        specs_url = request.host_url.rstrip('/') + '/apispec_1.json'
        html = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>白云文化智能问答助手 API v2.0</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <style>
        html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
        *, *:before, *:after { box-sizing: inherit; }
        body { margin: 0; background: #fafafa; }
        .topbar { display: none; }
        .swagger-ui .info { margin: 20px 0; }
        .swagger-ui .info .title { font-size: 28px; }
        .swagger-ui .scheme-container { box-shadow: none; }
    </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
<script>
window.onload = function() {
    SwaggerUIBundle({
        url: "''' + specs_url + r'''",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        plugins: [SwaggerUIBundle.plugins.DownloadUrl],
        layout: "StandaloneLayout",
        defaultModelsExpandDepth: -1,
        docExpansion: "list",
        filter: true,
        tryItOutEnabled: true
    });
};
</script>
</body>
</html>'''
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

    #  Static frontend  (with Amap key injection)
    # ──────────────────────────────────────────────────────────────────

    @app.route('/')
    def index():
        html_path = os.path.join(FRONTEND_DIR, 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        amap_key = getattr(Config, 'AMAP_KEY', '') or os.environ.get('AMAP_KEY', '')
        content = content.replace('${AMAP_KEY}', amap_key)
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}

    @app.route('/<path:filename>')
    def static_files(filename):
        # SPA fallback: serve index.html for non-static, non-API routes
        file_path = os.path.join(FRONTEND_DIR, filename)
        if os.path.isfile(file_path):
            return send_from_directory(FRONTEND_DIR, filename)
        # Vue Router SPA fallback
        html_path = os.path.join(FRONTEND_DIR, 'index.html')
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            amap_key = getattr(Config, 'AMAP_KEY', '') or os.environ.get('AMAP_KEY', '')
            content = content.replace('${AMAP_KEY}', amap_key)
            return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
        return jsonify({"error": "Not found"}), 404

    # ══════════════════════════════════════════════════════════════════
    #  Auth Routes (Production)
    # ══════════════════════════════════════════════════════════════════

    @app.route('/api/auth/register', methods=['POST'])
    @limiter.limit("5 per minute")
    def auth_register():
        data = sanitize_dict(request.get_json() or {})
        ok, err = validate_required(data, ['username', 'email', 'password'])
        if not ok:
            return err
        username = data['username'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        if len(password) < 8:
            return make_error("密码长度至少8位", 400, "weak_password")
        with get_db_session() as db:
            if db.query(User).filter((User.username == username) | (User.email == email)).first():
                return make_error("用户名或邮箱已存在", 409, "conflict")
            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role='user',
            )
            db.add(user)
            db.flush()
            log_audit("user.register", "user", str(user.id))
            return jsonify({"message": "注册成功", "user_id": str(user.public_id)}), 201

    @app.route('/api/auth/login', methods=['POST'])
    @limiter.limit("10 per minute")
    def auth_login():
        data = sanitize_dict(request.get_json() or {})
        ok, err = validate_required(data, ['username', 'password'])
        if not ok:
            return err
        username = data['username'].strip()
        password = data['password']
        with get_db_session() as db:
            user = db.query(User).filter_by(username=username).first()
            if not user or not verify_password(password, user.password_hash):
                return make_error("用户名或密码错误", 401, "unauthorized")
            if not user.is_active:
                return make_error("账户已被禁用", 403, "account_disabled")
            user.last_login_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            tokens = create_tokens(user.id, fresh=True)
            log_audit("user.login", "user", str(user.id))
            return jsonify({
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "user": {
                    "id": str(user.public_id),
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                }
            })

    @app.route('/api/auth/refresh', methods=['POST'])
    @jwt_required(refresh=True)
    def auth_refresh():
        user_id = get_jwt_identity()
        with get_db_session() as db:
            user = db.query(User).filter_by(id=int(user_id)).first()
        if not user or not user.is_active:
            return make_error("账户已被禁用或不存在", 403, "account_disabled")
        tokens = create_tokens(int(user_id), fresh=False)
        return jsonify({"access_token": tokens["access_token"]})

    @app.route('/api/auth/me', methods=['GET'])
    @jwt_required()
    def auth_me():
        user = get_current_user()
        if not user:
            return make_error("用户不存在", 404, "not_found")
        return jsonify({
            "id": str(user.public_id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "last_login": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat(),
        })

    @app.route('/api/auth/logout', methods=['POST'])
    @jwt_required()
    def auth_logout():
        from flask_jwt_extended import get_jwt
        from auth import revoke_token, revoke_all_user_tokens
        user_id = get_jwt_identity()
        claims = get_jwt()
        # 撤销当前 access token + 该用户全部已登记的 refresh token
        exp = datetime.datetime.fromtimestamp(claims['exp'])
        revoke_token(claims['jti'], int(user_id), exp)
        revoke_all_user_tokens(int(user_id))
        log_audit("user.logout", "user", user_id)
        return jsonify({"message": "已登出"})

    # ── Health Check (Merged) ──────────────────────────────────────
    @app.route('/api/health', methods=['GET'])
    def health_check():
        health = {"status": "ok", "version": "2.1.0", "message": "白云文化智能问答助手服务运行中"}
        try:
            with get_db_session() as db:
                from sqlalchemy import text
                db.execute(text("SELECT 1"))
            health["database"] = "ok"
        except Exception as e:
            health["database"] = f"error: {str(e)}"
            health["status"] = "degraded"
        health["agents"] = {"enabled": Config.ENABLE_AGENTS}
        health["recommendation"] = {"enabled": Config.ENABLE_RECOMMENDATION}

        # LLM 状态（判断 API Key 是否为真实密钥，过滤占位符）
        api_key = Config.LLM_API_KEY or ''
        is_placeholder = (
            not api_key or
            api_key.startswith('sk-your-') or
            api_key in ('your-api-key', 'change-me')
        )
        health["llm_enabled"] = bool(api_key) and not is_placeholder
        health["llm_provider"] = "deepseek" if "deepseek" in (Config.LLM_API_URL or '').lower() else "unknown"
        health["model"] = Config.LLM_MODEL
        health["streaming"] = bool(api_key)
        health["hybrid_search"] = Config.ENABLE_HYBRID_SEARCH
        health["ollama_fallback"] = Config.OLLAMA_ENABLED
        health["data_auto_sync"] = Config.DATA_SYNC_ENABLED
        health["knowledge_graph"] = {
            "entities": kg.get_graph_stats().get('total_entities', 0),
            "relations": kg.get_graph_stats().get('total_relations', 0),
        }
        if vector_store:
            health["vector_store"] = vector_store.get_stats()
        return jsonify(health)

    # System notice
    @app.route('/api/notice', methods=['GET'])
    def get_notice():
        try:
            with get_db_session() as db:
                from models import SystemSetting
                s = db.query(SystemSetting).filter_by(key='notice').first()
                return jsonify({"notice": s.value if s else ""})
        except Exception:
            return jsonify({"notice": ""})

    # Cache warmup (runs once at startup)
    def _warmup_cache():
        if not Config.CACHE_ENABLED or cache is None:
            return
        warmup_questions = [
            "白云山的景点",
            "白云区图书馆开放时间",
            "广州有哪些必去的景点",
        ]
        for q in warmup_questions:
            try:
                res = rag.query(q)
                cache.set(f'qa:{q}', res, ttl=Config.CACHE_QA_TTL)
            except Exception as e:
                logger.warning(f"Cache warmup failed for '{q}': {e}")

    # Run warmup in background thread
    import threading
    threading.Thread(target=_warmup_cache, daemon=True).start()

    # Register Blueprints
    app.register_blueprint(history.bp)
    app.register_blueprint(favorites.bp)
    app.register_blueprint(feedback.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(map3d.bp)

    # Prometheus metrics
    register_metrics_route(app)

    return app


if __name__ == '__main__':
    app = create_app()
    # Production: never use app.run() directly
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
