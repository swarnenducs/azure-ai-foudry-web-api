#!/usr/bin/env python3
"""Live Fabric Data Agent smoke test (requires az login locally).

Usage:
    az login
    uv run python scripts/test_fabric_live.py
    uv run python scripts/test_fabric_live.py --prompt-id contract_expiry_p15 --message "Which contracts expire next quarter?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.config import get_settings
from src.routing.registry import AgentRegistry
from src.routing.rule_router import RuleBasedAgentRouter
from src.services.azure_credential import describe_credential_choice
from src.services.fabric_data_agent_provider import FabricDataAgentProvider
from src.services.fabric_data_agent_service import FabricDataAgentService
from src.services.fabric_response_formatter import (
    PydanticJsonFabricResponseFormatter,
    build_fabric_response_formatter,
)


async def run(*, prompt_id: str, message: str) -> int:
    settings = get_settings()
    print("Credential:", json.dumps(describe_credential_choice(settings), indent=2))

    registry = AgentRegistry.load(settings)
    provider = FabricDataAgentProvider(settings)

    print("\nAcquiring Fabric token via DefaultAzureCredential...")
    try:
        await provider.initialize()
    except Exception as exc:
        print(f"\nAuth failed: {exc}", file=sys.stderr)
        print("Run: az login", file=sys.stderr)
        return 1

    service = FabricDataAgentService(
        settings=settings,
        provider=provider,
        registry=registry,
        router=RuleBasedAgentRouter(registry),
        response_formatter=build_fabric_response_formatter(settings),
    )

    print(f"\nInvoking prompt_id={prompt_id!r} ...")
    try:
        result = await service.ask(message=message, prompt_id=prompt_id)
    except Exception as exc:
        print(f"\nInvoke failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        await provider.aclose()
        return 1

    print(json.dumps(result.model_dump(), indent=2))
    await provider.aclose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Fabric Data Agent test")
    parser.add_argument(
        "--prompt-id",
        default="contract_expiry_p15",
        help="prompt_id from config/agent_registry.yaml",
    )
    parser.add_argument(
        "--message",
        default="Which contracts expire next quarter?",
        help="Question sent to the Fabric Data Agent",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(prompt_id=args.prompt_id, message=args.message)))


if __name__ == "__main__":
    main()
