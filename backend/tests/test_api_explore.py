import pytest
import json


class TestAPIExplore:
    """文旅探索 API tests"""

    def test_ai_search(self, client):
        resp = client.post("/api/explore/ai-search", json={
            "query": "白云山有什么历史文化",
            "search_type": "cultural"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "answer" in data or "results" in data

    def test_ai_search_no_query(self, client):
        resp = client.post("/api/explore/ai-search", json={})
        assert resp.status_code == 400

    def test_route_plan(self, client):
        resp = client.post("/api/explore/route-plan", json={
            "start": "白云山",
            "preferences": {"兴趣": ["自然"]}
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "route_plan" in data or "waypoints" in data

    def test_entity_enhanced(self, client):
        resp = client.get("/api/explore/entity/白云山/enhanced")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None

    def test_entity_nearby(self, client):
        resp = client.get("/api/explore/entity/白云山/nearby")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nearby" in data
        assert "entity" in data

    def test_entity_context(self, client):
        resp = client.get("/api/explore/entity/白云山/context")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None

    def test_entity_not_found(self, client):
        resp = client.get("/api/explore/entity/完全_不_存在的实体_9999/enhanced")
        assert resp.status_code == 404
