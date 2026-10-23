from app.retrieval.query_parser import parse_query


def test_extracts_simple_definition_target():
    parsed = parse_query(
        "Where is retrieve implemented?"
    )

    assert "retrieve" in parsed.definition_targets


def test_extracts_camel_case_definition_target():
    parsed = parse_query(
        "Where is InvestigationState defined?"
    )

    assert "InvestigationState" in parsed.definition_targets


def test_extracts_phrase_definition_target():
    parsed = parse_query(
        "Where is the investigation state defined?"
    )

    assert "investigation state" in parsed.definition_targets