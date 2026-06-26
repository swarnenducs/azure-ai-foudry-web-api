import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from src.config import Settings, get_settings
from src.services.agent_service import AgentService
from src.services.fabric_data_agent_provider import FabricDataAgentProvider
from src.services.fabric_data_agent_service import FabricDataAgentService
from src.services.fabric_response_formatter import LangChainFabricResponseFormatter
from src.services.foundry_client import FoundryClientProvider

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_foundry_provider(request: Request) -> FoundryClientProvider:
    provider = getattr(request.app.state, "foundry_provider", None)
    if provider is None:
        logger.error("Foundry provider is not initialized on application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready",
        )
    if not provider.is_ready:
        startup_error = getattr(request.app.state, "foundry_startup_error", None)
        detail = startup_error or "Foundry client is not ready"
        logger.error("Foundry provider is not ready", extra={"error": detail})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )
    return provider


def get_agent_service(
    settings: Annotated[Settings, Depends(get_settings)],
    foundry_provider: Annotated[FoundryClientProvider, Depends(get_foundry_provider)],
) -> AgentService:
    return AgentService(settings=settings, foundry_provider=foundry_provider)


def get_fabric_data_agent_provider(request: Request) -> FabricDataAgentProvider:
    provider = getattr(request.app.state, "fabric_data_agent_provider", None)
    if provider is None:
        logger.error("Fabric Data Agent provider is not initialized on application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fabric Data Agent is not configured",
        )
    if not provider.is_ready:
        startup_error = getattr(
            request.app.state, "fabric_data_agent_startup_error", None
        )
        detail = startup_error or "Fabric Data Agent client is not ready"
        logger.error("Fabric Data Agent provider is not ready", extra={"error": detail})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )
    return provider


def get_fabric_data_agent_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    fabric_provider: Annotated[
        FabricDataAgentProvider, Depends(get_fabric_data_agent_provider)
    ],
) -> FabricDataAgentService:
    registry = getattr(request.app.state, "agent_registry", None)
    router = getattr(request.app.state, "agent_router", None)
    response_formatter = getattr(request.app.state, "fabric_response_formatter", None)
    if registry is None or router is None or response_formatter is None:
        logger.error("Agent registry, router, or response formatter is not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fabric agent routing is not configured",
        )
    return FabricDataAgentService(
        settings=settings,
        provider=fabric_provider,
        registry=registry,
        router=router,
        response_formatter=response_formatter,
    )


async def verify_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    api_key: Annotated[str | None, Depends(_api_key_header)] = None,
) -> None:
    configured_key = settings.api_key.get_secret_value() if settings.api_key else None
    if configured_key is None:
        return
    if api_key != configured_key:
        logger.warning("Rejected request with invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


def get_request_id(
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> str | None:
    return x_request_id
