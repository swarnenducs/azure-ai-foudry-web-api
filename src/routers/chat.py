import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import get_agent_service, get_request_id, verify_api_key
from src.logging_config import request_id_ctx
from src.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from src.services.agent_service import AgentInvocationError, AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"], dependencies=[Depends(verify_api_key)])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={502: {"model": ErrorResponse}},
)
async def chat(
    body: ChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    request_id: Annotated[str | None, Depends(get_request_id)] = None,
) -> ChatResponse:
    if request_id:
        request_id_ctx.set(request_id)

    logger.info(
        "Chat request received",
        extra={
            "message_length": len(body.message),
            "conversation_id": body.conversation_id,
            "session_id": body.session_id,
        },
    )

    try:
        return await agent_service.chat(
            message=body.message,
            conversation_id=body.conversation_id,
            session_id=body.session_id,
        )
    except AgentInvocationError as exc:
        logger.error("Agent invocation failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/sessions", response_model=dict[str, str])
async def create_session(
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    request_id: Annotated[str | None, Depends(get_request_id)] = None,
) -> dict[str, str]:
    if request_id:
        request_id_ctx.set(request_id)

    try:
        session_id = await agent_service.create_session()
        return {"session_id": session_id}
    except AgentInvocationError as exc:
        logger.error("Session creation failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
    request_id: Annotated[str | None, Depends(get_request_id)] = None,
) -> None:
    if request_id:
        request_id_ctx.set(request_id)

    try:
        await agent_service.delete_session(session_id)
    except AgentInvocationError as exc:
        logger.error(
            "Session deletion failed",
            extra={"error": str(exc), "session_id": session_id},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
