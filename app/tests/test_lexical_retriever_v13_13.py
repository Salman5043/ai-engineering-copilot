"""v13.13: tokenization and search behavior regression checks."""
import random
import re
from types import SimpleNamespace

from app.retrieval import lexical_retriever as lr


def _legacy_meaningful_tokens(value):
    return {
        token for token in lr._tokenise(lr._CAMEL_BOUNDARY.sub(" ", value))
        if len(token) > 1 and token not in lr._STOPWORDS
    }


def test_tokenization_matches_v13_12_edge_cases():
    for value in (
        "", "A", "API", "HTTPRequest", "retryConfig", "retry_config",
        "src/app/retry.py", "C:\\repo\\source.py", "foo-bar::baz",
        "  café naïve 😀 ", "XMLParser", "123", "a_b", "FOOBar123", "\n\t",
    ):
        assert lr._meaningful_tokens(value) == _legacy_meaningful_tokens(value)


def test_tokenization_matches_v13_12_randomized():
    rng = random.Random(1313)
    alphabet = "aAbBcCdDeE0123456789_./:-\\\n\t !@#$%é"
    for _ in range(4000):
        value = "".join(rng.choices(alphabet, k=rng.randrange(180)))
        assert lr._meaningful_tokens(value) == _legacy_meaningful_tokens(value)


def test_prepared_symbol_tokens_match_v13_12():
    for symbol in ("HTTPRequest", "RetryConfig", "aB", "some_symbol", ""):
        before = _legacy_meaningful_tokens(lr._CAMEL_BOUNDARY.sub(" ", symbol))
        assert lr._meaningful_tokens(symbol) == before


def test_candidate_scoring_with_prepared_tokens_matches_unprepared():
    query = SimpleNamespace(raw_query="Where is RetryConfig implemented?",
                            keywords=["retry"], identifiers=["RetryConfig"],
                            definition_targets=["retry"])
    for symbol, path, content in (
        ("RetryConfig", "app/retry.py", "class RetryConfig: pass"),
        ("other", "tests/test_retry.py", "retry failed"),
        ("", "app/main.py", "unrelated source"),
    ):
        args = dict(file_path=path, symbol=symbol, content=content,
                    parsed_query=query, symbol_type="class")
        baseline = lr._candidate_score(**args)
        tokens = (lr._meaningful_tokens(symbol),
                  lr._meaningful_tokens(path.replace("\\", "/")),
                  lr._meaningful_tokens(content))
        prepared = lr._candidate_score(**args, prepared_tokens=tokens)
        assert baseline == prepared
