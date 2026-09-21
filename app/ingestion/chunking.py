from app.ingestion.chunker import CodeChunk, chunk_code
from app.ingestion.code_chunker import (
    CodeAwareChunk,
    create_symbol_chunks,
)
from app.ingestion.parsers import parse_code


def chunk_file(
    source: str,
    file_path: str,
    chunk_size: int = 1200,
    overlap: int = 200,
):
    parsed = parse_code(
        source,
        file_path,
    )

    if parsed and parsed.symbols:

        chunks = create_symbol_chunks(
            source,
            parsed.symbols,
        )

        if chunks:
            return chunks

    return [
        CodeAwareChunk(
            content=chunk.content,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            symbol=None,
            symbol_type=None,
        )
        for chunk in chunk_code(
            source,
            chunk_size=chunk_size,
            overlap=overlap,
        )
    ]