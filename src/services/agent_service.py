import json
import logging
from typing import Any

from azure.ai.projects.models import VersionRefIndicator
from azure.core.exceptions import HttpResponseError

from src.config import Settings
from src.schemas.chat import ChatResponse
from src.services.foundry_client import FoundryClientProvider

logger = logging.getLogger(__name__)


class AgentInvocationError(Exception):
    """Raised when the Foundry agent call fails."""


_CONVERSATION_ID_MIN_LENGTH = 8


def _validate_conversation_id(conversation_id: str | None) -> str | None:
    if conversation_id is None:
        return None

    normalized = conversation_id.strip()
    if not normalized:
        return None

    if normalized.isdigit():
        raise AgentInvocationError(
            "Invalid conversation_id. Do not use agent version numbers here. "
            "Omit conversation_id for a new chat, or pass the value returned "
            "from a previous /api/chat response."
        )

    if len(normalized) < _CONVERSATION_ID_MIN_LENGTH:
        raise AgentInvocationError(
            "Invalid conversation_id format. Omit it for a new chat, or pass "
            "the conversation_id returned from a previous /api/chat response."
        )

    return normalized


def _extract_conversation_id(response: Any, fallback: str | None = None) -> str | None:
    conversation = getattr(response, "conversation", None)
    if conversation is None:
        return fallback

    if isinstance(conversation, str):
        return conversation

    conversation_id = getattr(conversation, "id", None)
    if isinstance(conversation_id, str) and conversation_id:
        return conversation_id

    return fallback


class AgentService:
    def __init__(
        self,
        settings: Settings,
        foundry_provider: FoundryClientProvider,
    ) -> None:
        self._settings = settings
        self._foundry_provider = foundry_provider

    async def chat(
        self,
        *,
        message: str,
        conversation_id: str | None = None,
        session_id: str | None = None,
    ) -> ChatResponse:
        protocol = self._settings.agent_protocol.lower()
        logger.info(
            "Invoking agent",
            extra={
                "agent_name": self._settings.agent_name,
                "agent_version": self._settings.agent_version,
                "protocol": protocol,
                "responses_endpoint": self._settings.agent_responses_endpoint,
                "has_conversation_id": conversation_id is not None,
                "has_session_id": session_id is not None,
            },
        )

        if protocol == "responses":
            return await self._invoke_responses(
                message=message,
                conversation_id=conversation_id,
                session_id=session_id,
            )
        if protocol == "invocations":
            return await self._invoke_invocations(
                message=message,
                session_id=session_id,
            )

        raise AgentInvocationError(f"Unsupported agent protocol: {protocol}")

    async def create_session(self, session_id: str | None = None) -> str:
        version = self._settings.agent_version
        if not version:
            raise AgentInvocationError(
                "AGENT_VERSION is required to create hosted-agent sessions"
            )

        try:
            session = await self._foundry_provider.project_client.agents.create_session(
                agent_name=self._settings.agent_name,
                version_indicator=VersionRefIndicator(agent_version=version),
                agent_session_id=session_id,
            )
        except HttpResponseError as exc:
            logger.exception(
                "Failed to create hosted agent session",
                extra={"status_code": exc.status_code},
            )
            raise AgentInvocationError(str(exc.message or exc)) from exc

        created_id = getattr(session, "id", None) or getattr(session, "agent_session_id", None)
        if not created_id and isinstance(session, dict):
            created_id = session.get("id") or session.get("agent_session_id")

        if not created_id:
            raise AgentInvocationError("Session create did not return a session ID")

        logger.info("Created hosted agent session", extra={"session_id": created_id})
        return created_id

    async def delete_session(self, session_id: str) -> None:
        try:
            await self._foundry_provider.project_client.agents.delete_session(
                agent_name=self._settings.agent_name,
                session_id=session_id,
            )
        except HttpResponseError as exc:
            logger.exception(
                "Failed to delete hosted agent session",
                extra={"status_code": exc.status_code, "session_id": session_id},
            )
            raise AgentInvocationError(str(exc.message or exc)) from exc

        logger.info("Deleted hosted agent session", extra={"session_id": session_id})

    async def _invoke_responses(
        self,
        *,
        message: str,
        conversation_id: str | None,
        session_id: str | None,
    ) -> ChatResponse:
        conversation_id = _validate_conversation_id(conversation_id)

        request_kwargs: dict[str, Any] = {"input": message}
        if conversation_id:
            request_kwargs["conversation"] = conversation_id
        if session_id:
            request_kwargs["extra_body"] = {"session": {"id": session_id}}

        try:
            response = await self._foundry_provider.responses_client.responses.create(
                **request_kwargs
            )
        except HttpResponseError as exc:
            logger.exception(
                "Foundry HTTP error during responses invoke",
                extra={"status_code": exc.status_code},
            )
            raise AgentInvocationError(str(exc.message or exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected error during responses invoke")
            raise AgentInvocationError(str(exc)) from exc

        reply = _extract_response_text(response.output)
        result = ChatResponse(
            reply=reply,
            conversation_id=_extract_conversation_id(response, conversation_id),
            session_id=session_id,
        )
        logger.info(
            "Agent response received",
            extra={
                "conversation_id": result.conversation_id,
                "reply_length": len(result.reply),
            },
        )
        return result

    async def _invoke_invocations(
        self,
        *,
        message: str,
        session_id: str | None,
    ) -> ChatResponse:
        if session_id is None:
            session_id = await self.create_session()

        payload = json.dumps({"message": message})
        path = (
            f"/agents/{self._settings.agent_name}/endpoint/protocols/invocations"
        )

        try:
            raw = await self._foundry_provider.responses_client.post(
                path,
                body=payload,
                cast_to=dict,
                options={"headers": {"x-ms-agent-session-id": session_id}},
            )
        except HttpResponseError as exc:
            logger.exception(
                "Foundry HTTP error during invocations invoke",
                extra={"status_code": exc.status_code, "session_id": session_id},
            )
            raise AgentInvocationError(str(exc.message or exc)) from exc
        except Exception as exc:
            logger.exception(
                "Unexpected error during invocations invoke",
                extra={"session_id": session_id},
            )
            raise AgentInvocationError(str(exc)) from exc

        reply = _normalize_invocations_response(raw)
        logger.info(
            "Invocations agent response received",
            extra={"session_id": session_id, "reply_length": len(reply)},
        )
        return ChatResponse(reply=reply, session_id=session_id)


def _extract_response_text(output: Any) -> str:
    if not output:
        return ""

    chunks: list[str] = []
    for item in output:
        content = getattr(item, "content", None)
        if not content:
            continue
        for part in content:
            text = getattr(part, "text", None)
            if text:
                chunks.append(text)
    return "".join(chunks).strip()


def _normalize_invocations_response(raw: Any) -> str:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(parsed, dict):
            for key in ("reply", "message", "output", "response"):
                value = parsed.get(key)
                if isinstance(value, str):
                    return value
            return json.dumps(parsed)
        return str(parsed)
    if isinstance(raw, dict):
        for key in ("reply", "message", "output", "response"):
            value = raw.get(key)
            if isinstance(value, str):
                return value
        return json.dumps(raw)
    return str(raw)
