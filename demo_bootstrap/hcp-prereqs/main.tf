# HCP Terraform pre-requisites for the agentic Terraform workflow.
#
# Creates the dedicated sandbox project, the agent team, the custom project
# team access, and the team API token described in docs/getting_started.md
# (section "HCP Terraform Setup").

# Dedicated project that isolates agent/test workspaces from production.
resource "tfe_project" "sandbox" {
  organization = var.organization
  name         = var.project_name
}

# Dedicated team whose token the devcontainer maps to TFE_TOKEN.
resource "tfe_team" "agent_sandbox" {
  organization = var.organization
  name         = var.team_name
}

# Custom project team access — mirrors the permission matrix in
# docs/getting_started.md exactly.
resource "tfe_team_project_access" "agent_sandbox" {
  access     = "custom"
  team_id    = tfe_team.agent_sandbox.id
  project_id = tfe_project.sandbox.id

  # --- Project Access -------------------------------------------------------
  project_access {
    settings = "read" # "Read" — list and view project workspaces
  }

  # --- Workspace Permissions ------------------------------------------------
  workspace_access {
    create         = true    # "Create Workspaces" — consumer workflows create sandbox workspaces
    delete         = true    # "Delete Workspaces" — clean up sandbox workspaces after testing
    variables      = "read"  # "Read Variables"     — inspect workspace configuration
    state_versions = "write" # "Read State" + "Write State" (write includes read)
    sentinel_mocks = "read"  # "Download Sentinel Mocks" — policy testing support
    locking        = true    # "Lock/Unlock Workspaces" — prevent concurrent modifications during runs
    runs           = "apply" # Required: queue and apply runs in the sandbox workspaces the workflow creates
  }
}

# Team API token the agents/devcontainer consume (export as TEAM_TFE_TOKEN).
resource "tfe_team_token" "agent_sandbox" {
  team_id = tfe_team.agent_sandbox.id
}
