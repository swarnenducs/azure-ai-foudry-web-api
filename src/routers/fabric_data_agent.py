import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import (
    get_fabric_data_agent_service,
    get_request_id,
    verify_api_key,
)
from src.logging_config import request_id_ctx
from src.schemas.chat import ErrorResponse
from src.schemas.fabric_data_agent import (
    FabricDataAgentRequest,
    FabricDataAgentResponse,
)
from src.services.fabric_data_agent_service import (
    FabricDataAgentInvocationError,
    FabricDataAgentService,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/fabric",
    tags=["fabric-data-agent"],
    dependencies=[Depends(verify_api_key)],
)


@router.post(
    "/chat",
    response_model=FabricDataAgentResponse,
    responses={502: {"model": ErrorResponse}},
)
async def fabric_chat(
    body: FabricDataAgentRequest,
    fabric_service: Annotated[
        FabricDataAgentService, Depends(get_fabric_data_agent_service)
    ],
    request_id: Annotated[str | None, Depends(get_request_id)] = None,
) -> FabricDataAgentResponse:
    if request_id:
        request_id_ctx.set(request_id)

    logger.info(
        "Fabric Data Agent request received",
        extra={
            "message_length": len(body.message),
            "prompt_id": body.prompt_id,
            "thread_name": body.thread_name,
        },
    )

    try:
        return await fabric_service.ask(
            message=body.message,
            prompt_id=body.prompt_id,
            thread_name=body.thread_name,
        )
    except FabricDataAgentInvocationError as exc:
        logger.error("Fabric Data Agent invocation failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
