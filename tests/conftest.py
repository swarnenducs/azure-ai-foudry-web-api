import os

# Set required env before any src.main import during test collection.
os.environ.setdefault("AZURE_AI_PROJECT_ENDPOINT", "https://example.com")
os.environ.setdefault("AGENT_NAME", "test-agent")

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.config import Settings
from src.routing.registry import AgentRegistry


@pytest.fixture(autouse=True)
def _required_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AGENT_NAME", "test-agent")
    monkeypatch.delenv("FABRIC_DATA_AGENT_URL", raising=False)


@pytest.fixture
def registry_yaml(tmp_path: Path) -> Path:
    content = textwrap.dedent(
        """
        routing:
          mode: rule

        agents:
          sales-agent:
            url: https://fabric.example/sales/openai
            description: Sales and revenue data
            response_class: SalesAgentResponse

          inventory-agent:
            url: https://fabric.example/inventory/openai
            description: Inventory and stock data
            response_class: InventoryAgentResponse

        prompts:
          sales-q1-report:
            agent_id: sales-agent
          inventory-stock-check:
            agent_id: inventory-agent
        """
    ).strip()
    path = tmp_path / "agent_registry.yaml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def agent_registry(registry_yaml: Path, monkeypatch: pytest.MonkeyPatch) -> AgentRegistry:
    monkeypatch.setenv("AGENT_REGISTRY_PATH", str(registry_yaml))
    return AgentRegistry.load(Settings())


@pytest.fixture
def mock_fabric_provider() -> AsyncMock:
    from tests.support.fabric_mocks import build_mock_fabric_provider

    return build_mock_fabric_provider()
