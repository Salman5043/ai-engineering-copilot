import chromadb

from app.config import settings


COLLECTION_NAME = "code_chunks_v2"


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
    documents,
    embeddings,
    metadatas,
    ids,
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
    n_results=5,
    where=None,
):
    collection = get_collection()

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )