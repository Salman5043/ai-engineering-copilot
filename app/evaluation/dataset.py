from __future__ import annotations

from app.evaluation.models import (
    EvaluationCase,
    EvaluationTask,
    ExpectedEvidence,
)


DEFAULT_EVALUATION_CASES = (
    EvaluationCase(
        case_id="retrieval_symbol_001",
        task=EvaluationTask.RETRIEVAL,
        repository_id="demo",
        query="Where is the main application entrypoint?",
        expected_evidence=(
            ExpectedEvidence(
                file="app/main.py",
                keywords=(
                    "FastAPI",
                    "app",
                ),
            ),
        ),
        expected_intent="entrypoint_discovery",
    ),

    EvaluationCase(
        case_id="retrieval_function_001",
        task=EvaluationTask.RETRIEVAL,
        repository_id="demo",
        query="Where is the repository search function?",
        expected_evidence=(
            ExpectedEvidence(
                file="app/retrieval/retriever.py",
                keywords=(
                    "retrieve",
                ),
            ),
        ),
        expected_intent="symbol_lookup",
    ),

    EvaluationCase(
        case_id="configuration_001",
        task=EvaluationTask.RETRIEVAL,
        repository_id="demo",
        query="Where is the Groq configuration defined?",
        expected_evidence=(
            ExpectedEvidence(
                file="app/config.py",
                keywords=(
                    "groq",
                ),
            ),
        ),
        expected_intent="configuration",
    ),

    EvaluationCase(
        case_id="test_discovery_001",
        task=EvaluationTask.INVESTIGATION,
        repository_id="demo",
        query="Where are the tests for repository search?",
        expected_evidence=(
            ExpectedEvidence(
                file="app/tests",
                keywords=(
                    "test",
                ),
            ),
        ),
        expected_intent="test_discovery",
        expected_tools=(
            "test_search",
        ),
    ),
)


def get_evaluation_cases() -> list[EvaluationCase]:
    """
    Return a copy of the default benchmark dataset.
    """

    return list(
        DEFAULT_EVALUATION_CASES
    )


def get_cases_for_task(
    task: EvaluationTask,
) -> list[EvaluationCase]:
    return [
        case
        for case in DEFAULT_EVALUATION_CASES
        if case.task == task
    ]