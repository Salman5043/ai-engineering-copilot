import hashlib
from pathlib import Path

from app.config import settings
from app.ingestion.chunking import chunk_file
from app.ingestion.scanner import scan_repository
from app.retrieval.embeddings import embed_documents
from app.retrieval.vector_store import add_documents


def generate_repository_id(repository_path: str) -> str:
    resolved = str(
        Path(repository_path).resolve()
    ).lower()

    digest = hashlib.sha256(
        resolved.encode("utf-8")
    ).hexdigest()[:16]

    return f"repo_{digest}"


def generate_chunk_id(
    repository_id,
    relative_path,
    start_line,
    symbol=None,
):
    raw = (
        f"{repository_id}:"
        f"{relative_path}:"
        f"{start_line}:"
        f"{symbol or ''}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def detect_language(extension):
    languages = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".rb": "ruby",
        ".swift": "swift",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".txt": "text",
    }

    return languages.get(
        extension.lower(),
        "unknown",
    )


def index_repository(repository_path):
    repository_path = str(
        Path(repository_path).resolve()
    )

    repository_id = generate_repository_id(
        repository_path
    )

    files = scan_repository(
        repository_path,
        max_file_size_mb=settings.max_file_size_mb,
    )

    documents = []
    metadatas = []
    ids = []

    for file in files:
        path = Path(file.path)

        try:
            source = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            continue

        chunks = chunk_file(
            source=source,
            file_path=file.path,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )

        language = detect_language(
            file.extension
        )

        for chunk in chunks:
            documents.append(chunk.content)

            metadatas.append(
                {
                    "repository_id": repository_id,
                    "file": file.relative_path,
                    "extension": file.extension,
                    "language": language,
                    "symbol": chunk.symbol or "",
                    "symbol_type": chunk.symbol_type or "",
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                }
            )

            ids.append(
                generate_chunk_id(
                    repository_id,
                    file.relative_path,
                    chunk.start_line,
                    chunk.symbol,
                )
            )

    if not documents:
        return {
            "repository_id": repository_id,
            "repository_path": repository_path,
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
        "repository_id": repository_id,
        "repository_path": repository_path,
        "files": len(files),
        "chunks": len(documents),
    }