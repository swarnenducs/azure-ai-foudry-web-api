from src.config import Settings
from src.routing.registry import AgentRegistry


def test_registry_loads_agents_and_response_classes(agent_registry: AgentRegistry) -> None:
    sales = agent_registry.get_agent("sales-agent")
    inventory = agent_registry.get_agent("inventory-agent")

    assert sales.response_class.__name__ == "SalesAgentResponse"
    assert inventory.response_class.__name__ == "InventoryAgentResponse"
    assert agent_registry.get_agent_for_prompt("sales-q1-report") == "sales-agent"
