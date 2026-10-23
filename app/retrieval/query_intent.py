from dataclasses import dataclass
import re


@dataclass
class QueryIntent:
    name: str
    confidence: float
    matched_terms: list[str]


INTENT_PATTERNS: dict[str, list[str]] = {
    "reference_search": [
        r"\bwhere\s+is\s+.*\s+called\b",
        r"\bwhere\s+.*\s+called\b",
        r"\bwho\s+calls\b",
        r"\bwhat\s+calls\b",
        r"\bcalled\s+by\b",
        r"\bcallers?\b",
        r"\breferences?\b",
        r"\busages?\b",
        r"\bused\s+where\b",
        r"\bused\s+by\b",
    ],

    "test_discovery": [
        r"\bwhere\s+are\s+the\s+tests?\b",
        r"\btests?\s+for\b",
        r"\btest\s+files?\b",
        r"\btesting\b",
        r"\btest\s+coverage\b",
        r"\bunit\s+tests?\b",
        r"\bintegration\s+tests?\b",
    ],

    "dependency_search": [
        r"\bdependencies?\b",
        r"\bpackages?\b",
        r"\blibraries?\b",
        r"\bthird[- ]party\b",
        r"\bexternal\s+packages?\b",
        r"\bwhat\s+does\s+.*\s+depend\s+on\b",
        r"\bdepend\s+on\b",
    ],

    "entrypoint_discovery": [
        r"\bentry\s*point\b",
        r"\bwhere\s+does\s+.*\s+start\b",
        r"\bhow\s+does\s+.*\s+start\b",
        r"\bhow\s+does\s+the\s+application\s+start\b",
        r"\bapplication\s+start\b",
        r"\bapplication\s+startup\b",
        r"\bstartup\b",
        r"\bbootstrapping\b",
        r"\bmain\s+entry\b",
    ],

    "configuration": [
        r"\bwhere\s+is\s+.*\s+configured\b",
        r"\bwhere\s+are\s+.*\s+configured\b",
        r"\bconfiguration\b",
        r"\bconfigure\b",
        r"\bconfigured\b",
        r"\bsettings?\b",
        r"\benvironment\s+variables?\b",
        r"\benv\s+variables?\b",
        r"\bconnection\s+configured\b",
        r"\bdatabase\s+configured\b",
        r"\bapi\s+key\b",
        r"\bcredentials?\b",
    ],

    "architecture": [
        r"\barchitecture\b",
        r"\bapplication\s+structure\b",
        r"\bproject\s+structure\b",
        r"\bcode\s+structure\b",
        r"\bhow\s+is\s+.*\s+structured\b",
        r"\bhow\s+does\s+.*\s+fit\s+together\b",
        r"\bdata\s+flow\b",
        r"\bcomponents?\b",
        r"\bmodules?\b",
        r"\blayers?\b",

        # Architecture-style implementation questions.
        r"\bwhere\s+is\s+.*\s+workflow\s+created\b",
        r"\bwhere\s+is\s+.*\s+pipeline\s+created\b",
        r"\bwhere\s+is\s+.*\s+graph\s+created\b",
        r"\bwhere\s+is\s+.*\s+flow\s+created\b",
        r"\bwhere\s+is\s+.*\s+orchestrated\b",
        r"\bwhere\s+is\s+.*\s+assembled\b",
        r"\bwhere\s+is\s+.*\s+wired\b",
    ],

    "function_explanation": [
        r"\bhow\s+does\s+.*\s+work\b",
        r"\bhow\s+does\s+.*\s+function\b",
        r"\bwhat\s+does\s+.*\s+do\b",
        r"\bexplain\s+.*\b",
        r"\bexplain\s+how\b",
        r"\bhow\s+is\s+.*\s+implemented\b",
        r"\bhow\s+does\s+.*\s+implement\b",
    ],

    "symbol_lookup": [
        r"\bwhere\s+is\s+.*\s+defined\b",
        r"\bwhere\s+are\s+.*\s+defined\b",
        r"\bdefinition\s+of\b",
        r"\bimplementation\s+of\b",
        r"\blocate\s+the\s+(?:class|function|method|symbol)\b",
        r"\bfind\s+the\s+(?:class|function|method|symbol)\b",
        r"\bwhere\s+is\s+.*\s+implemented\b",
        r"\bwhere\s+are\s+.*\s+implemented\b",
        r"\bwhere\s+is\s+.*\s+declared\b",
        r"\bwhere\s+are\s+.*\s+declared\b",
        r"\bwhich\s+(?:file|module|class|function)\s+implements\b",
        r"\bwhere\s+are\s+.*\s+registered\b",
        r"\bwhere\s+is\s+.*\s+registered\b",
    ],
}


# Patterns that indicate a direct definition lookup.
DEFINITION_PATTERNS = (
    r"\bwhere\s+is\s+.*\s+defined\b",
    r"\bwhere\s+are\s+.*\s+defined\b",
    r"\bdefinition\s+of\b",
    r"\bimplementation\s+of\b",
    r"\bfind\s+the\s+(?:class|function|method|symbol)\b",
    r"\blocate\s+the\s+(?:class|function|method|symbol)\b",
    r"\bwhere\s+is\s+.*\s+implemented\b",
    r"\bwhere\s+are\s+.*\s+implemented\b",
    r"\bwhere\s+is\s+.*\s+declared\b",
    r"\bwhere\s+are\s+.*\s+declared\b",
    r"\bwhich\s+(?:file|module|class|function)\s+implements\b",
    r"\bwhere\s+are\s+.*\s+registered\b",
    r"\bwhere\s+is\s+.*\s+registered\b",
)


