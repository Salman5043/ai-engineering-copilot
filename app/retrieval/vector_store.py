import chromadb

from app.config import settings


COLLECTION_NAME = "code_chunks"


def get_client():
    return chromadb.PersistentClient(
        path=settings.chroma_path
    )


def get_collection():
    client = get_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
        },
    )


def add_documents(
    documents: list[str],
    embeddings,
    metadatas: list[dict],
    ids: list[str],
):
    collection = get_collection()

    collection.upsert(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )


def search(
    query_embedding,
    n_results: int = 5,
    where: dict | None = None,
):
    collection = get_collection()

    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": [
            "documents",
            "metadatas",
            "distances",
        ],
    }

    if where is not None:
        query_kwargs["where"] = where

    return collection.query(
        **query_kwargs
    )