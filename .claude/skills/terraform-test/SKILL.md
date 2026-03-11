---
name: terraform-test
description: Comprehensive guide for writing and running Terraform tests. Use when creating test files (.tftest.hcl), writing test scenarios with run blocks, validating infrastructure behavior, mocking providers, and troubleshooting test execution.
user-invocable: true
argument-hint: "No arguments — reference guide for Terraform test patterns"
---

# Terraform Test

Terraform's built-in testing framework enables module authors to validate that configuration updates don't introduce breaking changes. Tests execute against temporary resources, protecting existing infrastructure and state files.

## TDD Workflow

The SDD workflow adopts a **test-first approach** for Terraform modules. Tests are the starting point, not an afterthought.

### Test-First Principle

1. **Test files (.tftest.hcl) are written BEFORE module code.** The `tf-module-test-writer` agent reads `design.md` Section 5 (Test Scenarios) and generates complete test files before any `.tf` files exist.
2. **Tests are expected to FAIL initially.** This is by design -- a failing test confirms the test is actually exercising real conditions. The red-green-refactor cycle applies:
   - **Red**: Tests fail because the module code does not yet exist
   - **Green**: Implementation is added until tests pass
   - **Refactor**: Code is cleaned up while keeping tests green
3. **Each implementation step should end with `terraform test` to check progress.** After writing or modifying any `.tf` file, run `terraform test` to see which tests now pass and which still fail. This gives a clear progress indicator.
4. **Tests drive the implementation.** The test scenarios from `design.md` Section 5 define what the module must do. The implementation is complete when all tests pass.

### TDD Execution Flow

```
design.md Section 5 (Test Scenarios)
        |
        v
tf-module-test-writer generates .tftest.hcl files
        |
        v
terraform test --> ALL FAIL (expected)
        |
        v
Implement variables.tf, main.tf, outputs.tf
        |
        v
terraform test --> SOME PASS, some fail
        |
        v
Continue implementation...
        |
        v
terraform test --> ALL PASS (done!)
```

### Test File Organization Convention

Tests should be organized into three standard files:

- **`tests/basic.tftest.hcl`** -- Minimal inputs, default behaviors. Tests that the module works with only required variables and produces expected defaults.
- **`tests/complete.tftest.hcl`** -- All inputs, full feature set. Tests every variable, optional feature, and conditional resource path.
- **`tests/validation.tftest.hcl`** -- Invalid input testing with `expect_failures`. Tests that validation rules correctly reject bad inputs.

```
my-module/
├── main.tf
├── variables.tf
├── outputs.tf
└── tests/
    ├── basic.tftest.hcl
    ├── complete.tftest.hcl
    └── validation.tftest.hcl
```

## Test Patterns

These six patterns form the core testing vocabulary for modules.

### 1. Plan-Only Testing

Use `command = plan` for fast validation without creating real resources. This is the default for TDD because it requires no cloud credentials and runs in seconds.

```hcl
run "test_default_instance_type" {
  command = plan

  variables {
    name = "test-instance"
  }

  assert {
    condition     = aws_instance.main.instance_type == "t3.micro"
    error_message = "Default instance type should be t3.micro"
  }
}
```

### 2. Conditional Resource Testing

Test `count` and `for_each` logic using `resource.name[0]` index patterns. When `count` is used, resources become lists and must be accessed by index.

```hcl
run "test_optional_resource_created" {
  command = plan

  variables {
    enable_monitoring = true
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.cpu[*]) == 1
    error_message = "Monitoring alarm should be created when enabled"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.cpu[0].alarm_name == "cpu-high"
    error_message = "Alarm name should be 'cpu-high'"
  }
}

run "test_optional_resource_not_created" {
  command = plan

  variables {
    enable_monitoring = false
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.cpu[*]) == 0
    error_message = "Monitoring alarm should not be created when disabled"
  }
}
```

### 3. Validation Testing

Test input validation rules using `expect_failures = [var.name]`. The test passes when the specified variable's validation rule correctly rejects the input.

```hcl
run "test_empty_name_rejected" {
  command = plan

  variables {
    name = ""
  }

  expect_failures = [var.name]
}

run "test_invalid_environment_rejected" {
  command = plan

  variables {
    name        = "test"
    environment = "invalid-env"
  }

  expect_failures = [var.environment]
}

run "test_cidr_format_rejected" {
  command = plan

  variables {
    name     = "test"
    vpc_cidr = "not-a-cidr"
  }

  expect_failures = [var.vpc_cidr]
}
```

### 4. Cross-Variable Testing

Test multiple input combinations in a single run block to validate interactions between variables.

