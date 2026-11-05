terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.14"
    }
  }
  # Estado remoto en Azure Storage; se configura con -backend-config en el pipeline.
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  use_oidc                        = true
  storage_use_azuread             = true
  resource_provider_registrations = "none"
}

variable "resource_group_name" {
  type    = string
  default = "rg-fabrica-legado"
}

variable "location" {
  type    = string
  default = "eastus2"
}

data "azurerm_client_config" "actual" {}

data "azurerm_resource_group" "rg" {
  name = var.resource_group_name
}

locals {
  sufijo = substr(sha1(data.azurerm_client_config.actual.subscription_id), 0, 6)
  tags   = { proyecto = "fabrica-migracion", app = "banco-transferencias-legado", datos = "ficticios" }
}

resource "azurerm_service_plan" "plan" {
  name                = "asp-bancolegado-${local.sufijo}"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "B1"
  tags                = local.tags
}

resource "azurerm_linux_web_app" "app" {
  name                = "app-bancolegado-${local.sufijo}"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.location
  service_plan_id     = azurerm_service_plan.plan.id
  https_only          = true
  tags                = local.tags

  site_config {
    always_on                         = true
    ftps_state                        = "Disabled"
    minimum_tls_version               = "1.2"
    health_check_path                 = "/api/salud"
    health_check_eviction_time_in_min = 10
    # Un solo worker: SQLite no admite bien escritores concurrentes.
    app_command_line = "gunicorn --bind=0.0.0.0 --timeout 60 --workers 1 --threads 4 wsgi:app"
    application_stack {
      python_version = "3.12"
    }
  }

  app_settings = {
    SCM_DO_BUILD_DURING_DEPLOYMENT      = "true"
    WEBSITES_ENABLE_APP_SERVICE_STORAGE = "true"
    DATABASE_PATH                       = "/home/data/transferencias.db"
    DEMO_MODE                           = "1"
  }
}

output "app_name" {
  value = azurerm_linux_web_app.app.name
}

output "url" {
  value = "https://${azurerm_linux_web_app.app.default_hostname}"
}
