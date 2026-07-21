import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', '')
    DATA_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '智慧文旅与交通建设数据'
    )

    # ── Database (PostgreSQL) ───────────────────────────────────────
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('DB_PORT', '5432'))
    DB_NAME = os.environ.get('DB_NAME', 'baiyun_culture')
    DB_USER = os.environ.get('DB_USER', 'baiyun')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # ── JWT ─────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', '900'))
    JWT_REFRESH_TOKEN_EXPIRES = int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', '604800'))
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    # ── Security ────────────────────────────────────────────────────
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5000').split(',')
    TRUSTED_PROXIES = os.environ.get('TRUSTED_PROXIES', '').split(',')
    GRAPH_DATA_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'graph_data'
    )
    MODEL_CACHE_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '.model_cache'
    )

    # ── DeepSeek API ────────────────────────────────────────────────
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL = os.environ.get(
        'DEEPSEEK_BASE_URL',
        'https://api.deepseek.com/chat/completions'
    )
    DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')

    # ── 主 LLM (默认 DeepSeek) ─────────────────────────────────────
    LLM_API_KEY = os.environ.get('LLM_API_KEY', DEEPSEEK_API_KEY)
    LLM_API_URL = os.environ.get('LLM_API_URL', DEEPSEEK_BASE_URL)
    LLM_MODEL = os.environ.get('LLM_MODEL', DEEPSEEK_MODEL)

    # ── Ollama 本地回退 ─────────────────────────────────────────────
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b')
    OLLAMA_ENABLED = os.environ.get('OLLAMA_ENABLED', 'false').lower() == 'true'

    # ── Embedding ────────────────────────────────────────────────────
    EMBEDDING_MODEL = os.environ.get(
        'EMBEDDING_MODEL', 'BAAI/bge-small-zh-v1.5'
    )
    VECTOR_SIMILARITY_THRESHOLD = float(
        os.environ.get('VECTOR_SIMILARITY_THRESHOLD', '0.35')
    )

    # ── RAG / Hybrid ────────────────────────────────────────────────
    ENABLE_HYBRID_SEARCH = os.environ.get('ENABLE_HYBRID_SEARCH', 'true').lower() == 'true'
    RRF_K = int(os.environ.get('RRF_K', '60'))
    HYBRID_TOP_K = int(os.environ.get('HYBRID_TOP_K', '8'))
    KEYWORD_TOP_K = int(os.environ.get('KEYWORD_TOP_K', '5'))
    GRAPH_TOP_K = int(os.environ.get('GRAPH_TOP_K', '5'))
    VECTOR_TOP_K = int(os.environ.get('VECTOR_TOP_K', '8'))

    MAX_CONTEXT_LENGTH = int(os.environ.get('MAX_CONTEXT_LENGTH', '4000'))
    STREAM_TIMEOUT_SECONDS = int(os.environ.get('STREAM_TIMEOUT_SECONDS', '60'))
    STREAM_CHUNK_DELIMITER = "\n\n"

    # ── 数据同步 ────────────────────────────────────────────────────
    DATA_SYNC_INTERVAL_HOURS = int(os.environ.get('DATA_SYNC_INTERVAL_HOURS', '24'))
    DATA_SYNC_ENABLED = os.environ.get('DATA_SYNC_ENABLED', 'true').lower() == 'true'

    # ── 评估模式 ────────────────────────────────────────────────────
    ENABLE_EVALUATION = os.environ.get('ENABLE_EVALUATION', 'false').lower() == 'true'
    EVAL_QUESTIONS_PATH = os.environ.get(
        'EVAL_QUESTIONS_PATH',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'eval_questions.json')
    )

    # ── 多智能体 ────────────────────────────────────────────────────
    ENABLE_AGENTS = os.environ.get('ENABLE_AGENTS', 'true').lower() == 'true'
    AGENT_CONFIDENCE_THRESHOLD = float(os.environ.get('AGENT_CONFIDENCE_THRESHOLD', '0.05'))

    # ── 个性化推荐 ──────────────────────────────────────────────────
    ENABLE_RECOMMENDATION = os.environ.get('ENABLE_RECOMMENDATION', 'true').lower() == 'true'
    RECOMMEND_TOP_K = int(os.environ.get('RECOMMEND_TOP_K', '5'))
    MAX_SESSIONS = int(os.environ.get('MAX_SESSIONS', '1000'))
    SESSION_TTL_SECONDS = int(os.environ.get('SESSION_TTL_SECONDS', '3600'))

    # ── 实时数据 ────────────────────────────────────────────────────
    ENABLE_REALTIME_DATA = os.environ.get('ENABLE_REALTIME_DATA', 'false').lower() == 'true'
    AMAP_POI_CACHE_TTL = int(os.environ.get('AMAP_POI_CACHE_TTL', '86400'))

    # ── 地图 ────────────────────────────────────────────────────────
    AMAP_KEY = os.environ.get('AMAP_KEY', '')

    # ── 腾讯地图 3D ─────────────────────────────────────────────────
    TENCENT_MAP_KEY = os.environ.get('TENCENT_MAP_KEY', '')
    TENCENT_MAP_SECRET = os.environ.get('TENCENT_MAP_SECRET', '')
    # 浏览器端专用 key（控制台按域名白名单限制），避免下发服务端签名 key
    TENCENT_MAP_BROWSER_KEY = os.environ.get('TENCENT_MAP_BROWSER_KEY', '')
    ENABLE_3D_MAP = os.environ.get('ENABLE_3D_MAP', 'true').lower() == 'true'
    BUILDING_LOD_MAX_DISTANCE = int(os.environ.get('BUILDING_LOD_MAX_DISTANCE', '5000'))
    TRAFFIC_UPDATE_INTERVAL = int(os.environ.get('TRAFFIC_UPDATE_INTERVAL', '30'))
    CROWD_UPDATE_INTERVAL = int(os.environ.get('CROWD_UPDATE_INTERVAL', '60'))

    # ══════════════════════════════════════════════════════════════════
    #  Phase 3: Production / Caching / Async
    # ══════════════════════════════════════════════════════════════════

    # ── Redis ───────────────────────────────────────────────────────
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
    REDIS_DB = int(os.environ.get('REDIS_DB', '0'))
    CACHE_PREFIX = os.environ.get('CACHE_PREFIX', 'baiyun:')
    CACHE_ENABLED = os.environ.get('CACHE_ENABLED', 'false').lower() == 'true'
    CACHE_DEFAULT_TTL = int(os.environ.get('CACHE_DEFAULT_TTL', '300'))
    CACHE_QA_TTL = int(os.environ.get('CACHE_QA_TTL', '600'))
    CACHE_POI_TTL = int(os.environ.get('CACHE_POI_TTL', '86400'))
    CACHE_WEATHER_TTL = int(os.environ.get('CACHE_WEATHER_TTL', '3600'))
    CACHE_GRAPH_TTL = int(os.environ.get('CACHE_GRAPH_TTL', '3600'))

    # ── Celery ──────────────────────────────────────────────────────
    CELERY_ENABLED = os.environ.get('CELERY_ENABLED', 'false').lower() == 'true'
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')

    # ── Multi-modal ─────────────────────────────────────────────────
    ENABLE_MULTIMODAL = os.environ.get('ENABLE_MULTIMODAL', 'false').lower() == 'true'
    IMAGE_SEARCH_MODEL = os.environ.get('IMAGE_SEARCH_MODEL', 'clip-ViT-B-32')

    # ── Rate Limit ──────────────────────────────────────────────────
    RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'false').lower() == 'true'
    RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', '60'))
    RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))
