from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "news-radar"
    app_env: str = "development"
    debug: bool = True
    trust_proxy_headers: bool = False
    secret_key: str

    #TTL
    oauth_code_ttl: int

    
    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "newsradar"
    postgres_user: str = "newsradar"
    postgres_password: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Frontend
    frontend_url: str = "http://localhost:5173"

    # CORS
    @property
    def cors_origins(self) -> list[str]:
        if self.debug:
            return [
                "http://localhost:5173",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000",
            ]
        return ["https://news.safonovpavel.space"]

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Telegram
    telegram_bot_token: str = ""
    # Groq
    groq_api_key: str = ""
    groq_api_timeout: int = 30
    # Qdrant
    qdrant_host: str = "qdrant"
    # Embedding service
    embedding_service_url: str = "http://embedding-service:8001"
    embedding_service_timeout: float = 60.0
    embedding_dimension: int = 768


settings = Settings()
