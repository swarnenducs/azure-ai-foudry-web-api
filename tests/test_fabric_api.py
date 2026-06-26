from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.dependencies import get_fabric_data_agent_service
from src.main import create_app
from src.schemas.fabric_data_agent import FabricDataAgentResponse


@pytest.fixture
def fabric_client(agent_registry, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("src.main.AgentRegistry.load", lambda _settings: agent_registry)
    monkeypatch.setattr(
        "src.main.FoundryClientProvider.initialize",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.main.FabricDataAgentProvider.initialize",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.main.FabricDataAgentProvider.aclose",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.main.FoundryClientProvider.aclose",
        AsyncMock(),
    )

    mock_service = AsyncMock()
    mock_service.ask = AsyncMock(
        return_value=FabricDataAgentResponse(
            reply='{"answer": "Revenue grew"}',
            agent_id="sales-agent",
            response_class="SalesAgentResponse",
            routing_method="rule",
            data={
                "answer": "Revenue grew",
                "total_revenue": 1200000.0,
                "quarter": "Q1 2025",
                "currency": "USD",
            },
            prompt_id="sales-q1-report",
            thread_name=None,
        )
    )

    app = create_app()
    app.dependency_overrides[get_fabric_data_agent_service] = lambda: mock_service
    with TestClient(app) as client:
        client._mock_service = mock_service  # type: ignore[attr-defined]
        yield client


def test_fabric_chat_endpoint_returns_structured_response(fabric_client: TestClient) -> None:
    response = fabric_client.post(
        "/api/fabric/chat",
        json={
            "message": "What were Q1 sales?",
            "prompt_id": "sales-q1-report",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == "sales-agent"
    assert body["response_class"] == "SalesAgentResponse"
    assert body["data"]["total_revenue"] == 1200000.0
    assert body["prompt_id"] == "sales-q1-report"


def test_fabric_chat_endpoint_maps_service_errors_to_502(fabric_client: TestClient) -> None:
    from src.services.fabric_data_agent_service import FabricDataAgentInvocationError

    mock_service = fabric_client._mock_service  # type: ignore[attr-defined]
    mock_service.ask = AsyncMock(
        side_effect=FabricDataAgentInvocationError("Fabric agent unavailable")
    )

    response = fabric_client.post(
        "/api/fabric/chat",
        json={"message": "Hello", "prompt_id": "sales-q1-report"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Fabric agent unavailable"
