import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_plan_route_basic(planner):
    result = planner.plan_route("白云山", None, {})
    assert "route_plan" in result
    assert "waypoints_count" in result
    assert result["waypoints_count"] >= 0


def test_plan_route_with_end(planner):
    result = planner.plan_route("白云山", "帽峰山", {})
    assert "route_plan" in result
    assert result["waypoints_count"] >= 0


def test_plan_route_with_preferences(planner):
    result = planner.plan_route("白云山", None, {"兴趣": ["文化", "历史"]})
    assert "route_plan" in result


def test_nearby_attractions(planner):
    nearby = planner.get_nearby_attractions("白云山", max_distance=3, max_results=10)
    assert isinstance(nearby, list)


def test_get_enhanced_detail(planner):
    detail = planner.get_enhanced_detail("白云山")
    if detail:
        assert "name" in detail or "entity" in detail


def test_get_nearby_empty(planner):
    nearby = planner.get_nearby_attractions("完全_不存在_999", max_distance=3, max_results=5)
    assert isinstance(nearby, list)
