resource "azurerm_resource_group" "rg" {
  count    = var.create_resource_group ? 1 : 0
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

data "azurerm_resource_group" "rg" {
  count = var.create_resource_group ? 0 : 1
  name  = var.resource_group_name
}

locals {
  resource_group_name = var.create_resource_group ? azurerm_resource_group.rg[0].name : data.azurerm_resource_group.rg[0].name
  resource_group_location = var.create_resource_group ? azurerm_resource_group.rg[0].location : data.azurerm_resource_group.rg[0].location
}

module "managed_identity" {
  count  = var.identity_type == "UserAssigned" ? 1 : 0
  source = "./modules/managed_identity"

  name                = coalesce(var.user_assigned_identity_name, "${var.app_name}-mi")
  resource_group_name = local.resource_group_name
  location            = local.resource_group_location
  tags                = var.tags
}

resource "azurerm_service_plan" "plan" {
  name                = local.service_plan_name
  resource_group_name = local.resource_group_name
  location            = local.resource_group_location
  os_type             = "Linux"
  sku_name            = var.service_plan_sku
  tags                = var.tags
}

resource "azurerm_linux_web_app" "api" {
  name                = var.app_name
  resource_group_name = local.resource_group_name
  location            = local.resource_group_location
  service_plan_id     = azurerm_service_plan.plan.id
  tags                = var.tags

  identity {
    type = var.identity_type
    identity_ids = var.identity_type == "UserAssigned" ? [
      module.managed_identity[0].id
    ] : []
  }

  site_config {
    always_on        = true
    app_command_line = var.startup_command

    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = local.app_settings

  lifecycle {
    ignore_changes = [
      # Deployment pipelines often set these outside Terraform.
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
    ]
  }
}

resource "azurerm_role_assignment" "foundry" {
  count                = var.foundry_rbac_scope_id != null ? 1 : 0
  scope                = var.foundry_rbac_scope_id
  role_definition_name = var.foundry_role_definition_name
  principal_id         = local.managed_identity_principal_id
}

resource "azurerm_role_assignment" "openai" {
  count                = var.openai_rbac_scope_id != null ? 1 : 0
  scope                = var.openai_rbac_scope_id
  role_definition_name = var.openai_role_definition_name
  principal_id         = local.managed_identity_principal_id
}
