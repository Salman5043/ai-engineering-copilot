from app.evaluation.metrics import (
    symbol_aware_evidence_matches,
    symbol_aware_evidence_hit_at_k,
)
from app.evaluation.models import ExpectedEvidence


EXPECTED = ExpectedEvidence(
    file="app/changes/failure_investigator.py",
    keywords=("FailureInvestigator", "investigate"),
)


def make_result(
    *,
    file="app/changes/failure_investigator.py",
    parent="FailureInvestigator",
    symbol="investigate",
):
    return {
        "file": file,
        "symbol": symbol,
        "parent_symbol": parent,
        "qualified_symbol": f"{parent}.{symbol}",
        "content": f"def {symbol}(self): pass",
    }


def test_matching_class_and_method():
    assert symbol_aware_evidence_matches(
        EXPECTED,
        make_result(),
    )


def test_wrong_file():
    assert not symbol_aware_evidence_matches(
        EXPECTED,
        make_result(file="app/changes/other.py"),
    )


def test_wrong_parent_class():
    assert not symbol_aware_evidence_matches(
        EXPECTED,
        make_result(parent="OtherInvestigator"),
    )


def test_wrong_method():
    assert not symbol_aware_evidence_matches(
        EXPECTED,
        make_result(symbol="analyze_failure"),
    )


def test_symbol_aware_hit_at_10():
    results = [
        make_result(parent="OtherInvestigator"),
        make_result(),
    ]

    assert symbol_aware_evidence_hit_at_k(
        results,
        [EXPECTED],
        10,
    ) == 1.0


def test_symbol_aware_miss_at_1():
    results = [
        make_result(parent="OtherInvestigator"),
        make_result(),
    ]

    assert symbol_aware_evidence_hit_at_k(
        results,
        [EXPECTED],
        1,
    ) == 0.0