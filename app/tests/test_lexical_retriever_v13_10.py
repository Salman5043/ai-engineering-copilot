"""v13.10: query phrase preparation preserves legacy phrase matching."""
import random
from types import SimpleNamespace

from app.retrieval import lexical_retriever as lr


def test_prepared_phrase_matches_legacy_cases():
    phrases = ["retry", "RetryConfig", "retry config", "retry_config", "retry-config",
               "where is retry implemented", "", "---", "HTTPServer", "A/B"]
    texts = ["", "retry", "RetryConfig", "retry_config", "retry-config",
             "app/retry_config.py", "where is retry implemented?", "HTTP Server", "A/B",
             "def retry_config(): pass", "retry config implemented here"]
    for phrase in phrases:
        prepared = lr._prepared_phrase(phrase)
        for value in texts:
            assert lr._contains_prepared_phrase(value, prepared) == lr._contains_phrase(value, phrase)


def test_prepared_phrase_matches_legacy_randomized():
    rng = random.Random(1310)
    vocabulary = ["retry", "handler", "Config", "file", "API", "parse", "123", "call"]
    separators = [" ", "_", "-", "/", ".", "::"]
    for _ in range(300):
        phrase = rng.choice(separators).join(rng.choices(vocabulary, k=rng.randint(1, 4)))
        value = rng.choice(separators).join(rng.choices(vocabulary, k=rng.randint(1, 10)))
        assert lr._contains_prepared_phrase(value, lr._prepared_phrase(phrase)) == lr._contains_phrase(value, phrase)


def test_candidate_scoring_matches_prepared_phrase_path():
    query = SimpleNamespace(raw_query="Where is RetryConfig implemented?",
                            keywords=["retry"], identifiers=["RetryConfig"],
                            definition_targets=["retry"])
    args = dict(file_path="app/retry_config.py", symbol="RetryConfig",
                content="class RetryConfig: pass", parsed_query=query, symbol_type="class")
    baseline = lr._candidate_score(**args)
    prepared = {
        "terms": lr._query_terms(query),
        "keywords": [lr._meaningful_tokens("retry")],
        "identifiers": [lr._meaningful_tokens("Retry Config")],
        "definition_targets": [lr._meaningful_tokens("retry")],
        "implementation": lr._is_implementation_query(query),
        "raw_query": query.raw_query,
        "phrase_matcher": lr._prepared_phrase(query.raw_query),
    }
    assert lr._candidate_score(**args, prepared_query=prepared) == baseline
