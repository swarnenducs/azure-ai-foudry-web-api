from src.config import Settings
from src.routing.hybrid_router import HybridAgentRouter
from src.routing.llm_router import LLMAgentRouter
from src.routing.protocols import AgentRouter
from src.routing.registry import AgentRegistry
from src.routing.rule_router import RuleBasedAgentRouter


def build_agent_router(registry: AgentRegistry, settings: Settings) -> AgentRouter:
    mode = registry.routing_mode
    rule_router = RuleBasedAgentRouter(registry)

    if mode == "rule":
        return rule_router

    llm_router = LLMAgentRouter(registry, settings)

    if mode == "llm":
        return llm_router

    if mode == "hybrid":
        return HybridAgentRouter(rule_router, llm_router)

    raise ValueError(f"Unsupported routing mode: {mode}")
