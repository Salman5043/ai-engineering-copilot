import ast

from app.ingestion.parsers.base import CodeSymbol, ParsedCode


def _get_source_segment(
    source: str,
    node: ast.AST,
) -> str | None:
    try:
        return ast.get_source_segment(source, node)
    except Exception:
        return None


def parse_python(source: str) -> ParsedCode:
    tree = ast.parse(source)

    symbols: list[CodeSymbol] = []
    imports: list[str] = []

    # Record the actual AST parent of every node.
    parents: dict[ast.AST, ast.AST] = {}

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    def enclosing_class(node: ast.AST) -> str | None:
        classes: list[str] = []
        current = parents.get(node)

        while current is not None:
            if isinstance(current, ast.ClassDef):
                classes.append(current.name)

            current = parents.get(current)

        if not classes:
            return None

        return ".".join(reversed(classes))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""

            for alias in node.names:
                imports.append(
                    f"{module}.{alias.name}"
                )

        elif isinstance(node, ast.ClassDef):
            symbols.append(
                CodeSymbol(
                    name=node.name,
                    symbol_type="class",
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    parent=enclosing_class(node),
                    signature=f"class {node.name}",
                )
            )

        elif isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            symbol_type = (
                "async_function"
                if isinstance(node, ast.AsyncFunctionDef)
                else "function"
            )

            symbols.append(
                CodeSymbol(
                    name=node.name,
                    symbol_type=symbol_type,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    parent=enclosing_class(node),
                    signature=_get_source_segment(
                        source,
                        node,
                    ),
                )
            )

    return ParsedCode(
        language="python",
        symbols=symbols,
        imports=imports,
    )