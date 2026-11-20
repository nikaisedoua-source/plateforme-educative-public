from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Plateforme éducative API"
    database_url: str = Field(min_length=1)
    secret_key: SecretStr = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    cors_origins: list[str] = Field(default_factory=list)
    document_storage_path: str = Field(default="./data/documents")
    ocr_command: str = Field(default="./bin/ocr-vision")
    max_upload_mb: int = Field(default=200, ge=1, le=2000)
    # Modèle local (Ollama) qui relit l'image des exercices pour réécrire les formules en LaTeX.
    ollama_url: str = Field(default="http://localhost:11434")
    ollama_vision_model: str = Field(default="qwen2.5vl:7b")

    @field_validator("secret_key")
    @classmethod
    def reject_example_secret(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().lower().startswith("replace-"):
            raise ValueError("Generate a private SECRET_KEY before starting the API")
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
