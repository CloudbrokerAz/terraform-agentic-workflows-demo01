terraform {
  required_version = ">= 1.5"

  required_providers {
    tfe = {
      source  = "hashicorp/tfe"
      version = "~> 0.60"
    }
  }
}

# Authentication: the provider reads the token from the TFE_TOKEN environment
# variable (or a `terraform login` credentials block). Use a user/team token
# with permission to manage the organization's private module registry.
provider "tfe" {
  hostname     = var.hostname
  organization = var.organization
}
