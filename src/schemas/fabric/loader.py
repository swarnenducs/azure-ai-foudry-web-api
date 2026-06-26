import importlib
from typing import TypeVar

from src.schemas.fabric.base import FabricAgentResponseBase
from src.schemas.fabric.inventory import InventoryAgentResponse
from src.schemas.fabric.sales import SalesAgentResponse

T = TypeVar("T", bound=FabricAgentResponseBase)

# Short-name registry for agent_registry.yaml response_class values
RESPONSE_MODELS: dict[str, type[FabricAgentResponseBase]] = {
    "FabricAgentResponseBase": FabricAgentResponseBase,
    "SalesAgentResponse": SalesAgentResponse,
    "InventoryAgentResponse": InventoryAgentResponse,
}


def resolve_response_class(class_ref: str) -> type[FabricAgentResponseBase]:
    """Resolve a response model from a short name or dotted import path."""
    ref = class_ref.strip()
    if not ref:
        raise ValueError("response_class cannot be empty")

    if ref in RESPONSE_MODELS:
        return RESPONSE_MODELS[ref]

    module_path, _, class_name = ref.rpartition(".")
    if not module_path:
        raise ValueError(
            f"Unknown response_class '{ref}'. "
            f"Use one of: {', '.join(sorted(RESPONSE_MODELS))} "
            "or a dotted path such as src.schemas.fabric.sales.SalesAgentResponse"
        )

    module = importlib.import_module(module_path)
    model_cls = getattr(module, class_name, None)
    if model_cls is None:
        raise ValueError(f"response_class '{ref}' not found")

    if not isinstance(model_cls, type) or not issubclass(model_cls, FabricAgentResponseBase):
        raise ValueError(f"response_class '{ref}' must extend FabricAgentResponseBase")

    return model_cls
