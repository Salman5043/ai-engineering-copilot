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

def symbol_aware_evidence_matches(
    expected,
    actual: dict,
) -> bool:
    """
    Match expected evidence using content and
    structured symbol metadata.

    Preserve strict file matching.
    """

    if not path_matches(
        expected.file,
        actual.get("file", ""),
    ):
        return False

    metadata = actual.get("metadata") or {}

    symbol = (
        actual.get("symbol")
        or metadata.get("symbol")
        or ""
    )

    parent_symbol = (
        actual.get("parent_symbol")
        or metadata.get("parent_symbol")
        or ""
    )

    qualified_symbol = (
        actual.get("qualified_symbol")
        or metadata.get("qualified_symbol")
        or ""
    )

    content = str(actual.get("content") or "")

    searchable = " ".join(
        [
            content,
            str(symbol),
            str(parent_symbol),
            str(qualified_symbol),
        ]
    ).lower()

    if expected.symbol:
        expected_symbol = expected.symbol.lower()

        if expected_symbol not in {
            str(symbol).lower(),
            str(qualified_symbol).lower(),
        }:
            return False

    return all(
        keyword.lower() in searchable
        for keyword in expected.keywords
    )

def symbol_aware_evidence_hit_at_k(
    results,
    expected,
    k: int,
) -> float:
    if not expected:
        return 1.0

    top_results = results[:k]

    matched = sum(
        any(
            symbol_aware_evidence_matches(item, result)
            for result in top_results
        )
        for item in expected
    )

    return matched / len(expected)

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

# Evaluation Framework v2: file-level relevance (independent of chunk text).
def file_matches(actual: dict[str, Any], expected: ExpectedEvidence) -> bool:
    """Return True when a result belongs to the expected source file."""
    return path_matches(str(actual.get("file", "")), expected.file)


def file_hit_at_k(
    results: list[dict[str, Any]],
    expected: list[ExpectedEvidence],
    k: int,
) -> float:
    """Fraction of expected files represented within the first k results."""
    if not expected:
        return 1.0
    if k <= 0:
        return 0.0
    return sum(
        any(file_matches(result, item) for result in results[:k])
        for item in expected
    ) / len(expected)


def strict_evidence_hit_at_k(
    results: list[dict[str, Any]],
    expected: list[ExpectedEvidence],
    k: int,
) -> float:
    """Fraction of expected evidence entries fully matched within top k."""
    if not expected:
        return 1.0
    if k <= 0:
        return 0.0
    return sum(hit_at_k(results, item, k) for item in expected) / len(expected)


def file_reciprocal_rank_at_k(
    results: list[dict[str, Any]],
    expected: list[ExpectedEvidence],
    k: int,
) -> float:
    """Reciprocal rank of first file-level match in top k."""
    if k <= 0 or not expected:
        return 0.0
    for rank, result in enumerate(results[:k], start=1):
        if any(file_matches(result, item) for item in expected):
            return 1.0 / rank
    return 0.0
