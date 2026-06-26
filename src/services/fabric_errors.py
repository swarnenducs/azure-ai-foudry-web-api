import aiohttp
from openai import NotFoundError as OpenAINotFoundError


class FabricResponseFormatMismatchError(Exception):
    """Raised when Fabric output is not valid JSON or does not match the agent Pydantic model."""

    def __init__(
        self,
        message: str,
        *,
        agent_id: str,
        response_class: str,
        reason: str,
        validation_errors: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.agent_id = agent_id
        self.response_class = response_class
        self.reason = reason
        self.validation_errors = validation_errors or []

    def to_detail(self) -> dict:
        return {
            "error": "fabric_response_format_mismatch",
            "message": str(self),
            "agent_id": self.agent_id,
            "response_class": self.response_class,
            "reason": self.reason,
            "validation_errors": self.validation_errors,
        }


class FabricNotFoundError(Exception):
    """Raised when a Fabric agent, prompt mapping, or upstream Fabric resource cannot be found."""

    _HTTP_STATUS_BY_REASON = {
        "unknown_prompt_id": 404,
        "unknown_agent_id": 404,
        "agent_unresolved": 400,
        "fabric_resource_not_found": 502,
    }

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        prompt_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.prompt_id = prompt_id
        self.agent_id = agent_id

    @property
    def http_status_code(self) -> int:
        return self._HTTP_STATUS_BY_REASON.get(self.reason, 404)

    def to_detail(self) -> dict:
        detail = {
            "error": "fabric_not_found",
            "message": str(self),
            "reason": self.reason,
        }
        if self.prompt_id is not None:
            detail["prompt_id"] = self.prompt_id
        if self.agent_id is not None:
            detail["agent_id"] = self.agent_id
        return detail


def is_fabric_upstream_not_found(exc: BaseException) -> bool:
    if isinstance(exc, OpenAINotFoundError):
        return True
    if isinstance(exc, aiohttp.ClientResponseError) and exc.status == 404:
        return True
    status_code = getattr(exc, "status_code", None)
    return status_code == 404
