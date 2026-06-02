# Stage a minimum set of AWS modules into the HCP Terraform private registry.
#
# Modules are forks of the top public terraform-aws-modules repos, published
# branch-based from `var.branch`. Repo names follow the
# `terraform-<provider>-<name>` convention so HCP infers the registry module
# name and provider (e.g. terraform-aws-vpc -> aws/vpc).
#
# The forks themselves are created by ./fork-modules.sh (Terraform/tfe cannot
# fork GitHub repos). A VCS connection must already exist in the organization;
# pass its id via oauth_token_id or github_app_installation_id.

resource "tfe_registry_module" "this" {
  for_each = toset(var.module_repos)

  organization = var.organization

  vcs_repo {
    identifier         = "${var.github_org}/${each.value}"
    display_identifier = "${var.github_org}/${each.value}"

    # Exactly one of these must be set (the other stays null).
    oauth_token_id             = var.oauth_token_id
    github_app_installation_id = var.github_app_installation_id

    # Branch-based publishing: set branch, leave tags unset.
    branch = var.branch
  }

  initial_version = var.initial_version
}
