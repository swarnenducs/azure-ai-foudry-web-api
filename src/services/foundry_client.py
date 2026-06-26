import logging
import os

from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential, ManagedIdentityCredential
from openai import AsyncOpenAI

from src.config import Settings

logger = logging.getLogger(__name__)


def _build_credential(settings: Settings):
    if settings.is_production or os.getenv("WEBSITE_SITE_NAME"):
        client_id = os.getenv("AZURE_CLIENT_ID")
        logger.info(
            "Using managed identity credential",
            extra={"user_assigned": bool(client_id)},
        )
        if client_id:
            return ManagedIdentityCredential(client_id=client_id)
        return ManagedIdentityCredential()

    logger.info("Using DefaultAzureCredential for local development")
    return DefaultAzureCredential()


class FoundryClientProvider:
    """Provides shared async Foundry and OpenAI clients for the app lifetime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._project_client: AIProjectClient | None = None
        self._responses_client: AsyncOpenAI | None = None
        self._credential = None

    @property
    def is_ready(self) -> bool:
        return self._responses_client is not None

    @property
    def project_client(self) -> AIProjectClient:
        if self._project_client is None:
            raise RuntimeError("Foundry client is not initialized")
        return self._project_client

    @property
    def responses_client(self) -> AsyncOpenAI:
        if self._responses_client is None:
            raise RuntimeError("Foundry responses client is not initialized")
        return self._responses_client

    async def initialize(self) -> None:
        logger.info(
            "Initializing Foundry project client",
            extra={
                "endpoint": self._settings.azure_ai_project_endpoint,
                "agent_name": self._settings.agent_name,
                "agent_version": self._settings.agent_version,
                "responses_endpoint": self._settings.agent_responses_endpoint,
            },
        )
        self._credential = _build_credential(self._settings)
        self._project_client = AIProjectClient(
            endpoint=self._settings.azure_ai_project_endpoint,
            credential=self._credential,
            allow_preview=True,
        )

        openai_kwargs: dict[str, object] = {}
        if self._settings.agent_version:
            openai_kwargs["default_query"] = {
                "agent_version": self._settings.agent_version,
            }

        self._responses_client = self._project_client.get_openai_client(
            agent_name=self._settings.agent_name,
            **openai_kwargs,
        )

    async def aclose(self) -> None:
        if self._responses_client is not None:
            await self._responses_client.close()
            self._responses_client = None

        if self._project_client is not None:
            await self._project_client.close()
            self._project_client = None

        if self._credential is not None:
            close_fn = getattr(self._credential, "close", None)
            if callable(close_fn):
                await close_fn()
            self._credential = None

        logger.info("Closed Foundry clients")
