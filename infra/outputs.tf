output "web_app_name" {
  description = "Linux Web App name."
  value       = azurerm_linux_web_app.api.name
}

output "web_app_url" {
  description = "Default HTTPS URL."
  value       = "https://${azurerm_linux_web_app.api.default_hostname}"
}

output "web_app_principal_id" {
  description = "Managed identity principal (object) ID — use for Fabric workspace access."
  value       = local.managed_identity_principal_id
}

output "web_app_client_id" {
  description = "Client ID (user-assigned only; null for system-assigned)."
  value       = var.identity_type == "UserAssigned" ? module.managed_identity[0].client_id : null
}

output "resource_group_name" {
  value = local.resource_group_name
}

output "health_check_url" {
  value = "https://${azurerm_linux_web_app.api.default_hostname}/health"
}

output "swagger_url" {
  value = "https://${azurerm_linux_web_app.api.default_hostname}/docs"
}
