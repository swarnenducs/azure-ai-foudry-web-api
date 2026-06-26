from unittest.mock import AsyncMock, MagicMock


def build_mock_openai_client(reply_text: str) -> AsyncMock:
    client = AsyncMock()
    assistant = MagicMock()
    assistant.id = "asst-test"
    client.beta.assistants.create = AsyncMock(return_value=assistant)

    in_progress_run = MagicMock(status="in_progress", id="run-test")
    completed_run = MagicMock(status="completed", id="run-test")
    client.beta.threads.runs.create = AsyncMock(return_value=in_progress_run)
    client.beta.threads.runs.retrieve = AsyncMock(return_value=completed_run)
    client.beta.threads.messages.create = AsyncMock()
    client.beta.threads.delete = AsyncMock()

    message = MagicMock()
    message.role = "assistant"
    content = MagicMock()
    content.text.value = reply_text
    message.content = [content]
    messages = MagicMock()
    messages.data = [message]
    client.beta.threads.messages.list = AsyncMock(return_value=messages)
    return client


def build_mock_fabric_provider(
    reply_text: str = (
        '{"answer": "Revenue grew", "total_revenue": 1200000, "quarter": "Q1 2025"}'
    ),
) -> AsyncMock:
    provider = AsyncMock()
    provider.get_openai_client = AsyncMock(
        side_effect=lambda url: build_mock_openai_client(reply_text)
    )
    provider.get_or_create_thread = AsyncMock(
        return_value={"id": "thread-test", "name": "api-thread-test"}
    )
    return provider
