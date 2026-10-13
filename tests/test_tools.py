import pytest
from backend import db, tools


def test_suggest_problem_valid_topics():
    """Verify that suggest_problem returns valid problems for all supported topics and aliases."""
    canonical_topics = [
        "dynamic_programming",
        "graphs",
        "binary_search",
        "trees_and_heaps",
    ]

    for topic in canonical_topics:
        result = tools.suggest_problem(topic)
        assert result["status"] == "success"
        assert result["topic"] == topic
        assert "problem_name" in result
        assert "difficulty" in result
        assert "pattern" in result
        assert "summary" in result
        assert isinstance(result.get("curated_options"), list)

    # Test common topic aliases
    alias_map = {
        "dp": "dynamic_programming",
        "bfs": "graphs",
        "dijkstra": "graphs",
        "binary search": "binary_search",
        "trees": "trees_and_heaps",
        "heap": "trees_and_heaps",
    }

    for alias, expected_canonical in alias_map.items():
        result = tools.suggest_problem(alias)
        assert result["status"] == "success"
        assert result["topic"] == expected_canonical
        assert len(result["problem_name"]) > 0


def test_suggest_problem_handles_unknown_topic_cleanly():
    """Verify that unknown topics and invalid inputs are handled gracefully without raising exceptions."""
    unknown_inputs = [
        "quantum_computing",
        "unrecognized_algo_topic",
        "xyz_unseen_domain",
        "",
        "   ",
    ]

    for topic in unknown_inputs:
        result = tools.suggest_problem(topic)
        assert result["status"] == "success"
        assert "problem_name" in result
        assert "difficulty" in result
        assert "pattern" in result
        assert "summary" in result
        # Ensure it safely defaults to one of the valid curated catalog topics
        assert result["topic"] in tools.CURATED_PROBLEMS


def test_log_submission_writes_to_sqlite(temp_db):
    """Verify that log_submission inserts a new record into the SQLite submissions table."""
    problem_name = "Course Schedule"
    topic = "graphs"
    verdict = "Accepted"

    # Call log_submission tool
    result = tools.log_submission(problem=problem_name, topic=topic, verdict=verdict)

    assert result["status"] == "success"
    assert "id" in result
    assert result["problem"] == problem_name
    assert result["topic"] == "graphs"
    assert result["verdict"] == "Accepted"

    # Verify directly in SQLite database
    submissions = db.list_submissions(limit=10)
    assert len(submissions) >= 1
    matching = [s for s in submissions if s["id"] == result["id"]]
    assert len(matching) == 1

    saved = matching[0]
    assert saved["problem"] == problem_name
    assert saved["topic"] == "graphs"
    assert saved["verdict"] == "Accepted"
    assert "created_at" in saved
