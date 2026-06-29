import logging
import os
import time
import uuid

import aiohttp
from openai import AsyncOpenAI

from src.config import Settings
from src.services.azure_credential import build_async_credential

logger = logging.getLogger(__name__)

_FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
_TOKEN_REFRESH_BUFFER_SECONDS = 300


def _build_credential(settings: Settings):
    return build_async_credential(settings)


def _build_thread_base_url(data_agent_url: str) -> str:
    if "aiskills" in data_agent_url:
        return (
            data_agent_url.replace("aiskills", "dataagents")
            .removesuffix("/openai")
            .replace("/aiassistant", "/__private/aiassistant")
        )
    return data_agent_url.removesuffix("/openai").replace(
        "/aiassistant", "/__private/aiassistant"
    )


class FabricDataAgentProvider:
    """Provides authenticated access to Microsoft Fabric Data Agents."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._credential = None
        self._token = None
        self._openai_clients: dict[str, AsyncOpenAI] = {}
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def initialize(self) -> None:
        if not self._settings.fabric_enabled:
            logger.info("Fabric Data Agent is not configured; skipping initialization")
            return

        logger.info("Initializing Fabric Data Agent credential provider")
        self._credential = _build_credential(self._settings)
        await self._refresh_token()
        self._ready = True

    async def _refresh_token(self) -> None:
        if self._credential is None:
            raise RuntimeError("Fabric credential is not initialized")

        token = await self._credential.get_token(_FABRIC_SCOPE)
        self._token = token
        logger.debug(
            "Fabric token refreshed",
            extra={"expires_on": token.expires_on},
        )

    async def _ensure_token(self) -> str:
        if self._token is None or self._token.expires_on <= (
            time.time() + _TOKEN_REFRESH_BUFFER_SECONDS
        ):
            await self._refresh_token()
        if self._token is None:
            raise RuntimeError("No valid Fabric authentication token available")
        return self._token.token

    async def get_openai_client(self, data_agent_url: str) -> AsyncOpenAI:
        token = await self._ensure_token()
        cached = self._openai_clients.get(data_agent_url)
        if cached is not None:
            return cached.with_options(
                default_headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "ActivityId": str(uuid.uuid4()),
                }
            )

        client = AsyncOpenAI(
            api_key="fabric-bearer-token",
            base_url=data_agent_url,
            default_query={"api-version": "2024-05-01-preview"},
            default_headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        self._openai_clients[data_agent_url] = client
        return client

    async def get_or_create_thread(
        self,
        data_agent_url: str,
        thread_name: str | None = None,
    ) -> dict:
        resolved_name = thread_name or f"api-thread-{uuid.uuid4()}"
        base_url = _build_thread_base_url(data_agent_url)
        thread_url = f'{base_url}/threads/fabric?tag="{resolved_name}"'
        token = await self._ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "ActivityId": str(uuid.uuid4()),
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(thread_url, headers=headers) as response:
                response.raise_for_status()
                thread = await response.json()

        thread["name"] = resolved_name
        return thread

    async def aclose(self) -> None:
        for client in self._openai_clients.values():
            await client.close()
        self._openai_clients.clear()

        if self._credential is not None:
            close_fn = getattr(self._credential, "close", None)
            if callable(close_fn):
                await close_fn()
            self._credential = None

        self._token = None
        self._ready = False
        logger.info("Closed Fabric Data Agent client")