def _matches(query: str, patterns: list[str]) -> list[str]:
    matches: list[str] = []

    for pattern in patterns:
        match = re.search(pattern, query)

        if match:
            matches.append(match.group(0))

    return matches


def _is_definition_query(query: str) -> bool:
    return bool(_matches(query, list(DEFINITION_PATTERNS)))


# v13.2: structural phrasing, not repository-specific names.
# Apply before generic "module", "component", "configuration", or "entry point" signals.
ARCHITECTURE_ACTION_PATTERNS = (
    r"\b(?:how\s+is|how\s+are)\b.*\b(?:assembled|wired|connected|structured)\b",
    r"\b(?:find|locate)\b.*\b(?:graph|workflow)\b.*\b(?:compiled|compiles|constructed)\b",
    r"\b(?:find|locate)\b.*\b(?:compiles?|compilation)\b.*\b(?:graph|workflow)\b",
    r"\b(?:graph|workflow|state\s+machine)\b.*\b(?:assembled|compiled|constructed)\b",
)

SYMBOL_OWNERSHIP_PATTERNS = (
    r"\b(?:find|locate)\s+(?:the\s+)?(?:code|module|file|class|function|method|symbol|implementation|declaration|data\s+structure|interface|generator|operation|entry\s+point)\b",
    r"\b(?:find|locate)\s+the\s+[a-z_][\w]*\s+(?:class|implementation|declaration|data\s+structure|method|interface|generator|operation)\b",
    r"\bwhich\s+(?:class|component|module|file|function)\b.*\b(?:owns|implements|applies|investigates|decides|orchestrates|defines|stores|handles|performs|manages|records)\b",
    r"\bwhere\s+(?:is|are)\b.*\b(?:performed|checked|recorded|merged|reranked|stored)\b",
    r"\bwhere\s+does\b.*\b(?:store|implement|handle|record|manage)\b",
    r"\b(?:find|locate)\b.*\b(?:implementation|class|method|interface|generator|operation|declaration|data\s+structure)\b",
    r"\b(?:find|locate)\s+the\s+code\s+responsible\s+for\b",
    r"\b(?:find|locate)\b.*\b(?:policy\s+configuration|configuration\s+and\s+decision|model\s+and\s+tracing|entry\s+point|pipeline\s+coordinating)\b",
)


def _structural_intent(query: str) -> QueryIntent | None:
    architecture = _matches(query, list(ARCHITECTURE_ACTION_PATTERNS))
    if architecture:
        return QueryIntent("architecture", 0.90, architecture)
    ownership = _matches(query, list(SYMBOL_OWNERSHIP_PATTERNS))
    if ownership:
        return QueryIntent("symbol_lookup", 0.90, ownership)
    return None


def detect_intent(query: str) -> QueryIntent:
    normalized = query.strip().lower()

    if not normalized:
        return QueryIntent(
            name="general_search",
            confidence=0.5,
            matched_terms=[],
        )

    # Preserve explicit call-site/reference and test intent precedence.
    for special in ("reference_search", "test_discovery", "dependency_search"):
        hits = _matches(normalized, INTENT_PATTERNS[special])
        if hits:
            return QueryIntent(special, min(0.55 + 0.15 * len(hits), 0.95), hits)

    structural = _structural_intent(normalized)
    if structural is not None:
        return structural

    scores: dict[str, int] = {}
    matches_by_intent: dict[str, list[str]] = {}

    for intent, patterns in INTENT_PATTERNS.items():
        matches = _matches(normalized, patterns)

        if matches:
            scores[intent] = len(matches)
            matches_by_intent[intent] = matches

    if not scores:
        return QueryIntent(
            name="general_search",
            confidence=0.5,
            matched_terms=[],
        )

    # Explicit architecture questions should beat the old broad
    # "where is ..." symbol lookup behavior.
    if "architecture" in scores:
        architecture_terms = matches_by_intent["architecture"]

        if any(
            term in normalized
            for term in (
                "workflow",
                "pipeline",
                "graph",
                "data flow",
                "orchestrated",
                "assembled",
                "wired",
            )
        ):
            return QueryIntent(
                name="architecture",
                confidence=0.90,
                matched_terms=architecture_terms,
            )

    # Explicit definition queries should remain symbol lookups.
    if "symbol_lookup" in scores and _is_definition_query(normalized):
        return QueryIntent(
            name="symbol_lookup",
            confidence=0.90,
            matched_terms=matches_by_intent["symbol_lookup"],
        )

    # References should beat generic symbol lookup.
    if "reference_search" in scores:
        return QueryIntent(
            name="reference_search",
            confidence=min(
                0.55 + scores["reference_search"] * 0.15,
                0.95,
            ),
            matched_terms=matches_by_intent["reference_search"],
        )

    # Other explicit intents are selected by score.
    best_intent = max(
        scores,
        key=lambda intent: scores[intent],
    )

    best_score = scores[best_intent]

    confidence = min(
        0.5 + (best_score * 0.15),
        0.95,
    )

    return QueryIntent(
        name=best_intent,
        confidence=confidence,
        matched_terms=matches_by_intent[best_intent],
    )