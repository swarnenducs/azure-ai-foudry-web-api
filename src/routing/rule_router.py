import logging

from src.routing.protocols import AgentRouter, RoutingDecision
from src.routing.registry import AgentRegistry

logger = logging.getLogger(__name__)


class RuleBasedAgentRouter:
    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    async def resolve(
        self,
        *,
        message: str,
        prompt_id: str | None,
    ) -> RoutingDecision | None:
        if not prompt_id:
            logger.debug("Rule router: no prompt_id provided")
            return None

        agent_id = self._registry.get_agent_for_prompt(prompt_id)
        if agent_id is None:
            logger.info(
                "Rule router: no mapping for prompt_id",
                extra={"prompt_id": prompt_id},
            )
            return None

        logger.info(
            "Rule router resolved agent",
            extra={"prompt_id": prompt_id, "agent_id": agent_id},
        )
        return RoutingDecision(agent_id=agent_id, method="rule")
