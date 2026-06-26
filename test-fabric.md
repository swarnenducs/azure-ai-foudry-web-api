# Testing Fabric Data Agents

This guide explains how to run the existing Fabric test suite and how to add tests when you introduce a **new Fabric Data Agent**.

All tests use **mocked** Fabric clients — no live Azure or Fabric calls are required for the default pytest run.

---

## 1. Quick start

```bash
uv sync --extra dev
uv run pytest -v
```

Expected: **14 tests passed** (routing, registry, service, API).

Run only Fabric-related tests:

```bash
uv run pytest -v tests/test_fabric_data_agent_service.py tests/test_fabric_api.py tests/test_rule_router.py tests/test_registry.py
```

---

## 2. Test layout

```text
tests/
├── conftest.py                      # Shared fixtures (registry YAML, mock provider)
├── support/
│   └── fabric_mocks.py              # Reusable Fabric / OpenAI mocks
├── test_registry.py                 # YAML registry + response_class loading
├── test_rule_router.py              # prompt_id → agent_id routing
├── test_fabric_data_agent_service.py  # Service unit tests (mocked Fabric)
└── test_fabric_api.py               # HTTP endpoint tests (mocked service)
```

| Layer | What is mocked | What is real |
|-------|----------------|--------------|
| `test_rule_router` | Nothing | `AgentRegistry` from temp YAML |
| `test_registry` | Nothing | Registry loader + Pydantic class resolution |
| `test_fabric_data_agent_service` | `FabricDataAgentProvider`, Fabric OpenAI client | Service, router, formatter (JSON path) |
| `test_fabric_api` | `FabricDataAgentService` via FastAPI override | HTTP routing, request/response schema |

---

## 3. Shared fixtures (`tests/conftest.py`)

### `registry_yaml`

Creates a temporary `agent_registry.yaml` with:

- `sales-agent` → `SalesAgentResponse`
- `inventory-agent` → `InventoryAgentResponse`
- Prompt mappings: `sales-q1-report`, `inventory-stock-check`

### `agent_registry`

Loads the temp YAML into `AgentRegistry` and sets `AGENT_REGISTRY_PATH`.

### `mock_fabric_provider`

Returns a mock `FabricDataAgentProvider` from `tests/support/fabric_mocks.py` that simulates:

- `get_openai_client(url)` → mock OpenAI client
- `get_or_create_thread(url, thread_name)` → `{ "id": "thread-test", ... }`
- Completed assistant run with configurable JSON reply text

---

## 4. Mock helpers (`tests/support/fabric_mocks.py`)

### `build_mock_openai_client(reply_text)`

Builds a mock `AsyncOpenAI` client that:

1. Creates an assistant
2. Returns `in_progress` then `completed` run status
3. Returns assistant messages with `reply_text` as message content

### `build_mock_fabric_provider(reply_text=...)`

Wraps the mock client in a provider mock. Use a **JSON string** as `reply_text` when testing structured `data` output:

```python
from tests.support.fabric_mocks import build_mock_fabric_provider

provider = build_mock_fabric_provider(
    '{"answer": "Budget is on track", "budget_variance": -2.5, "fiscal_year": "2025"}'
)
```

---

## 5. What existing tests verify

### Registry (`test_registry.py`)

- Agents load from YAML
- `response_class` resolves to the correct Pydantic model
- `prompt_id` → `agent_id` mapping works

### Rule router (`test_rule_router.py`)

- Known `prompt_id` resolves to the correct agent
- Missing or unknown `prompt_id` returns `None` (for hybrid fallback)

### Service (`test_fabric_data_agent_service.py`)

