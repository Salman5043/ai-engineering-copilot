from dataclasses import dataclass
import re


@dataclass
class ParsedQuery:
    raw_query: str
    identifiers: list[str]
    keywords: list[str]


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


STOP_WORDS = {
    "where",
    "what",
    "when",
    "which",
    "who",
    "how",
    "does",
    "do",
    "is",
    "are",
    "the",
    "this",
    "that",
    "these",
    "those",
    "for",
    "from",
    "with",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "by",
    "a",
    "an",
    "it",
    "its",
}


def extract_identifiers(query: str) -> list[str]:
    identifiers: list[str] = []

    for match in IDENTIFIER_PATTERN.finditer(query):
        value = match.group(1) or match.group(2)

        if not value:
            continue

        value = value.strip()

        if value.lower() in STOP_WORDS:
            continue

        # Strong indicators of programming identifiers.
        looks_like_identifier = (
            "_" in value
            or "." in value
            or "/" in value
            or "\\" in value
            or "-" in value
            or any(char.isupper() for char in value[1:])
            or value.startswith("__")
            or value.endswith("()")
        )

        if looks_like_identifier:
            identifiers.append(value.rstrip("()"))

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(identifiers))


def extract_keywords(query: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", query.lower())

    return [
        word
        for word in words
        if word not in STOP_WORDS
    ]


def parse_query(query: str) -> ParsedQuery:
    return ParsedQuery(
        raw_query=query,
        identifiers=extract_identifiers(query),
        keywords=extract_keywords(query),
    )