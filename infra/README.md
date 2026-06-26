# Terraform — Azure Web App + Managed Identity

Provisions the Linux Web App, Managed Identity, application settings (wired to `src/config.py`), and optional Azure RBAC for Foundry and Azure OpenAI.

**Does not** grant Microsoft Fabric workspace access — complete that step manually after apply (see [Fabric-flow.md](../Fabric-flow.md)).

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.5
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) — `az login`
- Subscription with permission to create App Service, Managed Identity, and role assignments

## Quick start

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

az login
terraform init
terraform plan
terraform apply
```

After apply, note outputs:

```bash
terraform output web_app_principal_id   # → Fabric workspace "Manage access"
terraform output web_app_url
terraform output health_check_url
```

## What gets created

| Resource | Purpose |
|----------|---------|
| `azurerm_resource_group` | Optional RG (if `create_resource_group = true`) |
| `azurerm_service_plan` | Linux App Service plan |
| `azurerm_linux_web_app` | Python 3.12 Web App running this API |
| `azurerm_user_assigned_identity` | Only when `identity_type = "UserAssigned"` |
| `azurerm_role_assignment` | Optional Foundry + OpenAI RBAC |

## Application settings (auto-configured)

Terraform sets these to match the FastAPI app:

| App setting | Source variable |
|-------------|-----------------|
| `ENVIRONMENT` | `production` (fixed) |
| `WEBSITES_PORT` | `8000` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `AZURE_AI_PROJECT_ENDPOINT` | `azure_ai_project_endpoint` |
| `AGENT_NAME` | `agent_name` |
| `AGENT_VERSION` | `agent_version` |
| `AGENT_REGISTRY_PATH` | `agent_registry_path` |
| `FABRIC_ROUTING_MODE` | `fabric_routing_mode` (optional) |
| `ROUTING_LLM_*` | routing LLM vars (optional) |
| `AZURE_CLIENT_ID` | User-assigned MI client ID only |

## Identity modes

### System-assigned (default)

```hcl
identity_type = "SystemAssigned"
```

No `AZURE_CLIENT_ID` app setting. The Web App's built-in identity is used by `ManagedIdentityCredential()`.

### User-assigned

```hcl
identity_type               = "UserAssigned"
user_assigned_identity_name = "mi-fabric-agent-api"
```

Terraform creates the identity, attaches it to the Web App, and sets `AZURE_CLIENT_ID`.

## RBAC variables

```hcl
foundry_rbac_scope_id = "/subscriptions/.../Microsoft.CognitiveServices/accounts/..."
openai_rbac_scope_id  = "/subscriptions/.../Microsoft.CognitiveServices/accounts/..."
```

Find scope IDs: Azure Portal → resource → **Properties** → **Resource ID**.

Skip either by setting the variable to `null` or omitting from `terraform.tfvars`.

## Post-apply steps

1. **Fabric workspace** — Add `web_app_principal_id` output identity in Fabric **Manage access**
2. **Deploy code** — ZIP deploy, GitHub Actions, or `az webapp up` to the Web App
3. **Verify** — `curl $(terraform output -raw health_check_url)`

## Deploy application code

Example ZIP deploy after `terraform apply`:

```bash
cd ..
zip -r deploy.zip . -x ".git/*" -x ".venv/*" -x "infra/*" -x "tests/*"
az webapp deployment source config-zip \
  --resource-group "$(cd infra && terraform output -raw resource_group_name)" \
  --name "$(cd infra && terraform output -raw web_app_name)" \
  --src deploy.zip
```

Or use your existing CI/CD pipeline targeting the Terraform-created Web App.

## Destroy

```bash
cd infra
terraform destroy
```

## Files

```text
infra/
├── main.tf
├── variables.tf
├── outputs.tf
├── locals.tf
├── providers.tf
├── versions.tf
├── terraform.tfvars.example
├── README.md
└── modules/managed_identity/
```

See also [Fabric-flow.md § Option C — Terraform](../Fabric-flow.md).
