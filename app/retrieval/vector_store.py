from functools import lru_cache

import chromadb

from app.config import settings


COLLECTION_NAME = "code_chunks"


@lru_cache(maxsize=1)
def get_chroma_client():
    return chromadb.PersistentClient(
        path=settings.chroma_path
    )


def get_collection():
    client = get_chroma_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
        },
    )


def add_documents(
    documents: list[str],
    embeddings: list[list[float]],
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
    query_embedding: list[float],
    n_results: int = 5,
):
    collection = get_collection()

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )