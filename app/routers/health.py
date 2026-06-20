import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict[str, object]:
    provider = getattr(request.app.state, "foundry_provider", None)
    foundry_ready = bool(provider and provider.is_ready)
    startup_error = getattr(request.app.state, "foundry_startup_error", None)

    logger.debug("Health check requested", extra={"foundry_ready": foundry_ready})

    payload: dict[str, object] = {
        "status": "healthy" if foundry_ready else "degraded",
        "foundry_ready": foundry_ready,
    }
    if startup_error:
        payload["foundry_error"] = startup_error
    return payload
