import pytest

from src.config import Settings
from src.services.azure_credential import describe_credential_choice, resolve_credential_mode


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    monkeypatch.delenv("AZURE_CREDENTIAL_MODE", raising=False)
    return Settings()


def test_auto_mode_uses_default_locally(settings: Settings) -> None:
    assert resolve_credential_mode(settings) == "default"
    details = describe_credential_choice(settings)
    assert details["credential"] == "DefaultAzureCredential"


def test_website_site_name_forces_managed_identity(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBSITE_SITE_NAME", "my-web-app")
    assert resolve_credential_mode(settings) == "managed"


def test_explicit_default_overrides_website_site_name(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBSITE_SITE_NAME", "my-web-app")
    monkeypatch.setenv("AZURE_CREDENTIAL_MODE", "default")
    assert resolve_credential_mode(settings) == "default"


def test_production_uses_managed_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
    settings = Settings()
    assert resolve_credential_mode(settings) == "managed"