```hcl
run "test_production_configuration" {
  command = plan

  variables {
    name             = "prod-app"
    environment      = "production"
    instance_type    = "m5.large"
    min_size         = 3
    max_size         = 10
    enable_monitoring = true
    enable_backups    = true
  }

  assert {
    condition     = aws_autoscaling_group.main.min_size == 3
    error_message = "Production should have min_size of 3"
  }

  assert {
    condition     = aws_autoscaling_group.main.max_size == 10
    error_message = "Production should have max_size of 10"
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.cpu[*]) == 1
    error_message = "Production should have monitoring enabled"
  }

  assert {
    condition     = length(aws_backup_plan.main[*]) == 1
    error_message = "Production should have backups enabled"
  }
}

run "test_development_configuration" {
  command = plan

  variables {
    name             = "dev-app"
    environment      = "development"
    instance_type    = "t3.micro"
    min_size         = 1
    max_size         = 2
    enable_monitoring = false
    enable_backups    = false
  }

  assert {
    condition     = aws_autoscaling_group.main.min_size == 1
    error_message = "Development should have min_size of 1"
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.cpu[*]) == 0
    error_message = "Development should not have monitoring"
  }

  assert {
    condition     = length(aws_backup_plan.main[*]) == 0
    error_message = "Development should not have backups"
  }
}
```

### 5. Security Assertion Testing

Test security-critical configurations: encryption at rest, public access blocking, logging enablement.

**Important**: Many AWS provider nested blocks (SSE `rule`, lifecycle `transition`, CORS `cors_rule`, security group `ingress`/`egress`) are `set` types, not lists. Sets cannot be indexed with `[0]`. Use `one()` to extract the single element from a set-typed block.

```hcl
run "test_encryption_enabled" {
  command = plan

  variables {
    name = "secure-bucket"
  }

  # SSE rule is a set — use one() not [0]
  assert {
    condition     = one(aws_s3_bucket_server_side_encryption_configuration.main.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "aws:kms"
    error_message = "S3 bucket must use KMS encryption"
  }
}

run "test_public_access_blocked" {
  command = plan

  variables {
    name = "secure-bucket"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.main.block_public_acls == true
    error_message = "Public ACLs must be blocked"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.main.block_public_policy == true
    error_message = "Public policy must be blocked"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.main.ignore_public_acls == true
    error_message = "Public ACLs must be ignored"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.main.restrict_public_buckets == true
    error_message = "Public buckets must be restricted"
  }
}

run "test_logging_enabled" {
  command = plan

  variables {
    name              = "secure-bucket"
    enable_logging    = true
    logging_bucket_id = "my-log-bucket"
  }

  assert {
    condition     = length(aws_s3_bucket_logging.main[*]) == 1
    error_message = "Logging should be enabled when configured"
  }
}
```

### 6. Mock Provider Testing

Use `mock_provider` blocks for fully isolated unit tests that need no cloud credentials. Mocks only work with `command = plan`.

```hcl
mock_provider "aws" {
  mock_resource "aws_s3_bucket" {
    defaults = {
      id     = "test-bucket-12345"
      arn    = "arn:aws:s3:::test-bucket-12345"
      bucket = "test-bucket-12345"
      region = "us-west-2"
    }
  }

  mock_resource "aws_s3_bucket_versioning" {
    defaults = {
      id     = "test-bucket-12345"
      bucket = "test-bucket-12345"
    }
  }

  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
      arn        = "arn:aws:iam::123456789012:root"
    }
  }
}

run "test_bucket_naming_convention" {
  command = plan

  variables {
    name        = "my-app"
    environment = "production"
  }

  assert {
    condition     = aws_s3_bucket.main.bucket == "my-app-production-123456789012"
    error_message = "Bucket name should follow naming convention: {name}-{env}-{account_id}"
  }
}

run "test_versioning_enabled" {
  command = plan

  variables {
    name              = "my-app"
    environment       = "production"
    enable_versioning = true
  }

  assert {
    condition     = aws_s3_bucket_versioning.main[0].versioning_configuration[0].status == "Enabled"
    error_message = "Versioning should be enabled when configured"
  }
}
```

## Core Concepts

| Concept           | Description                                                                       |
| ----------------- | --------------------------------------------------------------------------------- |
| **Test File**     | `.tftest.hcl` or `.tftest.json` file containing test configuration and run blocks |
| **Test Block**    | Optional block for test-wide settings like parallel execution (since v1.6.0)      |
| **Run Block**     | Defines a single test scenario with variables, providers, and assertions          |
| **Assert Block**  | Condition that must evaluate to true for the test to pass                         |
| **Mock Provider** | Simulates provider behavior without real infrastructure (since v1.7.0)            |
| **Plan Mode**     | `command = plan` - validates logic without creating resources (unit test)         |
| **Apply Mode**    | `command = apply` (default) - creates real infrastructure (integration test)      |

## File Structure

