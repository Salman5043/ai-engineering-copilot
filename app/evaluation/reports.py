from __future__ import annotations

from typing import Any

from app.evaluation.models import (
    EvaluationReport,
)


def report_to_dict(
    report: EvaluationReport,
) -> dict[str, Any]:
    return {
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "pass_rate": report.pass_rate,
        "overall_score": report.overall_score,
        "metrics": report.metrics,
        "errors": report.errors,
        "results": [
            {
                "case_id": result.case_id,
                "task": result.task.value,
                "passed": result.passed,
                "score": result.score,
                "metrics": result.metrics,
                "expected": result.expected,
                "actual": result.actual,
                "errors": result.errors,
            }
            for result in report.results
        ],
    }