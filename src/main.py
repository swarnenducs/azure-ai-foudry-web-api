import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import get_settings
from app.logging_config import configure_logging, request_id_ctx
from app.routers import chat, health
from app.services.foundry_client import FoundryClientProvider

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    logger.info(
        "Starting application",
        extra={
            "environment": settings.environment,
            "agent_name": settings.agent_name,
            "agent_version": settings.agent_version,
            "agent_protocol": settings.agent_protocol,
            "responses_endpoint": settings.agent_responses_endpoint,
        },
    )

    foundry_provider = FoundryClientProvider(settings)
    app.state.foundry_provider = foundry_provider
    app.state.foundry_startup_error = None

    try:
        await foundry_provider.initialize()
    except Exception as exc:
        app.state.foundry_startup_error = str(exc)
        logger.exception(
            "Foundry client failed to initialize at startup; "
            "/health and /docs remain available"
        )

    yield

    await foundry_provider.aclose()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    root_path = os.getenv("ROOT_PATH", "")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for invoking Azure AI Foundry agents.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        root_path=root_path,
    )

    @app.get("/", include_in_schema=False, tags=["root"])
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()

        logger.info(
            "Request started",
            extra={"method": request.method, "path": request.url.path},
        )

        try:
            response: Response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled exception during request",
                extra={"method": request.method, "path": request.url.path},
            )
            request_id_ctx.reset(token)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        response.headers["X-Request-ID"] = request_id
        request_id_ctx.reset(token)
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "Unhandled application error",
            extra={"method": request.method, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id_ctx.get(),
            },
        )

    app.include_router(health.router)
    app.include_router(chat.router)
    return app


app = create_app()
