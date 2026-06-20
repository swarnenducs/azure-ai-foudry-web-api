# Foundry Agent FastAPI Web App

Async FastAPI service for invoking Azure AI Foundry agents, designed for Azure Web App deployment.

**Python:** 3.12

## Quick start

```bash
cp .env.example .env
# edit .env with your Foundry project endpoint and agent name

uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## API

- `GET /health`
- `POST /api/chat`
- `POST /api/sessions` (hosted agents)
- `DELETE /api/sessions/{session_id}`

## Azure Web App

- **Python 3.12** (`runtime.txt`)
- **Startup command** (Configuration → General settings):

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
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

- **Swagger UI:** `https://<your-app>.azurewebsites.net/docs` (root `/` redirects here)
- Enable managed identity and grant **Foundry User** RBAC on the project
- Set `LOG_JSON=true` in production
