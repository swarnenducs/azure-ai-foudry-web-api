from typing import Any

from pydantic import BaseModel, Field


class FabricDataAgentRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=32_000,
        examples=["What were the total sales last quarter?"],
    )
    prompt_id: str | None = Field(
        default=None,
        description=(
            "Registered prompt identifier for rule-based routing (prompt_id → agent_id). "
            "Each prompt_id request starts a new Fabric thread."
        ),
        examples=["sales-q1-report"],
    )
    thread_name: str | None = Field(
        default=None,
        description=(
            "Optional thread name when prompt_id is not provided. "
            "Not used when prompt_id is set. Future thread_id-based query "
            "continuation is not implemented yet."
        ),
    )


class FabricDataAgentResponse(BaseModel):
    fabric_raw_reply: str = Field(
        description="Exact unmodified text returned by the Fabric Data Agent",
    )
    fabric_json: dict[str, Any] | None = Field(
        default=None,
        description=(
            "JSON extracted from fabric_raw_reply when Fabric returned JSON; "
            "null when Fabric sent plain text and data was extracted another way"
        ),
    )
    data_source: str = Field(
        description=(
            "fabric_json: valid Fabric JSON as-is; "
            "fabric_json_repair: LLM fixed JSON syntax only; "
            "fabric_default: Fabric JSON incomplete, defaults filled from Fabric answer"
        ),
    )
    agent_id: str
    response_class: str = Field(
        description="Pydantic model name used to validate the Fabric JSON",
    )
    routing_method: str = Field(
        description="How the agent was chosen: rule or llm",
    )
    data: dict[str, Any] = Field(
        description=(
            "Structured response validated against response_class. "
            "Values come from Fabric; LLM never changes business data."
        ),
    )
    reply: str = Field(
        description="Deprecated alias for fabric_raw_reply",
    )
    prompt_id: str | None = None
    thread_name: str | None = None
