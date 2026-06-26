from pydantic import Field

from src.schemas.fabric.base import FabricAgentResponseBase


class SalesAgentResponse(FabricAgentResponseBase):
    total_revenue: float | None = Field(
        default=None,
        description="Total revenue figure extracted from the response",
    )
    quarter: str | None = Field(
        default=None,
        description="Reporting quarter, e.g. Q1 2025",
    )
    currency: str = Field(default="USD", description="Currency code for revenue figures")
