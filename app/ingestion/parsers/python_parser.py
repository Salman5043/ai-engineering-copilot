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
                    signature=f"class {node.name}",
                )
            )

        elif isinstance(node, ast.FunctionDef):
            symbols.append(
                CodeSymbol(
                    name=node.name,
                    symbol_type="function",
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=_get_source_segment(
                        source,
                        node,
                    ),
                )
            )

        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(
                CodeSymbol(
                    name=node.name,
                    symbol_type="async_function",
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
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