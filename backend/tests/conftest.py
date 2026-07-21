import sys
import os
import json
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def app():
    from app import create_app
    app = create_app()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def kg():
    from knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph()
    if not kg.load_graph():
        pytest.skip("知识图谱数据未加载，请先运行 app.py 初始化")
    return kg


@pytest.fixture
def data_cleaner():
    from data_cleaner import DataCleaner
    dc = DataCleaner()
    dc.load_all_data()
    return dc


@pytest.fixture
def vector_store():
    from vector_store import VectorStore
    vs = VectorStore()
    return vs


@pytest.fixture(scope="session")
def session_kg():
    from knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph()
    if not kg.load_graph():
        pytest.skip("知识图谱数据未加载")
    return kg


@pytest.fixture(scope="session")
def session_vector_store():
    from vector_store import VectorStore
    return VectorStore()


@pytest.fixture(scope="session")
def session_vector_store_obj():
    from vector_store import VectorStore
    return VectorStore()


@pytest.fixture(scope="session")
def session_rag(session_kg, session_vector_store_obj, session_data_cleaner):
    from rag_engine import RAGEngine
    rag = RAGEngine(session_kg, session_data_cleaner, vector_store=session_vector_store_obj)
    rag.build_index()
    return rag


@pytest.fixture
def mock_deepseek(monkeypatch):
    class MockResponse:
        def __init__(self):
            self.status_code = 200

        def json(self):
            return {
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "白云山位于广州市白云区，是南粤名山之一，自古有'羊城第一秀'之称。"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80}
            }

        def raise_for_status(self):
            pass

        def iter_lines(self):
            return []

    def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr("requests.post", mock_post)


@pytest.fixture
def mock_deepseek_failure(monkeypatch):
    class MockFailedResponse:
        def __init__(self):
            self.status_code = 500

        def json(self):
            return {"error": "Server Error"}

        def raise_for_status(self):
            raise Exception("API call failed")

        def iter_lines(self):
            return []

    def mock_post(*args, **kwargs):
        raise Exception("Connection timeout")

    monkeypatch.setattr("requests.post", mock_post)


@pytest.fixture
def sample_session(session_manager):
    session = session_manager.get_or_create(None)
    session_manager.record(session.session_id, "白云山有什么景点",
                           entities=[{"name": "白云山", "type": "景点"}],
                           agent="culture")
    session_manager.record(session.session_id, "帽峰山怎么去",
                           entities=[{"name": "帽峰山", "type": "景点"}],
                           agent="route")
    return session


@pytest.fixture
def session_manager(session_kg):
    from recommendation import SessionManager
    return SessionManager(session_kg, max_sessions=100, ttl_seconds=3600)


@pytest.fixture
def rec_engine(session_kg, session_manager, session_data_cleaner):
    from recommendation import RecommendationEngine
    return RecommendationEngine(session_kg, session_data_cleaner, session_manager)


@pytest.fixture(scope="session")
def session_data_cleaner():
    from data_cleaner import DataCleaner
    dc = DataCleaner()
    dc.load_all_data()
    return dc


@pytest.fixture(scope="session")
def agent_orchestrator(session_kg, session_rag, session_data_cleaner):
    from agent_engine import AgentOrchestrator
    from route_planner import RoutePlanner
    planner = RoutePlanner(session_kg, session_data_cleaner, session_rag)
    return AgentOrchestrator(session_kg, session_rag, session_data_cleaner, planner)


@pytest.fixture(scope="session")
def planner(session_kg, session_rag, session_data_cleaner):
    from route_planner import RoutePlanner
    return RoutePlanner(session_kg, session_data_cleaner, session_rag)