```
my-module/
├── main.tf
├── variables.tf
├── outputs.tf
└── tests/
    ├── defaults_unit_test.tftest.hcl
    ├── validation_unit_test.tftest.hcl
    └── full_stack_integration_test.tftest.hcl
```

A test file contains:

- **Zero to one** `test` block (settings)
- **One to many** `run` blocks (test executions)
- **Zero to one** `variables` block (input values)
- **Zero to many** `provider` blocks
- **Zero to many** `mock_provider` blocks (since v1.7.0)

## Test Block

```hcl
test {
  parallel = true  # Enable parallel execution for all run blocks (default: false)
}
```

## Run Block

Each run block executes a command against your configuration. Run blocks execute **sequentially by default**.

```hcl
run "test_name" {
  command = plan  # or apply (default)

  variables {
    key = "value"
  }

  assert {
    condition     = aws_instance.example.instance_type == "t2.micro"
    error_message = "Instance type should be t2.micro"
  }
}
```

**Run Block Attributes:**

| Attribute         | Description                                                     |
| ----------------- | --------------------------------------------------------------- |
| `command`         | `apply` (default) or `plan`                                     |
| `plan_options`    | Configure plan behavior: `mode`, `refresh`, `replace`, `target` |
| `variables`       | Override test-level variable values                             |
| `module`          | Reference alternate modules (`source`, `version`)               |
| `providers`       | Customize provider availability                                 |
| `assert`          | Validation conditions (multiple allowed)                        |
| `expect_failures` | Specify expected validation failures                            |
| `state_key`       | Manage state file isolation (since v1.9.0)                      |
| `parallel`        | Enable parallel execution (since v1.9.0)                        |

## Variables

Variables defined in test files have the **highest precedence**, overriding environment variables, `.tfvars` files, and `-var` flags.

- File-level `variables {}` block applies to all run blocks
- Run-level `variables {}` overrides file-level values
- Run blocks can reference prior run outputs: `run.<block_name>.<output>`

## Assert Block

```hcl
assert {
  condition     = <expression>
  error_message = "failure description"
}
```

Multiple assertions per run block are allowed. All must pass.

## Expect Failures

Test that validation rules correctly reject invalid input. The test **passes** if the specified checkable objects fail.

```hcl
run "test_invalid_input" {
  command = plan
  variables { instance_count = -1 }
  expect_failures = [var.instance_count]
}
```

Checkable objects: input variables, output values, check blocks, resources, data sources.

## Module Block

Test specific modules rather than root configuration.

**Supported sources:** local paths (`./modules/vpc`), public registry (`terraform-aws-modules/vpc/aws`), private registry (`app.terraform.io/org/module/provider`).

**Not supported:** Git repositories, HTTP URLs, S3/GCS sources.

```hcl
run "test_vpc_module" {
  command = plan
  module {
    source  = "./modules/vpc"
  }
  variables { cidr_block = "10.0.0.0/16" }
  assert {
    condition     = aws_vpc.main.cidr_block == "10.0.0.0/16"
    error_message = "VPC CIDR should match input"
  }
}
```

## Mock Providers

Simulate provider behavior without creating real infrastructure (requires Terraform 1.7.0+). Mocks only work with `command = plan`.

```hcl
mock_provider "aws" {
  mock_resource "aws_instance" {
    defaults = {
      id            = "i-1234567890abcdef0"
      instance_type = "t2.micro"
    }
  }

  mock_data "aws_ami" {
    defaults = {
      id = "ami-12345678"
    }
  }
}

run "test_with_mocks" {
  command = plan
  assert {
    condition     = aws_instance.example.id == "i-1234567890abcdef0"
    error_message = "Mock instance ID should match"
  }
}
```

## Parallel Execution

Requirements for `parallel = true`:

- No inter-run output references
- Different state files (via different modules or `state_key`)
- A non-parallel run block after parallel ones creates a synchronization point

## State Key Management

By default, main configuration shares state across run blocks; alternate modules get separate state. Use `state_key` to explicitly control sharing.

```hcl
run "step_a" {
  command   = apply
  module    { source = "./modules/a" }
  state_key = "shared"
}
run "step_b" {
  command   = apply
  module    { source = "./modules/b" }
  state_key = "shared"  # Shares state with step_a
}
```

## Cleanup

Resources are destroyed in **reverse run block order** after test completion. Use `terraform test -no-cleanup` for debugging.

## Test Execution

```bash
terraform test                                    # Run all tests
terraform test tests/defaults.tftest.hcl          # Run specific file
terraform test -verbose                           # Verbose output
terraform test -test-directory=integration-tests  # Specific directory
terraform test -filter=test_vpc_configuration     # Filter by name
terraform test -no-cleanup                        # Skip cleanup (debug)
```

## Plan-Mode Limitations

