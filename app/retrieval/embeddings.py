from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(
        settings.embedding_model
    )


def embed_documents(
    texts: list[str],
) -> list[list[float]]:

    if not texts:
        return []

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return embeddings.tolist()


def embed_query(text: str) -> list[float]:

    model = get_embedding_model()

    embedding = model.encode(
        text,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return embedding.tolist()