from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Manages application settings and environment variables.
    """

    DATABASE_URL: str
    CLERK_WEBHOOK_SECRET: str
    CLERK_ISSUER_URL: str
    ADMIN_SECRET_KEY: str

    # Pydantic will automatically try to load these variables from:
    # 1. The system's environment variables (which is how pytest-env works).
    # 2. A file named '.env' in the current working directory (for local dev).
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra variables in the .env file
    )


settings = Settings()
