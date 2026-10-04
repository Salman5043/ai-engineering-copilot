from __future__ import annotations

from pathlib import Path
from typing import Any

from app.changes.failure_analysis import (
    FailureAnalysis,
)
from app.changes.investigation_context import (
    InvestigationContext,
    add_evidence,
    add_observation,
    build_investigation_context,
)
from app.retrieval.retriever import (
    retrieve,
)


class FailureInvestigator:
    """
    Investigates a failed verification using the existing
    repository-aware retrieval system.

    No LLM is required for the initial investigation.
    """

    def __init__(
        self,
        repository_id: str,
        repository_root: Path,
    ) -> None:
        self.repository_id = repository_id
        self.repository_root = (
            repository_root.resolve()
        )

    def _search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        response = retrieve(
            repository_id=self.repository_id,
            query=query,
            top_k=top_k,
        )

        results = getattr(
            response,
            "results",
            response,
        )

        normalized: list[dict[str, Any]] = []

        for result in results:
            if hasattr(
                result,
                "model_dump",
            ):
                data = result.model_dump()
            elif isinstance(result, dict):
                data = dict(result)
            else:
                data = dict(
                    getattr(
                        result,
                        "__dict__",
                        {},
                    )
                )

            normalized.append(data)

        return normalized

    def investigate(
        self,
        *,
        original_query: str,
        failure: FailureAnalysis,
    ) -> InvestigationContext:
        context = build_investigation_context(
            original_query=original_query,
            failure=failure,
        )

        # 1. Investigate the failed test.
        for test in failure.failed_tests:
            test_query = (
                "Find the implementation and related "
                f"code for failing test: "
                f"{' '.join(test.command)}"
            )

            try:
                evidence = self._search(
                    test_query,
                    top_k=5,
                )

                add_evidence(
                    context,
                    evidence,
                    source_tool="test_investigation",
                )

            except Exception as exc:
                context.errors.append(
                    f"Test investigation failed: {exc}"
                )

        # 2. Investigate likely affected files.
        for file_path in failure.likely_files:
            query = (
                "Find the implementation and symbols "
                f"in {file_path}"
            )

            try:
                evidence = self._search(
                    query,
                    top_k=5,
                )

                add_evidence(
                    context,
                    evidence,
                    source_tool="implementation_search",
                )

                add_observation(
                    context,
                    (
                        "Investigated affected file: "
                        f"{file_path}"
                    ),
                )

            except Exception as exc:
                context.errors.append(
                    "Implementation investigation failed "
                    f"for {file_path}: {exc}"
                )

        # 3. Search the original task together with
        #    the failure.
        query = (
            f"{original_query}\n"
            f"Failure: {failure.failure_summary}"
        )

        try:
            evidence = self._search(
                query,
                top_k=10,
            )

            add_evidence(
                context,
                evidence,
                source_tool="failure_context_search",
            )

        except Exception as exc:
            context.errors.append(
                f"Failure context search failed: {exc}"
            )

        return context