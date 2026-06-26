import logging

from src.routing.protocols import AgentRouter, RoutingDecision
from src.routing.registry import AgentRegistry

logger = logging.getLogger(__name__)


class HybridAgentRouter:
    """Try rule-based routing first; fall back to LLM when no prompt mapping matches."""

    def __init__(self, rule_router: AgentRouter, llm_router: AgentRouter) -> None:
        self._rule_router = rule_router
        self._llm_router = llm_router

    async def resolve(
        self,
        *,
        message: str,
        prompt_id: str | None,
    ) -> RoutingDecision | None:
        decision = await self._rule_router.resolve(
            message=message,
            prompt_id=prompt_id,
        )
        if decision is not None:
            return decision

        logger.info(
            "Hybrid router: rule routing missed, falling back to LLM",
            extra={"prompt_id": prompt_id},
        )
        return await self._llm_router.resolve(message=message, prompt_id=prompt_id)
