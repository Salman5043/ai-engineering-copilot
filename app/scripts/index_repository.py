import sys

from app.ingestion.indexer import index_repository


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: "
            "uv run python -m scripts.index_repository "
            "<repository_path>"
        )
        raise SystemExit(1)

    repository_path = sys.argv[1]

    print(f"Indexing: {repository_path}")

    result = index_repository(
        repository_path
    )

    print("\nIndexing complete.")
    print(f"Repository ID: {result['repository_id']}")
    print(f"Files:         {result['files']}")
    print(f"Chunks:        {result['chunks']}")


if __name__ == "__main__":
    main()