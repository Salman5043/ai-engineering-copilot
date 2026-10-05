from __future__ import annotations

from typing import Any, Callable

from app.evaluation.metrics import (
    hit_at_k,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)
from app.evaluation.models import (
    EvaluationCase,
    EvaluationReport,
    EvaluationResult,
)


Retriever = Callable[
    [str, str],
    list[dict[str, Any]],
]


class EvaluationRunner:
    """
    Deterministic evaluation runner.

    The retriever is injected so the evaluator
    does not depend directly on one retrieval
    implementation.
    """

    def __init__(
        self,
        retriever: Retriever,
        *,
        top_k: int = 5,
    ) -> None:
        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        self.retriever = retriever
        self.top_k = top_k

    def evaluate_case(
        self,
        case: EvaluationCase,
    ) -> EvaluationResult:
        try:
            results = self.retriever(
                case.repository_id,
                case.query,
            )

            expected = list(
                case.expected_evidence
            )

            if not expected:
                return EvaluationResult(
                    case_id=case.case_id,
                    task=case.task,
                    passed=True,
                    score=1.0,
                    metrics={
                        "hit_at_k": 1.0,
                    },
                )

            hits = [
                hit_at_k(
                    results,
                    item,
                    self.top_k,
                )
                for item in expected
            ]

            hit_score = (
                sum(hits) / len(hits)
            )

            precision = precision_at_k(
                results,
                expected,
                self.top_k,
            )

            recall = recall_at_k(
                results,
                expected,
                self.top_k,
            )

            mrr = mean_reciprocal_rank(
                [
                    (
                        results,
                        expected,
                    )
                ]
            )

            score = (
                hit_score
                + precision
                + recall
                + mrr
            ) / 4

            return EvaluationResult(
                case_id=case.case_id,
                task=case.task,
                passed=score >= 0.5,
                score=score,
                metrics={
                    "hit_at_k": hit_score,
                    "precision_at_k": precision,
                    "recall_at_k": recall,
                    "mrr": mrr,
                },
                expected={
                    "evidence": expected,
                },
                actual={
                    "results": results,
                },
            )

        except Exception as exc:
            return EvaluationResult(
                case_id=case.case_id,
                task=case.task,
                passed=False,
                score=0.0,
                errors=[
                    str(exc)
                ],
            )

    def evaluate(
        self,
        cases: list[EvaluationCase],
    ) -> EvaluationReport:
        results = [
            self.evaluate_case(case)
            for case in cases
        ]

        passed = sum(
            result.passed
            for result in results
        )

        total = len(results)

        overall_score = (
            sum(
                result.score
                for result in results
            )
            / total
            if total
            else 0.0
        )

        return EvaluationReport(
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            overall_score=overall_score,
            results=results,
        )