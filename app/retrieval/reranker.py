
from pathlib import Path
from functools import lru_cache
import ast
import re
import textwrap

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

DEFINITION_SYMBOL_TYPES = {
    "class",
    "function",
    "async_function",
    "method",
}

REFERENCE_HINTS = (
    "calls",
    "called by",
    "caller",
    "callers",
    "references",
    "reference",
    "usage",
    "usages",
    "used by",
    "used where",
)


def _normalise(value: str) -> str:
    return value.replace("\\", "/").lower()


def _tokenise(value: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-zA-Z_][a-zA-Z0-9_]*",
            value.lower(),
        )
        if len(token) > 1
    }


def _candidate_metadata(candidate: dict) -> dict:
    return candidate.get("metadata") or {}


def _normalise_compact(value: str) -> str:
    """Normalize symbols and phrases for exact comparison."""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _split_identifier(value: str) -> list[str]:
    """Split CamelCase, snake_case, kebab-case, and paths into words."""
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return [
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9]*", value)
    ]


def _word_roots(value: str) -> set[str]:
    """
    Normalize common word forms without an NLP dependency.

    Examples:
        investigation -> investig
        investigator  -> investig
        retrieve      -> retriev
        retriever     -> retriev
        retrieval     -> retriev
        implemented   -> implement
        implementation -> implement
    """
    words = _split_identifier(value)

    roots: set[str] = set()

    for word in words:
        root = word

        # Ordered from more specific suffixes to shorter ones.
        for suffix in (
            "ization",
            "ational",
            "fulness",
            "ousness",
            "iveness",
            "ability",
            "ibility",
            "ations",
            "ators",
            "ator",
            "ation",
            "ition",
            "ments",
            "ment",
            "ness",
            "ingly",
            "edly",
            "ing",
            "ers",
            "er",
            "ed",
            "ies",
            "als",
            "al",
            "es",
            "s",
            "e",
        ):
            if (
                len(root) > len(suffix) + 3
                and root.endswith(suffix)
            ):
                root = root[:-len(suffix)]

                # Handle forms such as "retrieves" and
                # "retrieving" after suffix removal.
                if root.endswith("i") and suffix in {"ies"}:
                    root = root[:-1] + "y"

                break

        roots.add(root)

    # Small, general derivational family for retrieve-related forms.
    # These aliases are limited to common morphological variants.
    if roots & {"retriev", "retrieve", "retrieval"}:
        roots.add("retriev")

    if roots & {"investig", "investigat", "investigation"}:
        roots.add("investig")

    return roots



def _ordered_symbol_phrase_match(
    candidate: dict,
    parsed_query: ParsedQuery,
) -> float:
    """Reward ordered identifier words that occur in a definition target.

    This is an ordered *subsequence* match (not necessarily contiguous).
    Morphological variants match when their root sets intersect.
    """
    targets = getattr(parsed_query, "definition_targets", [])
    if not targets:
        return 0.0

    metadata = _candidate_metadata(candidate)
    symbol = str(metadata.get("symbol", "")).strip()
    symbol_type = str(metadata.get("symbol_type", "")).lower()
    if not symbol or symbol_type not in DEFINITION_SYMBOL_TYPES:
        return 0.0

    symbol_words = _split_identifier(symbol)
    if len(symbol_words) < 2:
        return 0.0

    symbol_roots = [_word_roots(word) for word in symbol_words]
    best_score = 0.0

    for target in targets:
        target_words = _split_identifier(str(target))
        if not target_words:
            continue

        target_roots = [_word_roots(word) for word in target_words]
        position = 0
        for roots in target_roots:
            if (
                position < len(symbol_roots)
                and roots & symbol_roots[position]
            ):
                position += 1

        if position == len(symbol_roots):
            coverage = len(symbol_roots) / len(target_roots)
            best_score = max(best_score, 0.15 + 0.15 * coverage)

    return min(best_score, 0.30)

def _identifier_match(
    candidate: dict,
    parsed_query: ParsedQuery,
) -> float:
    if not parsed_query.identifiers:
        return 0.0

    content = str(candidate.get("content", "")).lower()
    metadata = _candidate_metadata(candidate)

    symbol = str(metadata.get("symbol", "")).lower()
    file_path = str(metadata.get("file", "")).lower()

    score = 0.0

    for identifier in parsed_query.identifiers:
        identifier_lower = identifier.lower()

        if symbol == identifier_lower:
            score += 0.55
        elif identifier_lower in symbol:
            score += 0.30

        if identifier_lower in file_path:
            score += 0.25

        if identifier_lower in content:
            score += 0.08

    return min(score, 0.80)


