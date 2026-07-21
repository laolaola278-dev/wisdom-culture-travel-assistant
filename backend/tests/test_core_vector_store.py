import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_init_tfidf(session_vector_store_obj):
    stats = session_vector_store_obj.get_stats()
    assert stats['backend'] == 'tfidf'
    assert stats['vector_dimension'] == 256
    assert stats['total_segments'] >= 0


def test_incremental_update(session_vector_store_obj):
    count = session_vector_store_obj.incremental_update([
        {"text": "白云山是广州著名风景区", "metadata": {"source": "test"}},
        {"text": "帽峰山位于白云区太和镇", "metadata": {"source": "test"}},
    ])
    assert count >= 0
    stats = session_vector_store_obj.get_stats()
    assert stats['total_segments'] >= 2


def test_search_basic(session_vector_store_obj):
    session_vector_store_obj.incremental_update([
        {"text": "白云山是广州著名风景区", "metadata": {"source": "test"}},
    ])
    results = session_vector_store_obj.search("白云山", top_k=5)
    assert isinstance(results, list)
    if results:
        assert "segment" in results[0]
        assert "score" in results[0]
        assert "text" in results[0]["segment"]
        assert results[0]["score"] >= 0


def test_search_no_match(session_vector_store_obj):
    results = session_vector_store_obj.search("完全不相关查询xxxxxyyyyyzzzzz", top_k=3)
    assert isinstance(results, list)


def test_persist_load(session_vector_store_obj):
    session_vector_store_obj.incremental_update([
        {"text": "白云山风景区", "metadata": {"source": "p1"}},
    ])
    session_vector_store_obj._save_cache()
    assert os.path.exists(session_vector_store_obj.cache_path)
    from vector_store import VectorStore
    vs2 = VectorStore()
    loaded = vs2.load_cache()
    assert loaded
    assert vs2.get_stats()['total_segments'] >= 1


def test_incremental_update_dedup(session_vector_store_obj):
    text = "重复文档去重测试"
    first = session_vector_store_obj.incremental_update([{"text": text, "metadata": {}}])
    second = session_vector_store_obj.incremental_update([{"text": text, "metadata": {}}])
    assert second == 0


def test_stats_structure(session_vector_store_obj):
    stats = session_vector_store_obj.get_stats()
    assert 'total_segments' in stats
    assert 'vector_dimension' in stats
    assert 'backend' in stats
    assert isinstance(stats['total_segments'], int)


@pytest.mark.timeout(90)
def test_empty_search_empty_corpus():
    from vector_store import VectorStore
    vs = VectorStore()
    results = vs.search("anything", top_k=5)
    assert results == []
