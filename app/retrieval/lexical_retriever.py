
from __future__ import annotations

import re
import json
import os
import time
from pathlib import Path
from collections import Counter
from math import log
from typing import Any

from app.retrieval.query_parser import ParsedQuery
from app.retrieval.vector_store import get_collection


# ---------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "where", "which", "what", "who", "how", "when",
    "in", "on", "at", "to", "for", "of", "and", "or",
    "by", "with", "from", "be", "been", "being", "does",
    "do", "did", "this", "that", "it", "me", "show",
    "find", "tell", "please", "can", "could", "would",
}


def _normalise(value: str) -> str:
    """Normalize text while preserving common code separators."""
    return re.sub(r"[^a-zA-Z0-9_./:-]+", " ", value).strip().lower()


def _tokenise(value: str) -> set[str]:
    """Return lowercase alphanumeric tokens."""
    return {
        token.lower()
        for token in _TOKEN_PATTERN.findall(value)
        if token
    }


def _ordered_tokens(value: str) -> list[str]:
    """Tokenize text while retaining token order."""
    return [
        token.lower()
        for token in _TOKEN_PATTERN.findall(value)
        if token
    ]


def _identifier_variants(value: str) -> set[str]:
    """Generate generic variants of identifiers and natural language.

    Examples:
        FailureInvestigator -> failureinvestigator, failure, investigator
        repository-aware    -> repository, aware, repositoryaware
        my_function         -> my, function, myfunction
    """
    if not value:
        return set()

    camel_split = _CAMEL_BOUNDARY.sub(" ", value)
    variants: set[str] = set()

    original_normalized = _normalise(value).lower()
    if original_normalized:
        variants.add(original_normalized)

    compact_tokens = _ordered_tokens(camel_split)

    if compact_tokens:
        variants.update(compact_tokens)
        variants.add("".join(compact_tokens))
        variants.add(" ".join(compact_tokens))
        variants.add("_".join(compact_tokens))

    return variants


def _phrase_forms(value: str) -> set[str]:
    """Generate comparable phrase forms across naming conventions."""
    if not value:
        return set()

    tokens = _ordered_tokens(
        _CAMEL_BOUNDARY.sub(" ", value)
    )

    if not tokens:
        return set()

    return {
        " ".join(tokens),
        "_".join(tokens),
        "-".join(tokens),
        "".join(tokens),
    }


def _contains_phrase(text: str, phrase: str) -> bool:
    """Check phrase presence independent of common separators."""
    text_forms = _phrase_forms(text)
    phrase_forms = _phrase_forms(phrase)

    if text_forms & phrase_forms:
        return True

    text_tokens = _ordered_tokens(
        _CAMEL_BOUNDARY.sub(" ", text)
    )
    phrase_tokens = _ordered_tokens(
        _CAMEL_BOUNDARY.sub(" ", phrase)
    )

    if not phrase_tokens or len(phrase_tokens) > len(text_tokens):
        return False

    width = len(phrase_tokens)

    return any(
        text_tokens[index:index + width] == phrase_tokens
        for index in range(len(text_tokens) - width + 1)
    )


def _prepared_phrase(value: str) -> tuple[list[str], set[str]]:
    """Prepare query phrase once, instead of once per candidate field."""
    tokens = _ordered_tokens(_CAMEL_BOUNDARY.sub(" ", value))
    if not tokens:
        return [], set()
    return tokens, {" ".join(tokens), "_".join(tokens), "-".join(tokens), "".join(tokens)}


def _contains_prepared_phrase(text: str, prepared: tuple[list[str], set[str]]) -> bool:
    """Equivalent to _contains_phrase(text, phrase), with a precompiled phrase."""
    phrase_tokens, phrase_forms = prepared
    if not phrase_tokens:
        return False
    text_tokens = _ordered_tokens(_CAMEL_BOUNDARY.sub(" ", text))
    # A whole-field match across naming conventions is either identical
    # token sequences or an identical compact identifier. The four legacy
    # string forms are equivalent to these checks for tokenized input.
    if text_tokens == phrase_tokens:
        return True
    if text_tokens and "".join(text_tokens) in phrase_forms:
        return True
    width = len(phrase_tokens)
    if width > len(text_tokens):
        return False
    # Search token-aligned text, avoiding O(n * width) list-slice comparisons.
    # Surrounding spaces prevent matching inside individual tokens.
    needle = " " + " ".join(phrase_tokens) + " "
    haystack = " " + " ".join(text_tokens) + " "
    return needle in haystack


