from __future__ import annotations

import inspect
from time import perf_counter
from typing import Any, Callable

from app.evaluation.metrics import (
    file_hit_at_k,
    file_reciprocal_rank_at_k,
    hit_at_k,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
    strict_evidence_hit_at_k,
    symbol_aware_evidence_hit_at_k,
    symbol_aware_evidence_matches,
)
from app.evaluation.models import EvaluationCase, EvaluationReport, EvaluationResult

Retriever = Callable[..., list[dict[str, Any]]]


def symbol_aware_reciprocal_rank_at_k(
    results: list[dict[str, Any]], expected: list[Any], k: int,
) -> float:
    """Average reciprocal rank of the first matching result per expected item."""
    if not expected or k <= 0:
        return 0.0
    ranks = []
    for item in expected:
        rank = next(
            (i for i, result in enumerate(results[:k], 1)
             if symbol_aware_evidence_matches(item, result)),
            None,
        )
        ranks.append(1.0 / rank if rank is not None else 0.0)
    return sum(ranks) / len(ranks)


class EvaluationRunner:
    """v10: preserve legacy strict metrics; score symbol lookups structurally."""

    def __init__(self, retriever: Retriever, *, top_k: int = 5) -> None:
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        self.retriever = retriever
        self.top_k = top_k
        try:
            params = inspect.signature(retriever).parameters
            self._supports_top_k = "top_k" in params or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
            )
        except (TypeError, ValueError):
            self._supports_top_k = False

    def _retrieve(self, case: EvaluationCase) -> list[dict[str, Any]]:
        if self._supports_top_k:
            return self.retriever(case.repository_id, case.query, top_k=self.top_k)
        return self.retriever(case.repository_id, case.query)

    def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        start = perf_counter()
        try:
            results = self._retrieve(case)
            latency_ms = (perf_counter() - start) * 1000.0
            expected = list(case.expected_evidence)
            actual_intent = getattr(results, "intent", None)
            if actual_intent is not None and not isinstance(actual_intent, str):
                actual_intent = str(getattr(actual_intent, "name", actual_intent))
            expected_intent = case.expected_intent
            intent_accuracy = (
                float(actual_intent == expected_intent)
                if expected_intent is not None and actual_intent is not None
                else None
            )

            if not expected:
                metrics = {
                    "hit_at_k": 1.0, "legacy_score": 1.0,
                    "legacy_passed": 1.0, "v10_score": 1.0,
                    "symbol_aware_mrr_at_k": 1.0, "latency_ms": latency_ms,
                }
                if intent_accuracy is not None:
                    metrics["intent_accuracy"] = intent_accuracy
                return EvaluationResult(
                    case_id=case.case_id, task=case.task, passed=True,
                    score=1.0, metrics=metrics,
                    expected={"evidence": expected, "intent": expected_intent},
                    actual={"results": results, "intent": actual_intent},
                )

            hit_score = sum(hit_at_k(results, item, self.top_k) for item in expected) / len(expected)
            precision = precision_at_k(results, expected, self.top_k)
            recall = recall_at_k(results, expected, self.top_k)
            mrr = mean_reciprocal_rank([(results[:self.top_k], expected)])
            legacy_score = (hit_score + precision + recall + mrr) / 4

            structural_hit = symbol_aware_evidence_hit_at_k(results, expected, self.top_k)
            structural_mrr = symbol_aware_reciprocal_rank_at_k(results, expected, self.top_k)
            # Rank-sensitive score: rank 1 -> 1.0; rank 2 -> 0.75.
            # Both metrics require matching expected file and symbol evidence.
            v10_score = (
                (structural_hit + structural_mrr) / 2
                if expected_intent == "symbol_lookup" else legacy_score
            )

            metrics = {
                "hit_at_k": hit_score,
                "precision_at_k": precision,
                "recall_at_k": recall,
                "mrr": mrr,
                "legacy_score": legacy_score,
                "legacy_passed": float(legacy_score >= 0.5),
                "v10_score": v10_score,
                "symbol_aware_mrr_at_k": structural_mrr,
                "symbol_aware_evidence_hit_at_k": structural_hit,
                "file_hit_at_1": file_hit_at_k(results, expected, 1),
                "file_hit_at_5": file_hit_at_k(results, expected, 5),
                "file_hit_at_10": file_hit_at_k(results, expected, 10),
                "strict_evidence_hit_at_10": strict_evidence_hit_at_k(results, expected, 10),
                "file_mrr_at_10": file_reciprocal_rank_at_k(results, expected, 10),
                "latency_ms": latency_ms,
                "symbol_aware_evidence_hit_at_10": symbol_aware_evidence_hit_at_k(results, expected, 10),
            }
            if intent_accuracy is not None:
                metrics["intent_accuracy"] = intent_accuracy

            return EvaluationResult(
                case_id=case.case_id, task=case.task,
                passed=v10_score >= 0.5, score=v10_score, metrics=metrics,
                expected={"evidence": expected, "intent": expected_intent},
                actual={"results": results, "intent": actual_intent},
            )
        except Exception as exc:
            return EvaluationResult(
                case_id=case.case_id, task=case.task, passed=False,
                score=0.0, errors=[str(exc)],
                metrics={"latency_ms": (perf_counter() - start) * 1000.0},
            )

    def evaluate(self, cases: list[EvaluationCase]) -> EvaluationReport:
        results = [self.evaluate_case(case) for case in cases]
        total = len(results)
        passed = sum(1 for result in results if result.passed)
        overall_score = sum(result.score for result in results) / total if total else 0.0
        metric_names = (
            "hit_at_k", "precision_at_k", "recall_at_k", "mrr",
            "legacy_score", "legacy_passed", "v10_score",
            "symbol_aware_mrr_at_k", "symbol_aware_evidence_hit_at_k",
            "file_hit_at_1", "file_hit_at_5", "file_hit_at_10",
            "strict_evidence_hit_at_10", "symbol_aware_evidence_hit_at_10",
            "file_mrr_at_10", "intent_accuracy", "latency_ms",
        )
        aggregate_metrics: dict[str, float] = {}
        for name in metric_names:
            values = [result.metrics[name] for result in results if name in result.metrics]
            aggregate_metrics[name] = sum(values) / len(values) if values else 0.0
        return EvaluationReport(
            total_cases=total, passed_cases=passed,
            failed_cases=total - passed, overall_score=overall_score,
            results=results, metrics=aggregate_metrics,
        )
