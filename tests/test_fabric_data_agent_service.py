from unittest.mock import AsyncMock

import pytest

from src.config import Settings
from src.routing.protocols import RoutingDecision
from src.routing.rule_router import RuleBasedAgentRouter
from src.schemas.fabric.sales import SalesAgentResponse
from src.services.fabric_data_agent_service import (
    FabricDataAgentInvocationError,
    FabricDataAgentService,
    resolve_thread_scope,
)
from src.services.fabric_errors import (
    FabricNotFoundError,
    FabricResponseFormatMismatchError,
)
from src.services.fabric_response_formatter import FabricResponseProcessor
from tests.support.fabric_mocks import build_mock_fabric_provider, build_mock_openai_client

_MOCK_FABRIC_JSON_REPLY = (
    '{"answer": "Revenue grew", "total_revenue": 1200000, "quarter": "Q1 2025"}'
)


def test_resolve_thread_scope_prompt_id_always_new_thread() -> None:
    assert (
        resolve_thread_scope(
            prompt_id="sales-q1-report",
            thread_name="existing-session",
            agent_id="sales-agent",
        )
        is None
    )


def test_resolve_thread_scope_thread_name_without_prompt() -> None:
    assert (
        resolve_thread_scope(
            prompt_id=None,
            thread_name="existing-session",
            agent_id="sales-agent",
        )
        == "sales-agent:existing-session"
    )


def test_resolve_thread_scope_no_prompt_no_thread() -> None:
    assert (
        resolve_thread_scope(
            prompt_id=None,
            thread_name=None,
            agent_id="sales-agent",
        )
        is None
    )


@pytest.fixture
def fabric_service(agent_registry, mock_fabric_provider) -> FabricDataAgentService:
    router = RuleBasedAgentRouter(agent_registry)
    return FabricDataAgentService(
        settings=Settings(),
        provider=mock_fabric_provider,
        registry=agent_registry,
        router=router,
        response_formatter=FabricResponseProcessor(Settings()),
    )


@pytest.mark.asyncio
async def test_ask_with_prompt_id_parses_fabric_json_into_pydantic_model(
    fabric_service,
    mock_fabric_provider,
) -> None:
    result = await fabric_service.ask(
        message="What were Q1 sales?",
        prompt_id="sales-q1-report",
        thread_name="should-be-ignored",
    )

    assert result.agent_id == "sales-agent"
    assert result.routing_method == "rule"
    assert result.response_class == "SalesAgentResponse"
    assert result.fabric_raw_reply == _MOCK_FABRIC_JSON_REPLY
    assert result.reply == _MOCK_FABRIC_JSON_REPLY
    assert result.data_source == "fabric_json"
    assert result.fabric_json["total_revenue"] == 1200000.0
    assert result.data["total_revenue"] == 1200000.0
    assert result.data["quarter"] == "Q1 2025"
    assert result.data["answer"] == "Revenue grew"

    mock_fabric_provider.get_or_create_thread.assert_awaited_once_with(
        "https://fabric.example/sales/openai",
        None,
    )


@pytest.mark.asyncio
async def test_ask_without_prompt_uses_thread_name(
    fabric_service,
    mock_fabric_provider,
) -> None:
    inventory_reply = (
        '{"answer": "Stock is healthy", "sku_count": 42, "warehouse": "East", '
        '"stock_status": "healthy"}'
    )
    llm_router = AsyncMock()
    llm_router.resolve = AsyncMock(
        return_value=RoutingDecision(agent_id="inventory-agent", method="llm")
    )
    fabric_service._router = llm_router
    mock_fabric_provider.get_openai_client = AsyncMock(
        side_effect=lambda url: build_mock_openai_client(inventory_reply)
    )

    result = await fabric_service.ask(
        message="How is stock in the east warehouse?",
        thread_name="inventory-session",
    )

    assert result.agent_id == "inventory-agent"
    assert result.routing_method == "llm"
    assert result.data["sku_count"] == 42
    assert result.data["warehouse"] == "East"
    mock_fabric_provider.get_or_create_thread.assert_awaited_once_with(
        "https://fabric.example/inventory/openai",
        "inventory-agent:inventory-session",
    )


