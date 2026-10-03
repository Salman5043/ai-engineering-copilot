from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agent.llm import get_llm
from app.changes.llm_models import (
    PatchGenerationResponse,
)
from app.changes.patch_prompt import (
    SYSTEM_PROMPT,
    build_patch_prompt,
)
from app.changes.proposal import (
    create_change_proposal,
    create_file_change,
)
from app.changes.models import (
    ChangeProposal,
)


class PatchGenerationError(RuntimeError):
    """
    Raised when the LLM cannot generate a valid patch.
    """


class LLMPatchGenerator:
    """
    Generates repository change proposals using an LLM.

    This class NEVER writes files.
    """

    def __init__(
        self,
        llm: Any | None = None,
    ) -> None:
        self.llm = (
            llm
            if llm is not None
            else get_llm()
        )

    def _structured_llm(self) -> Any:
        """
        Request structured Pydantic output from the LLM.
        """

        if not hasattr(
            self.llm,
            "with_structured_output",
        ):
            raise PatchGenerationError(
                "Configured LLM does not support "
                "structured output."
            )

        return self.llm.with_structured_output(
            PatchGenerationResponse
        )

    def generate(
        self,
        *,
        repository_id: str,
        repository_root: Path,
        query: str,
        files: list[dict[str, str]],
        evidence: list[dict[str, Any]],
    ) -> ChangeProposal:
        """
        Generate a ChangeProposal from repository
        files and investigation evidence.

        `files` must contain:
            {
                "path": "...",
                "content": "..."
            }
        """

        if not files:
            raise PatchGenerationError(
                "At least one file must be supplied "
                "for patch generation."
            )

        allowed_paths = {
            item["path"]
            for item in files
        }

        prompt = build_patch_prompt(
            query=query,
            repository_id=repository_id,
            files=files,
            evidence=evidence,
        )

        structured_llm = (
            self._structured_llm()
        )

        response = structured_llm.invoke(
            [
                (
                    "system",
                    SYSTEM_PROMPT,
                ),
                (
                    "user",
                    prompt,
                ),
            ]
        )

        if not isinstance(
            response,
            PatchGenerationResponse,
        ):
            try:
                response = (
                    PatchGenerationResponse.model_validate(
                        response
                    )
                )
            except Exception as exc:
                raise PatchGenerationError(
                    "LLM returned an invalid patch "
                    "generation response."
                ) from exc

        changes = []

        for generated in response.changes:
            if generated.path not in allowed_paths:
                raise PatchGenerationError(
                    "LLM attempted to modify a file "
                    f"that was not supplied: "
                    f"{generated.path}"
                )

            change = create_file_change(
                repository_root=repository_root,
                path=generated.path,
                proposed_content=(
                    generated.proposed_content
                ),
                reason=generated.reason,
            )

            changes.append(change)

        return create_change_proposal(
            repository_id=repository_id,
            description=response.description,
            changes=changes,
        )

    def generate_llm_patch(
    *,
    repository_id: str,
    repository_root: Path,
    query: str,
    files: list[dict[str, str]],
    evidence: list[dict[str, Any]],
    llm: Any | None = None,
) -> ChangeProposal:
        """
        Convenience wrapper around LLMPatchGenerator.
        """

        generator = LLMPatchGenerator(
            llm=llm,
        )

        return generator.generate(
            repository_id=repository_id,
            repository_root=repository_root,
            query=query,
            files=files,
            evidence=evidence,
        )