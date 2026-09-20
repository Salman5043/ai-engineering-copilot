import hashlib
from pathlib import Path

from app.config import settings
from app.retrieval.embeddings import embed_documents
from app.retrieval.vector_store import add_documents

from .chunker import chunk_code
from .scanner import scan_repository


def generate_chunk_id(
    relative_path: str,
    start_line: int,
) -> str:

    value = f"{relative_path}:{start_line}"

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def index_repository(
    repository_path: str,
) -> dict:

    files = scan_repository(
        repository_path,
        max_file_size_mb=settings.max_file_size_mb,
    )

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    total_chunks = 0

    for repository_file in files:

        try:
            content = repository_file.path.read_text(
                encoding="utf-8"
            )
        except (UnicodeDecodeError, OSError):
            continue

        chunks = chunk_code(
            content,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )

        for chunk in chunks:

            documents.append(chunk.content)

            metadatas.append(
                {
                    "file": repository_file.relative_path,
                    "extension": repository_file.extension,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                }
            )

            ids.append(
                generate_chunk_id(
                    repository_file.relative_path,
                    chunk.start_line,
                )
            )

            total_chunks += 1

    if not documents:
        return {
            "files": len(files),
            "chunks": 0,
        }

    embeddings = embed_documents(documents)

    add_documents(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )

    return {
        "files": len(files),
        "chunks": total_chunks,
    }