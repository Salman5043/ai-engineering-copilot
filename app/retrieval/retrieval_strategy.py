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
    ),

    "reference_search": RetrievalStrategy(
        candidate_multiplier=6,
        prefer_symbols=True,
    ),

    "configuration": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_configuration=True,
        prefer_symbols=True,
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
    ),

    "dependency_search": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_dependencies=True,
    ),

    "entrypoint_discovery": RetrievalStrategy(
        candidate_multiplier=5,
        prefer_entrypoints=True,
        prefer_symbols=True,
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