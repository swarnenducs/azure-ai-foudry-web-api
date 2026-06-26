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

    fabric_tenant_id: str | None = Field(
        default=None,
        alias="FABRIC_TENANT_ID",
        description="Azure Entra tenant ID for Fabric Data Agent auth",
    )
    fabric_data_agent_url: str | None = Field(
        default=None,
        alias="FABRIC_DATA_AGENT_URL",
        description="Legacy single Fabric Data Agent URL (use agent_registry.yaml instead)",
    )
    fabric_query_timeout: int = Field(
        default=120,
        alias="FABRIC_QUERY_TIMEOUT",
        description="Max seconds to wait for a Fabric Data Agent response",
    )
    agent_registry_path: str = Field(
        default="config/agent_registry.yaml",
        alias="AGENT_REGISTRY_PATH",
        description="YAML/JSON file mapping prompt_id to agent_id and agent catalog",
    )
    fabric_routing_mode: str | None = Field(
        default=None,
        alias="FABRIC_ROUTING_MODE",
        description="Override routing mode: rule, llm, or hybrid",
    )
    routing_llm_endpoint: str | None = Field(
        default=None,
        alias="ROUTING_LLM_ENDPOINT",
        description="Azure OpenAI endpoint for LLM-based agent routing",
    )
    routing_llm_deployment: str | None = Field(
        default=None,
        alias="ROUTING_LLM_DEPLOYMENT",
        description="Azure OpenAI deployment name for routing LLM",
    )
    routing_llm_api_version: str = Field(
        default="2024-10-21",
        alias="ROUTING_LLM_API_VERSION",
    )

    @property
    def fabric_enabled(self) -> bool:
        from pathlib import Path

        if Path(self.agent_registry_path).is_file():
            return True
        return bool(self.fabric_data_agent_url)

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
