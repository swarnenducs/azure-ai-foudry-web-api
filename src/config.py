from functools import lru_cache
import os
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Azure Portal / some hosts use hyphens; pydantic expects underscores (Field aliases).
_ENV_UNDERSCORE_ALIASES: dict[str, str] = {
    "AZURE-AI-PROJECT-ENDPOINT": "AZURE_AI_PROJECT_ENDPOINT",
    "AGENT-NAME": "AGENT_NAME",
    "AGENT-VERSION": "AGENT_VERSION",
    "AGENT-PROTOCOL": "AGENT_PROTOCOL",
    "API-KEY": "API_KEY",
    "FABRIC-TENANT-ID": "FABRIC_TENANT_ID",
    "FABRIC-DATA-AGENT-URL": "FABRIC_DATA_AGENT_URL",
    "FABRIC-QUERY-TIMEOUT": "FABRIC_QUERY_TIMEOUT",
    "AGENT-REGISTRY-PATH": "AGENT_REGISTRY_PATH",
    "FABRIC-ROUTING-MODE": "FABRIC_ROUTING_MODE",
    "LLM-ENDPOINT": "LLM_ENDPOINT",
    "LLM-DEPLOYMENT": "LLM_DEPLOYMENT",
    "LLM-API-VERSION": "LLM_API_VERSION",
    "ROUTING-LLM-ENDPOINT": "LLM_ENDPOINT",
    "ROUTING-LLM-DEPLOYMENT": "LLM_DEPLOYMENT",
    "ROUTING-LLM-API-VERSION": "LLM_API_VERSION",
    "FABRIC-FORMATTER-LLM-ENDPOINT": "LLM_ENDPOINT",
    "FABRIC-FORMATTER-LLM-DEPLOYMENT": "LLM_DEPLOYMENT",
    "FABRIC-FORMATTER-LLM-API-VERSION": "LLM_API_VERSION",
    "LOG-LEVEL": "LOG_LEVEL",
    "LOG-JSON": "LOG_JSON",
}


def _apply_env_alias_fallbacks() -> None:
    """Map hyphenated OS env names to underscore aliases expected by Settings."""
    for hyphen_key, underscore_key in _ENV_UNDERSCORE_ALIASES.items():
        if hyphen_key in os.environ and not os.getenv(underscore_key):
            os.environ[underscore_key] = os.environ[hyphen_key]


def project_root() -> Path:
    """Repository root (parent of ``src/``)."""
    return Path(__file__).resolve().parent.parent


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def should_load_dotenv() -> bool:
    """Return whether to load values from a ``.env`` file.

    - **Local:** load ``.env`` from the project root when the file exists.
    - **Azure App Service:** use Application Settings (OS env) only.
    - **Override:** set ``LOAD_DOTENV=true|false`` to force behavior.
    """
    explicit = os.getenv("LOAD_DOTENV")
    if explicit is not None:
        return _parse_bool(explicit)
    if os.getenv("WEBSITE_SITE_NAME"):
        return False
    return True


def resolve_dotenv_path() -> Path | None:
    if not should_load_dotenv():
        return None
    dotenv = project_root() / ".env"
    return dotenv if dotenv.is_file() else None


def resolve_project_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str((project_root() / candidate).resolve())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
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
        validation_alias=AliasChoices(
            "AZURE_AI_PROJECT_ENDPOINT",
            "AZURE-AI-PROJECT-ENDPOINT",
        ),
        description="Azure AI Foundry project endpoint URL",
    )
    agent_name: str = Field(
        ...,
        validation_alias=AliasChoices("AGENT_NAME", "AGENT-NAME"),
    )
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
    llm_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LLM_ENDPOINT",
            "ROUTING_LLM_ENDPOINT",
            "FABRIC_FORMATTER_LLM_ENDPOINT",
        ),
        description="Azure OpenAI endpoint for LangChain (routing, structured output, etc.)",
    )
    llm_deployment: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LLM_DEPLOYMENT",
            "ROUTING_LLM_DEPLOYMENT",
            "FABRIC_FORMATTER_LLM_DEPLOYMENT",
        ),
        description="Azure OpenAI deployment name",
    )
    llm_api_version: str = Field(
        default="2024-10-21",
        validation_alias=AliasChoices(
            "LLM_API_VERSION",
            "ROUTING_LLM_API_VERSION",
            "FABRIC_FORMATTER_LLM_API_VERSION",
        ),
    )

    @field_validator("agent_registry_path", mode="before")
    @classmethod
    def _normalize_registry_path(cls, value: object) -> object:
        if isinstance(value, str) and value:
            return resolve_project_path(value)
        return value

    @property
    def fabric_enabled(self) -> bool:
        if Path(self.agent_registry_path).is_file():
            return True
        return bool(self.fabric_data_agent_url)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def loads_dotenv(self) -> bool:
        return resolve_dotenv_path() is not None

    @property
    def agent_openai_base_url(self) -> str:
        base = self.azure_ai_project_endpoint.rstrip("/")
        return f"{base}/agents/{self.agent_name}/endpoint/protocols/openai"

    @property
    def agent_responses_endpoint(self) -> str:
        return f"{self.agent_openai_base_url}/responses"


@lru_cache
def get_settings() -> Settings:
    _apply_env_alias_fallbacks()
    dotenv = resolve_dotenv_path()
    if dotenv is not None:
        return Settings(_env_file=dotenv)
    return Settings()
