"""v13.14 synthetic multi-project smoke and isolation checks."""
from app.scripts.evaluate_cross_project_v13_14 import CASES, PROJECTS, evaluate


def test_fixture_covers_distinct_python_project_styles():
    assert len(PROJECTS) >= 5
    assert len(CASES) >= 10
    for project, _, expected in CASES:
        assert expected in {row[0] for row in PROJECTS[project]}


def test_cross_project_lexical_evaluation_has_complete_report():
    report = evaluate(top_k=5)
    assert report["cases"] == len(CASES)
    assert report["isolation_passed"]
    assert set(report["per_project"]) == set(PROJECTS)
    assert all(0 <= row["reciprocal_rank"] <= 1 for row in report["results"])


def test_cross_project_top_k_one_respected():
    report = evaluate(top_k=1)
    assert all(len(row["returned_files"]) <= 1 for row in report["results"])


def test_cross_project_invalid_top_k_rejected():
    import pytest
    with pytest.raises(ValueError, match="positive"):
        evaluate(top_k=0)
