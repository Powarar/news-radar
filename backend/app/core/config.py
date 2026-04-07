from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "news-radar"
    app_env: str = "development"
    debug: bool = True
    secret_key: str

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

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_session_name: str = "newsradar"

    # HuggingFace
    huggingface_api_token: str = ""
    hf_classifier_model: str = "facebook/bart-large-mnli"
    hf_summarizer_model: str = "csebuetnlp/mT5_multilingual_XLSum"


settings = Settings()
