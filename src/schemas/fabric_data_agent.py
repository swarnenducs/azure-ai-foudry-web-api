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
    reply: str = Field(description="Raw text returned by the Fabric Data Agent")
    agent_id: str
    response_class: str = Field(
        description="Pydantic model name used to shape the structured data field",
    )
    routing_method: str = Field(
        description="How the agent was chosen: rule or llm",
    )
    data: dict[str, Any] = Field(
        description="Structured output validated against the agent response_class model",
    )
    prompt_id: str | None = None
    thread_name: str | None = None
