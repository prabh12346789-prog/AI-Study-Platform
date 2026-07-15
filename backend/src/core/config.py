from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool

    HOST: str
    PORT: int

    DATABASE_URL: str
    LLM_PROVIDER: str = "ollama"
    OLLAMA_MODEL: str = "qwen3:8b"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    VECTOR_DB: str = "chromadb"
    CHROMA_COLLECTION: str = "documents"
    CHROMA_DB_PATH: str = "./chroma_db"
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.70
    ENABLE_WEB_SEARCH: bool = True
    SEARCH_PROVIDER: str = "local_first"
    MAX_WEB_RESULTS: int = 5
    WEB_CACHE_ENABLED: bool = True
    WEB_CACHE_DIR: str = "./data/web_cache"
    WEB_STABLE_CACHE_DAYS: int = 30
    WEB_CURRENT_CACHE_HOURS: int = 24
    CHAT_MIN_GROUNDING_CONFIDENCE: float = 0.70
    ROADMAP_MIN_GROUNDING_CONFIDENCE: float = 0.78
    MAX_CHAT_HISTORY: int = 10
    INTERNAL_ADMIN_KEY: str | None = None

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_mode(cls, value):
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"release", "production", "prod"}: return False
            if normalized in {"development", "dev"}: return True
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()
