from app.retrieval.query_intent import detect_intent
from app.retrieval.query_parser import parse_query
from app.retrieval.retrieval_strategy import get_strategy


def test_symbol_lookup_intent():
    result = detect_intent(
        "Where is UserService defined?"
    )

    assert result.name == "symbol_lookup"


def test_function_explanation_intent():
    result = detect_intent(
        "How does process_order() work?"
    )

    assert result.name == "function_explanation"


def test_reference_search_intent():
    result = detect_intent(
        "Where is process_order() called?"
    )

    assert result.name == "reference_search"


def test_configuration_intent():
    result = detect_intent(
        "Where is the database connection configured?"
    )

    assert result.name == "configuration"


def test_test_discovery_intent():
    result = detect_intent(
        "Where are the tests for authentication?"
    )

    assert result.name == "test_discovery"


def test_dependency_search_intent():
    result = detect_intent(
        "What dependencies does this project use?"
    )

    assert result.name == "dependency_search"


def test_architecture_intent():
    result = detect_intent(
        "How is the application structured?"
    )

    assert result.name == "architecture"


def test_entrypoint_intent():
    result = detect_intent(
        "How does the application start?"
    )

    assert result.name == "entrypoint_discovery"


def test_identifier_extraction():
    result = parse_query(
        "Where is UserService.authenticate() defined?"
    )

    assert "UserService.authenticate" in result.identifiers


def test_snake_case_identifier():
    result = parse_query(
        "How does process_order() work?"
    )

    assert "process_order" in result.identifiers


def test_strategy_exists():
    strategy = get_strategy(
        "symbol_lookup"
    )

    assert strategy.prefer_symbols is True