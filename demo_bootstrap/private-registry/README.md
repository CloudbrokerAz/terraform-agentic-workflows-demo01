# Private Registry Pre-requisites (bootstrap)

Stages a **minimum set of AWS modules** into the HCP Terraform **private
registry** so the consumer workflow has modules to compose from
(`source = "app.terraform.io/<org>/<name>/aws"`).

The modules are **forks of the top public `terraform-aws-modules` repos**,
published **branch-based** from your GitHub org.

## What it creates

`tfe_registry_module` (VCS-backed, branch-based) for each fork in
`var.module_repos`. Repo names follow `terraform-<provider>-<name>`, so HCP
infers the registry name and provider (e.g. `terraform-aws-vpc` -> `aws/vpc`).

Default minimum set (covers the consumer demo prompts):

`vpc`, `security-group`, `sqs`, `sns`, `lambda`, `iam`, `cloudwatch`,
`ec2-instance`, `autoscaling`, `alb`, `cloudfront`, `s3-bucket`.

## Two steps (one script + Terraform)

Terraform/`tfe` cannot fork GitHub repos or create the VCS connection, so the
flow is:

### 1. Fork the public modules (`gh` script)

```bash
cd demo_bootstrap/private-registry

# Preview first (no changes):
GITHUB_ORG=hashi-demos-apj HCP_ORG=hashi-demos-apj TFE_TOKEN="$TFE_TOKEN" ./fork-modules.sh --dry-run

# Then run for real:
GITHUB_ORG=hashi-demos-apj HCP_ORG=hashi-demos-apj TFE_TOKEN="$TFE_TOKEN" ./fork-modules.sh
```

`--dry-run` (`-n`) reports what would be forked/skipped and makes no changes.
Forks `terraform-aws-modules/<repo>` into your org for each module. Before
forking it **checks the designated HCP Terraform private registry** (via the
TFE API) and skips any module already published there; it also skips repos that
already exist as a fork.

It then **reconciles the publish branch**: upstream `terraform-aws-*` repos
default to `master`, but publishing uses `main` (`PUBLISH_BRANCH` / `var.branch`),
so for each fork the script creates `main` from the fork's default branch when
it is missing. `--dry-run` previews this without making changes.

Requires `gh` (authenticated, repo write), `curl`, and `jq`.

| Env | Default | Purpose |
|---|---|---|
| `GITHUB_ORG` | _(required)_ | Target GitHub org for the forks |
| `HCP_ORG` | `$GITHUB_ORG` | HCP org whose private registry is checked |
| `TFE_TOKEN` | _(unset)_ | HCP token for the registry check (omit → GitHub-fork check only) |
| `TFE_HOSTNAME` | `app.terraform.io` | HCP / TFE hostname |
| `SOURCE_ORG` | `terraform-aws-modules` | Upstream org to fork from |

### 2. Connect a VCS provider (one-time, manual)

In HCP Terraform: **Settings -> Version Control -> Add a VCS provider**. Note the
resulting **OAuth token ID** (`ot-…`) or **GitHub App installation ID**
(`ghain-…`). Terraform can't bootstrap the OAuth handshake.

### 3. Publish into the private registry (Terraform)

```bash
export TFE_TOKEN="<user-or-team-token>"
cp terraform.tfvars.example terraform.tfvars   # set organization, github_org, oauth_token_id
terraform init
terraform plan
terraform apply
```

## Inputs

| Variable | Default | Description |
|---|---|---|
| `organization` | _(required)_ | HCP Terraform org |
| `github_org` | _(required)_ | GitHub owner holding the forks |
| `oauth_token_id` | `null` | HCP VCS OAuth token ID — set this **or** the GitHub App id |
| `github_app_installation_id` | `null` | HCP GitHub App installation ID |
| `hostname` | `app.terraform.io` | HCP / TFE hostname |
| `branch` | `main` | Branch to publish from (branch-based) |
| `initial_version` | `0.0.0` | Initial module version |
| `module_repos` | _(12 repos)_ | Fork repo names to publish |

> Keep the `MODULES` list in `fork-modules.sh` in sync with `var.module_repos`.

## Outputs

| Output | Description |
|---|---|
| `published_modules` | repo -> private registry source address |
| `module_count` | number of modules published |

## Notes

- **Branch-based publishing**: new versions come from commits on `branch`; the
  forks do not need semver git tags.
- `terraform.tfvars` is gitignored — keep org/VCS ids out of version control.

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
| [tfe_registry_module.this](https://registry.terraform.io/providers/hashicorp/tfe/latest/docs/resources/registry_module) | resource |

## Inputs

| Name | Description | Type | Default | Required |
| ---- | ----------- | ---- | ------- | :------: |
| <a name="input_branch"></a> [branch](#input\_branch) | Git branch to publish from (branch-based publishing) for every forked module. | `string` | `"main"` | no |
| <a name="input_github_app_installation_id"></a> [github\_app\_installation\_id](#input\_github\_app\_installation\_id) | GitHub App installation ID in HCP Terraform, e.g. "ghain-xxxxxxxx".<br/>Mutually exclusive with oauth\_token\_id; set exactly one. | `string` | `null` | no |
| <a name="input_github_org"></a> [github\_org](#input\_github\_org) | GitHub org/owner that holds the forked terraform-aws-* repos. | `string` | n/a | yes |
| <a name="input_hostname"></a> [hostname](#input\_hostname) | HCP Terraform / Terraform Enterprise hostname. | `string` | `"app.terraform.io"` | no |
| <a name="input_initial_version"></a> [initial\_version](#input\_initial\_version) | Initial module version for branch-based publishing (HCP default is 0.0.0). | `string` | `"0.0.0"` | no |
| <a name="input_module_repos"></a> [module\_repos](#input\_module\_repos) | Minimum set of forked public AWS modules to publish into the private<br/>registry. Each entry is a GitHub repo name in `github_org`, named with the<br/>`terraform-<provider>-<name>` convention so HCP infers the registry module<br/>name and provider (e.g. terraform-aws-vpc -> aws/vpc). Publishing is<br/>branch-based (see `branch`), so the forks do not need semver git tags. | `list(string)` | <pre>[<br/>  "terraform-aws-vpc",<br/>  "terraform-aws-security-group",<br/>  "terraform-aws-sqs",<br/>  "terraform-aws-sns",<br/>  "terraform-aws-lambda",<br/>  "terraform-aws-iam",<br/>  "terraform-aws-cloudwatch",<br/>  "terraform-aws-ec2-instance",<br/>  "terraform-aws-autoscaling",<br/>  "terraform-aws-alb",<br/>  "terraform-aws-cloudfront",<br/>  "terraform-aws-s3-bucket"<br/>]</pre> | no |
| <a name="input_oauth_token_id"></a> [oauth\_token\_id](#input\_oauth\_token\_id) | VCS connection (OAuth) token ID in HCP Terraform, e.g. "ot-xxxxxxxx".<br/>Find it under Settings -> Version Control. Mutually exclusive with<br/>github\_app\_installation\_id; set exactly one. | `string` | `null` | no |
| <a name="input_organization"></a> [organization](#input\_organization) | HCP Terraform organization whose private registry receives the modules. | `string` | n/a | yes |

## Outputs

| Name | Description |
| ---- | ----------- |
| <a name="output_module_count"></a> [module\_count](#output\_module\_count) | Number of modules published into the private registry. |
| <a name="output_published_modules"></a> [published\_modules](#output\_published\_modules) | Private registry source addresses for the published modules. |
<!-- END_TF_DOCS -->
