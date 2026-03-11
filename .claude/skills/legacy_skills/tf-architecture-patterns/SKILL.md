---
name: tf-architecture-patterns
description: >
  Terraform architecture patterns, module composition conventions, and project
  structure standards. Covers VPC, IAM, compute, storage, and database patterns
  for AWS module consumption.

# Terraform Architecture Patterns

## Module-First Architecture

All infrastructure MUST be provisioned through approved modules from the Private Module Registry (`app.terraform.io/<org-name>/`).

### Module Composition Rules
- Search and prioritize existing modules from private registry
- Module source MUST begin with `app.terraform.io/<org-name>/`
- MUST NOT use public registry sources
- Module consumption MUST follow semantic versioning (`version = "~> 2.1.0"`)
- If required module doesn't exist, surface gap to user — do NOT improvise with raw resources

### Module Usage Pattern
```hcl
module "vpc" {
  source  = "app.terraform.io/<org-name>/vpc/aws"
  version = "~> 3.2.0"

  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  enable_flow_logs   = true  # Required by security policy

  tags = local.common_tags
}
```

## Project Structure Convention

```
/
├── main.tf              # Module declarations
├── variables.tf         # Input variables with validation
├── outputs.tf           # Output exports with descriptions
├── locals.tf            # Computed values
├── providers.tf         # Provider config (no credentials)
├── terraform.tf         # Version constraints
├── override.tf          # HCP backend (testing, gitignored)
├── sandbox.auto.tfvars          # Test values (gitignored)
├── sandbox.auto.tfvars.example  # Committed example with placeholder values
└── README.md                    # Auto-generated via terraform-docs
```

## File Organization Rules
- No monolithic files exceeding 500 lines
- No intermingling resource types without logical grouping
- No default values for security-sensitive variables
- Variables: snake_case with descriptive names
- Resources: `<app>-<resource-type>-<purpose>`

## Security-First Defaults

- Zero trust: No static credentials in code
- Provider auth via dynamic credentials (workspace variable sets)
- Encryption at rest and in transit by default
- IAM least privilege — no wildcard permissions
- Private subnets for compute/database workloads
- Security groups deny all by default
- Ephemeral resources for secrets (not data sources)
- `sensitive = true` on all secret outputs

## AWS Architecture Patterns

### VPC Pattern
- Multi-AZ deployment across 2-3 availability zones
- Public/private/data subnet tiers
- NAT Gateway for private subnet egress
- VPC Flow Logs enabled
- No direct internet access for data tier

### IAM Pattern
- Role-based access with specific resource ARNs
- Instance profiles for EC2 (no embedded credentials)
- Service-linked roles where available
- Cross-account access via assume-role

### Compute Pattern
- Auto-scaling groups with health checks
- Launch templates (not launch configurations)
- IMDSv2 required
- SSM Session Manager for access (no SSH keys)

### Storage Pattern
- S3: versioning, encryption, public access blocked (`force_destroy` only in non-production)
- EBS: encrypted by default, appropriate volume types
- Lifecycle policies for cost optimization

### Database Pattern
- Multi-AZ for production
- Automated backups enabled
- Encryption at rest
- Private subnet placement (not publicly accessible)
- Parameter groups for tuning

## AWS Style Requirements

### Mandatory Resource Tagging (AWS-TAG-001 - MUST)

All taggable AWS resources MUST include an `Application` tag. Configure `default_tags` at provider level:

```hcl
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Application = var.application_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
```

### AWS Resource Naming (AWS-NAME-001 - SHOULD)

Pattern: `{application}-{environment}-{resource-type}-{identifier}`

For DNS-compatible names: lowercase letters, numbers, hyphens only; 3-63 chars.

### AWS Provider Configuration (AWS-PROV-001 - SHOULD)

- Use pessimistic version constraints (`~> 5.0`)
- Multi-region: use clear provider aliases
- Cross-account: use `assume_role` with proper session naming