| Test | Verifies |
|------|----------|
| `test_resolve_thread_scope_prompt_id_always_new_thread` | `prompt_id` → new thread (`None` scope) |
| `test_resolve_thread_scope_thread_name_without_prompt` | `thread_name` scoped as `{agent_id}:{thread_name}` |
| `test_ask_with_prompt_id_parses_fabric_json_into_pydantic_model` | End-to-end service with rule routing + structured `data` |
| `test_ask_without_prompt_uses_thread_name` | LLM routing path + thread reuse |
| `test_ask_raises_not_found_when_routing_fails_without_prompt` | `agent_unresolved` when no agent can be resolved |
| `test_ask_raises_not_found_for_unknown_prompt_id` | `unknown_prompt_id` for missing prompt |
| `test_ask_raises_not_found_when_fabric_returns_404` | `fabric_resource_not_found` when Fabric upstream returns 404 |
| `test_ask_raises_on_empty_message` | Validation error |
| `test_json_formatter_raises_format_mismatch_for_non_json` | `invalid_json` format mismatch |
| `test_json_formatter_raises_schema_mismatch` | `schema_mismatch` with Pydantic `validation_errors` |
| `test_ask_raises_format_mismatch_when_fabric_returns_non_json` | End-to-end format mismatch from Fabric reply |

### API (`test_fabric_api.py`)

- `POST /api/fabric/chat` returns 200 with structured body
- `unknown_prompt_id` → **404** (`fabric_not_found`)
- `agent_unresolved` → **400** (`fabric_not_found`)
- `fabric_resource_not_found` → **502** (`fabric_not_found`)
- Format mismatch → **422** (`fabric_response_format_mismatch`)
- Other service errors → **502** (plain `detail` string)