When using `command = plan`, be aware of these constraints:

1. **Output values are unknown**: Computed outputs (those depending on provider-assigned attributes like ARNs, endpoints, IDs) are unknown during plan. Assert on resource attributes directly, not on `output.*` values.

```hcl
# BAD — output.website_endpoint is unknown during plan
assert {
  condition     = output.website_endpoint != null
  error_message = "Website endpoint must not be null"
}

# GOOD — assert on the resource attribute instead
assert {
  condition     = length(aws_s3_bucket_website_configuration.this[*]) == 1
  error_message = "Website configuration must be created when enabled"
}
```

2. **Set-typed blocks cannot be indexed**: Many AWS provider nested blocks (`rule`, `transition`, `cors_rule`, `ingress`, `egress`) are `set` types. Use `one()` for single-element sets. When multiple levels of nesting are set-typed, chain `one()` at each level.

```hcl
# BAD — rule is a set, not a list
condition = aws_s3_bucket_server_side_encryption_configuration.this.rule[0].apply_server_side_encryption_by_default[0].sse_algorithm == "AES256"

# GOOD — use one() for set-typed blocks
condition = one(aws_s3_bucket_server_side_encryption_configuration.this.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "AES256"

# GOOD — chain one() when BOTH parent and child blocks are set-typed
# e.g., lifecycle rule.transition where rule is set AND transition is set
condition = one(one(aws_s3_bucket_lifecycle_configuration.this.rule).transition).days == 90
condition = one(one(aws_s3_bucket_lifecycle_configuration.this.rule).transition).storage_class == "GLACIER"
```

Check design.md Section 2 Schema Notes column to identify which nested blocks are set-typed. Apply `one()` at every set-typed level in the access path.

3. **Data sources need mocking**: When testing against the root module (no `module {}` block), data sources execute during plan. Add `mock_data` blocks for data sources the module uses.

```hcl
mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }
}
```

## Best Practices

1. **Naming**: Use `*_unit_test.tftest.hcl` for plan-mode tests, `*_integration_test.tftest.hcl` for apply-mode
2. **Start with plan mode**: Fast, free, no real resources
3. **Use mocks** for isolated unit testing (v1.7.0+)
4. **Clear error messages**: Write messages that help diagnose failures
5. **Test isolation**: Keep run blocks independent when possible
6. **Variable coverage**: Test different combinations to validate all code paths
7. **Negative testing**: Use `expect_failures` for invalid inputs
8. **CI/CD**: Run unit tests on every PR; integration tests on merge/nightly
9. **Parallel execution**: Use for independent tests with different state files

## Version Requirements

| Version | Feature                               |
| ------- | ------------------------------------- |
| 1.6.0   | Terraform test introduced             |
| 1.7.0   | Mock providers added                  |
| 1.9.0   | `state_key` and `parallel` attributes |

## Example: Complete Unit Test File

```hcl
# tests/vpc_module_unit_test.tftest.hcl
variables {
  environment = "test"
  aws_region  = "us-west-2"
}

run "test_defaults" {
  command = plan
  variables {
    vpc_cidr = "10.0.0.0/16"
    vpc_name = "test-vpc"
  }
  assert {
    condition     = aws_vpc.main.cidr_block == "10.0.0.0/16"
    error_message = "VPC CIDR should match input"
  }
  assert {
    condition     = aws_vpc.main.tags["Name"] == "test-vpc"
    error_message = "VPC name tag should match input"
  }
}

run "test_subnets" {
  command = plan
  variables {
    vpc_cidr        = "10.0.0.0/16"
    vpc_name        = "test-vpc"
    public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
    private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]
  }
  assert {
    condition     = length(aws_subnet.public) == 2
    error_message = "Should create 2 public subnets"
  }
  assert {
    condition     = length(aws_subnet.private) == 2
    error_message = "Should create 2 private subnets"
  }
}

run "test_invalid_cidr" {
  command = plan
  variables {
    vpc_cidr = "invalid"
    vpc_name = "test-vpc"
  }
  expect_failures = [var.vpc_cidr]
}
```

## References

For detailed examples and patterns, see:

- [Run Block Patterns](references/run-block-patterns.md) - Detailed run block configurations
- [Assertion Patterns](references/assertion-patterns.md) - Assert and expect_failures examples
- [Mock Patterns](references/mock-patterns.md) - Provider and data source mocking
- [Troubleshooting](references/troubleshooting.md) - Common issues, CI/CD integration

External documentation:

- [Terraform Testing Documentation](https://developer.hashicorp.com/terraform/language/tests)
- [Terraform Test Command Reference](https://developer.hashicorp.com/terraform/cli/commands/test)
- [Testing Best Practices](https://developer.hashicorp.com/terraform/language/tests/best-practices)
