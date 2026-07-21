from celery import Celery
from config import Config

celery_app = Celery(
    'baiyun_tasks',
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_data_task(self):
    from data_sync import DataSync
    from data_cleaner import DataCleaner
    from knowledge_graph import KnowledgeGraph
    from rag_engine import RAGEngine
    from vector_store import VectorStore
    dc = DataCleaner(); dc.load_all_data()
    kg = KnowledgeGraph(); kg.load_graph()
    vs = VectorStore()
    rag = RAGEngine(kg, dc, vector_store=vs); rag.build_index()
    ds = DataSync(dc, kg, vs, rag)
    ok = ds.sync(force=True)
    return {'synced': ok}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_evaluation_task(self):
    from evaluation import Evaluator
    from knowledge_graph import KnowledgeGraph
    from rag_engine import RAGEngine
    from vector_store import VectorStore
    kg = KnowledgeGraph(); kg.load_graph()
    vs = VectorStore()
    rag = RAGEngine(kg, None, vector_store=vs); rag.build_index()
    ev = Evaluator(rag, kg)
    return ev.evaluate(verbose=True)
