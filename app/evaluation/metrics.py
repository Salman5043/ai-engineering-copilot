from __future__ import annotations

from typing import Any

from app.evaluation.models import (
    ExpectedEvidence,
)


def normalize_path(path: str) -> str:
    return (
        path
        .replace("\\", "/")
        .strip("/")
        .lower()
    )


def path_matches(
    actual_path: str,
    expected_path: str,
) -> bool:
    actual = normalize_path(actual_path)
    expected = normalize_path(expected_path)

    return (
        actual == expected
        or actual.endswith(f"/{expected}")
    )


def evidence_matches(
    actual: dict[str, Any],
    expected: ExpectedEvidence,
) -> bool:
    actual_file = str(
        actual.get("file", "")
    )

    if not path_matches(
        actual_file,
        expected.file,
    ):
        return False

    if expected.symbol:
        actual_symbol = str(
            actual.get("symbol", "")
        )

        if (
            actual_symbol.lower()
            != expected.symbol.lower()
        ):
            return False

    content = str(
        actual.get("content", "")
    ).lower()

    for keyword in expected.keywords:
        if keyword.lower() not in content:
            return False

    return True


def hit_at_k(
    results: list[dict[str, Any]],
    expected: ExpectedEvidence,
    k: int,
) -> float:
    if k <= 0:
        return 0.0

    candidates = results[:k]

    return float(
        any(
            evidence_matches(
                result,
                expected,
            )
            for result in candidates
        )
    )


def precision_at_k(
    results: list[dict[str, Any]],
    expected: list[ExpectedEvidence],
    k: int,
) -> float:
    if k <= 0:
        return 0.0

    candidates = results[:k]

    if not candidates:
        return 0.0

    relevant = 0

    for result in candidates:
        if any(
            evidence_matches(
                result,
                item,
            )
            for item in expected
        ):
            relevant += 1

    return relevant / len(candidates)


def recall_at_k(
    results: list[dict[str, Any]],
    expected: list[ExpectedEvidence],
    k: int,
) -> float:
    if not expected:
        return 1.0

    candidates = results[:k]

    found = 0

    for item in expected:
        if any(
            evidence_matches(
                result,
                item,
            )
            for result in candidates
        ):
            found += 1

    return found / len(expected)


def reciprocal_rank(
    results: list[dict[str, Any]],
    expected: list[ExpectedEvidence],
) -> float:
    for index, result in enumerate(
        results,
        start=1,
    ):
        if any(
            evidence_matches(
                result,
                item,
            )
            for item in expected
        ):
            return 1.0 / index

    return 0.0


def mean_reciprocal_rank(
    result_sets: list[
        tuple[
            list[dict[str, Any]],
            list[ExpectedEvidence],
        ]
    ],
) -> float:
    if not result_sets:
        return 0.0

    scores = [
        reciprocal_rank(
            results,
            expected,
        )
        for results, expected in result_sets
    ]

    return sum(scores) / len(scores)