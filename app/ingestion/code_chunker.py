from dataclasses import dataclass

from app.ingestion.parsers.base import CodeSymbol


@dataclass
class CodeAwareChunk:
    content: str
    start_line: int
    end_line: int
    symbol: str | None
    symbol_type: str | None

    parent_symbol: str | None = None
    qualified_symbol: str | None = None


def create_symbol_chunks(
    source: str,
    symbols: list[CodeSymbol],
) -> list[CodeAwareChunk]:

    lines = source.splitlines()
    chunks: list[CodeAwareChunk] = []

    for symbol in symbols:
        start = max(symbol.start_line, 1)
        end = min(
            symbol.end_line,
            len(lines),
        )

        content = "\n".join(
            lines[start - 1:end]
        )

        if not content.strip():
            continue

        qualified_symbol = (
            f"{symbol.parent}.{symbol.name}"
            if symbol.parent
            else symbol.name
        )

        chunks.append(
            CodeAwareChunk(
                content=content,
                start_line=start,
                end_line=end,
                symbol=symbol.name,
                symbol_type=symbol.symbol_type,
                parent_symbol=symbol.parent,
                qualified_symbol=qualified_symbol,
            )
        )

    return chunks