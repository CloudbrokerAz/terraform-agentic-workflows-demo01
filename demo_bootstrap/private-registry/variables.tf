variable "organization" {
  description = "HCP Terraform organization whose private registry receives the modules."
  type        = string
}

variable "hostname" {
  description = "HCP Terraform / Terraform Enterprise hostname."
  type        = string
  default     = "app.terraform.io"
}

variable "github_org" {
  description = "GitHub org/owner that holds the forked terraform-aws-* repos."
  type        = string
}

variable "oauth_token_id" {
  description = <<-EOT
    VCS connection (OAuth) token ID in HCP Terraform, e.g. "ot-xxxxxxxx".
    Find it under Settings -> Version Control. Mutually exclusive with
    github_app_installation_id; set exactly one.
  EOT
  type        = string
  default     = null
}

variable "github_app_installation_id" {
  description = <<-EOT
    GitHub App installation ID in HCP Terraform, e.g. "ghain-xxxxxxxx".
    Mutually exclusive with oauth_token_id; set exactly one.
  EOT
  type        = string
  default     = null
}

variable "branch" {
  description = "Git branch to publish from (branch-based publishing) for every forked module."
  type        = string
  default     = "main"
}

variable "initial_version" {
  description = "Initial module version for branch-based publishing (HCP default is 0.0.0)."
  type        = string
  default     = "0.0.0"
}

variable "module_repos" {
  description = <<-EOT
    Minimum set of forked public AWS modules to publish into the private
    registry. Each entry is a GitHub repo name in `github_org`, named with the
    `terraform-<provider>-<name>` convention so HCP infers the registry module
    name and provider (e.g. terraform-aws-vpc -> aws/vpc). Publishing is
    branch-based (see `branch`), so the forks do not need semver git tags.
  EOT
  type        = list(string)
  default = [
    "terraform-aws-vpc",
    "terraform-aws-security-group",
    "terraform-aws-sqs",
    "terraform-aws-sns",
    "terraform-aws-lambda",
    "terraform-aws-iam",
    "terraform-aws-cloudwatch",
    "terraform-aws-ec2-instance",
    "terraform-aws-autoscaling",
    "terraform-aws-alb",
    "terraform-aws-cloudfront",
    "terraform-aws-s3-bucket",
  ]
}
