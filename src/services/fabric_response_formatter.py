import json
import logging
import re
from typing import Any, Protocol

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import AzureChatOpenAI
from pydantic import ValidationError

from src.config import Settings
from src.schemas.fabric.base import FabricAgentResponseBase
from src.services.azure_credential import build_sync_credential
from src.services.fabric_errors import FabricResponseFormatMismatchError

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

_STRUCTURE_PROMPT = """You convert a Microsoft Fabric Data Agent reply into structured data.

The target schema is `{response_class}`. Extract every required field from the raw reply.
- If the reply contains JSON, use those values.
- Ignore trailing notes such as file-generation messages.
- Preserve agreement lists, counts, and numeric values exactly.
- Populate `answer` with a short natural-language summary when it is missing.

Raw Fabric reply:
{raw_reply}
"""


class FabricResponseFormatter(Protocol):
    async def format(
        self,
        *,
        raw_reply: str,
        response_class: type[FabricAgentResponseBase],
        agent_id: str,
    ) -> FabricAgentResponseBase:
        ...


class PydanticJsonFabricResponseFormatter:
    """Parse Fabric JSON directly into the per-agent Pydantic model."""

    async def format(
        self,
        *,
        raw_reply: str,
        response_class: type[FabricAgentResponseBase],
        agent_id: str,
    ) -> FabricAgentResponseBase:
        model_name = response_class.__name__
        payload = _extract_json_object(raw_reply)
        if payload is None:
            logger.error(
                "Fabric raw reply is not valid JSON",
                extra={
                    "agent_id": agent_id,
                    "response_class": model_name,
                    "fabric_raw_reply": raw_reply,
                },
            )
            raise FabricResponseFormatMismatchError(
                f"Fabric response format mismatch: expected JSON for {model_name}",
                agent_id=agent_id,
                response_class=model_name,
                reason="invalid_json",
            )

        if "answer" not in payload and "reply" in payload:
            payload["answer"] = payload.pop("reply")

        try:
            result = response_class.model_validate(payload)
        except ValidationError as exc:
            logger.error(
                "Fabric JSON failed Pydantic validation",
                extra={
                    "agent_id": agent_id,
                    "response_class": model_name,
                    "fabric_raw_reply": raw_reply,
                    "fabric_extracted_json": payload,
                    "validation_errors": exc.errors(),
                },
            )
            raise FabricResponseFormatMismatchError(
                f"Fabric response format mismatch: JSON does not match {model_name}",
                agent_id=agent_id,
                response_class=model_name,
                reason="schema_mismatch",
                validation_errors=exc.errors(),
            ) from exc

        logger.info(
            "Validated Fabric JSON response",
            extra={
                "response_class": model_name,
                "agent_id": agent_id,
                "fabric_extracted_json": payload,
                "fabric_structured_data": result.model_dump(),
            },
        )
        return result


class LangChainFabricResponseFormatter:
    """Use LangChain structured output to map Fabric text into the agent Pydantic model."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._credential = build_sync_credential(settings)
        self._chains: dict[str, Runnable] = {}
        self._llm_config()

    def _llm_config(self) -> tuple[str, str, str]:
        endpoint = self._settings.llm_endpoint
        deployment = self._settings.llm_deployment
        if not endpoint or not deployment:
            raise ValueError(
                "LLM_ENDPOINT and LLM_DEPLOYMENT are required for LangChain structured output"
            )
        return endpoint, deployment, self._settings.llm_api_version

    def _token_provider(self) -> str:
        return self._credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        ).token

    def _get_chain(self, response_class: type[FabricAgentResponseBase]) -> Runnable:
        cache_key = response_class.__name__
        cached = self._chains.get(cache_key)
        if cached is not None:
            return cached

        endpoint, deployment, api_version = self._llm_config()
        llm = AzureChatOpenAI(
            azure_endpoint=endpoint.rstrip("/"),
            azure_deployment=deployment,
            api_version=api_version,
            azure_ad_token_provider=self._token_provider,
            temperature=0,
        )
        structured_llm = llm.with_structured_output(response_class)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _STRUCTURE_PROMPT),
            ]
        )
        chain = prompt | structured_llm
        self._chains[cache_key] = chain
        return chain

    async def format(
        self,
        *,
        raw_reply: str,
        response_class: type[FabricAgentResponseBase],
        agent_id: str,
    ) -> FabricAgentResponseBase:
        model_name = response_class.__name__
        chain = self._get_chain(response_class)

        try:
            result = await chain.ainvoke(
                {"raw_reply": raw_reply, "response_class": model_name}
            )
        except Exception as exc:
            logger.error(
                "LangChain structured output failed for Fabric reply",
                extra={
                    "agent_id": agent_id,
                    "response_class": model_name,
                    "fabric_raw_reply": raw_reply,
                },
            )
            raise FabricResponseFormatMismatchError(
                f"Fabric response format mismatch: could not structure reply as {model_name}",
                agent_id=agent_id,
                response_class=model_name,
                reason="structured_output_failed",
            ) from exc

        if isinstance(result, response_class):
            structured = result
        else:
            try:
                structured = response_class.model_validate(result)
            except ValidationError as exc:
                raise FabricResponseFormatMismatchError(
                    f"Fabric response format mismatch: structured output does not match {model_name}",
                    agent_id=agent_id,
                    response_class=model_name,
                    reason="schema_mismatch",
                    validation_errors=exc.errors(),
                ) from exc

        logger.info(
            "LangChain structured Fabric response",
            extra={
                "agent_id": agent_id,
                "response_class": model_name,
                "fabric_raw_reply": raw_reply,
                "fabric_structured_data": structured.model_dump(),
            },
        )
        return structured


def build_fabric_response_formatter(settings: Settings) -> FabricResponseFormatter:
    return LangChainFabricResponseFormatter(settings)


def _extract_json_object(raw_reply: str) -> dict | None:
    candidates: list[str] = [raw_reply.strip()]
    match = _JSON_BLOCK_RE.search(raw_reply)
    if match:
        candidates.insert(0, match.group(1))

    decoder = json.JSONDecoder()
    for candidate in candidates:
        start = candidate.find("{")
        if start == -1:
            continue
        try:
            parsed, _end = decoder.raw_decode(candidate[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
