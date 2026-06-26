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
            raise FabricResponseFormatMismatchError(
                f"Fabric response format mismatch: JSON does not match {model_name}",
                agent_id=agent_id,
                response_class=model_name,
                reason="schema_mismatch",
                validation_errors=exc.errors(),
            ) from exc

        logger.debug(
            "Validated Fabric JSON response",
            extra={"response_class": model_name, "agent_id": agent_id},
        )
        return result


def _extract_json_object(raw_reply: str) -> dict | None:
    candidates: list[str] = [raw_reply.strip()]
    match = _JSON_BLOCK_RE.search(raw_reply)
    if match:
        candidates.insert(0, match.group(1))

    for candidate in candidates:
        if not candidate.startswith("{"):
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
