import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import yaml

from src.config import Settings
from src.schemas.fabric.base import FabricAgentResponseBase
from src.schemas.fabric.loader import resolve_response_class

logger = logging.getLogger(__name__)

_VALID_MODES = {"rule", "llm", "hybrid"}
T = TypeVar("T", bound=FabricAgentResponseBase)


@dataclass(frozen=True)
class AgentConfig:
    id: str
    url: str
    description: str
    response_class: type[FabricAgentResponseBase]


class AgentRegistry:
    def __init__(
        self,
        *,
        agents: dict[str, AgentConfig],
        prompts: dict[str, str],
        routing_mode: str,
    ) -> None:
        self._agents = agents
        self._prompts = prompts
        self.routing_mode = routing_mode

    @property
    def agent_ids(self) -> list[str]:
        return list(self._agents.keys())

    def get_agent(self, agent_id: str) -> AgentConfig:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Unknown agent_id: {agent_id}")
        return agent

    def get_agent_for_prompt(self, prompt_id: str) -> str | None:
        return self._prompts.get(prompt_id)

    def list_agents(self) -> list[AgentConfig]:
        return list(self._agents.values())

    @classmethod
    def load(cls, settings: Settings) -> "AgentRegistry":
        path = Path(settings.agent_registry_path)
        if path.is_file():
            return cls._load_from_file(path, settings)

        if settings.fabric_data_agent_url:
            logger.warning(
                "Agent registry file not found; using legacy FABRIC_DATA_AGENT_URL as default agent",
                extra={"path": str(path)},
            )
            return cls._from_legacy_url(settings)

        raise FileNotFoundError(
            f"Agent registry not found at {path} and FABRIC_DATA_AGENT_URL is not set"
        )

    @classmethod
    def _load_from_file(cls, path: Path, settings: Settings) -> "AgentRegistry":
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) if path.suffix in {".yaml", ".yml"} else json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"Agent registry must be a mapping: {path}")

        routing = data.get("routing", {})
        mode = settings.fabric_routing_mode or routing.get("mode", "rule")
        if mode not in _VALID_MODES:
            raise ValueError(f"Invalid routing mode '{mode}'. Use: rule, llm, hybrid")

        agents: dict[str, AgentConfig] = {}
        for agent_id, agent_data in (data.get("agents") or {}).items():
            if not isinstance(agent_data, dict):
                raise ValueError(f"Invalid agent config for '{agent_id}'")
            url = agent_data.get("url", "").strip()
            if not url:
                raise ValueError(f"Agent '{agent_id}' is missing url")
            response_class_ref = str(
                agent_data.get("response_class", "FabricAgentResponseBase")
            ).strip()
            response_class = resolve_response_class(response_class_ref)
            agents[agent_id] = AgentConfig(
                id=agent_id,
                url=url,
                description=str(agent_data.get("description", agent_id)).strip(),
                response_class=response_class,
            )

        if not agents:
            raise ValueError(f"Agent registry must define at least one agent: {path}")

        prompts: dict[str, str] = {}
        for prompt_id, prompt_data in (data.get("prompts") or {}).items():
            if isinstance(prompt_data, dict):
                agent_id = str(prompt_data.get("agent_id", "")).strip()
            else:
                agent_id = str(prompt_data).strip()
            if not agent_id:
                raise ValueError(f"Prompt '{prompt_id}' is missing agent_id")
            if agent_id not in agents:
                raise ValueError(
                    f"Prompt '{prompt_id}' references unknown agent_id '{agent_id}'"
                )
            prompts[prompt_id] = agent_id

        logger.info(
            "Loaded agent registry",
            extra={
                "path": str(path),
                "agent_count": len(agents),
                "prompt_count": len(prompts),
                "routing_mode": mode,
            },
        )
        return cls(agents=agents, prompts=prompts, routing_mode=mode)

    @classmethod
    def _from_legacy_url(cls, settings: Settings) -> "AgentRegistry":
        url = settings.fabric_data_agent_url
        if not url:
            raise ValueError("FABRIC_DATA_AGENT_URL is required for legacy fallback")
        agents = {
            "default": AgentConfig(
                id="default",
                url=url,
                description="Default Fabric Data Agent",
                response_class=resolve_response_class("FabricAgentResponseBase"),
            )
        }
        mode = settings.fabric_routing_mode or "rule"
        return cls(agents=agents, prompts={}, routing_mode=mode)
