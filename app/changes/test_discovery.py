from __future__ import annotations

from pathlib import Path


TEST_DIRECTORIES = {
    "test",
    "tests",
}


def discover_tests(
    repository_root: Path,
) -> list[str]:
    """
    Discover likely test files without executing them.
    """

    results: list[str] = []

    if not repository_root.exists():
        return results

    for path in repository_root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(
            repository_root
        )

        parts = {
            part.lower()
            for part in relative.parts
        }

        name = path.name.lower()

        is_test_directory = bool(
            parts.intersection(
                TEST_DIRECTORIES
            )
        )

        is_test_file = (
            name.startswith("test_")
            or name.endswith("_test.py")
        )

        if (
            is_test_directory
            or is_test_file
        ):
            results.append(
                relative.as_posix()
            )

    return sorted(
        set(results)
    )


def discover_related_tests(
    repository_root: Path,
    changed_files: list[str],
) -> list[str]:
    """
    Find tests that are likely related to the
    changed files.

    Strategy:

    1. test_<module>.py
    2. <module>_test.py
    3. Tests in the same directory
    4. Tests under the repository test directories
    """

    all_tests = discover_tests(
        repository_root
    )

    if not changed_files:
        return all_tests

    related: set[str] = set()

    for changed_file in changed_files:
        changed_path = Path(
            changed_file
        )

        stem = changed_path.stem.lower()

        candidates = {
            f"test_{stem}.py",
            f"{stem}_test.py",
        }

        for test_path in all_tests:
            test = Path(test_path)

            if test.name.lower() in candidates:
                related.add(
                    test_path
                )

            # Same directory relationship.
            if (
                test.parent
                == changed_path.parent
            ):
                related.add(
                    test_path
                )

    # If no directly-related tests exist,
    # return all discovered tests so the
    # repository still receives verification.
    if not related:
        return all_tests

    return sorted(related)