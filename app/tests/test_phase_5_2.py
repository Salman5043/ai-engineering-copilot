from pathlib import Path

from app.evaluation.dataset_loader import (
    load_retrieval_dataset,
)
from app.evaluation.retrieval_adapter import (
    real_repository_retriever,
)
from app.evaluation.runner import (
    EvaluationRunner,
)


def test_load_retrieval_dataset(
    tmp_path: Path,
):
    dataset = tmp_path / "benchmark.json"

    dataset.write_text(
        """
        {
          "name": "test",
          "version": "1.0",
          "cases": [
            {
              "case_id": "case_001",
              "repository_id": "demo",
              "query": "Where is example?",
              "expected_intent": "symbol_lookup",
              "expected_evidence": [
                {
                  "file": "app/example.py",
                  "keywords": [
                    "example"
                  ]
                }
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    cases = load_retrieval_dataset(
        dataset
    )

    assert len(cases) == 1

    case = cases[0]

    assert case.case_id == "case_001"
    assert case.repository_id == "demo"
    assert case.expected_intent == (
        "symbol_lookup"
    )

    assert (
        case.expected_evidence[0].file
        == "app/example.py"
    )


def test_real_retriever_adapter(
    monkeypatch,
):
    class FakeResult:
        def model_dump(self):
            return {
                "file": "app/example.py",
                "content": "def example():",
                "start_line": 1,
                "end_line": 2,
                "symbol": "example",
            }

    class FakeResponse:
        results = [
            FakeResult()
        ]

    def fake_retrieve(
        repository_id,
        query,
        top_k,
    ):
        assert repository_id == "demo"
        assert query == "Where is example?"
        assert top_k == 10

        return FakeResponse()

    monkeypatch.setattr(
        "app.evaluation.retrieval_adapter.retrieve",
        fake_retrieve,
    )

    results = real_repository_retriever(
        "demo",
        "Where is example?",
    )

    assert len(results) == 1
    assert (
        results[0]["file"]
        == "app/example.py"
    )


def test_real_retrieval_benchmark_runner(
    monkeypatch,
):
    def fake_retrieve(
        repository_id,
        query,
        top_k,
    ):
        return [
            {
                "file": "app/example.py",
                "content": (
                    "def example():"
                ),
                "symbol": "example",
            }
        ]

    monkeypatch.setattr(
        "app.evaluation.retrieval_adapter.retrieve",
        fake_retrieve,
    )

    from app.evaluation.models import (
        EvaluationCase,
        EvaluationTask,
        ExpectedEvidence,
    )

    case = EvaluationCase(
        case_id="real_001",
        task=EvaluationTask.RETRIEVAL,
        repository_id="demo",
        query="Where is example?",
        expected_evidence=(
            ExpectedEvidence(
                file="app/example.py",
                keywords=(
                    "example",
                ),
            ),
        ),
    )

    runner = EvaluationRunner(
        real_repository_retriever,
        top_k=5,
    )

    result = runner.evaluate_case(
        case
    )

    assert result.passed
    assert result.metrics[
        "hit_at_k"
    ] == 1.0