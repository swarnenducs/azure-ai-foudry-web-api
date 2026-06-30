variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Resource group name (created if create_resource_group is true)."
  type        = string
}

variable "create_resource_group" {
  description = "Create the resource group; set false to use an existing one."
  type        = bool
  default     = true
}

variable "app_name" {
  description = "Globally unique Linux Web App name."
  type        = string
}

variable "service_plan_name" {
  description = "App Service plan name."
  type        = string
  default     = null
}

variable "service_plan_sku" {
  description = "App Service plan SKU (e.g. B1, P1v3)."
  type        = string
  default     = "B1"
}

variable "identity_type" {
  description = "Managed identity: SystemAssigned or UserAssigned."
  type        = string
  default     = "SystemAssigned"

  validation {
    condition     = contains(["SystemAssigned", "UserAssigned"], var.identity_type)
    error_message = "identity_type must be SystemAssigned or UserAssigned."
  }
}

variable "user_assigned_identity_name" {
  description = "Name for user-assigned identity (required when identity_type is UserAssigned)."
  type        = string
  default     = null
}

# --- Application settings (wired to src/config.py) ---

variable "azure_ai_project_endpoint" {
  description = "AZURE_AI_PROJECT_ENDPOINT — Foundry project URL."
  type        = string
}

variable "agent_name" {
  description = "AGENT_NAME — Foundry agent name."
  type        = string
}

variable "agent_version" {
  description = "AGENT_VERSION."
  type        = string
  default     = "1"
}

variable "agent_protocol" {
  description = "AGENT_PROTOCOL (responses or invocations)."
  type        = string
  default     = "responses"
}

variable "agent_registry_path" {
  description = "AGENT_REGISTRY_PATH."
  type        = string
  default     = "config/agent_registry.yaml"
}

variable "fabric_routing_mode" {
  description = "FABRIC_ROUTING_MODE override: rule, llm, or hybrid. Leave null to use YAML."
  type        = string
  default     = null
}

variable "routing_llm_endpoint" {
  description = "LLM_ENDPOINT — Azure OpenAI endpoint (routing, structured output, etc.)."
  type        = string
  default     = null
}

variable "routing_llm_deployment" {
  description = "LLM_DEPLOYMENT."
  type        = string
  default     = null
}

variable "routing_llm_api_version" {
  description = "LLM_API_VERSION."
  type        = string
  default     = "2024-10-21"
}

variable "fabric_query_timeout" {
  description = "FABRIC_QUERY_TIMEOUT in seconds."
  type        = number
  default     = 120
}

variable "log_level" {
  description = "LOG_LEVEL."
  type        = string
  default     = "INFO"
}

variable "log_json" {
  description = "LOG_JSON — structured logs in production."
  type        = bool
  default     = true
}

variable "api_key" {
  description = "Optional API_KEY for /api routes (sensitive)."
  type        = string
  default     = null
  sensitive   = true
}

variable "startup_command" {
  description = "Web App startup command (matches startup.sh / README)."
  type        = string
  default     = "python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*"
}

# --- RBAC (Azure resources only; Fabric workspace ACL is still manual) ---

variable "foundry_rbac_scope_id" {
  description = "Resource ID for Foundry / AI Services project RBAC scope. Null skips assignment."
  type        = string
  default     = null
}

variable "foundry_role_definition_name" {
  description = "Role on foundry_rbac_scope_id (e.g. Cognitive Services User)."
  type        = string
  default     = "Cognitive Services User"
}

variable "openai_rbac_scope_id" {
  description = "Resource ID for Azure OpenAI RBAC (LLM routing). Null skips assignment."
  type        = string
  default     = null
}

variable "openai_role_definition_name" {
  description = "Role on openai_rbac_scope_id."
  type        = string
  default     = "Cognitive Services User"
}

variable "tags" {
  description = "Tags applied to resources."
  type        = map(string)
  default     = {}
}
