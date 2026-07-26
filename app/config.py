"""
Central configuration.

Everything is read from environment variables (.env in dev).
Keeping ALL config here means main.py, services, and routers never
touch os.environ directly -- and it means V2 (Docker) needs zero code
changes, only different env values.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    app_name: str = "rag_system"
    environment: str = "development"
    log_level: str = "INFO"

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "rag_system"
    postgres_user: str = "rag_user"
    postgres_password: str = "change_me"

    # --- FAISS ---
    faiss_index_dir: str = "./faiss_index"

    # --- Document storage ---
    upload_dir: str = "./documents"
    max_upload_size_mb: int = 25

    # --- Chunking ---
    chunk_size: int = 1000
    chunk_overlap: int = 150

    # --- Embeddings ---
    embedding_provider: str = "gemini"  # gemini | fastembed
    google_api_key: str = ""
    fastembed_model: str = "BAAI/bge-small-en-v1.5"

    # --- LLM ---
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-70b-versatile"

    # --- Voice (Deepgram) ---
    deepgram_api_key: str = ""
    deepgram_stt_model: str = "nova-3"
    deepgram_tts_model: str = "aura-2-thalia-en"

    # --- Retrieval ---
    retrieval_top_k: int = 4
    conversation_history_turns: int = 3  # how many past Q&As to include as memory

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached so we parse .env only once per process."""
    return Settings()