from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Reservas API", validation_alias=AliasChoices("APP_NAME"))
    app_version: str = Field(default="0.1.0", validation_alias=AliasChoices("APP_VERSION"))
    app_env: str = Field(default="local", validation_alias=AliasChoices("APP_ENV"))
    app_debug: bool = Field(default=True, validation_alias=AliasChoices("APP_DEBUG", "DEBUG"))
    api_host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("API_HOST"))
    api_port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT"))
    cors_allowed_origins: str = Field(
        default="",
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS"),
    )

    database_url: str = Field(default="", validation_alias=AliasChoices("DATABASE_URL"))
    mysql_host: str = Field(default="localhost", validation_alias=AliasChoices("MYSQL_HOST"))
    mysql_port: int = Field(default=3306, validation_alias=AliasChoices("MYSQL_PORT"))
    mysql_user: str = Field(default="root", validation_alias=AliasChoices("MYSQL_USER"))
    mysql_password: str = Field(default="", validation_alias=AliasChoices("MYSQL_PASSWORD"))
    mysql_database: str = Field(default="reservas", validation_alias=AliasChoices("MYSQL_DATABASE"))
    db_pool_size: int = Field(default=10, validation_alias=AliasChoices("DB_POOL_SIZE"))
    db_max_overflow: int = Field(default=20, validation_alias=AliasChoices("DB_MAX_OVERFLOW"))
    db_pool_timeout_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices("DB_POOL_TIMEOUT_SECONDS"),
    )
    db_pool_recycle_seconds: int = Field(
        default=1800,
        validation_alias=AliasChoices("DB_POOL_RECYCLE_SECONDS"),
    )

    stripe_api_base_url: str = Field(
        default="https://api.stripe.com", validation_alias=AliasChoices("STRIPE_API_BASE_URL")
    )
    stripe_api_key: str = Field(default="", validation_alias=AliasChoices("STRIPE_API_KEY"))
    provider_api_base_url: str = Field(
        default="https://provider.example.com",
        validation_alias=AliasChoices("PROVIDER_API_BASE_URL"),
    )
    provider_api_key: str = Field(default="", validation_alias=AliasChoices("PROVIDER_API_KEY"))

    external_api_timeout_seconds: int = Field(
        default=10,
        validation_alias=AliasChoices("EXTERNAL_API_TIMEOUT_SECONDS", "HTTP_TIMEOUT_SECONDS"),
    )
    force_https: bool = Field(default=False, validation_alias=AliasChoices("FORCE_HTTPS"))
    tls_cert_file: str = Field(default="", validation_alias=AliasChoices("TLS_CERT_FILE"))
    tls_key_file: str = Field(default="", validation_alias=AliasChoices("TLS_KEY_FILE"))
    http_max_connections: int = Field(default=100, validation_alias=AliasChoices("HTTP_MAX_CONNECTIONS"))
    rate_limit_requests_per_minute: int = Field(
        default=120,
        validation_alias=AliasChoices("RATE_LIMIT_REQUESTS_PER_MINUTE"),
    )
    rate_limit_reservations_per_minute: int = Field(
        default=30,
        validation_alias=AliasChoices("RATE_LIMIT_RESERVATIONS_PER_MINUTE"),
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
            "CIRCUIT_BREAKER_THRESHOLD",
        ),
    )
    circuit_breaker_recovery_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "CIRCUIT_BREAKER_RECOVERY_SECONDS",
            "CIRCUIT_BREAKER_TIMEOUT",
        ),
    )
    retry_max_attempts: int = Field(default=3, validation_alias=AliasChoices("RETRY_MAX_ATTEMPTS"))

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [value.strip() for value in self.cors_allowed_origins.split(",") if value.strip()]


settings = Settings()
