from app.retrieval.query_intent import detect_intent


def test_workflow_creation_is_architecture():
    result = detect_intent(
        "Where is the LangGraph workflow created?"
    )

    assert result.name == "architecture"
    assert result.confidence >= 0.9


def test_definition_question_is_symbol_lookup():
    result = detect_intent(
        "Where is InvestigationState defined?"
    )

    assert result.name == "symbol_lookup"


def test_reference_question_is_reference_search():
    result = detect_intent(
        "Where is retrieve called?"
    )

    assert result.name == "reference_search"


def test_generic_where_question_is_not_forced_to_symbol_lookup():
    result = detect_intent(
        "Where does the application start?"
    )

    assert result.name == "entrypoint_discovery"