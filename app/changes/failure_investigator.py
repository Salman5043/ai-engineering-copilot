from __future__ import annotations

from pathlib import Path
from typing import Any

from app.changes.failure_analysis import (
    FailureAnalysis,
)

from app.changes.investigation_context import (
    InvestigationContext,
    add_evidence,
    add_error,
    add_observation,
    build_investigation_context,
)

from app.retrieval.retriever import retrieve


class FailureInvestigator:
    """
    Investigates a failed verification using the
    existing repository-aware retrieval system.

    No LLM is required for the initial investigation.

    The investigator is read-only.
    It does not modify repository files.
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
        """
        Search the indexed repository and normalize
        retrieval results into dictionaries.
        """

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

        normalized: list[
            dict[str, Any]
        ] = []

        for result in results:

            if hasattr(
                result,
                "model_dump",
            ):
                data = result.model_dump()

            elif isinstance(
                result,
                dict,
            ):
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
        """
        Perform repository investigation after
        a verification failure.

        Investigation stages:

        1. Failed test investigation
        2. Affected-file investigation
        3. Failure-context investigation
        """

        context = build_investigation_context(
            original_query=original_query,
            failure=failure,
        )

        # --------------------------------------------------
        # 1. Investigate failed tests
        # --------------------------------------------------

        for test in failure.failed_tests:

            test_query = (
                "Find the implementation and related "
                "code for failing test: "
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
                    source_tool=(
                        "test_investigation"
                    ),
                )

            except Exception as exc:
                add_error(
                    context,
                    (
                        "Test investigation failed: "
                        f"{exc}"
                    ),
                )

        # --------------------------------------------------
        # 2. Investigate affected files
        # --------------------------------------------------

        for file_path in (
            failure.likely_files
        ):

            query = (
                "Find the implementation and "
                f"symbols in {file_path}"
            )

            try:
                evidence = self._search(
                    query,
                    top_k=5,
                )

                add_evidence(
                    context,
                    evidence,
                    source_tool=(
                        "implementation_search"
                    ),
                )

                add_observation(
                    context,
                    (
                        "Investigated affected file: "
                        f"{file_path}"
                    ),
                )

            except Exception as exc:
                add_error(
                    context,
                    (
                        "Implementation investigation "
                        f"failed for {file_path}: {exc}"
                    ),
                )

        # --------------------------------------------------
        # 3. Search original task + failure
        # --------------------------------------------------

        failure_query = (
            f"{original_query}\n"
            f"Failure: {failure.failure_summary}"
        )

        try:
            evidence = self._search(
                failure_query,
                top_k=10,
            )

            add_evidence(
                context,
                evidence,
                source_tool=(
                    "failure_context_search"
                ),
            )

        except Exception as exc:
            add_error(
                context,
                (
                    "Failure context search failed: "
                    f"{exc}"
                ),
            )

        return context