def _meaningful_tokens(value: str) -> set[str]:
    """Extract searchable tokens without common conversational words."""
    return {
        token
        for token in _tokenise(
            _CAMEL_BOUNDARY.sub(" ", value)
        )
        if len(token) > 1 and token not in _STOPWORDS
    }


# ---------------------------------------------------------------------
# Query interpretation helpers
# ---------------------------------------------------------------------

def _query_values(parsed_query: ParsedQuery, field: str) -> list[str]:
    """Safely retrieve list-like fields from a parsed query."""
    value = getattr(parsed_query, field, None)

    if not value:
        return []

    if isinstance(value, str):
        return [value] if value.strip() else []

    try:
        return [
            str(item)
            for item in value
            if str(item).strip()
        ]
    except TypeError:
        return []


def _is_implementation_query(parsed_query: ParsedQuery) -> bool:
    """Determine whether the user is asking where code is implemented."""
    query = str(
        getattr(parsed_query, "raw_query", "") or ""
    ).lower()

    implementation_phrases = (
        "implemented",
        "implementation",
        "defined",
        "definition",
        "where is",
        "where are",
        "which file",
        "which module",
        "located",
        "written",
        "declared",
    )

    return any(
        phrase in query
        for phrase in implementation_phrases
    )


def _query_terms(parsed_query: ParsedQuery) -> set[str]:
    """Build a generic term set from the parsed query."""
    values = [
        str(getattr(parsed_query, "raw_query", "") or "")
    ]

    for field in ("keywords", "identifiers", "definition_targets"):
        values.extend(_query_values(parsed_query, field))

    terms: set[str] = set()

    for value in values:
        terms.update(_meaningful_tokens(value))

    return terms


# ---------------------------------------------------------------------
# BM25 scoring
# ---------------------------------------------------------------------

def _bm25_scores(
    records: list[dict[str, Any]],
    parsed_query: ParsedQuery,
    *,
    prepared_terms: set[str] | None = None,
    prepared_tokens: list[tuple[set[str], set[str], set[str]]] | None = None,
) -> list[float]:
    """Compute corpus-aware BM25 scores for repository chunks.

    Symbols and paths receive greater term weight than source content.
    Inverse document frequency reduces the influence of common terms.
    No repository-specific symbol or concept mappings are used.
    """
    query_terms = prepared_terms if prepared_terms is not None else _query_terms(parsed_query)

    if not records or not query_terms:
        return [0.0] * len(records)

    indexed_documents: list[dict[str, Any]] = []
    document_frequency: Counter[str] = Counter()
    total_length = 0

    for index, record in enumerate(records):
        if prepared_tokens is not None:
            symbol_tokens, path_tokens, content_tokens = prepared_tokens[index]
        else:
            metadata = record.get("metadata") or {}
            symbol = str(metadata.get("symbol") or "")
            file_path = str(metadata.get("file") or "")
            content = str(record.get("content") or "")
            symbol_tokens = _meaningful_tokens(_CAMEL_BOUNDARY.sub(" ", symbol))
            path_tokens = _meaningful_tokens(_CAMEL_BOUNDARY.sub(" ", file_path))
            content_tokens = _meaningful_tokens(content)

        # Field-aware term frequencies: definitions and paths are
        # generally more discriminative than repeated body text.
        term_frequency: Counter[str] = Counter()

        for token in symbol_tokens:
            term_frequency[token] += 3

        for token in path_tokens:
            term_frequency[token] += 2

        term_frequency.update(content_tokens)

        # Length normalization includes the same field weighting.
        document_length = (
            3 * len(symbol_tokens)
            + 2 * len(path_tokens)
            + len(content_tokens)
        )

        indexed_documents.append({
            "tf": term_frequency,
            "length": document_length,
        })

        document_frequency.update(term_frequency.keys())
        total_length += document_length

    document_count = len(indexed_documents)
    average_length = max(
        total_length / max(document_count, 1),
        1.0,
    )

    k1 = 1.5
    b = 0.75
    scores: list[float] = []

    for document in indexed_documents:
        score = 0.0
        term_frequency = document["tf"]
        document_length = document["length"]

        for term in query_terms:
            tf = term_frequency.get(term, 0)

            if tf <= 0:
                continue

            df = document_frequency.get(term, 0)

            inverse_document_frequency = log(
                1.0
                + (
                    document_count - df + 0.5
                ) / (
                    df + 0.5
                )
            )

            denominator = tf + k1 * (
                1.0
                - b
                + b * document_length / average_length
            )

            score += inverse_document_frequency * (
                tf * (k1 + 1.0) / denominator
            )

        scores.append(score)

    return scores


