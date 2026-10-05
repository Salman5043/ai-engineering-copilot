from app.evaluation.metrics import (
    hit_at_k,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)
from app.evaluation.models import (
    EvaluationCase,
    EvaluationTask,
    ExpectedEvidence,
)
from app.evaluation.runner import (
    EvaluationRunner,
)


def test_hit_at_k():
    results = [
        {
            "file": "app/wrong.py",
            "content": "wrong",
        },
        {
            "file": "app/example.py",
            "content": "def example():",
        },
    ]

    expected = ExpectedEvidence(
        file="app/example.py",
        keywords=("example",),
    )

    assert hit_at_k(
        results,
        expected,
        2,
    ) == 1.0

    assert hit_at_k(
        results,
        expected,
        1,
    ) == 0.0


def test_precision_at_k():
    results = [
        {
            "file": "app/example.py",
            "content": "example",
        },
        {
            "file": "app/other.py",
            "content": "other",
        },
    ]

    expected = [
        ExpectedEvidence(
            file="app/example.py",
            keywords=("example",),
        )
    ]

    assert precision_at_k(
        results,
        expected,
        2,
    ) == 0.5


def test_recall_at_k():
    results = [
        {
            "file": "app/example.py",
            "content": "example",
        },
        {
            "file": "app/service.py",
            "content": "service",
        },
    ]

    expected = [
        ExpectedEvidence(
            file="app/example.py",
            keywords=("example",),
        ),
        ExpectedEvidence(
            file="app/service.py",
            keywords=("service",),
        ),
    ]

    assert recall_at_k(
        results,
        expected,
        2,
    ) == 1.0


def test_mrr():
    results = [
        {
            "file": "app/wrong.py",
            "content": "wrong",
        },
        {
            "file": "app/example.py",
            "content": "example",
        },
    ]

    expected = [
        ExpectedEvidence(
            file="app/example.py",
            keywords=("example",),
        )
    ]

    assert mean_reciprocal_rank(
        [
            (
                results,
                expected,
            )
        ]
    ) == 0.5


def test_evaluation_runner():
    def fake_retriever(
        repository_id: str,
        query: str,
    ):
        return [
            {
                "file": "app/example.py",
                "content": (
                    "def example():"
                ),
            }
        ]

    case = EvaluationCase(
        case_id="test_001",
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
        fake_retriever,
        top_k=5,
    )

    result = runner.evaluate_case(case)

    assert result.passed
    assert result.score > 0
    assert result.metrics["hit_at_k"] == 1.0


def test_evaluation_report():
    def fake_retriever(
        repository_id: str,
        query: str,
    ):
        return [
            {
                "file": "app/example.py",
                "content": "example",
            }
        ]

    cases = [
        EvaluationCase(
            case_id="test_001",
            task=EvaluationTask.RETRIEVAL,
            repository_id="demo",
            query="example",
            expected_evidence=(
                ExpectedEvidence(
                    file="app/example.py",
                    keywords=("example",),
                ),
            ),
        )
    ]

    runner = EvaluationRunner(
        fake_retriever
    )

    report = runner.evaluate(cases)

    assert report.total_cases == 1
    assert report.passed_cases == 1
    assert report.failed_cases == 0
    assert report.pass_rate == 1.0