def _definition_target_match(
    candidate: dict,
    parsed_query: ParsedQuery,
) -> float:
    """
    Rank definition candidates for where/what implementation queries.

    Exact symbol matches are strongest. Path and symbol morphology
    provide deterministic signals; source-content overlap provides
    a weaker signal for natural-language capability descriptions.
    """
    targets = getattr(parsed_query, "definition_targets", [])

    if not targets:
        return 0.0

    metadata = _candidate_metadata(candidate)

    symbol = str(metadata.get("symbol", "")).strip()
    file_path = str(metadata.get("file", "")).strip()
    content = str(candidate.get("content", ""))

    if not symbol and not file_path:
        return 0.0

    symbol_compact = _normalise_compact(symbol)
    file_compact = _normalise_compact(file_path)

    symbol_roots = _word_roots(symbol)
    file_roots = _word_roots(file_path)
    content_roots = _word_roots(content)

    symbol_type = str(
        metadata.get("symbol_type", "")
    ).strip().lower()

    is_definition = symbol_type in DEFINITION_SYMBOL_TYPES
    content_lower = content.lower()

    best_score = 0.0

    for target in targets:
        target = str(target).strip()

        if not target:
            continue

        target_compact = _normalise_compact(target)
        target_roots = _word_roots(target)

        # 1. Exact symbol match.
        if target_compact and target_compact == symbol_compact:
            best_score = max(best_score, 1.20)
            continue

        # 2. Exact target contained in the symbol.
        if (
            target_compact
            and len(target_compact) >= 4
            and target_compact in symbol_compact
        ):
            best_score = max(best_score, 0.85)

        # 3. Exact target represented by the file path.
        if (
            target_compact
            and len(target_compact) >= 4
            and target_compact in file_compact
        ):
            best_score = max(best_score, 0.80)

        # 4. Coverage-aware symbol and path matching.
        if target_roots:
            symbol_overlap = len(target_roots & symbol_roots)
            file_overlap = len(target_roots & file_roots)
            symbol_coverage = symbol_overlap / len(target_roots)
            file_coverage = file_overlap / len(target_roots)

            if symbol_coverage == 1.0:
                best_score = max(best_score, 0.95)
            elif symbol_coverage >= 0.66:
                best_score = max(best_score, 0.70)
            elif symbol_coverage >= 0.50:
                best_score = max(best_score, 0.45)
            elif symbol_overlap > 0:
                best_score = max(best_score, 0.20)

            if file_coverage == 1.0:
                best_score = max(best_score, 0.75)
            elif file_coverage >= 0.66:
                best_score = max(best_score, 0.55)
            elif file_coverage >= 0.50:
                best_score = max(best_score, 0.35)
            elif file_overlap > 0:
                best_score = max(best_score, 0.15)

        # 6. Literal phrase in content is weak because it may be
        # a usage/reference rather than the definition.
        if (
            target_compact
            and len(target_compact) >= 5
            and target.lower() in content_lower
        ):
            best_score = max(best_score, 0.18)

        # 7. Natural-language concept evidence in source code.
        # Multi-word concepts supported by several source terms
        # receive a moderate score, especially for definitions.
        if len(target_roots) >= 2:
            content_overlap = len(target_roots & content_roots)

            if content_overlap >= 2:
                content_ratio = content_overlap / len(target_roots)

                if is_definition:
                    concept_score = 0.40 + (0.15 * content_ratio)
                else:
                    concept_score = 0.15 + (0.10 * content_ratio)

                best_score = max(
                    best_score,
                    min(concept_score, 0.55),
                )

    return min(best_score, 1.20)


def _keyword_overlap(
    candidate: dict,
    parsed_query: ParsedQuery,
) -> float:
    if not parsed_query.keywords:
        return 0.0

    metadata = _candidate_metadata(candidate)

    content = str(candidate.get("content", ""))
    file_path = str(metadata.get("file", ""))
    symbol = str(metadata.get("symbol", ""))

    candidate_tokens = (
        _tokenise(content)
        | _tokenise(file_path)
        | _tokenise(symbol)
    )

    query_tokens = {
        token.lower()
        for token in parsed_query.keywords
        if len(token) > 1
    }

    if not query_tokens:
        return 0.0

    overlap = len(query_tokens & candidate_tokens)
    ratio = overlap / len(query_tokens)

    return min(ratio * 0.30, 0.30)


