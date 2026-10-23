from dataclasses import dataclass, field
import re


@dataclass
class ParsedQuery:
    raw_query: str
    identifiers: list[str]
    keywords: list[str]
    definition_targets: list[str]
    concept_candidates: list[str] = field(default_factory=list)


IDENTIFIER_PATTERN = re.compile(
    r"""
    `
    ([A-Za-z_][A-Za-z0-9_.:/\\-]*)
    `
    |
    \b
    ([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
    \b
    """,
    re.VERBOSE,
)


DEFINITION_QUERY_PATTERN = re.compile(
    r"""
    \b
    (?:where|which)
    \s+
    (?:is|are)
    \s+
    (?:the\s+)?
    (.+?)
    \s+
    (?:defined|implemented|located|created|registered)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


SIMPLE_DEFINITION_PATTERN = re.compile(
    r"""
    \b
    (?:where|what)
    \s+
    (?:is|are)
    \s+
    (?:the\s+)?
    ([A-Za-z_][A-Za-z0-9_.]*)
    \s+
    (?:definition|implementation)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


STOP_WORDS = {
    "where", "what", "when", "which", "who", "how",
    "does", "do", "is", "are", "the", "this", "that",
    "these", "those", "for", "from", "with", "and", "or",
    "to", "of", "in", "on", "by", "a", "an", "it", "its",
    "please", "tell", "show", "find", "explain",
}


DEFINITION_STOP_WORDS = STOP_WORDS | {
    "defined", "implemented", "located", "created", "registered",
    "definition", "implementation", "registration",
}


def _clean_identifier(value: str) -> str:
    value = value.strip().strip("`")
    return value.rstrip("()").strip()


def _is_identifier(value: str) -> bool:
    if not value:
        return False

    if value.lower() in STOP_WORDS:
        return False

    return (
        "_" in value
        or "." in value
        or "/" in value
        or "\\" in value
        or "-" in value
        or any(char.isupper() for char in value[1:])
        or value.startswith("__")
        or value.endswith("()")
    )


def extract_identifiers(query: str) -> list[str]:
    identifiers: list[str] = []

    for match in IDENTIFIER_PATTERN.finditer(query):
        value = match.group(1) or match.group(2)

        if not value:
            continue

        value = _clean_identifier(value)

        if _is_identifier(value):
            identifiers.append(value)

    return list(dict.fromkeys(identifiers))


def _normalise_definition_phrase(value: str) -> str:
    value = value.strip()

    value = re.sub(
        r"\b(?:the|a|an)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"[^A-Za-z0-9_.:/\\-]+",
        " ",
        value,
    )

    return " ".join(value.split())


def extract_definition_targets(query: str) -> list[str]:
    targets: list[str] = []

    # Preserve explicit code-like identifiers as strong targets.
    targets.extend(extract_identifiers(query))

    match = DEFINITION_QUERY_PATTERN.search(query)

    if match:
        phrase = _normalise_definition_phrase(match.group(1))

        if phrase:
            targets.append(phrase)

            words = [
                word
                for word in phrase.split()
                if word.lower() not in DEFINITION_STOP_WORDS
            ]

            # Keep a standalone word only when the phrase has one
            # meaningful word; do not fragment longer concepts.
            if len(words) == 1:
                targets.append(words[0])

    match = SIMPLE_DEFINITION_PATTERN.search(query)

    if match:
        target = _clean_identifier(match.group(1))

        if target:
            targets.append(target)

    return list(dict.fromkeys(
        target
        for target in targets
        if target
    ))


def extract_keywords(query: str) -> list[str]:
    words = re.findall(
        r"[A-Za-z][A-Za-z0-9_-]{2,}",
        query.lower(),
    )

    return list(dict.fromkeys(
        word
        for word in words
        if word not in STOP_WORDS
    ))


def extract_concept_candidates(
    query: str,
    definition_targets: list[str] | None = None,
) -> list[str]:
    """Generate generic phrase variants for code-aware retrieval.

    This does not map natural language to repository-specific symbols.
    It creates phrase variants for matching indexed symbols, paths,
    and content.
    """
    targets = (
        definition_targets
        if definition_targets is not None
        else extract_definition_targets(query)
    )

    candidates: list[str] = []

    for target in targets:
        phrase = _normalise_definition_phrase(target)

        if not phrase:
            continue

        candidates.append(phrase)

        words = [
            word.lower()
            for word in re.findall(r"[A-Za-z0-9]+", phrase)
            if word.lower() not in DEFINITION_STOP_WORDS
        ]

        if not words:
            continue

        candidates.append("_".join(words))

        for start in range(1, len(words)):
            suffix = words[start:]

            if len(suffix) >= 2:
                candidates.append(" ".join(suffix))
                candidates.append("_".join(suffix))

        for index in range(len(words) - 1):
            pair = words[index:index + 2]
            candidates.append(" ".join(pair))
            candidates.append("_".join(pair))

    return list(dict.fromkeys(
        candidate
        for candidate in candidates
        if candidate
    ))


def parse_query(query: str) -> ParsedQuery:
    identifiers = extract_identifiers(query)
    keywords = extract_keywords(query)
    definition_targets = extract_definition_targets(query)
    concept_candidates = extract_concept_candidates(
        query,
        definition_targets,
    )

    return ParsedQuery(
        raw_query=query,
        identifiers=identifiers,
        keywords=keywords,
        definition_targets=definition_targets,
        concept_candidates=concept_candidates,
    )
