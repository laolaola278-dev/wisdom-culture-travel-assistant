import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_query_basic(session_rag):
    result = session_rag.query("白云山有什么特色")
    assert "answer" in result
    assert "source" in result
    assert result["source"] is not None


def test_query_empty(session_rag):
    result = session_rag.query("")
    assert "answer" in result or "error" in result


def test_keyword_search_fallback(session_rag):
    result = session_rag.query("白云山")
    assert "answer" in result
    assert result.get("source") is not None


def test_deepseek_call(session_rag, mock_deepseek):
    result = session_rag.query("白云山在哪里？")
    assert result["source"] == "hybrid_rag_v2"
    assert "白云" in result["answer"]


def test_hot_questions(session_rag):
    questions = session_rag.get_hot_questions()
    assert isinstance(questions, list)
    assert len(questions) >= 0


def test_related_entities_in_result(session_rag):
    result = session_rag.query("白云山风景名胜区")
    related = result.get("related_entities", [])
    assert isinstance(related, list)


def test_query_with_context(session_rag):
    result = session_rag.query("广州白云区有什么非遗项目")
    assert "answer" in result
    assert len(result["answer"]) > 0


def test_rag_source_tracking(session_rag):
    result = session_rag.query("帽峰山")
    assert "source" in result


def test_query_multiple_times(session_rag):
    for q in ["白云山", "帽峰山", "非遗"]:
        result = session_rag.query(q)
        assert "answer" in result


def test_query_with_special_chars(session_rag):
    result = session_rag.query("  白云山 在哪里？  ")
    assert "answer" in result
