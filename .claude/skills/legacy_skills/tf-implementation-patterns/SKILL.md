---
name: tf-implementation-patterns
description: Common Terraform implementation patterns for AWS infrastructure. VPC, IAM, compute, storage, database, and deployment patterns using private registry modules.
---

# Terraform Implementation Patterns

Reference patterns for implementing AWS infrastructure using private registry modules. All patterns enforce module-first architecture and security-first defaults.

## Workflow

1. **Identify**: Determine infrastructure type needed (VPC, IAM, compute, storage, database)
2. **Search**: Query private registry for appropriate module (`search_private_modules`)
3. **Select**: Choose pattern from Context section matching the use case
4. **Adapt**: Customize pattern inputs for specific requirements
5. **Wire**: Connect module outputs to dependent module inputs
6. **Validate**: Run `terraform fmt` and `terraform validate`

## Output

- **Location**: Feature directory files (`main.tf`, `variables.tf`, `outputs.tf`, `locals.tf`)
- **Format**: HCL with private registry module blocks
- **Validation**: `terraform fmt` after every file change, `terraform validate` after every phase

## Constraints

- All infrastructure via private registry modules (`app.terraform.io/<org-name>/`)
- Provider auth via dynamic credentials (workspace variable sets — never override)
- `terraform fmt` after every file change
- `terraform validate` after every phase
- Commit incrementally per logical change
- ALL variables: `description` + `type` constraints
- Security-sensitive values: `sensitive = true`
- Business logic validation: use `validation` blocks

## Examples

**Good module declaration**:
```hcl
module "vpc" {
  source  = "app.terraform.io/acme-corp/vpc/aws"
  version = "~> 3.0"

  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  enable_flow_logs   = true

  tags = local.common_tags
}
```

**Bad module declaration** (public registry):
```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"
  # ...
}
```
Must use private registry (`app.terraform.io/<org>/`).

**Good variable definition**:
```hcl
variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}
```

**Bad variable definition**:
```hcl
variable "environment" {}
```
Missing description, type, and validation.

## Context

### AWS VPC Pattern

```hcl
module "vpc" {
  source  = "app.terraform.io/<org-name>/vpc/aws"
  version = "~> 3.0"

  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  enable_flow_logs   = true
  enable_nat_gateway = true

  tags = local.common_tags
}
```

| Consideration | Requirement |
|---------------|-------------|
| Availability | Multi-AZ (2-3 zones) |
| Subnets | Public/private/data tiers |
| Egress | NAT Gateway for private subnets |
| Logging | VPC Flow Logs always enabled |

### AWS IAM Pattern

```hcl
module "iam_role" {
  source  = "app.terraform.io/<org-name>/iam-role/aws"
  version = "~> 2.0"

  role_name   = "${var.app_name}-${var.environment}-role"
  description = "Service role for ${var.app_name}"

  policy_statements = [
    {
      effect    = "Allow"
      actions   = ["s3:GetObject", "s3:PutObject"]
      resources = ["${module.bucket.arn}/*"]
    }
  ]

  tags = local.common_tags
}
```

| Consideration | Requirement |
|---------------|-------------|
| Resources | Specific ARNs, never `*` |
| EC2 | Use instance profiles |
| Services | Service-linked roles where available |
| Credentials | No static credentials ever |

### AWS Compute Pattern

```hcl
module "compute" {
  source  = "app.terraform.io/<org-name>/ec2/aws"
  version = "~> 4.0"

  instance_type        = var.instance_type
  ami_id               = var.ami_id
  subnet_ids           = module.vpc.private_subnet_ids
  security_group_ids   = [module.sg.id]
  iam_instance_profile = module.iam_role.instance_profile_name

  metadata_options = {
    http_tokens = "required"  # IMDSv2
  }

  tags = local.common_tags
}
```

### AWS Storage Pattern

```hcl
module "s3_bucket" {
  source  = "app.terraform.io/<org-name>/s3-bucket/aws"
  version = "~> 2.0"

  bucket_name   = "${var.app_name}-${var.environment}-data"
  versioning    = true
  encryption    = true
  force_destroy = true  # Required for terraform destroy
  block_public  = true

  tags = local.common_tags
}
```

### AWS Database Pattern

```hcl
module "rds" {
  source  = "app.terraform.io/<org-name>/rds/aws"
  version = "~> 3.0"

  identifier     = "${var.app_name}-${var.environment}"
  engine         = var.db_engine
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  subnet_ids          = module.vpc.data_subnet_ids
  security_group_ids  = [module.db_sg.id]
  publicly_accessible = false
  multi_az            = var.environment == "prod"
  encrypted           = true
  backup_retention    = 7

  tags = local.common_tags
}
```

### Common Tags Pattern

```hcl
locals {
  common_tags = {
    Environment = var.environment
    Application = var.app_name
    ManagedBy   = "terraform"
    Owner       = var.owner
  }
}
```