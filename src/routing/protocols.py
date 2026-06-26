from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RoutingDecision:
    agent_id: str
    method: str  # "rule" | "llm"


class AgentRouter(Protocol):
    async def resolve(
        self,
        *,
        message: str,
        prompt_id: str | None,
    ) -> RoutingDecision | None:
        """Return the chosen agent, or None when rule-based routing cannot decide."""
