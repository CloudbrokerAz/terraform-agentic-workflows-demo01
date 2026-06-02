# HCP Terraform Pre-requisites (bootstrap)

Terraform configuration (using the `hashicorp/tfe` provider) that provisions the
HCP Terraform pre-requisites from
[docs/getting_started.md](../../docs/getting_started.md) → *HCP Terraform Setup*:

- a dedicated **`sandbox`** project,
- the **`agent_sandbox_team`** team,
- **custom project team access** with exactly the documented permission matrix, and
- a **team API token** for the devcontainer/agents to consume.

Run this once per organization to bootstrap, then hand the token to the
devcontainer via `TEAM_TFE_TOKEN`.

## Prerequisites

- An HCP Terraform **organization** you administer.
- A **user** API token with permission to manage teams/projects, exported so the
  provider can authenticate:

  ```bash
  export TFE_TOKEN="<your-user-token>"   # owner/admin token, used only to bootstrap
  ```

> This bootstrap intentionally runs **locally** (CLI-driven), not in an HCP
> workspace — it creates the very team/token the workflow later relies on.

## Usage

```bash
cd demo_bootstrap/hcp-prereqs
cp terraform.tfvars.example terraform.tfvars   # set `organization`
terraform init
terraform plan
terraform apply
```

Retrieve the team token and wire it into your shell (the devcontainer maps
`TEAM_TFE_TOKEN` → `TFE_TOKEN`):

```bash
export TEAM_TFE_TOKEN="$(terraform output -raw team_token)"
# add to ~/.zshrc or ~/.bashrc to persist
```

## Permission mapping

The `tfe_team_project_access` resource (`access = "custom"`) maps 1:1 to the
getting-started matrix:

| Getting-started permission | Attribute | Value |
|---|---|---|
| Read (project) | `project_access.settings` | `read` |
| Create Workspaces | `workspace_access.create` | `true` |
| Delete Workspaces | `workspace_access.delete` | `true` |
| Read Variables | `workspace_access.variables` | `read` |
| Read State + Write State | `workspace_access.state_versions` | `write` (includes read) |
| Download Sentinel Mocks | `workspace_access.sentinel_mocks` | `read` |
| Lock/Unlock Workspaces | `workspace_access.locking` | `true` |
| Apply runs (deploy) | `workspace_access.runs` | `apply` |

`runs = "apply"` is **required** — the consumer workflow queues and applies runs
in the sandbox workspaces it creates, so a plan-only team cannot complete a
deploy. (This row is not in the getting-started table yet; the Terraform here is
the source of truth.)

## Inputs

| Variable | Default | Description |
|---|---|---|
| `organization` | _(required)_ | HCP Terraform organization name |
| `hostname` | `app.terraform.io` | HCP Terraform / TFE hostname |
| `project_name` | `sandbox` | Dedicated sandbox project name |
| `team_name` | `agent_sandbox_team` | Agent team name |

## Outputs

| Output | Description |
|---|---|
| `project_id` / `project_name` | The sandbox project |
| `team_id` / `team_name` | The agent team |
| `team_token` | Team API token (**sensitive**; shown only at creation) |

## State note

`terraform apply` stores the generated team token in Terraform state. Keep the
state secure (use a protected remote backend or delete local state after wiring
the token), and treat `terraform.tfvars` as untracked.

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
| ---- | ------- |
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.5 |
| <a name="requirement_tfe"></a> [tfe](#requirement\_tfe) | ~> 0.60 |

## Providers

| Name | Version |
| ---- | ------- |
| <a name="provider_tfe"></a> [tfe](#provider\_tfe) | 0.77.0 |

## Modules

No modules.

## Resources

| Name | Type |
| ---- | ---- |
| [tfe_project.sandbox](https://registry.terraform.io/providers/hashicorp/tfe/latest/docs/resources/project) | resource |
| [tfe_team.agent_sandbox](https://registry.terraform.io/providers/hashicorp/tfe/latest/docs/resources/team) | resource |
| [tfe_team_project_access.agent_sandbox](https://registry.terraform.io/providers/hashicorp/tfe/latest/docs/resources/team_project_access) | resource |
| [tfe_team_token.agent_sandbox](https://registry.terraform.io/providers/hashicorp/tfe/latest/docs/resources/team_token) | resource |

## Inputs

| Name | Description | Type | Default | Required |
| ---- | ----------- | ---- | ------- | :------: |
| <a name="input_hostname"></a> [hostname](#input\_hostname) | HCP Terraform / Terraform Enterprise hostname. | `string` | `"app.terraform.io"` | no |
| <a name="input_organization"></a> [organization](#input\_organization) | HCP Terraform organization name that owns the project, team, and token. | `string` | n/a | yes |
| <a name="input_project_name"></a> [project\_name](#input\_project\_name) | Name of the dedicated sandbox project the agents deploy into. | `string` | `"sandbox"` | no |
| <a name="input_team_name"></a> [team\_name](#input\_team\_name) | Name of the team whose token the devcontainer/agents consume. | `string` | `"agent_sandbox_team"` | no |

## Outputs

| Name | Description |
| ---- | ----------- |
| <a name="output_project_id"></a> [project\_id](#output\_project\_id) | ID of the dedicated sandbox project. |
| <a name="output_project_name"></a> [project\_name](#output\_project\_name) | Name of the dedicated sandbox project. |
| <a name="output_team_id"></a> [team\_id](#output\_team\_id) | ID of the agent sandbox team. |
| <a name="output_team_name"></a> [team\_name](#output\_team\_name) | Name of the agent sandbox team. |
| <a name="output_team_token"></a> [team\_token](#output\_team\_token) | Team API token for the agent sandbox team. Export this as TEAM\_TFE\_TOKEN on<br/>your host (the devcontainer maps it to TFE\_TOKEN). Retrieve with:<br/>  terraform output -raw team\_token<br/>The token is shown only at creation time and cannot be retrieved from HCP later. |
<!-- END_TF_DOCS -->
