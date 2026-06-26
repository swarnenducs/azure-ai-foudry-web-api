import logging
import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI

from src.config import Settings
from src.routing.protocols import AgentRouter, RoutingDecision
from src.routing.registry import AgentRegistry

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You route user questions to the best Fabric Data Agent.
Reply with ONLY the agent_id from the list below — no explanation, no punctuation.

Available agents:
{agents}
"""


def _build_routing_credential(settings: Settings):
    if settings.is_production or os.getenv("WEBSITE_SITE_NAME"):
        client_id = os.getenv("AZURE_CLIENT_ID")
        from azure.identity import ManagedIdentityCredential

        if client_id:
            return ManagedIdentityCredential(client_id=client_id)
        return ManagedIdentityCredential()

    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


class LLMAgentRouter:
    def __init__(self, registry: AgentRegistry, settings: Settings) -> None:
        self._registry = registry
        self._settings = settings
        self._chain = self._build_chain(settings)

    def _build_chain(self, settings: Settings):
        if not settings.routing_llm_endpoint or not settings.routing_llm_deployment:
            raise ValueError(
                "ROUTING_LLM_ENDPOINT and ROUTING_LLM_DEPLOYMENT are required for LLM routing"
            )

        credential = _build_routing_credential(settings)

        def token_provider() -> str:
            return credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            ).token

        llm = AzureChatOpenAI(
            azure_endpoint=settings.routing_llm_endpoint.rstrip("/"),
            azure_deployment=settings.routing_llm_deployment,
            api_version=settings.routing_llm_api_version,
            azure_ad_token_provider=token_provider,
            temperature=0,
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", "{message}"),
            ]
        )
        return prompt | llm | StrOutputParser()

    def _format_agents(self) -> str:
        lines = []
        for agent in self._registry.list_agents():
            lines.append(f"- {agent.id}: {agent.description}")
        return "\n".join(lines)

    async def resolve(
        self,
        *,
        message: str,
        prompt_id: str | None,
    ) -> RoutingDecision | None:
        raw = await self._chain.ainvoke(
            {"agents": self._format_agents(), "message": message}
        )
        agent_id = raw.strip().strip('"').strip("'")
        if agent_id not in self._registry.agent_ids:
            raise ValueError(
                f"LLM router returned unknown agent_id '{agent_id}'. "
                f"Valid options: {', '.join(self._registry.agent_ids)}"
            )

        logger.info(
            "LLM router resolved agent",
            extra={"agent_id": agent_id, "prompt_id": prompt_id},
        )
        return RoutingDecision(agent_id=agent_id, method="llm")
