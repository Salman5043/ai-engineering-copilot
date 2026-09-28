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
        r"\bwhere\s+is\s+.*\b",
        r"\bfind\s+.*\b",
        r"\blocate\s+.*\b",
        r"\bdefinition\s+of\b",
        r"\bimplementation\s+of\b",
    ],
}


def detect_intent(query: str) -> QueryIntent:
    normalized = query.strip().lower()

    scores: dict[str, int] = {}

    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        matched_terms: list[str] = []

        for pattern in patterns:
            match = re.search(pattern, normalized)

            if match:
                score += 1
                matched_terms.append(match.group(0))

        if score:
            scores[intent] = score

    if not scores:
        return QueryIntent(
            name="general_search",
            confidence=0.5,
            matched_terms=[],
        )

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    confidence = min(0.5 + (best_score * 0.15), 0.95)

    return QueryIntent(
        name=best_intent,
        confidence=confidence,
        matched_terms=[
            term
            for pattern in INTENT_PATTERNS[best_intent]
            for term in [
                re.search(pattern, normalized).group(0)
                if re.search(pattern, normalized)
                else None
            ]
            if term
        ],
    )