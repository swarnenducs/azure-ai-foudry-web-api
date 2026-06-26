from pydantic import Field

from src.schemas.fabric.base import FabricAgentResponseBase


class InventoryAgentResponse(FabricAgentResponseBase):
    sku_count: int | None = Field(
        default=None,
        description="Number of SKUs referenced in the response",
    )
    warehouse: str | None = Field(
        default=None,
        description="Warehouse or location mentioned in the response",
    )
    stock_status: str | None = Field(
        default=None,
        description="Overall stock status, e.g. low, healthy, critical",
    )
