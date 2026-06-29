import json
import logging
import re
from typing import Protocol

from pydantic import ValidationError

from src.schemas.fabric.base import FabricAgentResponseBase
from src.services.fabric_errors import FabricResponseFormatMismatchError

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


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
    """Parse Fabric JSON into the per-agent Pydantic model from agent_registry.yaml."""

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