def _path_relevance(
    candidate: dict,
    parsed_query: ParsedQuery,
) -> float:
    metadata = _candidate_metadata(candidate)

    file_path = _normalise(str(metadata.get("file", "")))
    symbol = str(metadata.get("symbol", "")).lower()

    if not file_path:
        return 0.0

    score = 0.0

    path_tokens = _tokenise(file_path)
    symbol_tokens = _tokenise(symbol)

    for identifier in parsed_query.identifiers:
        identifier_lower = identifier.lower()

        if identifier_lower in path_tokens:
            score += 0.30
        elif identifier_lower in symbol_tokens:
            score += 0.20

    for keyword in parsed_query.keywords:
        keyword_lower = keyword.lower()

        if keyword_lower in path_tokens:
            score += 0.20

    return min(score, 0.60)


def _definition_match(
    candidate: dict,
    strategy: RetrievalStrategy,
) -> float:
    if not strategy.prefer_definitions:
        return 0.0

    metadata = _candidate_metadata(candidate)

    symbol = str(metadata.get("symbol", "")).strip()
    symbol_type = str(
        metadata.get("symbol_type", "")
    ).strip().lower()

    if not symbol:
        return -0.12

    if symbol_type in DEFINITION_SYMBOL_TYPES:
        return 0.30

    return 0.05


def _reference_match(
    candidate: dict,
    parsed_query: ParsedQuery,
    strategy: RetrievalStrategy,
) -> float:
    if not strategy.prefer_references:
        return 0.0

    content = str(candidate.get("content", "")).lower()
    query_text = " ".join(parsed_query.keywords).lower()

    if any(hint in query_text for hint in REFERENCE_HINTS):
        if any(hint in content for hint in REFERENCE_HINTS):
            return 0.25

    return 0.0


