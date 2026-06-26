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
from src.services.fabric_response_formatter import LangChainFabricResponseFormatter
from tests.support.fabric_mocks import build_mock_fabric_provider, build_mock_openai_client


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
    formatter = LangChainFabricResponseFormatter(Settings())
    return FabricDataAgentService(
        settings=Settings(),
        provider=mock_fabric_provider,
        registry=agent_registry,
        router=router,
        response_formatter=formatter,
    )


@pytest.mark.asyncio
async def test_ask_with_prompt_id_routes_sales_agent_and_formats_response(
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
    assert result.data["total_revenue"] == 1200000.0
    assert result.data["quarter"] == "Q1 2025"
    assert "Revenue grew" in result.reply

    mock_fabric_provider.get_or_create_thread.assert_awaited_once_with(
        "https://fabric.example/sales/openai",
        None,
    )


@pytest.mark.asyncio
async def test_ask_without_prompt_uses_thread_name(
    fabric_service,
    mock_fabric_provider,
) -> None:
    llm_router = AsyncMock()
    llm_router.resolve = AsyncMock(
        return_value=RoutingDecision(agent_id="inventory-agent", method="llm")
    )
    fabric_service._router = llm_router
    mock_fabric_provider.get_openai_client = AsyncMock(
        side_effect=lambda url: build_mock_openai_client(
            '{"answer": "Stock is healthy", "sku_count": 42, "warehouse": "East", "stock_status": "healthy"}'
        )
    )

    result = await fabric_service.ask(
        message="How is stock in the east warehouse?",
        thread_name="inventory-session",
    )

    assert result.agent_id == "inventory-agent"
    assert result.routing_method == "llm"
    assert result.data["sku_count"] == 42
    mock_fabric_provider.get_or_create_thread.assert_awaited_once_with(
        "https://fabric.example/inventory/openai",
        "inventory-agent:inventory-session",
    )


@pytest.mark.asyncio
async def test_ask_raises_when_routing_fails(fabric_service) -> None:
    with pytest.raises(FabricDataAgentInvocationError, match="Could not resolve"):
        await fabric_service.ask(message="No route", prompt_id=None)


@pytest.mark.asyncio
async def test_ask_raises_on_empty_message(fabric_service) -> None:
    with pytest.raises(FabricDataAgentInvocationError, match="cannot be empty"):
        await fabric_service.ask(message="   ", prompt_id="sales-q1-report")


@pytest.mark.asyncio
async def test_response_formatter_json_path() -> None:
    formatter = LangChainFabricResponseFormatter(Settings())
    structured = await formatter.format(
        raw_reply='{"answer": "OK", "total_revenue": 99.5, "quarter": "Q2"}',
        response_class=SalesAgentResponse,
    )
    assert structured.total_revenue == 99.5
    assert structured.quarter == "Q2"
