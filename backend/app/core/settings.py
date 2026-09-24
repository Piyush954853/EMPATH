from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EMPATH"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    database_url: str = "sqlite:///./empath.db"

    jwt_secret_key: str = "change-this-development-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()