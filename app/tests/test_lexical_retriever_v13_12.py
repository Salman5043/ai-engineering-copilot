"""v13.12: optimized token-aligned phrase search retains legacy semantics."""
import random
from types import SimpleNamespace

from app.retrieval import lexical_retriever as lr


def test_optimized_phrase_matches_legacy_edge_cases():
    phrases = ["", "---", "retry", "retry config", "RetryConfig", "a b",
               "http server", "a/b", "API", "123", "foo bar baz"]
    texts = ["", "---", "retry", "retry-config", "RetryConfig", "retry config",
             "retry_config", "retryconfig", "a b", "xa b", "a bx", "a/b",
             "HTTPServer", "http server", "API", "123", "foo bar baz",
             "prefix foo bar baz suffix", "foo-bar-baz", "foobar", "foobarbaz"]
    for phrase in phrases:
        prepared = lr._prepared_phrase(phrase)
        for text in texts:
            assert lr._contains_prepared_phrase(text, prepared) == lr._contains_phrase(text, phrase), (text, phrase)


def test_optimized_phrase_matches_legacy_randomized():
    rng = random.Random(1312)
    vocab = ["retry", "handler", "Config", "file", "API", "parse", "123", "call", "x"]
    separators = [" ", "_", "-", "/", ".", "::", "", "\n", "("]
    for _ in range(2500):
        phrase = rng.choice(separators).join(rng.choices(vocab, k=rng.randint(0, 6)))
        text = rng.choice(separators).join(rng.choices(vocab, k=rng.randint(0, 25)))
        assert lr._contains_prepared_phrase(text, lr._prepared_phrase(phrase)) == lr._contains_phrase(text, phrase), (text, phrase)


def test_candidate_score_preserves_query_phrase_signal():
    query = SimpleNamespace(raw_query="retry configuration", keywords=["retry"],
                            identifiers=[], definition_targets=[])
    args = dict(file_path="src/retry.py", symbol="retry_configuration",
                content="retry configuration is here", parsed_query=query,
                symbol_type="function")
    score, signals = lr._candidate_score(**args)
    assert signals.get("query_phrase") == 0.25
    assert score >= 0.25
