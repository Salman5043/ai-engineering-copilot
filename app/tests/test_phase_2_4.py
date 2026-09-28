from app.agent.evidence import (
    add_evidence,
    generate_evidence_id,
    normalize_evidence,
)
from app.agent.graph import build_investigation_graph

def test_graph_collects_evidence(monkeypatch):
    from app.agent import tools

    def fake_symbol_search(**kwargs):
        return [
            sample_result()
        ]

    monkeypatch.setitem(
        tools.TOOL_REGISTRY,
        "symbol_search",
        fake_symbol_search,
    )

    graph = build_investigation_graph()

    result = graph.invoke(
        {
            "repository_id": "repo_123",
            "query": "Where is build_graph defined?",
        }
    )

    assert result["evidence"]

    assert result["evidence_count"] == len(
        result["evidence"]
    )

    assert (
        result["evidence"][0]["source_tool"]
        == "symbol_search"
    )

def sample_result():
    return {
        "content": "def build_graph():",
        "file": "graph/graph_builder.py",
        "start_line": 8,
        "end_line": 42,
        "language": "python",
        "symbol": "build_graph",
        "symbol_type": "function",
        "score": 0.91,
        "semantic_score": 0.87,
    }


def test_generate_evidence_id_is_deterministic():
    first = generate_evidence_id(
        repository_id="repo_123",
        file="main.py",
        start_line=1,
        end_line=10,
        symbol="main",
        content="def main():",
    )

    second = generate_evidence_id(
        repository_id="repo_123",
        file="main.py",
        start_line=1,
        end_line=10,
        symbol="main",
        content="def main():",
    )

    assert first == second


def test_normalize_evidence():
    evidence = normalize_evidence(
        sample_result(),
        repository_id="repo_123",
        source_tool="symbol_search",
    )

    assert evidence.file == "graph/graph_builder.py"
    assert evidence.start_line == 8
    assert evidence.end_line == 42
    assert evidence.symbol == "build_graph"
    assert evidence.symbol_type == "function"
    assert evidence.source_tool == "symbol_search"
    assert evidence.repository_id == "repo_123"


def test_evidence_id_is_created():
    evidence = normalize_evidence(
        sample_result(),
        repository_id="repo_123",
        source_tool="symbol_search",
    )

    assert evidence.evidence_id
    assert evidence.evidence_id.startswith(
        "evidence_"
    )


def test_add_evidence():
    store = []

    updated = add_evidence(
        store,
        [sample_result()],
        repository_id="repo_123",
        source_tool="symbol_search",
    )

    assert len(updated) == 1
    assert updated[0]["symbol"] == "build_graph"


def test_duplicate_evidence_is_removed():
    store = []

    results = [
        sample_result(),
        sample_result(),
    ]

    updated = add_evidence(
        store,
        results,
        repository_id="repo_123",
        source_tool="symbol_search",
    )

    assert len(updated) == 1


def test_same_code_from_different_tools_is_deduplicated():
    store = []

    add_evidence(
        store,
        [sample_result()],
        repository_id="repo_123",
        source_tool="symbol_search",
    )

    add_evidence(
        store,
        [sample_result()],
        repository_id="repo_123",
        source_tool="repository_search",
    )

    assert len(store) == 1


def test_different_code_creates_different_evidence():
    first = sample_result()

    second = sample_result()
    second["start_line"] = 50
    second["end_line"] = 60
    second["content"] = "def another_function():"

    store = []

    add_evidence(
        store,
        [first, second],
        repository_id="repo_123",
        source_tool="repository_search",
    )

    assert len(store) == 2