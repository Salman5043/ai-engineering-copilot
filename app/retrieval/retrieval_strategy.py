from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalStrategy:
    candidate_multiplier: int = 4

    prefer_symbols: bool = False
    preferred_symbol_types: tuple[str, ...] = ()

    prefer_tests: bool = False
    prefer_configuration: bool = False
    prefer_dependencies: bool = False
    prefer_entrypoints: bool = False
    prefer_documentation: bool = False

    prefer_definitions: bool = False
    prefer_references: bool = False
    prefer_path_relevance: bool = True
    prefer_keyword_overlap: bool = True


STRATEGIES: dict[str, RetrievalStrategy] = {
    "symbol_lookup": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_symbols=True,
        preferred_symbol_types=(
            "class",
            "function",
            "async_function",
            "method",
        ),
        prefer_definitions=True,
    ),

    "function_explanation": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_symbols=True,
        preferred_symbol_types=(
            "function",
            "async_function",
            "method",
            "class",
        ),
        prefer_documentation=True,
        prefer_definitions=True,
    ),

    "reference_search": RetrievalStrategy(
        candidate_multiplier=6,
        prefer_symbols=True,
        prefer_references=True,
    ),

    "configuration": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_configuration=True,
        prefer_symbols=True,
        prefer_definitions=True,
    ),

    "test_discovery": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_tests=True,
        prefer_symbols=True,
    ),

    "architecture": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_symbols=True,
        prefer_documentation=True,
        prefer_definitions=True,
    ),

    "dependency_search": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_dependencies=True,
    ),

    "entrypoint_discovery": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_entrypoints=True,
        prefer_symbols=True,
        prefer_definitions=True,
    ),

    "general_search": RetrievalStrategy(
        candidate_multiplier=3,
    ),
}


def get_strategy(intent: str) -> RetrievalStrategy:
    return STRATEGIES.get(
        intent,
        STRATEGIES["general_search"],
    )