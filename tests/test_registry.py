import pytest

from src.config import Settings
from src.routing.registry import AgentRegistry
from src.services.fabric_errors import FabricNotFoundError


def test_registry_loads_agents_and_response_classes(agent_registry: AgentRegistry) -> None:
    sales = agent_registry.get_agent("sales-agent")
    inventory = agent_registry.get_agent("inventory-agent")

    assert sales.response_class.__name__ == "SalesAgentResponse"
    assert inventory.response_class.__name__ == "InventoryAgentResponse"
    assert agent_registry.get_agent_for_prompt("sales-q1-report") == "sales-agent"


def test_registry_raises_not_found_for_unknown_agent(agent_registry: AgentRegistry) -> None:
    with pytest.raises(FabricNotFoundError) as exc_info:
        agent_registry.get_agent("missing-agent")
    assert exc_info.value.reason == "unknown_agent_id"
    assert exc_info.value.agent_id == "missing-agent"
    assert exc_info.value.http_status_code == 404
