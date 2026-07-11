from pydantic_settings import BaseSettings, SettingsConfigDict


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
    MAX_CHAT_HISTORY: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()