def _symbol_match(
    candidate: dict,
    strategy: RetrievalStrategy,
) -> float:
    metadata = _candidate_metadata(candidate)

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
        str(_candidate_metadata(candidate).get("file", ""))
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
        str(_candidate_metadata(candidate).get("file", ""))
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
        str(_candidate_metadata(candidate).get("file", ""))
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
        str(_candidate_metadata(candidate).get("file", ""))
    )

    if file_path.stem.lower() in ENTRYPOINT_NAMES:
        return 0.30

    symbol = str(
        _candidate_metadata(candidate).get("symbol", "")
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

    metadata = _candidate_metadata(candidate)

    file_path = _normalise(str(metadata.get("file", "")))
    extension = str(metadata.get("extension", "")).lower()

    if extension in {".md", ".txt"}:
        return 0.12

    if "/docs/" in file_path or file_path.startswith("docs/"):
        return 0.12

    return 0.0


def _architecture_match(
    candidate: dict,
    parsed_query: ParsedQuery,
    intent: QueryIntent,
) -> float:
    if intent.name != "architecture":
        return 0.0

    metadata = _candidate_metadata(candidate)

    file_path = _normalise(str(metadata.get("file", "")))
    symbol = str(metadata.get("symbol", "")).lower()
    content = str(candidate.get("content", "")).lower()

    score = 0.0

    architecture_terms = (
        "graph",
        "workflow",
        "pipeline",
        "router",
        "orchestr",
        "stategraph",
        "compile",
        "architecture",
        "structure",
    )

    query_text = " ".join(parsed_query.keywords).lower()

    for term in architecture_terms:
        if term in query_text:
            if term in file_path:
                score += 0.18

            if term in symbol:
                score += 0.18

            if term in content:
                score += 0.05

    return min(score, 0.45)


def _reference_penalty(
    candidate: dict,
    parsed_query: ParsedQuery,
    intent: QueryIntent,
) -> float:
    if intent.name != "architecture":
        return 0.0

    if not parsed_query.identifiers:
        return 0.0

    metadata = _candidate_metadata(candidate)

    symbol = str(metadata.get("symbol", "")).strip()
    symbol_type = str(metadata.get("symbol_type", "")).lower()

    if symbol and symbol_type in DEFINITION_SYMBOL_TYPES:
        return 0.0

    content = str(candidate.get("content", "")).lower()

    identifier_found = any(
        identifier.lower() in content
        for identifier in parsed_query.identifiers
    )

    if identifier_found and not symbol:
        return -0.12

    return 0.0


def _definition_reference_penalty(
    candidate: dict,
    parsed_query: ParsedQuery,
) -> float:
    """Penalize non-definition chunks that mention a definition target."""
    targets = getattr(parsed_query, "definition_targets", [])

    if not targets:
        return 0.0

    metadata = _candidate_metadata(candidate)

    symbol = str(metadata.get("symbol", "")).strip()
    symbol_type = str(
        metadata.get("symbol_type", "")
    ).strip().lower()

    if not symbol:
        return 0.0

    if symbol_type in DEFINITION_SYMBOL_TYPES:
        return 0.0

    symbol_compact = _normalise_compact(symbol)

    for target in targets:
        target_compact = _normalise_compact(str(target))

        if target_compact and target_compact == symbol_compact:
            return 0.0

    content = str(candidate.get("content", "")).lower()

    if any(
        str(target).lower() in content
        for target in targets
        if len(str(target)) >= 5
    ):
        return -0.20

    return 0.0


def _structural_symbol_match(
    candidate: dict,
    parsed_query: ParsedQuery,
    intent: QueryIntent,
) -> float:
    """Reward definition targets supported by both parent class and method.

    Only applies to symbol-lookup queries and uses indexed structural metadata.
    """
    if intent.name != "symbol_lookup":
        return 0.0

    targets = getattr(parsed_query, "definition_targets", [])
    if not targets:
        return 0.0

    metadata = _candidate_metadata(candidate)
    parent = str(metadata.get("parent_symbol") or "").strip()
    symbol = str(metadata.get("symbol") or "").strip()
    qualified = str(metadata.get("qualified_symbol") or "").strip()

    if not parent or not symbol:
        return 0.0

    if not qualified:
        qualified = f"{parent}.{symbol}"

    qualified_roots = _word_roots(qualified)
    parent_roots = _word_roots(parent)
    symbol_roots = _word_roots(symbol)

    best = 0.0
    for target in targets:
        target_roots = _word_roots(str(target))
        if not target_roots:
            continue

        # Match both sides of the class.method relationship.
        if not (target_roots & parent_roots and target_roots & symbol_roots):
            continue

        coverage = len(target_roots & qualified_roots) / len(target_roots)
        if coverage >= 0.75:
            best = max(best, 0.20)
        elif coverage >= 0.50:
            best = max(best, 0.10)

    return best




@lru_cache(maxsize=1024)
def _parse_source_definition(content: str):
    """Cache parsed definitions by immutable source text; invalid snippets cache as None.

    AST consumers in this module only read nodes. Cache size bounds memory use.
    """
    try:
        tree = ast.parse(textwrap.dedent(content))
    except (SyntaxError, ValueError, IndentationError, RecursionError):
        return None
    return next(
        (node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))),
        None,
    )


def _source_node(candidate: dict):
    """Read a cached Python AST definition, including indented methods."""
    metadata = _candidate_metadata(candidate)
    if metadata.get("language") not in ("python", "py", None, ""):
        return None
    content = str(candidate.get("content") or candidate.get("text") or "")
    if not content.strip():
        return None
    return _parse_source_definition(content)


