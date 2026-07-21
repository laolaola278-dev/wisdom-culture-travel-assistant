import pytest
import json


class TestAPIv2:
    """Phase 2 multi-agent + recommendation API tests"""

    def test_v2_qa(self, client):
        resp = client.post("/api/v2/qa", json={
            "question": "白云山有什么历史文化",
            "use_agent": True
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "answer" in data
        assert "routed_agent" in data
        assert "session_id" in data
        assert data["version"] == "2.1"

    def test_v2_qa_empty(self, client):
        resp = client.post("/api/v2/qa", json={"question": ""})
        assert resp.status_code == 400

    def test_v2_qa_no_agent(self, client):
        resp = client.post("/api/v2/qa", json={
            "question": "白云山在哪里",
            "use_agent": False
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["agents_enabled"] is False

    def test_v2_agents(self, client):
        resp = client.get("/api/v2/agents")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "agents" in data
        assert len(data["agents"]) == 4
        ids = [a["id"] for a in data["agents"]]
        assert "culture" in ids
        assert "route" in ids
        assert "nearby" in ids
        assert "general" in ids

    def test_v2_session_create(self, client):
        resp = client.post("/api/v2/session", json={"session_id": "test-session-001"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["session_id"] == "test-session-001"

    def test_v2_session_get(self, client):
        client.post("/api/v2/session", json={"session_id": "test-get-001"})
        resp = client.get("/api/v2/session?session_id=test-get-001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["session_id"] == "test-get-001"

    def test_v2_recommend(self, client):
        client.post("/api/v2/session", json={"session_id": "test-rec-001"})
        resp = client.get("/api/v2/recommend?session_id=test-rec-001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "recommendations" in data

    def test_v2_poi_search_disabled(self, client):
        resp = client.get("/api/v2/poi/search?keywords=白云山")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_v2_poi_nearby_disabled(self, client):
        resp = client.get("/api/v2/poi/nearby?lng=113.29&lat=23.18")
        assert resp.status_code == 400

    def test_v2_weather_disabled(self, client):
        resp = client.get("/api/v2/weather?city=440111")
        assert resp.status_code == 400

    def test_v2_itinerary(self, client):
        resp = client.post("/api/v2/itinerary", json={
            "start": "白云山",
            "days": 2,
            "budget": 500
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "timeline" in data
        assert "days" in data
        assert data["days"] == 2

    def test_v2_itinerary_no_start(self, client):
        resp = client.post("/api/v2/itinerary", json={"days": 1})
        assert resp.status_code == 400
