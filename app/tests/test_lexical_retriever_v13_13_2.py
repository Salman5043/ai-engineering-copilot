"""v13.13.2: preserve v13.12 tokenization with redundant split removed."""
import random
from types import SimpleNamespace
from app.retrieval import lexical_retriever as lr


def test_meaningful_tokens_uses_v13_12_set_path():
    rng = random.Random(13132)
    alphabet = "aAbBcCdDeE0123456789_./:-\\\n\t !@#$%é"
    for value in ("", "HTTPRequest", "XMLParser", "retryConfig", "src/app/retry.py", "A", "aB") + tuple(
        "".join(rng.choices(alphabet, k=rng.randrange(150))) for _ in range(1500)
    ):
        expected = {token for token in lr._tokenise(lr._CAMEL_BOUNDARY.sub(" ", value))
                    if len(token) > 1 and token not in lr._STOPWORDS}
        assert lr._meaningful_tokens(value) == expected


def test_redundant_camel_split_has_no_effect():
    rng = random.Random(131321)
    alphabet = "abAB09_./:- "
    for value in ("HTTPResponse", "retryConfig", "aB", "foo_bar") + tuple(
        "".join(rng.choices(alphabet, k=rng.randrange(80))) for _ in range(1500)
    ):
        assert lr._meaningful_tokens(value) == lr._meaningful_tokens(
            lr._CAMEL_BOUNDARY.sub(" ", value))


def test_prepared_scoring_matches_unprepared():
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
        tokens = (lr._meaningful_tokens(symbol),
                  lr._meaningful_tokens(path.replace("\\", "/")),
                  lr._meaningful_tokens(content))
        assert lr._candidate_score(**args) == lr._candidate_score(**args, prepared_tokens=tokens)
