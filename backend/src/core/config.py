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
    OLLAMA_GENERATION_MODEL: str = "qwen2.5:3b"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_CONNECT_TIMEOUT_SECONDS: float = 5.0
    OLLAMA_GENERATION_TIMEOUT_SECONDS: float = 180.0
    EMBEDDING_PROVIDER: str = "ollama"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_EMBEDDING_TIMEOUT_SECONDS: float = 60.0
    OLLAMA_HEALTH_TIMEOUT_SECONDS: float = 1.0
    VECTOR_DB: str = "chromadb"
    CHROMA_COLLECTION: str = "documents_ollama_nomic_embed_text"
    CHROMA_DB_PATH: str = "./chroma_db"
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.70
    ENABLE_WEB_SEARCH: bool = True
    SEARCH_PROVIDER: str = "bing_rss"
    MAX_WEB_RESULTS: int = 5
    WEB_CACHE_ENABLED: bool = True
    WEB_CACHE_DIR: str = "./data/web_cache"
    WEB_STABLE_CACHE_DAYS: int = 30
    WEB_CURRENT_CACHE_HOURS: int = 24
    CHAT_MIN_GROUNDING_CONFIDENCE: float = 0.70
    ROADMAP_MIN_GROUNDING_CONFIDENCE: float = 0.78
    MAX_CHAT_HISTORY: int = 10
    INTERNAL_ADMIN_KEY: str | None = None
    CA_DAILY_MAX_RESULTS: int = 10
    CA_DAILY_LANGUAGE: str = "english"
    CA_DAILY_TIME: str = "07:00"
    CURRENT_AFFAIRS_CONTENT_MODE: str = "private_local"
    CURRENT_AFFAIRS_AUTO_INGEST: bool = False
    CURRENT_AFFAIRS_INTERVAL_HOURS: int = 6
    CURRENT_AFFAIRS_STARTUP_MAX_AGE_HOURS: int = 12
    CURRENT_AFFAIRS_TIMEZONE: str = "Asia/Kolkata"
    CURRENT_AFFAIRS_REQUEST_TIMEOUT_SECONDS: float = 15.0
    CURRENT_AFFAIRS_MAX_RESPONSE_BYTES: int = 5242880
    PIB_RSS_URL: str = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1"
    RBI_RSS_URL: str = "https://rbi.org.in/Scripts/rss.aspx"
    MEA_RSS_URL: str = "https://www.mea.gov.in/rss-feeds.htm"
    MEA_PRESS_RELEASES_URL: str = "https://www.mea.gov.in/press-releases"
    CURRENT_AFFAIRS_ALLOWED_DOMAINS: list[str] = [
        "pib.gov.in", "www.pib.gov.in",
        "rbi.org.in", "www.rbi.org.in",
        "mea.gov.in", "www.mea.gov.in"
    ]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_mode(cls, value):
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"release", "production", "prod"}: return False
            if normalized in {"development", "dev"}: return True
        return value

    @field_validator("OLLAMA_BASE_URL", "OLLAMA_GENERATION_MODEL", "OLLAMA_EMBEDDING_MODEL", mode="before")
    @classmethod
    def normalize_ollama_setting(cls, value):
        return value.strip().strip('"\'') if isinstance(value, str) else value

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


settings = Settings()
