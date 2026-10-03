from __future__ import annotations

import ast


def validate_python_syntax(
    content: str,
    *,
    path: str,
) -> list[tuple[str, str, int | None]]:
    """
    Validate Python source code.

    Returns tuples containing:

        (code, message, line)
    """

    try:
        ast.parse(
            content,
            filename=path,
        )

    except SyntaxError as exc:
        return [
            (
                "PYTHON_SYNTAX_ERROR",
                exc.msg,
                exc.lineno,
            )
        ]

    return []


def validate_python_ast(
    content: str,
    *,
    path: str,
) -> list[tuple[str, str, int | None]]:
    """
    Perform lightweight AST-level validation.

    This intentionally does not execute the code.
    """

    try:
        tree = ast.parse(
            content,
            filename=path,
        )
    except SyntaxError:
        return []

    issues: list[
        tuple[str, str, int | None]
    ] = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                if not alias.name:
                    issues.append(
                        (
                            "INVALID_IMPORT",
                            "Import has no module name.",
                            getattr(
                                node,
                                "lineno",
                                None,
                            ),
                        )
                    )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.level < 0:
                issues.append(
                    (
                        "INVALID_IMPORT_LEVEL",
                        "Invalid relative import level.",
                        getattr(
                            node,
                            "lineno",
                            None,
                        ),
                    )
                )

    return issues