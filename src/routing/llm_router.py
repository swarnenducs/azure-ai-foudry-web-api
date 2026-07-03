import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI

from src.config import Settings
from src.routing.protocols import AgentRouter, RoutingDecision
from src.routing.registry import AgentRegistry
from src.services.langchain_llm import build_langchain_chat_model, is_foundry_v1_llm_endpoint

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You route user questions to the best Fabric Data Agent.
Reply with ONLY the agent_id from the list below — no explanation, no punctuation.

Available agents:
{agents}
"""


def _build_routing_credential(settings: Settings):
    from src.services.azure_credential import build_sync_credential

    return build_sync_credential(settings)


class LLMAgentRouter:
    def __init__(self, registry: AgentRegistry, settings: Settings) -> None:
        self._registry = registry
        self._settings = settings
        self._chain = self._build_chain(settings)

    def _build_chain(self, settings: Settings):
        if not settings.llm_endpoint or not settings.llm_deployment:
            raise ValueError(
                "LLM_ENDPOINT and LLM_DEPLOYMENT are required for LLM routing"
            )

        credential = _build_routing_credential(settings)

        if is_foundry_v1_llm_endpoint(settings.llm_endpoint):
            llm = build_langchain_chat_model(settings)
        else:
            def token_provider() -> str:
                return credential.get_token(
                    "https://cognitiveservices.azure.com/.default"
                ).token

            llm = AzureChatOpenAI(
                azure_endpoint=settings.llm_endpoint.rstrip("/"),
                azure_deployment=settings.llm_deployment,
                api_version=settings.llm_api_version,
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
