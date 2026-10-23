from types import SimpleNamespace

import pytest

from app.evaluation.runner import EvaluationRunner
from app.evaluation.models import ExpectedEvidence


FILE = "app/changes/failure_investigator.py"
EXPECTED = ExpectedEvidence(file=FILE, keywords=("FailureInvestigator", "investigate"))


def result(file=FILE, symbol="investigate", parent="FailureInvestigator"):
    return {
        "file": file,
        "content": "def investigate(self):\n    return 'evidence'",
        "symbol": symbol,
        "parent_symbol": parent,
        "qualified_symbol": f"{parent}.{symbol}",
    }


def case(intent="symbol_lookup"):
    return SimpleNamespace(
        case_id="v10_case", task="retrieval", repository_id="test_repo",
        query="Where is autonomous failure investigation implemented?",
        expected_evidence=[EXPECTED], expected_intent=intent,
    )


def evaluate(results, intent="symbol_lookup"):
    return EvaluationRunner(lambda repo, query, top_k: results, top_k=10).evaluate_case(case(intent))


def test_symbol_method_at_rank_two_passes_while_legacy_fails():
    actual = evaluate([result(file="app/changes/autonomous_fix.py"), result()])
    assert actual.passed
    assert actual.score == pytest.approx(0.75)
    assert actual.metrics["legacy_score"] == 0.0
    assert actual.metrics["legacy_passed"] == 0.0
    assert actual.metrics["strict_evidence_hit_at_10"] == 0.0
    assert actual.metrics["symbol_aware_evidence_hit_at_10"] == 1.0


def test_correct_symbol_at_rank_one_scores_higher():
    first = evaluate([result()])
    second = evaluate([result(file="other.py"), result()])
    assert first.score == 1.0
    assert first.score > second.score


@pytest.mark.parametrize("bad", [
    result(file="app/changes/other.py"),
    result(symbol="unrelated", parent="OtherClass"),
])
def test_wrong_file_or_unrelated_symbol_fails(bad):
    actual = evaluate([bad])
    assert not actual.passed
    assert actual.score == 0.0


def test_non_symbol_lookup_keeps_legacy_score():
    actual = evaluate([result()], intent="code_search")
    assert actual.score == actual.metrics["legacy_score"]
    assert not actual.passed
