import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_agent_count(agent_orchestrator):
    info = agent_orchestrator.get_agent_info()
    assert len(info) == 4
    ids = [a["id"] for a in info]
    assert "culture" in ids
    assert "route" in ids
    assert "nearby" in ids
    assert "general" in ids


def test_route_culture(agent_orchestrator):
    result = agent_orchestrator.route_query("白云山有什么历史故事？")
    assert result.get("routed_agent") == "culture"


def test_route_culture_feiyi(agent_orchestrator):
    result = agent_orchestrator.route_query("白云区有哪些非物质文化遗产？")
    assert result.get("routed_agent") == "culture"


def test_route_route(agent_orchestrator):
    result = agent_orchestrator.route_query("从白云山到白云湖怎么走？")
    assert result.get("routed_agent") == "route"


def test_route_nearby(agent_orchestrator):
    result = agent_orchestrator.route_query("白云山附近有什么景点？")
    assert result.get("routed_agent") == "nearby"


def test_route_general(agent_orchestrator):
    result = agent_orchestrator.route_query("今天天气怎么样")
    routed = result.get("routed_agent") or result.get("agent")
    assert routed == "general"


def test_routed_agent_has_answer(agent_orchestrator):
    result = agent_orchestrator.route_query("白云山有什么景点")
    assert "answer" in result
    assert len(result["answer"]) > 0


def test_get_agent_info_structure(agent_orchestrator):
    info = agent_orchestrator.get_agent_info()
    for agent in info:
        assert "id" in agent
        assert "name" in agent
        assert "description" in agent
        assert "keywords" in agent
        assert isinstance(agent["keywords"], list)
