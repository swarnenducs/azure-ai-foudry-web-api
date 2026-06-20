from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=32_000,
        examples=["Hello, what can you help me with?"],
    )
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Optional. Omit for a new chat. For follow-up messages, pass the "
            "`conversation_id` returned by the previous /api/chat response "
            "(format: conv_...). Do not use agent version numbers here."
        ),
        examples=[None],
    )
    session_id: str | None = Field(
        default=None,
        description="Optional hosted-agent session ID (invocations or hosted responses)",
    )


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str | None = None
    session_id: str | None = None


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None
