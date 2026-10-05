from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EvaluationTask(str, Enum):
    RETRIEVAL = "retrieval"
    INVESTIGATION = "investigation"
    PATCH = "patch"
    END_TO_END = "end_to_end"


@dataclass(frozen=True)
class ExpectedEvidence:
    """
    Expected repository evidence for an evaluation case.
    """

    file: str

    symbol: str | None = None

    start_line: int | None = None

    end_line: int | None = None

    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationCase:
    """
    One deterministic benchmark case.
    """

    case_id: str

    task: EvaluationTask

    query: str

    repository_id: str

    expected_evidence: tuple[
        ExpectedEvidence, ...
    ] = ()

    expected_intent: str | None = None

    expected_tools: tuple[str, ...] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class EvaluationResult:
    """
    Result of evaluating one benchmark case.
    """

    case_id: str

    task: EvaluationTask

    passed: bool

    score: float

    metrics: dict[str, float] = field(
        default_factory=dict
    )

    expected: dict[str, Any] = field(
        default_factory=dict
    )

    actual: dict[str, Any] = field(
        default_factory=dict
    )

    errors: list[str] = field(
        default_factory=list
    )


@dataclass
class EvaluationReport:
    """
    Aggregated evaluation report.
    """

    total_cases: int

    passed_cases: int

    failed_cases: int

    overall_score: float

    results: list[EvaluationResult] = field(
        default_factory=list
    )

    metrics: dict[str, float] = field(
        default_factory=dict
    )

    errors: list[str] = field(
        default_factory=list
    )

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0

        return (
            self.passed_cases
            / self.total_cases
        )