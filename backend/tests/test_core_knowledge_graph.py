import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def first_entity(kg):
    results = kg.search_entities("白云山", top_k=1)
    if not results:
        pytest.skip("KG 中未找到匹配实体")
    return results[0][0]


def test_load_graph(kg):
    assert kg.graph.number_of_nodes() > 0
    assert kg.graph.number_of_edges() > 0


def test_search_entities(kg):
    results = kg.search_entities("白云山", top_k=5)
    assert len(results) > 0
    assert len(results[0]) == 2
    name, score = results[0]
    assert score >= 0


def test_search_top_k(kg):
    results = kg.search_entities("白云山", top_k=3)
    assert len(results) <= 3


def test_search_no_match(kg):
    results = kg.search_entities("不存在_实体_xxxxx", top_k=5)
    assert results == []


def test_get_entity_details(kg, first_entity):
    details = kg.get_entity_details(first_entity)
    assert details is not None
    assert "entity" in details
    assert "type" in details
    assert "relations" in details


def test_get_entity_missing(kg):
    details = kg.get_entity_details("完全_不存在_666")
    assert details is None


def test_get_subgraph(kg, first_entity):
    sub = kg.get_subgraph(first_entity, depth=1)
    assert isinstance(sub, list)
    assert len(sub) >= 1
    if sub:
        assert "head" in sub[0]
        assert "relation" in sub[0]
        assert "tail" in sub[0]


def test_get_subgraph_via_search(kg):
    results = kg.search_entities("帽峰山", top_k=1)
    if results:
        sub = kg.get_subgraph(results[0][0], depth=1)
        assert isinstance(sub, list)


def test_get_all_entities_by_type(kg):
    entities = kg.get_all_entities_by_type("景点")
    assert isinstance(entities, list)
    if entities:
        assert "name" in entities[0]
        assert "relations" in entities[0]


def test_get_graph_stats(kg):
    stats = kg.get_graph_stats()
    assert "total_entities" in stats
    assert "total_relations" in stats
    assert "entity_types" in stats
    assert stats["total_entities"] > 0
    assert stats["total_relations"] > 0
