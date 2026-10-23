import pytest

from app.retrieval.query_intent import detect_intent


@pytest.mark.parametrize('query,expected', [
    ('Which component investigates failures automatically?', 'symbol_lookup'),
    ('Locate the repository code search interface.', 'symbol_lookup'),
    ('Which module defines the investigation state schema?', 'symbol_lookup'),
    ('Find the code that compiles the LangGraph workflow.', 'architecture'),
    ('How is the LangGraph state machine assembled?', 'architecture'),
    ('Locate the MCP retry policy configuration.', 'symbol_lookup'),
    ('Find the retrieval pipeline coordinating search strategies.', 'symbol_lookup'),
    ('Where is the LangGraph workflow created?', 'architecture'),
    ('Where are MCP tools registered?', 'symbol_lookup'),
    ('Who calls retrieve?', 'reference_search'),
    ('Where are the tests for the retriever?', 'test_discovery'),
    ('Which dependencies does this package use?', 'dependency_search'),
    ('How does the application start?', 'entrypoint_discovery'),
    ('Where is the database configured?', 'configuration'),
    ('Explain how the retry mechanism works.', 'function_explanation'),
])
def test_v13_2_intent(query, expected):
    assert detect_intent(query).name == expected


def test_empty_query_falls_back():
    assert detect_intent('  ').name == 'general_search'