def _responsibility_alignment(candidate: dict, parsed_query: ParsedQuery, intent: QueryIntent) -> float:
    """Small, bounded ownership signal from symbols and definition docstrings."""
    if getattr(intent, "name", "") != "symbol_lookup":
        return 0.0
    query = str(getattr(parsed_query, "raw_query", "") or "").lower()
    metadata = _candidate_metadata(candidate)
    symbol = str(metadata.get("qualified_symbol") or metadata.get("symbol") or "")
    node = _source_node(candidate)
    doc = (ast.get_docstring(node) or "") if node is not None else ""
    # Only compare the actual definition documentation, not arbitrary comments
    # or references to another implementation in its body.
    symbol_roots = _word_roots(symbol)
    doc_roots = _word_roots(doc)
    query_roots = _word_roots(" ".join(getattr(parsed_query, "keywords", []) or []))
    if not query_roots:
        return 0.0
    # Prefer an explicit class/function responsibility, but do not let generic
    # documentation or a single identifier overwhelm lexical retrieval.
    doc_overlap = len(query_roots & doc_roots) / len(query_roots)
    symbol_overlap = len(query_roots & symbol_roots) / len(query_roots)
    score = 0.0
    if symbol_overlap >= 0.5 and doc_overlap >= 0.4:
        score += 0.12
    elif doc_overlap >= 0.6:
        score += 0.06
    # A "registered" query is closely related to a registry; this is a
    # language-level derivation, not a repository-specific filename rule.
    if re.search(r"\b(register|registered|registration)\b", query):
        if "registr" in symbol.lower() or "registry" in symbol.lower():
            score += 0.25
    return min(score, 0.37)


def _ownership_evidence(candidate: dict, parsed_query: ParsedQuery, intent: QueryIntent) -> float:
    """Conservative structural evidence of ownership, not a filename whitelist.

    Registration questions favor registry classes; multi-stage implementation
    questions favor functions that actually invoke several named stages.
    """
    if getattr(intent, "name", "") != "symbol_lookup":
        return 0.0
    query = str(getattr(parsed_query, "raw_query", "") or "").lower()
    metadata = _candidate_metadata(candidate)
    symbol = str(metadata.get("symbol") or "")
    symbol_type = str(metadata.get("symbol_type") or "").lower()
    node = _source_node(candidate)
    score = 0.0

    # A registry is an owner of registration/discovery state, whereas a
    # catalog-building helper is not necessarily a runtime registry.
    if re.search(r"\b(?:register|registered|registration)\b", query):
        if symbol_type == "class" and "registry" in _split_identifier(symbol):
            score += 0.07

    # An orchestration implementation must call multiple distinct stages
    # explicitly named by the query. Mentioning them in comments is insufficient.
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        called = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        query_roots = _word_roots(query)
        matches = sum(bool(_word_roots(name) & query_roots) for name in called)
        if matches >= 2:
            score += 0.08
    return min(score, 0.15)


def _delegation_adjustments(
    candidates: list[dict],
    parsed_query: ParsedQuery,
    intent: QueryIntent,
) -> dict[int, float]:
    """Reward a query-relevant callee when a retrieved wrapper invokes it.

    This is intentionally conservative: the callee must match at least two
    distinct content roots (or every root for a one-word concept), and the
    caller must actually instantiate the callee's enclosing class.
    """
    if getattr(intent, "name", "") != "symbol_lookup":
        return {}

    raw_query = str(getattr(parsed_query, "raw_query", "") or "").lower()
    if not re.search(
        r"\b(?:implement(?:ed|ation)?|investigat\w*|perform\w*|defin\w*|where)\b",
        raw_query,
    ):
        return {}

    # Definition phrases are preferable to query keywords because keywords
    # may contain action words such as "implemented".
    targets = getattr(parsed_query, "definition_targets", []) or []
    query_roots = set()
    for target in targets:
        query_roots.update(_word_roots(str(target)))
    if not query_roots:
        query_roots = _word_roots(
            " ".join(getattr(parsed_query, "keywords", []) or [])
        )
    if not query_roots:
        return {}

    indexed: dict[tuple[str, str], list[int]] = {}
    for index, candidate in enumerate(candidates):
        metadata = _candidate_metadata(candidate)
        parent = str(metadata.get("parent_symbol") or "")
        symbol = str(metadata.get("symbol") or "")
        if parent and symbol:
            indexed.setdefault((parent, symbol), []).append(index)

    adjustments: dict[int, float] = {}
    for index, candidate in enumerate(candidates):
        node = _source_node(candidate)
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        constructors: dict[str, str] = {}
        for item in ast.walk(node):
            if not isinstance(item, ast.Assign):
                continue
            call = item.value
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            for assigned in item.targets:
                if isinstance(assigned, ast.Name):
                    constructors[assigned.id] = call.func.id

        for item in ast.walk(node):
            if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Attribute):
                continue
            owner = item.func.value
            if not isinstance(owner, ast.Name):
                continue
            class_name = constructors.get(owner.id)
            if not class_name:
                continue

            for target_index in indexed.get((class_name, item.func.attr), []):
                if target_index == index:
                    continue
                target_meta = _candidate_metadata(candidates[target_index])
                qualified = str(
                    target_meta.get("qualified_symbol")
                    or f"{class_name}.{item.func.attr}"
                )
                # Require substantive concept coverage, not a single generic
                # shared word such as "failure" or "fix".
                matched = len(_word_roots(qualified) & query_roots)
                required = min(2, len(query_roots))
                if matched < required:
                    continue

                # A verified wrapper -> implementation call is stronger
                # ownership evidence than incidental lexical overlap. Keep
                # both adjustments bounded and only apply to the matched pair.
                adjustments[index] = max(
                    -0.20, adjustments.get(index, 0.0) - 0.20
                )
                adjustments[target_index] = min(
                    0.40, adjustments.get(target_index, 0.0) + 0.40
                )

    return adjustments



