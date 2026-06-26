from pydantic import BaseModel, ConfigDict, Field


class FabricAgentResponseBase(BaseModel):
    """Base schema for structured Fabric Data Agent output."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="Primary natural-language answer from the agent")
