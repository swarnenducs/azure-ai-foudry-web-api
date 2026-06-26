import asyncio
import logging
import time
from typing import Any

from src.config import Settings
from src.routing.protocols import AgentRouter
from src.routing.registry import AgentRegistry
from src.schemas.fabric_data_agent import FabricDataAgentResponse
from src.services.fabric_data_agent_provider import FabricDataAgentProvider
from src.services.fabric_errors import (
    FabricNotFoundError,
    FabricResponseFormatMismatchError,
    is_fabric_upstream_not_found,
)
from src.services.fabric_response_formatter import PydanticJsonFabricResponseFormatter

logger = logging.getLogger(__name__)


class FabricDataAgentInvocationError(Exception):
    """Raised when the Fabric Data Agent call fails."""


def resolve_thread_scope(
    *,
    prompt_id: str | None,
    thread_name: str | None,
    agent_id: str,
) -> str | None:
    """Return the Fabric thread tag, or None to force a new thread.

    Requests with prompt_id always start a new thread.
    thread_name is only honored when prompt_id is absent.
    (Future: query + thread_id continuation is not implemented yet.)
    """
    if prompt_id:
        return None
    if thread_name:
        return f"{agent_id}:{thread_name}"
    return None


class FabricDataAgentService:
    def __init__(
        self,
        settings: Settings,
        provider: FabricDataAgentProvider,
        registry: AgentRegistry,
        router: AgentRouter,
        response_formatter: PydanticJsonFabricResponseFormatter,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._registry = registry
        self._router = router
        self._response_formatter = response_formatter

    async def ask(
        self,
        *,
        message: str,
        prompt_id: str | None = None,
        thread_name: str | None = None,
    ) -> FabricDataAgentResponse:
        question = message.strip()
        if not question:
            raise FabricDataAgentInvocationError("Message cannot be empty")

        decision = await self._router.resolve(message=question, prompt_id=prompt_id)
        if decision is None:
            if prompt_id:
                raise FabricNotFoundError(
                    f"Fabric agent not found: unknown prompt_id '{prompt_id}'",
                    reason="unknown_prompt_id",
                    prompt_id=prompt_id,
                )
            raise FabricNotFoundError(
                "Fabric agent not found: could not resolve agent from request. "
                "Provide a valid prompt_id or enable llm/hybrid routing.",
                reason="agent_unresolved",
            )

        agent = self._registry.get_agent(decision.agent_id)
        scoped_thread_name = resolve_thread_scope(
            prompt_id=prompt_id,
            thread_name=thread_name,
            agent_id=decision.agent_id,
        )
        timeout = self._settings.fabric_query_timeout

        logger.info(
            "Invoking Fabric Data Agent",
            extra={
                "agent_id": agent.id,
                "routing_method": decision.method,
                "prompt_id": prompt_id,
                "message_length": len(question),
                "has_thread_name": thread_name is not None,
                "timeout": timeout,
            },
        )

        try:
            client = await self._provider.get_openai_client(agent.url)
            assistant = await client.beta.assistants.create(model="not used")
            thread = await self._provider.get_or_create_thread(
                agent.url,
                scoped_thread_name,
            )

            await client.beta.threads.messages.create(
                thread_id=thread["id"],
                role="user",
                content=question,
            )

            run = await client.beta.threads.runs.create(
                thread_id=thread["id"],
                assistant_id=assistant.id,
            )

            start_time = time.time()
            while run.status in {"queued", "in_progress"}:
                if time.time() - start_time > timeout:
                    raise FabricDataAgentInvocationError(
                        f"Fabric Data Agent request timed out after {timeout} seconds"
                    )
                await asyncio.sleep(2)
                run = await client.beta.threads.runs.retrieve(
                    thread_id=thread["id"],
                    run_id=run.id,
                )

            if run.status != "completed":
                raise FabricDataAgentInvocationError(
                    f"Fabric Data Agent run finished with status: {run.status}"
                )

            messages = await client.beta.threads.messages.list(
                thread_id=thread["id"],
                order="asc",
            )
            reply = _extract_assistant_reply(messages)

            try:
                structured = await self._response_formatter.format(
                    raw_reply=reply,
                    response_class=agent.response_class,
                    agent_id=agent.id,
                )
            except FabricResponseFormatMismatchError:
                raise

            try:
                await client.beta.threads.delete(thread_id=thread["id"])
            except Exception:
                logger.warning(
                    "Failed to delete Fabric Data Agent thread after response",
                    extra={"thread_id": thread["id"], "agent_id": agent.id},
                )

            result = FabricDataAgentResponse(
                reply=reply,
                agent_id=agent.id,
                response_class=agent.response_class.__name__,
                routing_method=decision.method,
                data=structured.model_dump(),
                prompt_id=prompt_id,
                thread_name=thread_name,
            )
            logger.info(
                "Fabric Data Agent response received",
                extra={
                    "agent_id": result.agent_id,
                    "routing_method": result.routing_method,
                    "thread_name": result.thread_name,
                    "reply_length": len(result.reply),
                },
            )
            return result
        except FabricResponseFormatMismatchError:
            raise
        except FabricNotFoundError:
            raise
        except FabricDataAgentInvocationError:
            raise
        except Exception as exc:
            if is_fabric_upstream_not_found(exc):
                raise FabricNotFoundError(
                    f"Fabric agent not found at configured URL for '{agent.id}'",
                    reason="fabric_resource_not_found",
                    agent_id=agent.id,
                ) from exc
            logger.exception("Unexpected error during Fabric Data Agent invoke")
            raise FabricDataAgentInvocationError(str(exc)) from exc


def _extract_assistant_reply(messages: Any) -> str:
    responses: list[str] = []
    for msg in messages.data:
        if msg.role != "assistant":
            continue
        for content in msg.content:
            text = getattr(content, "text", None)
            if text is not None and hasattr(text, "value"):
                responses.append(text.value)
            elif text is not None:
                responses.append(str(text))
            else:
                responses.append(str(content))

    if responses:
        return "\n".join(responses).strip()
    return "No response received from the Fabric Data Agent."