@pytest.mark.asyncio
async def test_ask_raises_not_found_when_routing_fails_without_prompt(
    fabric_service,
) -> None:
    with pytest.raises(FabricNotFoundError) as exc_info:
        await fabric_service.ask(message="No route", prompt_id=None)
    assert exc_info.value.reason == "agent_unresolved"
    assert exc_info.value.http_status_code == 400


@pytest.mark.asyncio
async def test_ask_raises_not_found_for_unknown_prompt_id(fabric_service) -> None:
    with pytest.raises(FabricNotFoundError) as exc_info:
        await fabric_service.ask(
            message="Unknown prompt",
            prompt_id="does-not-exist",
        )
    assert exc_info.value.reason == "unknown_prompt_id"
    assert exc_info.value.prompt_id == "does-not-exist"


@pytest.mark.asyncio
async def test_ask_raises_not_found_when_fabric_returns_404(
    fabric_service,
    mock_fabric_provider,
) -> None:
    from unittest.mock import MagicMock

    from openai import NotFoundError

    mock_fabric_provider.get_openai_client = AsyncMock(
        side_effect=NotFoundError(
            "Fabric agent endpoint not found",
            response=MagicMock(status_code=404),
            body=None,
        )
    )
    with pytest.raises(FabricNotFoundError) as exc_info:
        await fabric_service.ask(
            message="What were Q1 sales?",
            prompt_id="sales-q1-report",
        )
    assert exc_info.value.reason == "fabric_resource_not_found"
    assert exc_info.value.agent_id == "sales-agent"
    assert exc_info.value.http_status_code == 502


@pytest.mark.asyncio
async def test_ask_raises_on_empty_message(fabric_service) -> None:
    with pytest.raises(FabricDataAgentInvocationError, match="cannot be empty"):
        await fabric_service.ask(message="   ", prompt_id="sales-q1-report")


@pytest.mark.asyncio
async def test_json_formatter_validates_fabric_json() -> None:
    formatter = FabricResponseProcessor(Settings())
    result = await formatter.format(
        raw_reply='{"answer": "OK", "total_revenue": 99.5, "quarter": "Q2"}',
        response_class=SalesAgentResponse,
        agent_id="sales-agent",
    )
    assert result.structured.total_revenue == 99.5
    assert result.structured.quarter == "Q2"
    assert result.extracted_json["total_revenue"] == 99.5
    assert result.data_source == "fabric_json"


@pytest.mark.asyncio
async def test_json_formatter_raises_format_mismatch_for_non_json_without_llm() -> None:
    processor = FabricResponseProcessor(Settings())
    result = await processor.format(
        raw_reply="Plain text from Fabric",
        response_class=SalesAgentResponse,
        agent_id="sales-agent",
    )
    assert result.data_source == "fabric_default"
    assert result.structured.answer == "Plain text from Fabric"


@pytest.mark.asyncio
async def test_json_formatter_returns_default_on_schema_mismatch() -> None:
    processor = FabricResponseProcessor(Settings())
    result = await processor.format(
        raw_reply='{"answer": "OK", "total_revenue": "not-a-number"}',
        response_class=SalesAgentResponse,
        agent_id="sales-agent",
    )
    assert result.data_source == "fabric_default"
    assert result.structured.answer == "OK"


@pytest.mark.asyncio
async def test_ask_returns_default_when_fabric_returns_non_json(
    fabric_service,
    mock_fabric_provider,
) -> None:
    mock_fabric_provider.get_openai_client = AsyncMock(
        side_effect=lambda url: build_mock_openai_client("Not JSON")
    )
    result = await fabric_service.ask(
        message="What were Q1 sales?",
        prompt_id="sales-q1-report",
    )
    assert result.data_source == "fabric_default"
    assert result.reply == "Not JSON"
    assert result.data["answer"] == "Not JSON"
