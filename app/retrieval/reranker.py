from pathlib import Path

from app.retrieval.query_intent import QueryIntent
from app.retrieval.query_parser import ParsedQuery
from app.retrieval.retrieval_strategy import RetrievalStrategy


TEST_PATTERNS = (
    "/test/",
    "/tests/",
    "\\test\\",
    "\\tests\\",
    "test_",
    "_test.",
    ".test.",
    ".spec.",
    "__tests__",
)

CONFIG_PATTERNS = (
    ".env",
    "config",
    "configuration",
    "settings",
    "application.properties",
    "application.yml",
    "application.yaml",
)

DEPENDENCY_PATTERNS = (
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "cargo.toml",
    "composer.json",
    "gemfile",
)

ENTRYPOINT_NAMES = {
    "main",
    "app",
    "index",
    "server",
    "start",
    "cli",
    "manage",
    "__main__",
    "application",
}


def _normalise(value: str) -> str:
    return value.replace("\\", "/").lower()


def _identifier_match(
    candidate: dict,
    parsed_query: ParsedQuery,
) -> float:
    if not parsed_query.identifiers:
        return 0.0

    content = candidate["content"].lower()
    metadata = candidate["metadata"]

    symbol = str(metadata.get("symbol", "")).lower()
    file_path = str(metadata.get("file", "")).lower()

    score = 0.0

    for identifier in parsed_query.identifiers:
        identifier_lower = identifier.lower()

        if symbol == identifier_lower:
            score += 0.40

        elif identifier_lower in symbol:
            score += 0.25

        if identifier_lower in file_path:
            score += 0.20

        if identifier_lower in content:
            score += 0.10

    return min(score, 0.60)


def _symbol_match(
    candidate: dict,
    strategy: RetrievalStrategy,
) -> float:
    metadata = candidate["metadata"]

    symbol = str(metadata.get("symbol", "")).strip()
    symbol_type = str(metadata.get("symbol_type", "")).strip()

    if not strategy.prefer_symbols:
        return 0.0

    if not symbol:
        return -0.05

    if (
        strategy.preferred_symbol_types
        and symbol_type in strategy.preferred_symbol_types
    ):
        return 0.20

    return 0.10


def _test_match(
    candidate: dict,
    strategy: RetrievalStrategy,
) -> float:
    if not strategy.prefer_tests:
        return 0.0

    file_path = _normalise(
        str(candidate["metadata"].get("file", ""))
    )

    if any(pattern in file_path for pattern in TEST_PATTERNS):
        return 0.30

    return -0.10


def _configuration_match(
    candidate: dict,
    strategy: RetrievalStrategy,
) -> float:
    if not strategy.prefer_configuration:
        return 0.0

    file_path = _normalise(
        str(candidate["metadata"].get("file", ""))
    )

    if any(pattern in file_path for pattern in CONFIG_PATTERNS):
        return 0.25

    return 0.0


def _dependency_match(
    candidate: dict,
    strategy: RetrievalStrategy,
) -> float:
    if not strategy.prefer_dependencies:
        return 0.0

    file_path = _normalise(
        str(candidate["metadata"].get("file", ""))
    )

    if any(pattern in file_path for pattern in DEPENDENCY_PATTERNS):
        return 0.35

    return 0.0


def _entrypoint_match(
    candidate: dict,
    strategy: RetrievalStrategy,
) -> float:
    if not strategy.prefer_entrypoints:
        return 0.0

    file_path = Path(
        str(candidate["metadata"].get("file", ""))
    )

    stem = file_path.stem.lower()

    if stem in ENTRYPOINT_NAMES:
        return 0.30

    symbol = str(
        candidate["metadata"].get("symbol", "")
    ).lower()

    if symbol in ENTRYPOINT_NAMES:
        return 0.20

    return 0.0


def _documentation_match(
    candidate: dict,
    strategy: RetrievalStrategy,
) -> float:
    if not strategy.prefer_documentation:
        return 0.0

    file_path = _normalise(
        str(candidate["metadata"].get("file", ""))
    )

    extension = str(
        candidate["metadata"].get("extension", "")
    ).lower()

    if extension in {".md", ".txt"}:
        return 0.12

    if "/docs/" in file_path or file_path.startswith("docs/"):
        return 0.12

    return 0.0


def rerank(
    candidates: list[dict],
    parsed_query: ParsedQuery,
    intent: QueryIntent,
    strategy: RetrievalStrategy,
) -> list[dict]:
    ranked = []

    for candidate in candidates:
        distance = float(candidate.get("distance", 1.0))

        # Stable cosine-distance conversion.
        semantic_score = 1.0 / (1.0 + max(distance, 0.0))

        identifier_score = _identifier_match(
            candidate,
            parsed_query,
        )

        symbol_score = _symbol_match(
            candidate,
            strategy,
        )

        test_score = _test_match(
            candidate,
            strategy,
        )

        configuration_score = _configuration_match(
            candidate,
            strategy,
        )

        dependency_score = _dependency_match(
            candidate,
            strategy,
        )

        entrypoint_score = _entrypoint_match(
            candidate,
            strategy,
        )

        documentation_score = _documentation_match(
            candidate,
            strategy,
        )

        score = (
            semantic_score
            + identifier_score
            + symbol_score
            + test_score
            + configuration_score
            + dependency_score
            + entrypoint_score
            + documentation_score
        )

        enriched = dict(candidate)
        enriched["score"] = round(score, 6)
        enriched["semantic_score"] = round(
            semantic_score,
            6,
        )

        ranked.append(enriched)

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return ranked