See [Fabric-flow.md — Error responses](Fabric-flow.md#error-responses) for the full HTTP mapping table and example payloads.

---

## 6. How to test a new Fabric Data Agent

Follow this checklist whenever you add an agent (example: `finance-agent` with `FinanceAgentResponse`).

### Step 1 — Create the Pydantic model

**File:** `src/schemas/fabric/finance.py`

```python
from pydantic import Field
from src.schemas.fabric.base import FabricAgentResponseBase


class FinanceAgentResponse(FabricAgentResponseBase):
    budget_variance: float | None = Field(default=None)
    fiscal_year: str | None = Field(default=None)
```

Register in `src/schemas/fabric/loader.py`:

```python
"FinanceAgentResponse": FinanceAgentResponse,
```

**Add a registry test** in `tests/test_registry.py` or extend the conftest YAML (see Step 2).

---

### Step 2 — Add the agent to the test registry fixture

Edit `tests/conftest.py` → `registry_yaml` fixture:

```yaml
agents:
  finance-agent:
    url: https://fabric.example/finance/openai
    description: Budget and fiscal planning data
    response_class: FinanceAgentResponse

prompts:
  budget-review:
    agent_id: finance-agent
```

---

### Step 3 — Add rule router test

**File:** `tests/test_rule_router.py`

```python
@pytest.mark.asyncio
async def test_rule_router_resolves_finance_prompt(agent_registry) -> None:
    router = RuleBasedAgentRouter(agent_registry)

    decision = await router.resolve(
        message="What is the budget variance?",
        prompt_id="budget-review",
    )

    assert decision == RoutingDecision(agent_id="finance-agent", method="rule")
```

---

### Step 4 — Add registry assertion

**File:** `tests/test_registry.py`

```python
def test_finance_agent_response_class(agent_registry) -> None:
    agent = agent_registry.get_agent("finance-agent")
    assert agent.response_class.__name__ == "FinanceAgentResponse"
    assert agent_registry.get_agent_for_prompt("budget-review") == "finance-agent"
```

---

### Step 5 — Add service test with mocked Fabric reply

**File:** `tests/test_fabric_data_agent_service.py`

```python
@pytest.mark.asyncio
async def test_ask_finance_agent_formats_structured_response(
    agent_registry,
) -> None:
    from src.routing.rule_router import RuleBasedAgentRouter
    from src.services.fabric_response_formatter import PydanticJsonFabricResponseFormatter
    from tests.support.fabric_mocks import build_mock_fabric_provider

    provider = build_mock_fabric_provider(
        '{"answer": "Variance is -2.5%", "budget_variance": -2.5, "fiscal_year": "2025"}'
    )
    service = FabricDataAgentService(
        settings=Settings(),
        provider=provider,
        registry=agent_registry,
        router=RuleBasedAgentRouter(agent_registry),
        response_formatter=PydanticJsonFabricResponseFormatter(),
    )

    result = await service.ask(
        message="What is the budget variance?",
        prompt_id="budget-review",
    )

    assert result.agent_id == "finance-agent"
    assert result.response_class == "FinanceAgentResponse"
    assert result.data["budget_variance"] == -2.5
    assert result.data["fiscal_year"] == "2025"

    # prompt_id always forces a new thread
    provider.get_or_create_thread.assert_awaited_once_with(
        "https://fabric.example/finance/openai",
        None,
    )
```

---

### Step 6 — Add API test (optional but recommended)

**File:** `tests/test_fabric_api.py`

Either extend the existing mock response or add a dedicated test that overrides `get_fabric_data_agent_service` with a finance-specific `FabricDataAgentResponse`.

Minimal pattern:

```python
def test_fabric_chat_finance_agent(fabric_client) -> None:
    response = fabric_client.post(
        "/api/fabric/chat",
        json={
            "message": "What is the budget variance?",
            "prompt_id": "budget-review",
        },
    )
    assert response.status_code == 200
```

Update the `fabric_client` fixture mock if you want to assert finance-specific `data` fields in the API layer.

---

### Step 7 — Run tests

```bash
uv run pytest -v tests/test_rule_router.py::test_rule_router_resolves_finance_prompt
uv run pytest -v tests/test_fabric_data_agent_service.py::test_ask_finance_agent_formats_structured_response
uv run pytest -v
```

All tests must pass before merging.

---

## 7. Testing checklist for a new agent

| # | Task | File(s) |
|---|------|---------|
| 1 | Create `FabricAgentResponseBase` subclass | `src/schemas/fabric/<agent>.py` |
| 2 | Register in `RESPONSE_MODELS` | `src/schemas/fabric/loader.py` |
| 3 | Add agent + prompt to production registry | `config/agent_registry.yaml` |
| 4 | Add agent + prompt to test registry fixture | `tests/conftest.py` |
| 5 | Test rule routing for new `prompt_id` | `tests/test_rule_router.py` |
| 6 | Test `response_class` loads correctly | `tests/test_registry.py` |
| 7 | Test service returns structured `data` | `tests/test_fabric_data_agent_service.py` |
| 8 | Test API endpoint (optional) | `tests/test_fabric_api.py` |
| 9 | Run full suite | `uv run pytest -v` |

---

## 8. Manual / integration testing (optional)

Use this **after** unit tests pass, when you have real Fabric URLs and Azure credentials.

### Prerequisites

- `config/agent_registry.yaml` updated with real agent URLs
- `az login` (local) or Managed Identity (Azure)
- Identity has access to the Fabric Data Agent

### Start the app

```bash
uv run uvicorn src.main:app --reload --port 8000
```

### Call the endpoint

```bash
curl -X POST http://localhost:8000/api/fabric/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What were total sales last quarter?",
    "prompt_id": "sales-q1-report"
  }'
```

### Verify

- HTTP `200`
- `agent_id` matches the expected agent
- `routing_method` is `rule` (when using `prompt_id`)
- `data` contains fields from the agent's Pydantic model
- `GET /health` shows `fabric_data_agent_ready: true`

---

## 9. Troubleshooting tests

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| `ValidationError` for `Settings` on collection | Env vars not set before `src.main` import | Ensure `tests/conftest.py` sets `AZURE_AI_PROJECT_ENDPOINT` and `AGENT_NAME` at top |
| `Unknown response_class` on registry load | Model not in `RESPONSE_MODELS` | Register short name in `loader.py` |
| `Could not resolve a Fabric Data Agent` in service test | Missing `prompt_id` with `rule` mode router | Pass `prompt_id` or mock an LLM router |
| Structured `data` fields are `null` | Mock reply is plain text, not JSON | Use JSON string in `build_mock_fabric_provider(...)` |
| API test returns 503 | Fabric routes not registered | Patch `AgentRegistry.load` in `test_fabric_api.py` fixture (already done) |

---

## 10. Related documentation

- [Fabric-flow.md](Fabric-flow.md) — end-to-end Fabric flow and how to add a new agent
- [README.md](README.md) — project setup and deployment
