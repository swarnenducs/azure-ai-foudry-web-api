import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from src.config import Settings
from src.services.azure_credential import build_sync_credential

logger = logging.getLogger(__name__)

_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


def normalize_foundry_llm_endpoint(endpoint: str) -> str:
    """Map Foundry URLs (including /responses) to OpenAI v1 chat base URL."""
    base = endpoint.rstrip("/")
    if base.endswith("/responses"):
        base = base[: -len("/responses")]
    if not base.endswith("/openai/v1"):
        if ".services.ai.azure.com" in base and "/openai/" not in base:
            base = f"{base}/openai/v1"
    return base


def is_foundry_v1_llm_endpoint(endpoint: str) -> bool:
    return ".services.ai.azure.com" in endpoint


def build_langchain_chat_model(settings: Settings) -> BaseChatModel:
    if not settings.llm_endpoint or not settings.llm_deployment:
        raise ValueError("LLM_ENDPOINT and LLM_DEPLOYMENT are required")

    credential = build_sync_credential(settings)

    def token_provider() -> str:
        return credential.get_token(_COGNITIVE_SCOPE).token

    if is_foundry_v1_llm_endpoint(settings.llm_endpoint):
        base_url = normalize_foundry_llm_endpoint(settings.llm_endpoint)
        logger.info(
            "Using Foundry OpenAI v1 chat model",
            extra={"base_url": base_url, "model": settings.llm_deployment},
        )
        return ChatOpenAI(
            model=settings.llm_deployment,
            base_url=base_url,
            api_key=token_provider(),
            temperature=0,
        )

    return AzureChatOpenAI(
        azure_endpoint=settings.llm_endpoint.rstrip("/"),
        azure_deployment=settings.llm_deployment,
        api_version=settings.llm_api_version,
        azure_ad_token_provider=token_provider,
        temperature=0,
    )
