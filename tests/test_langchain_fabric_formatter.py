import pytest

from src.config import Settings
from src.schemas.fabric.sales import SalesAgentResponse
from src.services.fabric_errors import FabricResponseFormatMismatchError
from src.services.fabric_response_formatter import (
    LangChainFabricResponseFormatter,
    build_fabric_response_formatter,
)


@pytest.fixture
def formatter_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.setenv("LLM_ENDPOINT", "https://openai.example.com")
    monkeypatch.setenv("LLM_DEPLOYMENT", "gpt-4o-mini")
    return Settings()


def test_build_fabric_response_formatter_returns_langchain(formatter_settings: Settings) -> None:
    formatter = build_fabric_response_formatter(formatter_settings)
    assert isinstance(formatter, LangChainFabricResponseFormatter)


@pytest.mark.asyncio
async def test_langchain_formatter_maps_fabric_reply_to_pydantic(
    formatter_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formatter = LangChainFabricResponseFormatter(formatter_settings)

    class MockChain:
        async def ainvoke(self, inputs: dict) -> SalesAgentResponse:
            assert inputs["response_class"] == "SalesAgentResponse"
            return SalesAgentResponse(
                answer="Revenue grew",
                total_revenue=1200000.0,
                quarter="Q1 2025",
            )

    monkeypatch.setattr(formatter, "_get_chain", lambda _cls: MockChain())

    result = await formatter.format(
        raw_reply='{"total_revenue": 1200000, "quarter": "Q1 2025"}',
        response_class=SalesAgentResponse,
        agent_id="sales-agent",
    )

    assert result.total_revenue == 1200000.0
    assert result.quarter == "Q1 2025"


@pytest.mark.asyncio
async def test_langchain_formatter_raises_format_mismatch_on_chain_failure(
    formatter_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formatter = LangChainFabricResponseFormatter(formatter_settings)

    class FailingChain:
        async def ainvoke(self, inputs: dict) -> SalesAgentResponse:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(formatter, "_get_chain", lambda _cls: FailingChain())

    with pytest.raises(FabricResponseFormatMismatchError) as exc_info:
        await formatter.format(
            raw_reply="not structured",
            response_class=SalesAgentResponse,
            agent_id="sales-agent",
        )

    assert exc_info.value.reason == "structured_output_failed"


def test_langchain_formatter_requires_llm_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_DEPLOYMENT", raising=False)
    monkeypatch.delenv("ROUTING_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("ROUTING_LLM_DEPLOYMENT", raising=False)

    with pytest.raises(ValueError, match="LLM_ENDPOINT"):
        LangChainFabricResponseFormatter(Settings())
