from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "news-radar"
    app_env: str = "development"
    debug: bool = True
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
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_session_name: str = "newsradar"

    # HuggingFace (deprecated, kept for compatibility)
    huggingface_api_token: str = ""
    hf_classifier_model_url: str = ""
    hf_summarizer_model_url: str = ""

    # Groq
    groq_api_key: str = ""
    groq_api_timeout: int = 30


settings = Settings()
