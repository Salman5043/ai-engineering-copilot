from pathlib import Path

from app.changes.llm_models import (
    GeneratedFileChange,
    PatchGenerationResponse,
)
from app.changes.llm_patch import (
    LLMPatchGenerator,
)
from app.changes.manager import (
    ChangeManager,
)
from app.changes.models import (
    ChangeStatus,
    ValidationSeverity,
)
from app.changes.proposal import (
    create_change_proposal,
    create_file_change,
)
from app.changes.validator import (
    PatchValidator,
)


class FakeStructuredLLM:
    def __init__(self, response):
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


def test_valid_python_patch(
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

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "def hello():\n"
            "    return 'hello world'\n"
        ),
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Fix greeting.",
        changes=[change],
    )

    validator = PatchValidator(
        tmp_path
    )

    result = validator.validate(
        proposal
    )

    assert result.valid
    assert result.errors == []
    assert "app.py" in result.checked_files


def test_invalid_python_is_rejected(
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

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "def hello(\n"
            "    return 'broken'\n"
        ),
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Broken patch.",
        changes=[change],
    )

    validator = PatchValidator(
        tmp_path
    )

    result = validator.validate(
        proposal
    )

    assert not result.valid

    assert any(
        issue.code
        == "PYTHON_SYNTAX_ERROR"
        for issue in result.errors
    )


def test_test_discovery(
    tmp_path: Path,
):
    tests_dir = (
        tmp_path / "tests"
    )

    tests_dir.mkdir()

    test_file = (
        tests_dir / "test_app.py"
    )

    test_file.write_text(
        "def test_app():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    validator = PatchValidator(
        tmp_path
    )

    result = validator.validate(
        create_change_proposal(
            repository_id="test-repo",
            description="Update app.",
            changes=[
                create_file_change(
                    repository_root=tmp_path,
                    path="app.py",
                    proposed_content=(
                        "print('hello')\n"
                    ),
                )
            ],
        )
    )

    assert (
        "tests/test_app.py"
        in result.discovered_tests
    )


def test_unsafe_path_is_rejected(
    tmp_path: Path,
):
    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Unsafe change.",
        changes=[],
    )

    # Construct a FileChange directly so that
    # validation, rather than proposal creation,
    # is responsible for detecting the path.
    from app.changes.models import (
        FileChange,
    )

    proposal.changes.append(
        FileChange(
            path="../outside.py",
            original_content="",
            proposed_content=(
                "print('bad')\n"
            ),
        )
    )

    validator = PatchValidator(
        tmp_path
    )

    result = validator.validate(
        proposal
    )

    assert not result.valid

    assert any(
        issue.code == "UNSAFE_PATH"
        for issue in result.errors
    )


def test_empty_proposal_is_invalid(
    tmp_path: Path,
):
    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Nothing changed.",
        changes=[],
    )

    validator = PatchValidator(
        tmp_path
    )

    result = validator.validate(
        proposal
    )

    assert not result.valid

    assert any(
        issue.code == "EMPTY_PROPOSAL"
        for issue in result.errors
    )


def test_validation_integrates_with_manager(
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

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "def hello():\n"
            "    return 'world'\n"
        ),
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Update greeting.",
        changes=[change],
    )

    manager = ChangeManager(
        tmp_path
    )

    result = manager.validate_patch(
        proposal
    )

    assert result.valid

    assert (
        proposal.status
        == ChangeStatus.VALIDATED
    )


def test_manager_rejects_invalid_patch(
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

    change = create_file_change(
        repository_root=tmp_path,
        path="app.py",
        proposed_content=(
            "def hello(\n"
            "    return 'broken'\n"
        ),
    )

    proposal = create_change_proposal(
        repository_id="test-repo",
        description="Broken patch.",
        changes=[change],
    )

    manager = ChangeManager(
        tmp_path
    )

    result = manager.validate_patch(
        proposal
    )

    assert not result.valid

    assert (
        proposal.status
        == ChangeStatus.FAILED
    )

    assert proposal.validation_errors