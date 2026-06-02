output "project_id" {
  description = "ID of the dedicated sandbox project."
  value       = tfe_project.sandbox.id
}

output "project_name" {
  description = "Name of the dedicated sandbox project."
  value       = tfe_project.sandbox.name
}

output "team_id" {
  description = "ID of the agent sandbox team."
  value       = tfe_team.agent_sandbox.id
}

output "team_name" {
  description = "Name of the agent sandbox team."
  value       = tfe_team.agent_sandbox.name
}

output "team_token" {
  description = <<-EOT
    Team API token for the agent sandbox team. Export this as TEAM_TFE_TOKEN on
    your host (the devcontainer maps it to TFE_TOKEN). Retrieve with:
      terraform output -raw team_token
    The token is shown only at creation time and cannot be retrieved from HCP later.
  EOT
  value       = tfe_team_token.agent_sandbox.token
  sensitive   = true
}
