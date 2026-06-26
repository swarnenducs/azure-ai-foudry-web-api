# Foundry Agent FastAPI Web App

Async FastAPI service for invoking Azure AI Foundry agents, designed for Azure Web App deployment.

**Python:** 3.12

## Quick start

```bash
cp .env.example .env
# edit .env with your Foundry project endpoint and agent name

uv sync
uv run uvicorn src.main:app --reload --port 8000
```

Run tests (mocked Fabric agents, no live Azure calls):

```bash
uv sync --extra dev
uv run pytest -v
```

## API

- `GET /health`
- `POST /api/chat`
- `POST /api/fabric/chat` — routes to a Fabric Data Agent via rule, LLM, or hybrid routing (see [Fabric-flow.md — Error responses](Fabric-flow.md#error-responses) for HTTP error mapping)
- `POST /api/sessions` (hosted agents)
- `DELETE /api/sessions/{session_id}`

### Fabric agent routing

Edit `config/agent_registry.yaml`:

- **`agents`** — `agent_id` → `url`, `description`, and `response_class` (Pydantic model name)
- **`prompts`** — `prompt_id` → `agent_id` (used by rule routing)
- **`routing.mode`** — `rule`, `llm`, or `hybrid` (rule first, then LLM fallback)

Agent response models live in `src/schemas/fabric/` and extend `FabricAgentResponseBase`.
Each agent's `response_class` in YAML controls the structured `data` field returned by `/api/fabric/chat`.

Example request:

```json
{
  "message": "What were total sales last quarter?",
  "prompt_id": "sales-q1-report",
  "thread_name": "my-session"
}
```

For `llm` / `hybrid` modes, set `ROUTING_LLM_ENDPOINT` and `ROUTING_LLM_DEPLOYMENT`.

**Docs:** [Fabric-flow.md](Fabric-flow.md) (architecture & adding agents) · [test-fabric.md](test-fabric.md) (testing guide) · [infra/README.md](infra/README.md) (Terraform) · [GIT-PRACTICES.md](GIT-PRACTICES.md) (Git workflow & merge process)

## Azure Web App

- **Python 3.12** (`runtime.txt`)
- **Startup command** (Configuration → General settings):

```bash
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
```

Or use the script:

```bash
bash startup.sh
```

- **App settings:**

| Name | Example |
|------|---------|
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `WEBSITES_PORT` | `8000` |
| `ENVIRONMENT` | `production` |
| `AZURE_AI_PROJECT_ENDPOINT` | your project URL |
| `AGENT_NAME` | `tool-agent-demo-01` |
| `AGENT_VERSION` | `1` |
| `AGENT_REGISTRY_PATH` | `config/agent_registry.yaml` |
| `FABRIC_ROUTING_MODE` | `rule`, `llm`, or `hybrid` (overrides YAML) |
| `ROUTING_LLM_ENDPOINT` | Azure OpenAI endpoint for LLM routing |
| `ROUTING_LLM_DEPLOYMENT` | deployment name for routing LLM |
| `FABRIC_DATA_AGENT_URL` | legacy single-agent fallback |
| `FABRIC_QUERY_TIMEOUT` | `120` |

- **Swagger UI:** `https://<your-app>.azurewebsites.net/docs` (root `/` redirects here)
- Enable managed identity and grant **Foundry User** RBAC on the project
- Set `LOG_JSON=true` in production