def _v13_5_structural_ownership(candidate: dict, parsed_query: ParsedQuery, intent: QueryIntent) -> float:
    """Conservative, source-backed owner signal for implementation lookups.

    Uses AST definitions and method names, never repository-specific paths.
    Tests and reference-only snippets cannot earn this bonus.
    """
    if getattr(intent, "name", "") not in {"symbol_lookup", "architecture"}:
        return 0.0
    query = str(getattr(parsed_query, "raw_query", "") or "").lower()
    if not re.search(r"\b(?:where|which|find|implement\w*|defin\w*|locat\w*|orchestrat\w*)\b", query):
        return 0.0
    metadata = _candidate_metadata(candidate)
    path = _normalise(str(metadata.get("file", "")))
    if any(pattern in path for pattern in TEST_PATTERNS):
        return 0.0
    node = _source_node(candidate)
    if node is None:
        return 0.0
    query_roots = _word_roots(" ".join(getattr(parsed_query, "keywords", []) or []))
    if len(query_roots) < 2:
        return 0.0
    doc = ast.get_docstring(node) or ""
    symbol = str(metadata.get("symbol", ""))
    name_overlap = len(_word_roots(symbol) & query_roots)
    doc_overlap = len(_word_roots(doc) & query_roots)
    if isinstance(node, ast.ClassDef):
        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        method_overlap = len(set().union(*(_word_roots(m) for m in methods)) & query_roots) if methods else 0
        if name_overlap >= 1 and method_overlap >= 1 and doc_overlap >= 1:
            return 0.14
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                fn = child.func
                if isinstance(fn, ast.Name):
                    calls.append(fn.id)
                elif isinstance(fn, ast.Attribute):
                    calls.append(fn.attr)
        matching_calls = sum(bool(_word_roots(name) & query_roots) for name in set(calls))
        if name_overlap >= 1 and matching_calls >= 2 and doc_overlap >= 1:
            return 0.12
    return 0.0


