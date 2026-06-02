variable "organization" {
  description = "HCP Terraform organization name that owns the project, team, and token."
  type        = string
}

variable "hostname" {
  description = "HCP Terraform / Terraform Enterprise hostname."
  type        = string
  default     = "app.terraform.io"
}

variable "project_name" {
  description = "Name of the dedicated sandbox project the agents deploy into."
  type        = string
  default     = "sandbox"
}

variable "team_name" {
  description = "Name of the team whose token the devcontainer/agents consume."
  type        = string
  default     = "agent_sandbox_team"
}
