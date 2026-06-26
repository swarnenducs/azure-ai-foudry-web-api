locals {
  service_plan_name = coalesce(var.service_plan_name, "${var.app_name}-plan")

  app_settings = merge(
    {
      ENVIRONMENT                    = "production"
      WEBSITES_PORT                  = "8000"
      SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
      AZURE_AI_PROJECT_ENDPOINT      = var.azure_ai_project_endpoint
      AGENT_NAME                     = var.agent_name
      AGENT_VERSION                  = var.agent_version
      AGENT_PROTOCOL                 = var.agent_protocol
      AGENT_REGISTRY_PATH            = var.agent_registry_path
      FABRIC_QUERY_TIMEOUT           = tostring(var.fabric_query_timeout)
      ROUTING_LLM_API_VERSION        = var.routing_llm_api_version
      LOG_LEVEL                      = var.log_level
      LOG_JSON                       = var.log_json ? "true" : "false"
    },
    var.fabric_routing_mode != null ? { FABRIC_ROUTING_MODE = var.fabric_routing_mode } : {},
    var.routing_llm_endpoint != null ? { ROUTING_LLM_ENDPOINT = var.routing_llm_endpoint } : {},
    var.routing_llm_deployment != null ? { ROUTING_LLM_DEPLOYMENT = var.routing_llm_deployment } : {},
    var.api_key != null ? { API_KEY = var.api_key } : {},
    var.identity_type == "UserAssigned" ? {
      AZURE_CLIENT_ID = module.managed_identity[0].client_id
    } : {}
  )

  managed_identity_principal_id = var.identity_type == "SystemAssigned" ? (
    azurerm_linux_web_app.api.identity[0].principal_id
  ) : (
    module.managed_identity[0].principal_id
  )
}
