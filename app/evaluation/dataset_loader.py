from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.evaluation.models import (
    EvaluationCase,
    EvaluationTask,
    ExpectedEvidence,
)


class EvaluationDatasetError(
    RuntimeError
):
    pass


def load_retrieval_dataset(
    path: Path,
) -> list[EvaluationCase]:
    """
    Load retrieval benchmark cases from JSON.
    """

    if not path.exists():
        raise EvaluationDatasetError(
            f"Evaluation dataset not found: {path}"
        )

    try:
        payload: dict[str, Any] = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        raise EvaluationDatasetError(
            f"Invalid evaluation JSON: {path}"
        ) from exc

    raw_cases = payload.get(
        "cases",
        [],
    )

    if not isinstance(raw_cases, list):
        raise EvaluationDatasetError(
            "'cases' must be a list."
        )

    cases: list[EvaluationCase] = []

    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise EvaluationDatasetError(
                "Each benchmark case must be an object."
            )

        raw_evidence = raw.get(
            "expected_evidence",
            [],
        )

        evidence: list[
            ExpectedEvidence
        ] = []

        for item in raw_evidence:
            evidence.append(
                ExpectedEvidence(
                    file=item["file"],
                    symbol=item.get(
                        "symbol"
                    ),
                    start_line=item.get(
                        "start_line"
                    ),
                    end_line=item.get(
                        "end_line"
                    ),
                    keywords=tuple(
                        item.get(
                            "keywords",
                            [],
                        )
                    ),
                )
            )

        cases.append(
            EvaluationCase(
                case_id=raw["case_id"],
                task=EvaluationTask.RETRIEVAL,
                repository_id=raw[
                    "repository_id"
                ],
                query=raw["query"],
                expected_evidence=tuple(
                    evidence
                ),
                expected_intent=raw.get(
                    "expected_intent"
                ),
                metadata=raw.get(
                    "metadata",
                    {},
                ),
            )
        )

    return cases