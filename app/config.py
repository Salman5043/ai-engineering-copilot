from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "AI Engineering Copilot"
    environment: str = "development"

    repository_root: str = str(
        BASE_DIR / "data" / "repositories"
    )

    chroma_path: str = str(
        BASE_DIR / "data" / "chroma"
    )

    embedding_model: str = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    max_file_size_mb: int = 2

    chunk_size: int = 1200
    chunk_overlap: int = 200

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()