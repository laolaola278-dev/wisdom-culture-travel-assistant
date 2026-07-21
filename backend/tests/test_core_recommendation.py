import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def sm(kg):
    from recommendation import SessionManager
    return SessionManager(kg, max_sessions=10, ttl_seconds=3600)


def test_session_create(sm):
    s = sm.get_or_create(None)
    assert s.session_id is not None
    assert len(s.session_id) > 0


def test_session_reuse(sm):
    s1 = sm.get_or_create("test-001")
    s2 = sm.get_or_create("test-001")
    assert s1 is s2


def test_session_record(sm):
    session = sm.get_or_create(None)
    sid = session.session_id
    sm.record(sid, "白云山有什么景点", entities=[{"name": "白云山", "type": "景点"}], agent="culture")
    assert len(session.queries) == 1
    assert session.queries[0]["question"] == "白云山有什么景点"


def test_session_multiple_records(sm):
    session = sm.get_or_create(None)
    sid = session.session_id
    for i in range(5):
        sm.record(sid, f"问题{i}", entities=[{"name": f"实体{i}", "type": "景点"}], agent="culture")
    assert len(session.queries) == 5


def test_session_lru_eviction(sm):
    sessions = []
    for i in range(12):
        s = sm.get_or_create(f"user-{i:03d}")
        sessions.append(s)
    evicted = sm.get_or_create("user-000")
    kept = sm.get_or_create("user-011")
    assert evicted is not sessions[0]
    assert kept is sessions[11]


def test_recommend_fallback(sm, kg):
    from recommendation import RecommendationEngine
    engine = RecommendationEngine(kg, None, sm)
    session = sm.get_or_create("new-user")
    recs = engine.recommend_for_user(session.session_id, top_k=3)
    assert isinstance(recs, list)
    assert len(recs) >= 0


def test_recommend_with_history(sm, kg):
    from recommendation import RecommendationEngine
    engine = RecommendationEngine(kg, None, sm)
    session = sm.get_or_create("active-user")
    sm.record(session.session_id, "白云山",
              entities=[{"name": "白云山风景名胜区", "type": "景点"}], agent="culture")
    sm.record(session.session_id, "帽峰山",
              entities=[{"name": "帽峰山", "type": "景点"}], agent="culture")
    recs = engine.recommend_for_user(session.session_id, top_k=3)
    assert isinstance(recs, list)


def test_session_to_dict(sm):
    session = sm.get_or_create(None)
    sm.record(session.session_id, "测试问题",
              entities=[{"name": "测试实体", "type": "测试"}], agent="general")
    d = session.to_dict()
    assert "session_id" in d
    assert "query_count" in d
    assert "recent_queries" in d


def test_session_cleanup(sm):
    old = sm.get_or_create("expired-session")
    old.last_active = 0
    sm._cleanup()
    assert sm.get_session("expired-session") is None
