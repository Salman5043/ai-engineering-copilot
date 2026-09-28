from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Evidence:
    """
    Structured repository evidence collected during an investigation.
    """

    evidence_id: str

    content: str

    file: str
    start_line: int | None
    end_line: int | None

    language: str | None
    symbol: str | None
    symbol_type: str | None

    score: float | None
    semantic_score: float | None

    source_tool: str

    repository_id: str


def _safe_int(value: Any) -> int | None:
    """
    Convert a value to int when possible.
    """

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    """
    Convert a value to float when possible.
    """

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def generate_evidence_id(
    repository_id: str,
    file: str,
    start_line: int | None,
    end_line: int | None,
    symbol: str | None,
    content: str,
) -> str:
    """
    Generate a deterministic identifier for evidence.

    The same repository location and content will generate
    the same evidence ID, allowing duplicate evidence to
    be detected across multiple tool calls.
    """

    raw = "|".join(
        [
            repository_id,
            file,
            str(start_line),
            str(end_line),
            symbol or "",
            content.strip(),
        ]
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

    return f"evidence_{digest[:16]}"


def normalize_evidence(
    result: dict[str, Any],
    *,
    repository_id: str,
    source_tool: str,
) -> Evidence:
    """
    Convert a raw search result into structured Evidence.
    """

    content = str(
        result.get("content", "")
    ).strip()

    file = str(
        result.get("file", "")
    )

    start_line = _safe_int(
        result.get("start_line")
    )

    end_line = _safe_int(
        result.get("end_line")
    )

    symbol = result.get("symbol")
    symbol_type = result.get("symbol_type")

    if symbol is not None:
        symbol = str(symbol)

    if symbol_type is not None:
        symbol_type = str(symbol_type)

    language = result.get("language")

    if language is not None:
        language = str(language)

    score = _safe_float(
        result.get("score")
    )

    semantic_score = _safe_float(
        result.get("semantic_score")
    )

    evidence_id = generate_evidence_id(
        repository_id=repository_id,
        file=file,
        start_line=start_line,
        end_line=end_line,
        symbol=symbol,
        content=content,
    )

    return Evidence(
        evidence_id=evidence_id,
        content=content,
        file=file,
        start_line=start_line,
        end_line=end_line,
        language=language,
        symbol=symbol,
        symbol_type=symbol_type,
        score=score,
        semantic_score=semantic_score,
        source_tool=source_tool,
        repository_id=repository_id,
    )


def evidence_to_dict(
    evidence: Evidence,
) -> dict[str, Any]:
    """
    Convert Evidence into a JSON/state-friendly dictionary.
    """

    return asdict(evidence)


def add_evidence(
    evidence_store: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    repository_id: str,
    source_tool: str,
) -> list[dict[str, Any]]:
    """
    Normalize and add search results to the evidence store.

    Duplicate evidence is ignored.
    """

    existing_ids = {
        item.get("evidence_id")
        for item in evidence_store
    }

    for result in results:
        evidence = normalize_evidence(
            result,
            repository_id=repository_id,
            source_tool=source_tool,
        )

        if evidence.evidence_id in existing_ids:
            continue

        evidence_store.append(
            evidence_to_dict(evidence)
        )

        existing_ids.add(
            evidence.evidence_id
        )

    return evidence_store