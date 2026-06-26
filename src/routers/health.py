import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, object]:
    provider = getattr(request.app.state, "foundry_provider", None)
    foundry_ready = bool(provider and provider.is_ready)
    startup_error = getattr(request.app.state, "foundry_startup_error", None)

    fabric_provider = getattr(request.app.state, "fabric_data_agent_provider", None)
    fabric_ready = bool(fabric_provider and fabric_provider.is_ready)
    fabric_error = getattr(request.app.state, "fabric_data_agent_startup_error", None)
    registry = getattr(request.app.state, "agent_registry", None)

    logger.debug(
        "Health check requested",
        extra={"foundry_ready": foundry_ready, "fabric_ready": fabric_ready},
    )

    payload: dict[str, object] = {
        "status": "healthy" if foundry_ready or fabric_ready else "degraded",
        "foundry_ready": foundry_ready,
        "fabric_data_agent_ready": fabric_ready,
    }
    if registry is not None:
        payload["fabric_routing_mode"] = registry.routing_mode
        payload["fabric_agent_count"] = len(registry.agent_ids)
    if startup_error:
        payload["foundry_error"] = startup_error
    if fabric_error:
        payload["fabric_data_agent_error"] = fabric_error
    return payload
