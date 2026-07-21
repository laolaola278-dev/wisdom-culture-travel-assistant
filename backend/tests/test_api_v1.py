import pytest
import json


class TestAPIv1:
    """v1 backward-compatible API tests"""

    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "knowledge_graph" in data
        assert "vector_store" in data

    def test_qa_post(self, client):
        resp = client.post("/api/qa", json={"question": "白云山有什么特色"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "answer" in data
        assert "source" in data

    def test_qa_post_empty(self, client):
        resp = client.post("/api/qa", json={"question": ""})
        assert resp.status_code == 400

    def test_qa_post_missing_key(self, client):
        resp = client.post("/api/qa", json={})
        assert resp.status_code == 400

    def test_graph_stats(self, client):
        resp = client.get("/api/graph/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_entities" in data
        assert "total_relations" in data

    def test_graph_search(self, client):
        resp = client.get("/api/graph/search?q=白云山")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data

    def test_graph_search_no_q(self, client):
        resp = client.get("/api/graph/search")
        assert resp.status_code == 400

    def test_hot_questions(self, client):
        resp = client.get("/api/hot-questions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "questions" in data
        assert isinstance(data["questions"], list)

    def test_system_stats(self, client):
        resp = client.get("/api/system/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "graph" in data
        assert "vector_store" in data
        assert "data_sync" in data

    def test_data_categories(self, client):
        resp = client.get("/api/data/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "categories" in data
        assert len(data["categories"]) > 0
