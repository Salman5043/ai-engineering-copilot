from pathlib import Path

import pytest

from app.changes.llm_models import (
    PatchGenerationResponse,
    GeneratedFileChange,
)
from app.changes.llm_patch import (
    LLMPatchGenerator,
    PatchGenerationError,
)
from app.changes.models import (
    ChangeStatus,
)


class FakeStructuredLLM:
    """
    Fake LLM used for deterministic unit tests.
    """

    def __init__(
        self,
        response,
    ):
        self.response = response

    def with_structured_output(
        self,
        schema,
    ):
        return self

    def invoke(
        self,
        messages,
    ):
        return self.response


def test_generates_patch_proposal(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    file_path.write_text(
        "def hello():\n"
        "    return 'hello'\n",
        encoding="utf-8",
    )

    response = PatchGenerationResponse(
        description=(
            "Fix the greeting returned "
            "by hello."
        ),
        changes=[
            GeneratedFileChange(
                path="app.py",
                proposed_content=(
                    "def hello():\n"
                    "    return 'hello world'\n"
                ),
                reason=(
                    "Update the returned greeting."
                ),
            )
        ],
    )

    llm = FakeStructuredLLM(
        response
    )

    generator = LLMPatchGenerator(
        llm=llm
    )

    proposal = generator.generate(
        repository_id="test-repo",
        repository_root=tmp_path,
        query=(
            "Change hello() to return "
            "'hello world'."
        ),
        files=[
            {
                "path": "app.py",
                "content": file_path.read_text(
                    encoding="utf-8"
                ),
            }
        ],
        evidence=[
            {
                "file": "app.py",
                "start_line": 1,
                "end_line": 2,
                "content": (
                    "def hello():\n"
                    "    return 'hello'\n"
                ),
                "source_tool": "symbol_search",
            }
        ],
    )

    assert (
        proposal.repository_id
        == "test-repo"
    )

    assert (
        proposal.description
        == "Fix the greeting returned by hello."
    )

    assert len(proposal.changes) == 1
    assert (
        proposal.changes[0].path
        == "app.py"
    )

    assert proposal.changes[0].is_modified


def test_generated_patch_preserves_original_content(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "service.py"
    )

    original = (
        "def calculate():\n"
        "    return 1\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    response = PatchGenerationResponse(
        description="Update calculation.",
        changes=[
            GeneratedFileChange(
                path="service.py",
                proposed_content=(
                    "def calculate():\n"
                    "    return 2\n"
                ),
                reason="Correct calculation.",
            )
        ],
    )

    generator = LLMPatchGenerator(
        llm=FakeStructuredLLM(
            response
        )
    )

    proposal = generator.generate(
        repository_id="test-repo",
        repository_root=tmp_path,
        query="Fix calculation.",
        files=[
            {
                "path": "service.py",
                "content": original,
            }
        ],
        evidence=[],
    )

    assert (
        proposal.changes[0].original_content
        == original
    )


def test_unknown_file_is_rejected(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    file_path.write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    response = PatchGenerationResponse(
        description="Modify another file.",
        changes=[
            GeneratedFileChange(
                path="secret.py",
                proposed_content=(
                    "print('bad')\n"
                ),
                reason="Bad change.",
            )
        ],
    )

    generator = LLMPatchGenerator(
        llm=FakeStructuredLLM(
            response
        )
    )

    with pytest.raises(
        PatchGenerationError
    ):
        generator.generate(
            repository_id="test-repo",
            repository_root=tmp_path,
            query="Modify the repository.",
            files=[
                {
                    "path": "app.py",
                    "content": (
                        "print('hello')\n"
                    ),
                }
            ],
            evidence=[],
        )


def test_empty_change_is_supported(
    tmp_path: Path,
):
    file_path = (
        tmp_path / "app.py"
    )

    original = (
        "print('hello')\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    response = PatchGenerationResponse(
        description=(
            "No safe change can be generated "
            "from the available evidence."
        ),
        changes=[],
    )

    generator = LLMPatchGenerator(
        llm=FakeStructuredLLM(
            response
        )
    )

    proposal = generator.generate(
        repository_id="test-repo",
        repository_root=tmp_path,
        query="Fix something.",
        files=[
            {
                "path": "app.py",
                "content": original,
            }
        ],
        evidence=[],
    )

    assert proposal.is_empty
    assert proposal.changes == []


def test_generated_patch_can_be_validated(
    tmp_path: Path,
):
    from app.changes.manager import (
        ChangeManager,
    )

    file_path = (
        tmp_path / "app.py"
    )

    original = (
        "print('hello')\n"
    )

    file_path.write_text(
        original,
        encoding="utf-8",
    )

    response = PatchGenerationResponse(
        description="Update greeting.",
        changes=[
            GeneratedFileChange(
                path="app.py",
                proposed_content=(
                    "print('hello world')\n"
                ),
                reason="Update greeting.",
            )
        ],
    )

    generator = LLMPatchGenerator(
        llm=FakeStructuredLLM(
            response
        )
    )

    proposal = generator.generate(
        repository_id="test-repo",
        repository_root=tmp_path,
        query="Update greeting.",
        files=[
            {
                "path": "app.py",
                "content": original,
            }
        ],
        evidence=[],
    )

    manager = ChangeManager(
        tmp_path
    )

    manager.validate(
        proposal
    )

    assert (
        proposal.status
        == ChangeStatus.VALIDATED
    )

    assert proposal.is_valid