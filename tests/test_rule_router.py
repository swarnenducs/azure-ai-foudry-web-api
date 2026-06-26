import pytest

from src.routing.protocols import RoutingDecision
from src.routing.rule_router import RuleBasedAgentRouter


@pytest.mark.asyncio
async def test_rule_router_resolves_known_prompt(agent_registry) -> None:
    router = RuleBasedAgentRouter(agent_registry)

    decision = await router.resolve(
        message="What were Q1 sales?",
        prompt_id="sales-q1-report",
    )

    assert decision == RoutingDecision(agent_id="sales-agent", method="rule")


@pytest.mark.asyncio
async def test_rule_router_returns_none_without_prompt_id(agent_registry) -> None:
    router = RuleBasedAgentRouter(agent_registry)

    decision = await router.resolve(message="What were Q1 sales?", prompt_id=None)

    assert decision is None


@pytest.mark.asyncio
async def test_rule_router_returns_none_for_unknown_prompt(agent_registry) -> None:
    router = RuleBasedAgentRouter(agent_registry)

    decision = await router.resolve(
        message="Unknown prompt",
        prompt_id="does-not-exist",
    )

    assert decision is None