def rerank(
    candidates: list[dict],
    parsed_query: ParsedQuery,
    intent: QueryIntent,
    strategy: RetrievalStrategy,
) -> list[dict]:
    ranked = []
    delegation_scores = _delegation_adjustments(candidates, parsed_query, intent)

    raw_query_lower = str(
        getattr(parsed_query, "raw_query", "") or ""
    ).lower()

    # An implementation-location request should prefer production source over
    # test examples quoting that source. Do not apply this to test discovery.
    implementation_query = (
        intent.name in {"symbol_lookup", "architecture", "function_explanation"}
        and bool(re.search(
            r"\b(?:implemented|implementation|defined|definition|"
            r"where\s+(?:is|are)|which\s+(?:file|module|function)|"
            r"locat(?:e|ed)|written|declared|find\s+the\s+(?:code|"
            r"implementation|function|method|class)|orchestrat(?:e|es|ing))\b",
            raw_query_lower,
        ))
    )

    for candidate_index, candidate in enumerate(candidates):
        responsibility_score = _responsibility_alignment(candidate, parsed_query, intent)
        delegation_score = delegation_scores.get(candidate_index, 0.0)
        ownership_score = _ownership_evidence(candidate, parsed_query, intent)
        structural_ownership_score = _v13_5_structural_ownership(candidate, parsed_query, intent)
        # A positive delegation adjustment already rewards a verified callee.
        # Avoid stacking a generic multi-call ownership bonus on that evidence.
        if delegation_score > 0.0:
            structural_ownership_score = 0.0
        distance_value = candidate.get("distance")

        # Lexical-only candidates have no semantic distance.
        if distance_value is None and (
            "retrieval_score" in candidate
            or "lexical_score" in candidate
        ):
            semantic_score = 0.0
        else:
            distance = float(
                1.0 if distance_value is None else distance_value
            )
            semantic_score = 1.0 / (
                1.0 + max(distance, 0.0)
            )

        lexical_retrieval_score = max(
            0.0,
            min(
                float(candidate.get("retrieval_score", 0.0) or 0.0),
                1.0,
            ),
        )
        lexical_score = 0.80 * lexical_retrieval_score

        identifier_score = _identifier_match(
            candidate,
            parsed_query,
        )

        keyword_score = (
            _keyword_overlap(candidate, parsed_query)
            if strategy.prefer_keyword_overlap
            else 0.0
        )

        path_score = (
            _path_relevance(candidate, parsed_query)
            if strategy.prefer_path_relevance
            else 0.0
        )

        symbol_score = _symbol_match(candidate, strategy)
        definition_score = _definition_match(candidate, strategy)

        definition_target_score = _definition_target_match(
            candidate,
            parsed_query,
        )

        ordered_phrase_score = _ordered_symbol_phrase_match(
            candidate,
            parsed_query,
        )

        structural_symbol_score = _structural_symbol_match(
            candidate,
            parsed_query,
            intent,
        )

        definition_reference_penalty = (
            _definition_reference_penalty(
                candidate,
                parsed_query,
            )
        )

        reference_score = _reference_match(
            candidate,
            parsed_query,
            strategy,
        )

        architecture_score = _architecture_match(
            candidate,
            parsed_query,
            intent,
        )

        reference_penalty = _reference_penalty(
            candidate,
            parsed_query,
            intent,
        )

        test_score = _test_match(candidate, strategy)

        candidate_path = _normalise(
            str(_candidate_metadata(candidate).get("file", ""))
        )

        implementation_test_penalty = (
            -0.55
            if implementation_query
            and any(
                pattern in candidate_path
                for pattern in TEST_PATTERNS
            )
            else 0.0
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
            + lexical_score
            + identifier_score
            + keyword_score
            + path_score
            + symbol_score
            + definition_score
            + definition_target_score
            + ordered_phrase_score
            + structural_symbol_score
            + responsibility_score
            + delegation_score
            + ownership_score
            + structural_ownership_score
            + definition_reference_penalty
            + reference_score
            + architecture_score
            + reference_penalty
            + test_score
            + implementation_test_penalty
            + configuration_score
            + dependency_score
            + entrypoint_score
            + documentation_score
        )

        enriched = dict(candidate)

        enriched["score"] = round(score, 6)
        enriched["semantic_score"] = round(semantic_score, 6)

        enriched["ranking_signals"] = {
            "semantic": round(semantic_score, 6),
            "configuration": round(configuration_score, 6),
            "dependency": round(dependency_score, 6),
            "entrypoint": round(entrypoint_score, 6),
            "documentation": round(documentation_score, 6),
            "test": round(test_score, 6),
            "identifier": round(identifier_score, 6),
            "lexical_retrieval": round(lexical_score, 6),
            "keyword": round(keyword_score, 6),
            "path": round(path_score, 6),
            "symbol": round(symbol_score, 6),
            "definition": round(definition_score, 6),
            "reference": round(reference_score, 6),
            "architecture": round(architecture_score, 6),
            "reference_penalty": round(reference_penalty, 6),
            "definition_target": round(
                definition_target_score,
                6,
            ),
            "ordered_phrase": round(ordered_phrase_score, 6),
            "structural_symbol": round(structural_symbol_score, 6),
            "responsibility_alignment": round(responsibility_score, 6),
            "delegation": round(delegation_score, 6),
            "ownership_evidence": round(ownership_score, 6),
            "v13_5_structural_ownership": round(structural_ownership_score, 6),
            "definition_reference_penalty": round(
                definition_reference_penalty,
                6,
            ),
            "implementation_test_penalty": round(
                implementation_test_penalty,
                6,
            ),
        }

        ranked.append(enriched)

    ranked.sort(
        key=lambda item: (
            item["score"],
            item.get("semantic_score", 0.0),
        ),
        reverse=True,
    )

    return ranked
