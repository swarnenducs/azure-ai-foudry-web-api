import pytest

from src.config import Settings
from src.schemas.fabric.contract_expiry import ContractExpiryAgentResponse
from src.schemas.fabric.sales import SalesAgentResponse
from src.services.fabric_response_formatter import (
    FabricResponseProcessor,
    LangChainJsonFormatRepair,
    build_fabric_response_formatter,
)
from src.services.langchain_llm import build_langchain_chat_model


@pytest.fixture
def formatter_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.setenv("LLM_ENDPOINT", "https://openai.example.com/openai/v1/responses")
    monkeypatch.setenv("LLM_DEPLOYMENT", "gpt-5.4-mini")
    return Settings()


@pytest.mark.asyncio
async def test_processor_uses_fabric_json_when_valid(formatter_settings: Settings) -> None:
    processor = FabricResponseProcessor(formatter_settings)
    result = await processor.format(
        raw_reply='{"answer": "OK", "total_revenue": 10.0, "quarter": "Q1 2025", "currency": "USD"}',
        response_class=SalesAgentResponse,
        agent_id="sales-agent",
    )
    assert result.data_source == "fabric_json"
    assert result.structured.total_revenue == 10.0


@pytest.mark.asyncio
async def test_processor_returns_default_when_fabric_json_incomplete(
    formatter_settings: Settings,
) -> None:
    processor = FabricResponseProcessor(formatter_settings)
    result = await processor.format(
        raw_reply='{"answer": "I don\'t know sorry"}',
        response_class=ContractExpiryAgentResponse,
        agent_id="contract_expiry_p15",
    )
    assert result.data_source == "fabric_default"
    assert result.structured.answer == "I don't know sorry"
    assert result.structured.total_contract_expiring_next_quarter == 0
    assert result.structured.agreements == []


@pytest.mark.asyncio
async def test_json_repair_uses_llm_for_malformed_json_only(
    formatter_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processor = FabricResponseProcessor(formatter_settings)

    class MockRepair:
        async def repair(self, raw_reply: str) -> dict:
            return {"answer": "fixed", "total_revenue": 99.0, "quarter": "Q2 2025"}

    monkeypatch.setattr(processor, "_json_repair", MockRepair())

    result = await processor.format(
        raw_reply="not json at all",
        response_class=SalesAgentResponse,
        agent_id="sales-agent",
    )
    assert result.data_source == "fabric_json_repair"
    assert result.structured.total_revenue == 99.0


def test_build_fabric_response_formatter_returns_processor() -> None:
    formatter = build_fabric_response_formatter(Settings())
    assert isinstance(formatter, FabricResponseProcessor)


def test_json_repair_requires_llm_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_DEPLOYMENT", raising=False)
    with pytest.raises(ValueError, match="LLM_ENDPOINT"):
        build_langchain_chat_model(Settings())
