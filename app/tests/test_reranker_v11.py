"""Regression checks for v11's bounded AST delegation ranking signal."""
from types import SimpleNamespace

from app.retrieval.reranker import _delegation_adjustments


QUERY = SimpleNamespace(
    raw_query="Where is autonomous failure investigation implemented?",
    definition_targets=["autonomous failure investigation"],
    keywords=["autonomous", "failure", "investigation", "implemented"],
)
SYMBOL_LOOKUP = SimpleNamespace(name="symbol_lookup")


def _candidate(symbol, parent, source):
    return {
        "metadata": {
            "language": "python",
            "symbol": symbol,
            "parent_symbol": parent,
            "qualified_symbol": f"{parent}.{symbol}",
        },
        "content": source,
    }


def _pair():
    return [
        _candidate(
            "investigate_failure",
            "AutonomousFixVerifier",
            "def investigate_failure(self):\n"
            "    investigator = FailureInvestigator()\n"
            "    return investigator.investigate()\n",
        ),
        _candidate(
            "investigate",
            "FailureInvestigator",
            "def investigate(self):\n    return 'evidence'\n",
        ),
    ]


def test_v11_verified_delegation_prefers_implementation():
    adjustments = _delegation_adjustments(_pair(), QUERY, SYMBOL_LOOKUP)
    assert adjustments[0] == -0.20
    assert adjustments[1] == 0.40
    # v9 diagnostic gap was approximately 0.067; this pairwise
    # adjustment can overcome that gap without modifying other signals.
    assert adjustments[1] - adjustments[0] > 0.067


def test_v11_no_bonus_without_actual_call():
    candidates = _pair()
    candidates[0]["content"] = (
        "def investigate_failure(self):\n"
        "    investigator = FailureInvestigator()\n"
        "    return investigator\n"
    )
    assert _delegation_adjustments(candidates, QUERY, SYMBOL_LOOKUP) == {}


def test_v11_no_bonus_for_unrelated_callee():
    candidates = _pair()
    candidates[1] = _candidate(
        "write_report", "ReportBuilder",
        "def write_report(self):\n    return 'report'\n",
    )
    assert _delegation_adjustments(candidates, QUERY, SYMBOL_LOOKUP) == {}


def test_v11_no_bonus_for_other_intent():
    assert _delegation_adjustments(
        _pair(), QUERY, SimpleNamespace(name="architecture")
    ) == {}
