from types import SimpleNamespace

from app.retrieval.reranker import _delegation_adjustments


INTENT = SimpleNamespace(name="symbol_lookup")
QUERY = SimpleNamespace(
    raw_query="Where is autonomous failure investigation implemented?",
    definition_targets=["autonomous failure investigation"],
    keywords=["autonomous", "failure", "investigation", "implemented"],
)


def candidate(symbol, parent, content):
    return {
        "metadata": {
            "symbol": symbol,
            "parent_symbol": parent,
            "qualified_symbol": f"{parent}.{symbol}" if parent else symbol,
            "language": "python",
        },
        "content": content,
    }


def test_direct_investigator_beats_wrapper_delegation():
    candidates = [
        candidate(
            "investigate_failure", "AutonomousFixVerifier",
            "def investigate_failure(self):\n"
            "    investigator = FailureInvestigator()\n"
            "    return investigator.investigate()\n",
        ),
        candidate(
            "investigate", "FailureInvestigator",
            "def investigate(self):\n    return 'evidence'\n",
        ),
    ]
    scores = _delegation_adjustments(candidates, QUERY, INTENT)
    assert scores[0] < 0
    assert scores[1] > 0


def test_unrelated_helper_is_not_rewarded():
    candidates = [
        candidate(
            "prepare_next_fix", "AutonomousFixVerifier",
            "def prepare_next_fix(self):\n"
            "    helper = FailureFormatter()\n"
            "    return helper.format()\n",
        ),
        candidate(
            "format", "FailureFormatter",
            "def format(self):\n    return 'text'\n",
        ),
    ]
    assert _delegation_adjustments(candidates, QUERY, INTENT) == {}


def test_non_lookup_intent_has_no_adjustments():
    candidates = [
        candidate(
            "investigate_failure", "AutonomousFixVerifier",
            "def investigate_failure(self):\n"
            "    investigator = FailureInvestigator()\n"
            "    return investigator.investigate()\n",
        ),
        candidate(
            "investigate", "FailureInvestigator",
            "def investigate(self):\n    return 'evidence'\n",
        ),
    ]
    assert _delegation_adjustments(
        candidates, QUERY, SimpleNamespace(name="architecture")
    ) == {}
