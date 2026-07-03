import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from src.config import Settings
from src.schemas.fabric.base import FabricAgentResponseBase
from src.schemas.fabric.contract_expiry import ContractExpiryAgentResponse
from src.services.fabric_errors import FabricResponseFormatMismatchError
from src.services.langchain_llm import build_langchain_chat_model

logger = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

DataSource = Literal["fabric_json", "fabric_json_repair", "fabric_default"]

_JSON_REPAIR_PROMPT = """You repair malformed JSON from a Microsoft Fabric Data Agent reply.

Return ONLY a valid JSON object.
- Preserve every value, count, ID, and string exactly as written in the reply.
- Do NOT invent or infer missing business data.
- Fix syntax only: remove // comments, trailing notes, and invalid tokens.
- If the reply is plain text with no JSON object, return {{"answer": "<exact reply text>"}}.

Raw Fabric reply:
{raw_reply}
"""


@dataclass(frozen=True)
class FabricValidationResult:
    structured: FabricAgentResponseBase
    extracted_json: dict[str, Any] | None
    data_source: DataSource


class FabricResponseFormatter(Protocol):
    async def format(
        self,
        *,
        raw_reply: str,
        response_class: type[FabricAgentResponseBase],
        agent_id: str,
    ) -> FabricValidationResult:
        ...


class LangChainJsonFormatRepair:
    """Use LLM only to fix JSON syntax — never to change Fabric business values."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._chain = self._build_chain()

    def _build_chain(self):
        llm = build_langchain_chat_model(self._settings)
        prompt = ChatPromptTemplate.from_messages([("system", _JSON_REPAIR_PROMPT)])
        return prompt | llm | StrOutputParser()

    async def repair(self, raw_reply: str) -> dict[str, Any] | None:
        try:
            repaired_text = await self._chain.ainvoke({"raw_reply": raw_reply})
        except Exception:
            logger.exception("LangChain JSON format repair failed")
            return None
        return _extract_json_object(repaired_text) or _extract_json_object(raw_reply)


class FabricResponseProcessor:
    """Fabric is the source of truth. LLM repairs JSON format only."""

    def __init__(self, settings: Settings) -> None:
        self._json_repair = (
            LangChainJsonFormatRepair(settings)
            if settings.llm_endpoint and settings.llm_deployment
            else None
        )

    async def format(
        self,
        *,
        raw_reply: str,
        response_class: type[FabricAgentResponseBase],
        agent_id: str,
    ) -> FabricValidationResult:
        model_name = response_class.__name__
        data_source: DataSource = "fabric_json"

        payload = _extract_json_object(raw_reply)
        if payload is None and self._json_repair is not None:
            logger.info(
                "Fabric reply is not valid JSON; attempting LLM JSON format repair",
                extra={"agent_id": agent_id, "fabric_raw_reply": raw_reply},
            )
            payload = await self._json_repair.repair(raw_reply)
            if payload is not None:
                data_source = "fabric_json_repair"

        if payload is None:
            payload = {"answer": raw_reply.strip() or "No response from Fabric."}
            data_source = "fabric_default"

        if not payload:
            payload = {"answer": raw_reply.strip() or "No data in Fabric reply."}
            data_source = "fabric_default"

        try:
            structured = _validate_fabric_payload(
                payload=payload,
                response_class=response_class,
                agent_id=agent_id,
                model_name=model_name,
                raw_reply=raw_reply,
            )
        except FabricResponseFormatMismatchError as exc:
            if exc.reason != "schema_mismatch":
                raise
            logger.warning(
                "Fabric JSON incomplete for schema; returning default structured reply",
                extra={
                    "agent_id": agent_id,
                    "response_class": model_name,
                    "fabric_raw_reply": raw_reply,
                    "fabric_extracted_json": payload,
                },
            )
            structured = _build_default_response(
                response_class=response_class,
                payload=payload,
                raw_reply=raw_reply,
            )
            data_source = "fabric_default"

        logger.info(
            "Fabric response processed",
            extra={
                "agent_id": agent_id,
                "response_class": model_name,
                "data_source": data_source,
                "fabric_raw_reply": raw_reply,
                "fabric_extracted_json": payload,
            },
        )
        return FabricValidationResult(
            structured=structured,
            extracted_json=payload,
            data_source=data_source,
        )


# Backward-compatible aliases used in tests and docs.
PydanticJsonFabricResponseFormatter = FabricResponseProcessor
HybridFabricResponseFormatter = FabricResponseProcessor


def build_fabric_response_formatter(settings: Settings) -> FabricResponseFormatter:
    return FabricResponseProcessor(settings)


def _fabric_answer(payload: dict[str, Any], raw_reply: str) -> str:
    if "answer" in payload and payload["answer"] is not None:
        return str(payload["answer"])
    if "reply" in payload and payload["reply"] is not None:
        return str(payload["reply"])
    return raw_reply.strip() or "No response from Fabric."


def _build_default_response(
    *,
    response_class: type[FabricAgentResponseBase],
    payload: dict[str, Any],
    raw_reply: str,
) -> FabricAgentResponseBase:
    answer = _fabric_answer(payload, raw_reply)
    merged = {"answer": answer}

    if issubclass(response_class, ContractExpiryAgentResponse):
        count = (
            payload.get("total_contracts_expiring_next_quarter")
            or payload.get("total_contract_expiring_next_quarter")
            or payload.get("total_contract_expiring_next_quater")
            or payload.get("total_contracts_expiring_next_quater")
        )
        if count is None:
            agreements = payload.get("agreements") or payload.get("agrrements")
            count = len(agreements) if isinstance(agreements, list) else 0
        merged["total_contracts_expiring_next_quarter"] = count
        merged["agreements"] = payload.get("agreements") or payload.get("agrrements") or []
    else:
        for key, value in payload.items():
            if key in {"answer", "reply"}:
                continue
            merged[key] = value

    try:
        return response_class.model_validate(merged)
    except ValidationError:
        minimal: dict[str, Any] = {"answer": answer}
        if issubclass(response_class, ContractExpiryAgentResponse):
            minimal["total_contracts_expiring_next_quarter"] = 0
            minimal["agreements"] = []
        return response_class.model_validate(minimal)


def _validate_fabric_payload(
    *,
    payload: dict[str, Any],
    response_class: type[FabricAgentResponseBase],
    agent_id: str,
    model_name: str,
    raw_reply: str,
) -> FabricAgentResponseBase:
    validation_payload = dict(payload)
    if "answer" not in validation_payload and "reply" in validation_payload:
        validation_payload["answer"] = validation_payload["reply"]

    try:
        return response_class.model_validate(validation_payload)
    except ValidationError as exc:
        raise FabricResponseFormatMismatchError(
            f"Fabric response format mismatch: JSON does not match {model_name}",
            agent_id=agent_id,
            response_class=model_name,
            reason="schema_mismatch",
            validation_errors=exc.errors(),
            fabric_raw_reply=raw_reply,
            fabric_json=payload,
        ) from exc


def _sanitize_fabric_json_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if "//" in line:
            line = line[: line.find("//")].rstrip()
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _extract_json_object(raw_reply: str) -> dict[str, Any] | None:
    candidates: list[str] = [raw_reply.strip()]
    match = _JSON_BLOCK_RE.search(raw_reply)
    if match:
        candidates.insert(0, match.group(1))

    decoder = json.JSONDecoder()
    for candidate in candidates:
        for text in (candidate, _sanitize_fabric_json_text(candidate)):
            start = text.find("{")
            if start == -1:
                continue
            try:
                parsed, _end = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None
