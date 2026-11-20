import pytest
from pydantic import ValidationError

from app.config import Settings


def test_example_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            secret_key="replace-with-a-random-secret-generated-locally",
            cors_origins=[],
        )


def test_generated_secret_is_accepted():
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        secret_key="test-secret-key-123456789012345678901234567890",
        cors_origins=[],
    )
    assert settings.secret_key.get_secret_value().startswith("test-secret-key-")