# ---------------------------------------------------------------------
# Existing code-aware lexical scoring
# ---------------------------------------------------------------------

def _candidate_score(
    *,
    file_path: str,
    symbol: str,
    content: str,
    parsed_query: ParsedQuery,
    symbol_type: str = "",
    prepared_query: dict[str, Any] | None = None,
    prepared_tokens: tuple[set[str], set[str], set[str]] | None = None,
    profile_detail: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    """Score a chunk using generic symbol, path, and content evidence."""
    score = 0.0
    signals: dict[str, float] = {}

    normalized_path = file_path.replace("\\", "/")
    if prepared_tokens is None:
        path_tokens = _meaningful_tokens(normalized_path)
        symbol_tokens = _meaningful_tokens(_CAMEL_BOUNDARY.sub(" ", symbol))
        content_tokens = _meaningful_tokens(content)
    else:
        symbol_tokens, path_tokens, content_tokens = prepared_tokens

    if prepared_query is None:
        query_terms = _query_terms(parsed_query)
        keywords = [_meaningful_tokens(_CAMEL_BOUNDARY.sub(" ", item)) for item in _query_values(parsed_query, "keywords")]
        identifiers = [_meaningful_tokens(_CAMEL_BOUNDARY.sub(" ", item)) for item in _query_values(parsed_query, "identifiers")]
        definition_targets = [_meaningful_tokens(_CAMEL_BOUNDARY.sub(" ", item)) for item in _query_values(parsed_query, "definition_targets")]
        implementation_query = _is_implementation_query(parsed_query)
        raw_query = str(getattr(parsed_query, "raw_query", "") or "").strip()
    else:
        query_terms = prepared_query["terms"]
        keywords = prepared_query["keywords"]
        identifiers = prepared_query["identifiers"]
        definition_targets = prepared_query["definition_targets"]
        implementation_query = prepared_query["implementation"]
        raw_query = prepared_query["raw_query"]
    phrase_matcher = (prepared_query.get("phrase_matcher")
                      if prepared_query is not None else None)
    if phrase_matcher is None and raw_query:
        phrase_matcher = _prepared_phrase(raw_query)

    # -------------------------------------------------------------
    # 1. Explicit identifier matching
    # -------------------------------------------------------------
    identifier_score = 0.0

    for identifier in identifiers:
        variants = identifier

        if not variants:
            continue

        if variants == symbol_tokens and symbol_tokens:
            identifier_score = max(identifier_score, 3.0)
        elif variants and variants.issubset(symbol_tokens):
            identifier_score = max(identifier_score, 2.0)
        elif variants.issubset(path_tokens):
            identifier_score = max(identifier_score, 1.5)
        elif variants & symbol_tokens:
            identifier_score = max(identifier_score, 0.75)

    if identifier_score:
        score += identifier_score
        signals["identifier"] = identifier_score

    # -------------------------------------------------------------
    # 2. Definition-target matching
    # -------------------------------------------------------------
    definition_score = 0.0

    for target in definition_targets:
        target_tokens = target

        if not target_tokens:
            continue

        if symbol_tokens and target_tokens.issubset(symbol_tokens):
            definition_score = max(definition_score, 1.2)
        elif path_tokens and target_tokens.issubset(path_tokens):
            definition_score = max(definition_score, 1.0)
        elif target_tokens & symbol_tokens:
            overlap = len(target_tokens & symbol_tokens)
            definition_score = max(
                definition_score,
                0.95 * overlap / len(target_tokens),
            )
        elif target_tokens & path_tokens:
            overlap = len(target_tokens & path_tokens)
            definition_score = max(
                definition_score,
                0.8 * overlap / len(target_tokens),
            )
        elif target_tokens & content_tokens:
            overlap = len(target_tokens & content_tokens)
            definition_score = max(
                definition_score,
                0.3 * overlap / len(target_tokens),
            )

    if definition_score:
        score += definition_score
        signals["definition_target"] = definition_score

    # -------------------------------------------------------------
    # 3. General concept and term overlap
    # -------------------------------------------------------------
    if query_terms:
        symbol_overlap = query_terms & symbol_tokens
        path_overlap = query_terms & path_tokens
        content_overlap = query_terms & content_tokens

        symbol_score = (
            1.0 * len(symbol_overlap) / len(query_terms)
            if symbol_overlap
            else 0.0
        )
        path_score = min(
            0.70,
            0.25 * len(path_overlap),
        )
        content_score = (
            0.35 * len(content_overlap) / len(query_terms)
            if content_overlap
            else 0.0
        )

        # Symbol matches are most specific, followed by paths,
        # then source-body matches.
        if symbol_score:
            score += symbol_score
            signals["symbol"] = symbol_score

        if path_score:
            score += path_score
            signals["path"] = path_score

        if content_score:
            score += content_score
            signals["content"] = content_score

    # -------------------------------------------------------------
    # 4. Keyword matching
    # -------------------------------------------------------------
    keyword_score = 0.0

    for keyword in keywords:
        variants = keyword

        if not variants:
            continue

        if variants & symbol_tokens:
            keyword_score += 0.25
        elif variants & path_tokens:
            keyword_score += 0.20
        elif variants & content_tokens:
            keyword_score += 0.08

    keyword_score = min(keyword_score, 0.80)

    if keyword_score:
        score += keyword_score
        signals["keyword"] = keyword_score

    _phrase_start = time.perf_counter() if profile_detail is not None else None
    # -------------------------------------------------------------
    # 5. Raw query phrase matching
    # -------------------------------------------------------------
    if raw_query and phrase_matcher and (
        _contains_prepared_phrase(content, phrase_matcher)
        or _contains_prepared_phrase(symbol, phrase_matcher)
        or _contains_prepared_phrase(file_path, phrase_matcher)
    ):
        score += 0.25
        signals["query_phrase"] = 0.25

    if _phrase_start is not None:
        profile_detail["phrase_matching_ms"] = profile_detail.get("phrase_matching_ms", 0.0) + (time.perf_counter() - _phrase_start) * 1000

    # -------------------------------------------------------------
    # 6. Implementation query adjustment
    # -------------------------------------------------------------
    if symbol and symbol_type.lower() in {
        "function",
        "class",
        "method",
    }:
        score += 0.10
        signals["code_symbol"] = 0.10

    if implementation_query:
        path_parts = {
            part.lower()
            for part in normalized_path.split("/")
        }

        # Tests can be useful evidence, but are less likely to be
        # the implementation location for "where is implemented?"
        if any(
            part == "tests"
            or part == "test"
            or part.startswith("test_")
            for part in path_parts
        ):
            penalty = min(score * 0.35, 0.80)
            score -= penalty
            signals["test_file_penalty"] = -penalty

    return max(score, 0.0), signals


# ---------------------------------------------------------------------
# Public lexical search
# ---------------------------------------------------------------------

def lexical_search(
    *,
    repository_id: str,
    parsed_query: ParsedQuery,
    top_k: int = 10,
    language: str | None = None,
    symbol_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search indexed chunks using generic lexical and BM25 ranking.

    The search is restricted to the requested repository and uses
    indexed symbols, paths, and source content. It does not contain
    repository-specific concept-to-symbol mappings.
    """
    if not repository_id:
        raise ValueError("repository_id must not be empty.")

    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    _profile_path = os.getenv("COPILOT_LEXICAL_PROFILE_JSONL")
    _profile_start = time.perf_counter() if _profile_path else None
    _profile_marks = {}
    _detail = {"query_preparation_ms": 0.0, "candidate_tokenization_ms": 0.0, "candidate_score_core_ms": 0.0, "phrase_matching_ms": 0.0}

    def _mark(stage: str) -> None:
        if _profile_start is not None:
            _profile_marks[stage] = time.perf_counter()

    def _emit_profile(candidate_count: int, result_count: int) -> None:
        if _profile_start is None or not _profile_path:
            return
        now = time.perf_counter()
        start = _profile_start
        fetch_end = _profile_marks.get("fetch", start)
        score_end = _profile_marks.get("score", fetch_end)
        bm25_end = _profile_marks.get("bm25", score_end)
        _detail["other_candidate_ms"] = max(0.0, (score_end - fetch_end) * 1000 - sum(_detail.values()))
        record = {
            "repository_id": repository_id,
            "candidate_count": candidate_count,
            "result_count": result_count,
            "collection_get_ms": round((fetch_end - start) * 1000, 3),
            "candidate_scoring_ms": round((score_end - fetch_end) * 1000, 3),
            "candidate_detail_ms": {key: round(value, 3) for key, value in _detail.items()},
            "bm25_ms": round((bm25_end - score_end) * 1000, 3),
            "normalization_sort_ms": round((now - bm25_end) * 1000, 3),
            "total_ms": round((now - start) * 1000, 3),
        }
        try:
            destination = Path(_profile_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record, separators=(",", ":")) + "\n")
        except OSError:
            pass  # Profiling must not break retrieval.

    collection = get_collection()

    raw = collection.get(
        where={"repository_id": repository_id},
        include=["documents", "metadatas"],
    )

    _mark("fetch")

    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []

    candidates: list[dict[str, Any]] = []
    token_rows: list[tuple[set[str], set[str], set[str]]] = []
    def prepared_values(field: str) -> list[set[str]]:
        return [_meaningful_tokens(value)
                for value in _query_values(parsed_query, field)]

    _query_prepare_start = time.perf_counter() if _profile_start is not None else None
    prepared_query = {
        "terms": _query_terms(parsed_query),
        "keywords": prepared_values("keywords"),
        "identifiers": prepared_values("identifiers"),
        "definition_targets": prepared_values("definition_targets"),
        "implementation": _is_implementation_query(parsed_query),
        "raw_query": str(getattr(parsed_query, "raw_query", "") or "").strip(),
        "phrase_matcher": _prepared_phrase(
            str(getattr(parsed_query, "raw_query", "") or "").strip()
        ),
    }

    if _query_prepare_start is not None:
        _detail["query_preparation_ms"] += (time.perf_counter() - _query_prepare_start) * 1000

    for document, metadata in zip(documents, metadatas):
        metadata = metadata or {}

        # Match the same optional filters used by semantic retrieval.
        if language and metadata.get("language") != language:
            continue
        if symbol_type and metadata.get("symbol_type") != symbol_type:
            continue

        symbol = str(metadata.get("symbol", ""))
        file_path = str(metadata.get("file", ""))
        content = str(document or "")
        _token_start = time.perf_counter() if _profile_start is not None else None
        tokens = (
            _meaningful_tokens(symbol),
            _meaningful_tokens(file_path.replace("\\", "/")),
            _meaningful_tokens(content),
        )
        token_rows.append(tokens)
        if _token_start is not None:
            _detail["candidate_tokenization_ms"] += (time.perf_counter() - _token_start) * 1000

        _score_start = time.perf_counter() if _profile_start is not None else None

        score, signals = _candidate_score(
            file_path=str(metadata.get("file", "")),
            symbol=str(metadata.get("symbol", "")),
            content=str(document or ""),
            parsed_query=parsed_query,
            symbol_type=str(metadata.get("symbol_type", "")),
            prepared_query=prepared_query,
            prepared_tokens=tokens,
            profile_detail=_detail if _profile_start is not None else None,
        )

        if _score_start is not None:
            _detail["candidate_score_core_ms"] += (time.perf_counter() - _score_start) * 1000

        candidates.append({
            "content": document,
            "metadata": metadata,
            "lexical_score": score,
            "ranking_signals": {"lexical": signals},
        })

    _detail["candidate_score_core_ms"] = max(0.0, _detail["candidate_score_core_ms"] - _detail["phrase_matching_ms"])
    _mark("score")
    if not candidates:
        _mark("bm25")
        _emit_profile(0, 0)
        return []

    bm25_scores = _bm25_scores(
        candidates, parsed_query, prepared_terms=prepared_query["terms"],
        prepared_tokens=token_rows,
    )

    _mark("bm25")

    max_lexical = max(
        (candidate["lexical_score"] for candidate in candidates),
        default=0.0,
    )
    max_bm25 = max(bm25_scores, default=0.0)

    for candidate, bm25_score in zip(candidates, bm25_scores):
        lexical_normalized = (
            candidate["lexical_score"] / max_lexical
            if max_lexical > 0
            else 0.0
        )

        bm25_normalized = (
            bm25_score / max_bm25
            if max_bm25 > 0
            else 0.0
        )

        combined_score = (
            0.45 * lexical_normalized
            + 0.55 * bm25_normalized
        )

        candidate["bm25_score"] = bm25_score
        candidate["retrieval_score"] = combined_score
        candidate["ranking_signals"]["bm25"] = bm25_score
        candidate["ranking_signals"]["combined"] = combined_score

    candidates = [
        candidate
        for candidate in candidates
        if candidate["retrieval_score"] > 0
    ]

    candidates.sort(
        key=lambda item: (
            item["retrieval_score"],
            item["lexical_score"],
            bool(item["metadata"].get("symbol")),
            str(item["metadata"].get("file", "")),
        ),
        reverse=True,
    )

    results = candidates[:top_k]
    _emit_profile(len(token_rows), len(results))
    return results
