import json
import logging
import os
import re
from typing import Protocol

from langchain_openai import AzureChatOpenAI

from src.config import Settings
from src.schemas.fabric.base import FabricAgentResponseBase

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _build_formatting_credential(settings: Settings):
    if settings.is_production or os.getenv("WEBSITE_SITE_NAME"):
        client_id = os.getenv("AZURE_CLIENT_ID")
        from azure.identity import ManagedIdentityCredential

        if client_id:
            return ManagedIdentityCredential(client_id=client_id)
        return ManagedIdentityCredential()

    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


class FabricResponseFormatter(Protocol):
    async def format(
        self,
        *,
        raw_reply: str,
        response_class: type[FabricAgentResponseBase],
    ) -> FabricAgentResponseBase:
        ...


class LangChainFabricResponseFormatter:
    """Parse Fabric agent text into the agent-specific Pydantic response model."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm = self._build_llm(settings)

    def _build_llm(self, settings: Settings) -> AzureChatOpenAI | None:
        if not settings.routing_llm_endpoint or not settings.routing_llm_deployment:
            return None

        credential = _build_formatting_credential(settings)

        def token_provider() -> str:
            return credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            ).token

        return AzureChatOpenAI(
            azure_endpoint=settings.routing_llm_endpoint.rstrip("/"),
            azure_deployment=settings.routing_llm_deployment,
            api_version=settings.routing_llm_api_version,
            azure_ad_token_provider=token_provider,
            temperature=0,
        )

    async def format(
        self,
        *,
        raw_reply: str,
        response_class: type[FabricAgentResponseBase],
    ) -> FabricAgentResponseBase:
        parsed = self._try_parse_json(raw_reply, response_class)
        if parsed is not None:
            return parsed

        if self._llm is None:
            logger.warning(
                "No routing LLM configured; returning base fields only",
                extra={"response_class": response_class.__name__},
            )
            return response_class(answer=raw_reply)

        structured_llm = self._llm.with_structured_output(response_class)
        prompt = (
            "Extract structured fields from this Fabric Data Agent response. "
            "Use the full response text for the answer field when needed.\n\n"
            f"Agent response:\n{raw_reply}"
        )
        result = await structured_llm.ainvoke(prompt)
        if isinstance(result, response_class):
            return result
        return response_class.model_validate(result)

    def _try_parse_json(
        self,
        raw_reply: str,
        response_class: type[FabricAgentResponseBase],
    ) -> FabricAgentResponseBase | None:
        candidates = [raw_reply.strip()]
        match = _JSON_BLOCK_RE.search(raw_reply)
        if match:
            candidates.insert(0, match.group(1))

        for candidate in candidates:
            if not candidate.startswith("{"):
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                if "answer" not in payload and "reply" in payload:
                    payload["answer"] = payload.pop("reply")
                try:
                    return response_class.model_validate(payload)
                except Exception:
                    continue
        return None
