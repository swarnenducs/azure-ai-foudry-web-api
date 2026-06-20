from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Foundry Agent API"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")

    azure_ai_project_endpoint: str = Field(
        ...,
        alias="AZURE_AI_PROJECT_ENDPOINT",
        description="Azure AI Foundry project endpoint URL",
    )
    agent_name: str = Field(..., alias="AGENT_NAME")
    agent_version: str | None = Field(default="1", alias="AGENT_VERSION")
    agent_protocol: str = Field(default="responses", alias="AGENT_PROTOCOL")

    api_key: SecretStr | None = Field(
        default=None,
        alias="API_KEY",
        description="Optional shared secret for protecting /api routes",
    )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def agent_openai_base_url(self) -> str:
        base = self.azure_ai_project_endpoint.rstrip("/")
        return f"{base}/agents/{self.agent_name}/endpoint/protocols/openai"

    @property
    def agent_responses_endpoint(self) -> str:
        return f"{self.agent_openai_base_url}/responses"


@lru_cache
def get_settings() -> Settings:
    return Settings()
