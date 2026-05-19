---
name: tf-policy
description: Source of truth for Terraform Policy (tfpolicy) — block structure, top-level `input` / `policy` / `locals` blocks, `attrs` / `prior_attrs` / `meta` model, `core::` function reference, targeting (wildcards and partial wildcards), `.policytest.hcl` testing, enforcement levels, evaluation stages, and the lifecycle `operations` scope. Use when authoring, designing, or reviewing `.policy.hcl` and `.policytest.hcl` files, mapping compliance baselines to tfpolicy, or answering any question about tfpolicy syntax, semantics, or limits.
user-invocable: false
---

# Terraform Policy (tfpolicy)

Reference for authoring Terraform Policy (tfpolicy) — the native policy-as-code engine for Terraform and HCP Terraform. Single source of truth for the language; other skills and agents should link here rather than restate.

Validated by running `tfpolicy validate` and `tfpolicy test` against the engine in `github.com/CloudbrokerAz/terraform-policy-core`.

## File-Level Structure

A `.policy.hcl` file can contain four kinds of top-level blocks; all are optional except that at least one policy block usually exists.

```hcl
# 1. policy {} — file-level configuration (optional, max one per file)
policy {
  plugins        { source = "..." }    # optional, see Plugins
  terraform_config { ... }             # optional, terraform-side configuration
}

# 2. input "name" {} — typed inputs evaluated from the runtime context
input "expected_name" {
  type      = string
  default   = "ok"          # optional
  sensitive = false         # optional; true marks the value sensitive
}

# 3. locals {} — top-level computed values shared across all policies
locals {
  approved_regions = ["us-east-1", "us-west-2"]
}

# 4. <block_type> "<target>" "<name>" { ... } — one or more policy blocks
resource_policy "aws_ebs_volume" "encryption" { ... }
```

References use one of these roots only: `input`, `local`, `attrs`, `prior_attrs`, `meta`. Bare identifiers (e.g., naming a sibling local without `local.`) are rejected with "The root of a traversal must be one of input, local, attrs, meta, or prior_attrs."

## Policy Block Structure

Every policy uses one of three block types. The first label is the **target**, the second is a unique **policy name**.

| Block Type        | First Label                                                                                          | `attrs`                                                                                   | `meta`                                       |
| ----------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------- |
| `resource_policy` | Resource type, prefix wildcard (`aws_*`), or `"*"`                                                   | Resource attributes from plan (schema-driven)                                             | `address`, `provider_type`, `tfe_workspace`  |
| `provider_policy` | Provider TYPE (e.g., `aws`) or `"*"` — `hashicorp/aws` validates but never matches at runtime        | Provider configuration values                                                             | `name`, `type`, `source`, `version`, `alias` |
| `module_policy`   | Full module SOURCE (`app.terraform.io/org/vpc/aws`) or `"*"` — substring like `"vpc"` does not match | Module input variable values (`attrs.<input_name>`) — supply via `attrs = {...}` in mocks | `source`, `version`, `address`               |

```hcl
<block_type> "<target>" "<policy_name>" {
  enforcement_level = "mandatory"           # advisory | mandatory_overridable | mandatory ; default mandatory
  operations        = ["create","update","delete"]  # optional; limits the lifecycle ops this policy fires on
  filter            = <boolean_expression>  # optional pre-select
  locals { ... }                            # optional, computed per filtered item

  enforce {                                 # zero or more — a policy without any enforce blocks validates fine but does nothing
    condition     = <boolean_expression>
    error_message = "<actionable message>"  # rendered on failure
    # info_message = "..."                  # rendered on success (useful in advisory policies)
  }
}
```

**Execution per filtered item:** `filter` → `locals` → every `enforce` block. Each `enforce` runs independently; every failing message is reported.

**`enforce` block messages.** `error_message` and `info_message` are both optional; you may set one, both, or neither (the engine accepts all three). `error_message` is rendered when the condition fails; `info_message` is rendered when the condition passes (so it's useful for "passed-check" diagnostics in advisory policies). A failing block always raises a diagnostic regardless of which message was set.

**`operations`** scopes a policy to specific Terraform lifecycle operations. When omitted, the policy fires for every change. When set, the policy only fires for the listed operations. Required when the policy reads `prior_attrs` — the engine rejects `prior_attrs` without `operations = ["update"]` and/or `["update","delete"]` because the prior state only exists during update and delete.

## Traversal Roots — `attrs`, `prior_attrs`, `meta`, `input`, `local`

| Root          | Available in                                                    | Notes                                                                                   |
| ------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `attrs`       | every policy type                                               | Planned/current attribute values; shape comes from the provider schema                  |
| `prior_attrs` | `resource_policy` only, with `operations = ["update"/"delete"]` | The pre-change attribute values (before/after diffs are possible)                       |
| `meta`        | every policy type                                               | Metadata about the target (see table above)                                             |
| `input`       | every policy type                                               | Top-level `input "name" { type, default, sensitive }` blocks; reference as `input.name` |
| `local`       | every policy type                                               | Top-level `locals {}` or policy-block `locals {}`; reference siblings as `local.x`      |

### `meta` fields by block type

| Block             | Fields                                                                   |
| ----------------- | ------------------------------------------------------------------------ |
| `resource_policy` | `meta.address`, `meta.provider_type`, `meta.tfe_workspace.tags["<tag>"]` |
| `provider_policy` | `meta.name`, `meta.type`, `meta.source`, `meta.version`, `meta.alias`    |
| `module_policy`   | `meta.source`, `meta.version`, `meta.address`                            |

Only `resource_policy` exposes `meta.tfe_workspace`. Use `meta.tfe_workspace.tags["<tag>"]` for environment-aware policies.

### `attrs` per block

| Block             | Shape                                                                                                                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `resource_policy` | Planned attribute values for the current resource instance                                                                                                                                        |
| `provider_policy` | Provider configuration values (e.g., `attrs.region`, `attrs.default_tags[0].tags`). Omitting `attrs` in a mock makes the engine defer with "Provider attributes are not yet known at this stage." |
| `module_policy`   | Module input variable values (`attrs.<input_name>`). Same deferral behaviour for missing mock `attrs`.                                                                                            |

### `local.` inside `locals`

Inside a `locals` block, references to sibling locals must use `local.name`, not bare `name`. Bare identifiers fail with "The root of a traversal must be one of input, local, attrs, meta, or prior_attrs."

```hcl
locals {
  s    = core::lower(attrs.name)          # define
  is_p = core::startswith(local.s, "prod") # reference sibling with local.
}
```

## Critical Rules

### 1. ALL built-in functions require the `core::` prefix

```hcl
filter        = core::try(attrs.encrypted, false) == true
keys_list     = core::keys(attrs.tags)              # not keys(...)
error_message = "Allowed: ${core::join(", ", local.versions)}"
```

Missing prefix produces "There is no function named 'try'" (etc.).

### 2. Use `core::semverconstraint()` for ALL version comparisons

Direct comparison like `meta.version >= "4.0.0"` fails with "a number is required" — semver strings are not comparable as numbers.

```hcl
condition = core::semverconstraint(meta.version, ">= 4.0.0, < 5.0.0")
```

`core::semvercmp(a, b)` is also available — returns `-1`, `0`, or `1`. Use `semverconstraint` for human-readable rules and `semvercmp` when you need ordering.

Constraint operators in `core::semverconstraint`:

| Operator | Example               | Matches               |
| -------- | --------------------- | --------------------- |
| `=`      | `"= 4.67.0"`          | exact                 |
| `!=`     | `"!= 4.50.0"`         | exclude               |
| `>` `>=` | `">= 4.0.0"`          | minimum               |
| `<` `<=` | `"< 5.0.0"`           | maximum               |
| `~>`     | `"~> 4.67.0"`         | `>= 4.67.0, < 4.68.0` |
| `~>`     | `"~> 4.0"`            | `>= 4.0.0, < 5.0.0`   |
| `,`      | `">= 4.0.0, < 5.0.0"` | AND                   |

OR is HCL: `core::semverconstraint(meta.version, "~> 4.0") || core::semverconstraint(meta.version, "~> 5.0")`.

### 3. Always wrap optional/maybe-missing attributes with `core::try()`

You cannot test attribute existence directly — `attrs.foo != null` errors with "This object does not have an attribute named 'foo'" if `foo` is absent. Two-step pattern:

```hcl
locals {
  region_value = core::try(attrs.region, null)
  has_region   = local.region_value != null
}
```

Note: when running `tfpolicy test`, an omitted attribute that the policy reads (without `core::try`) raises an evaluation error. `expect_failure = true` on the mock will still mark the case "expected failure" — but it is cleaner to design policies that handle absence with `core::try` rather than rely on the test framework.

### 4. Blocks vs Attributes — schema dictates access

The provider schema distinguishes **blocks** (repeating, list-shaped even when singleton) from **attributes** (direct values).

- **Blocks** → indexed list of maps. Access with `[0]`: `attrs.default_tags[0].tags`, `attrs.versioning[0].enabled`, `attrs.metadata_options[0].http_tokens`.
- **Attributes** → direct value: `attrs.region`, `attrs.tags`, `attrs.instance_type`.

Common AWS blocks needing `[0]`: `default_tags`, `assume_role`, `endpoints`, `versioning`, `server_side_encryption_configuration`, `lifecycle_rule`, `metadata_options`.

Map access supports both forms: `attrs.tags["Environment"]` and `attrs.tags.Environment` — both work for string-keyed maps. Bracket form is required for keys that aren't valid identifiers.

### 5. Single-line boolean expressions

The HCL parser doesn't accept a multi-line `&&` / `||` chain in a `condition`. Keep the whole expression on one line.

```hcl
# correct
condition = local.a && local.b && local.c

# error: "Expected the start of an expression"
condition = local.a &&
            local.b
```

### 6. Sets are not indexable — convert with `core::tolist` or a `for` comprehension

```hcl
# error if attrs.rule is a set
sse_algorithm = attrs.rule[0].apply_server_side_encryption_by_default[0].sse_algorithm

# convert to list first
sse_algorithm = core::tolist(attrs.rule)[0].apply_server_side_encryption_by_default[0].sse_algorithm
# or
sse_algorithm = [for r in attrs.rule : r][0].apply_server_side_encryption_by_default[0].sse_algorithm
```

### 7. Targeting

| Form                                             | Behaviour                                                                        |
| ------------------------------------------------ | -------------------------------------------------------------------------------- |
| `"aws_s3_bucket"`                                | exact resource type                                                              |
| `"aws_*"`                                        | prefix wildcard (matches all resources whose type starts with `aws_`)            |
| `"*"`                                            | every resource of that block type, regardless of provider                        |
| `provider_policy "aws"`                          | provider TYPE — `"hashicorp/aws"` validates but does not match any real provider |
| `module_policy "app.terraform.io/myorg/vpc/aws"` | exact module SOURCE — substring like `"vpc"` does not match                      |

## Core Function Reference

All functions take the `core::` prefix. Grouped by purpose; quirks called out where they exist.

### Safe access and reflection

| Function                     | Notes                                          |
| ---------------------------- | ---------------------------------------------- |
| `core::try(expr, default)`   | Returns `default` on any evaluation error      |
| `core::can(expr)`            | `true` if `expr` evaluates without error       |
| `core::type(value)`          | Returns the cty type of a value                |
| `core::valuetostring(value)` | Convert any value to its string representation |

### Collections

| Function                                                                           | Notes                                                                                                                                                                                                                                                             |
| ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `core::contains(list, value)`                                                      | **List membership only.** Does NOT do substring matching on strings.                                                                                                                                                                                              |
| `core::contains_substring(str, substr)`                                            | Substring containment for strings                                                                                                                                                                                                                                 |
| `core::length(value)`                                                              | Lists, sets, maps, tuples ONLY. **Does NOT work on strings or objects** — both raise "collection must be a list, a map or a tuple". Convert objects with `core::keys(x)`; for strings use `core::regexall(".", s)` length or stay away from string length checks. |
| `core::keys(map)`, `core::values(map)`                                             | Map keys / values as a list                                                                                                                                                                                                                                       |
| `[for v in list : v if !P(v)]` then `core::length(...) == 0`                       | tfpolicy does NOT have `core::anytrue` / `core::alltrue`. Use list comprehensions + `core::length`. See "Any / All idiom" below.                                                                                                                                  |
| `core::distinct(list)`                                                             | Deduplicate, preserving order                                                                                                                                                                                                                                     |
| `core::concat(list, list, ...)`                                                    | List concatenation                                                                                                                                                                                                                                                |
| `core::flatten(list)`                                                              | Flatten nested lists                                                                                                                                                                                                                                              |
| `core::compact(list)`                                                              | Remove empty strings                                                                                                                                                                                                                                              |
| `core::merge(map, map, ...)`                                                       | Map merge (right wins)                                                                                                                                                                                                                                            |
| `core::zipmap(keys, values)`                                                       | Build a map from two parallel lists                                                                                                                                                                                                                               |
| `core::tolist(value)`                                                              | Convert set → list (required before indexing a set)                                                                                                                                                                                                               |
| `core::toset(list)`                                                                | Convert list → set (deduplicates)                                                                                                                                                                                                                                 |
| `core::one(list_or_set)`                                                           | Single-element extraction: returns the element if length 1, else null/error                                                                                                                                                                                       |
| `core::element(list, idx)`                                                         | Index with wrap-around                                                                                                                                                                                                                                            |
| `core::slice(list, from, to)`                                                      | Sublist                                                                                                                                                                                                                                                           |
| `core::reverse(list)`                                                              | Reverse                                                                                                                                                                                                                                                           |
| `core::sort(list)`                                                                 | Sort strings                                                                                                                                                                                                                                                      |
| `core::range(n)` / `core::range(start,end,step)`                                   | Numeric sequences                                                                                                                                                                                                                                                 |
| `core::chunklist(list, size)`                                                      | Chunk a list                                                                                                                                                                                                                                                      |
| `core::setunion`, `core::setintersection`, `core::setsubtract`, `core::setproduct` | Set operations                                                                                                                                                                                                                                                    |

### Strings

The skill previously claimed many of these did not exist — they all do.

| Function                                                                               | Notes                                                                                                                                                                            |
| -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `core::startswith(str, prefix)`                                                        | Prefix check                                                                                                                                                                     |
| `core::endswith(str, suffix)`                                                          | Suffix check                                                                                                                                                                     |
| `core::contains_substring(str, substr)`                                                | Substring check (`core::contains` is list-only)                                                                                                                                  |
| `core::regex(pattern, str)`                                                            | Match and return the first match. **Errors on no-match** ("pattern did not match any part of the given string") — wrap with `core::try` or guard with `core::regex_match` first. |
| `core::regexall(pattern, str)`                                                         | All matches as a list; empty list on no-match (does NOT error).                                                                                                                  |
| `core::regex_match(str, pattern)`                                                      | **Unanchored** boolean match — `(str, pattern)` argument order is reversed from `core::regex`. Use `^...$` for full match. Safe — returns false rather than erroring.            |
| `core::split(sep, str)`                                                                | Split into a list                                                                                                                                                                |
| `core::substr(str, offset, length)`                                                    | Substring extraction                                                                                                                                                             |
| `core::lower`, `core::upper`, `core::title`, `core::strrev`                            | Case / reverse                                                                                                                                                                   |
| `core::trim`, `core::trimspace`, `core::trimprefix`, `core::trimsuffix`, `core::chomp` | Whitespace and affix trimming                                                                                                                                                    |
| `core::join(sep, list)`                                                                | Build display strings for messages                                                                                                                                               |
| `core::format(fmt, args...)`, `core::formatlist`, `core::formatdate`                   | printf-style formatting                                                                                                                                                          |
| `core::indent(n, str)`                                                                 | Reindent multi-line strings                                                                                                                                                      |

### Numbers

| Function                                                                                                                       | Notes              |
| ------------------------------------------------------------------------------------------------------------------------------ | ------------------ |
| `core::abs`, `core::ceil`, `core::floor`, `core::signum`, `core::log`, `core::pow`, `core::max`, `core::min`, `core::parseint` | Arithmetic helpers |

### Encoding / decoding

| Function                               |
| -------------------------------------- |
| `core::jsondecode`, `core::jsonencode` |
| `core::yamldecode`, `core::yamlencode` |
| `core::csvdecode`                      |

### Time

The skill previously said tfpolicy has no time support. It does — though policies are stateless, you can compare timestamps within an evaluation.

| Function                      | Notes                           |
| ----------------------------- | ------------------------------- |
| `core::timestamp()`           | Returns current time in RFC3339 |
| `core::timeadd(ts, duration)` | e.g., `"1h"`, `"30m"`           |
| `core::timecmp(a, b)`         | Returns `-1`, `0`, `1`          |

### Versions

| Function                                      |
| --------------------------------------------- |
| `core::semverconstraint(version, constraint)` |
| `core::semvercmp(a, b)` → `-1`/`0`/`1`        |

### Sensitivity

| Function                    | Notes                    |
| --------------------------- | ------------------------ |
| `core::sensitive(value)`    | Mark a value sensitive   |
| `core::nonsensitive(value)` | Strip the sensitive mark |
| `core::issensitive(value)`  | Boolean check            |

### Cross-resource / data sources / HTTP

| Function                                | Notes                                                                                                |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `core::getresources(type, filter_map)`  | All matching resources. **O(N)** — cache in top-level `locals`, never call inside a resource policy. |
| `core::getdatasource(type, filter_map)` | **Executes** the data source — real provider API call. Top-level only, sparingly.                    |
| `core::gethttprequest(...)`             | HTTP call via the configured plugins block (see Plugins).                                            |

**Attribute access on `getresources()` results is at the TOP LEVEL — NOT through `.attrs`.** Resources returned use `resource.bucket`, not `resource.attrs.bucket`. This differs from the current evaluation context where you use `attrs.bucket`.

### Any / All idiom

There are no `core::anytrue`, `core::alltrue`, or HCL `all`/`any` quantifiers in tfpolicy. Express set-wide predicates with list comprehensions and `core::length`:

```hcl
# "any element satisfies P" — collect matches; non-empty means true
any_match = core::length([for v in list : v if P(v)]) > 0

# "all elements satisfy P" — collect counter-examples; empty means true
all_match = core::length([for v in list : v if !P(v)]) == 0

# "no element satisfies P" — same shape, semantic flip
none_match = core::length([for v in list : v if P(v)]) == 0
```

### Functions that genuinely don't exist

A policy is stateless across runs; there's no built-in for:

- Cross-workspace state access
- Stateful comparisons between previous evaluations
- Mutable storage / counters

Use HCP Terraform Policy Sets / workspace tags / external plugins for these.

## Performance Rules

1. **Cache `core::getresources()` in top-level `locals`** — calling it inside `resource_policy` re-iterates every module per resource (O(N²)).
2. **Never call `core::getdatasource()` in `resource_policy`** — it makes a real provider API call per resource. Top-level only, and only when truly necessary.
3. **Build lookup maps for O(1) joins** — transform a `getresources()` result into a map keyed on the join attribute, then index it.
4. **Use `filter` aggressively.** Pair null + length checks: `filter = attrs.ingress != null && core::length(attrs.ingress) > 0`.
5. **Multi-stage `locals`** — break compound predicates into named intermediates; each evaluates once and the code stays debuggable.
6. **Cross-resource references during creation** — newly-created resources may have unresolved references at policy evaluation time. Cross-resource checks are reliable for updates and explicit literals.

## Enforcement Levels

The valid keywords are exactly `advisory`, `mandatory_overridable`, `mandatory` — underscores, no hyphens. `"mandatory-overridable"` is rejected at validate time. Default is `mandatory` when omitted.

| Level                   | `tfpolicy test` diagnostic | Real HCP Terraform run                                    |
| ----------------------- | -------------------------- | --------------------------------------------------------- |
| `advisory`              | `Warning:`                 | Informational; the run is not blocked.                    |
| `mandatory_overridable` | `Error:`                   | Blocks apply; users with override permission can bypass.  |
| `mandatory`             | `Error:`                   | Hard gate; apply blocked until the configuration changes. |

Important: in `tfpolicy test`, **all three levels mark the resource as `fail` on a failing condition** — the only difference is the severity tag on the diagnostic. `expect_failure = true` catches all three. The "still passes overall" claim some docs make is about HCP run _outcome_, not the test framework.

## Evaluation Stages

The CLI flag is `--evaluation-stage=setup|plan` (the CLI help wrongly shows `--evaluate-stage`; the working flag is `--evaluation-stage`). `plan` is the default. The stage is a runner-level choice — there is **no** `evaluation_stage` attribute on the policy block; the engine rejects it as an unsupported argument.

| Stage      | When                     | Use For                                                                                                                                                                       |
| ---------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `setup`    | Before plan              | **`provider_policy` and `module_policy` only**, and **only `meta`** (version / source). `resource_policy` is rejected: "Setup evaluation does not support resource policies." |
| `plan`     | After plan, before apply | The default. Everything else.                                                                                                                                                 |
| Apply-time | After apply              | Attributes that are `"(known after apply)"` at plan: IPs, IDs, ARNs.                                                                                                          |

## Patterns

### Required attribute

```hcl
resource_policy "aws_ebs_volume" "encryption" {
  enforce {
    condition     = core::try(attrs.encrypted, false) == true
    error_message = "EBS volume ${core::try(meta.address, "?")} must set encrypted = true."
  }
}
```

### Allowlist

```hcl
resource_policy "aws_instance" "instance_type" {
  locals {
    allowed    = ["t3.micro", "t3.small", "t3.medium"]
    is_allowed = core::contains(local.allowed, attrs.instance_type)
  }
  enforce {
    condition     = local.is_allowed
    error_message = "Instance type ${attrs.instance_type} not allowed. Use: ${core::join(", ", local.allowed)}"
  }
}
```

### Required tags (wildcard, sensitive to absent maps)

```hcl
resource_policy "*" "required_tags" {
  filter = attrs.tags != null && core::length(core::keys(attrs.tags)) > 0

  locals {
    required = ["Environment", "Owner", "CostCenter"]
    tag_keys = core::keys(attrs.tags)
    missing  = [for t in local.required : t if !core::contains(local.tag_keys, t)]
    has_all  = core::length(local.missing) == 0
  }

  enforce {
    condition     = local.has_all
    error_message = "Missing required tags: ${core::join(", ", local.missing)}"
  }
}
```

`core::length(core::keys(attrs.tags))` instead of `core::length(attrs.tags)` is the safer form: it works whether the provider schema delivers `tags` as `map(string)` or as an `object({...})`. Object-typed values raise "collection must be a list, a map or a tuple" from `core::length`.

### Prefix-based naming convention

```hcl
resource_policy "aws_s3_bucket" "name_prefix" {
  enforce {
    condition     = core::startswith(attrs.bucket, "myorg-")
    error_message = "Bucket ${attrs.bucket} must start with 'myorg-'."
  }
}
```

### Regex match for resource names

`core::regex_match(str, pattern)` is **`(str, pattern)`** — string first, pattern second. This is the opposite order of the stdlib `core::regex(pattern, str)` and `core::regexall(pattern, str)`. Match is unanchored; use `^...$` for full match.

```hcl
resource_policy "aws_iam_role" "role_naming" {
  enforce {
    condition     = core::regex_match(attrs.name, "^role-[a-z][a-z0-9-]*$")
    error_message = "IAM role ${attrs.name} must match ^role-[a-z][a-z0-9-]*$."
  }
}
```

### Provider version range

```hcl
provider_policy "aws" "version_range" {
  enforce {
    condition     = core::semverconstraint(meta.version, ">= 4.0.0, < 6.0.0")
    error_message = "AWS provider ${meta.version} is outside the approved range >= 4.0.0, < 6.0.0."
  }
}
```

### Inputs

Inputs let the runner parameterise a policy. Define at the top of the file, reference as `input.<name>`.

```hcl
input "approved_kms_key_arn" {
  type    = string
  default = ""
}

resource_policy "aws_ebs_volume" "kms_key" {
  enforce {
    condition     = core::try(attrs.kms_key_id, "") == input.approved_kms_key_arn
    error_message = "EBS volume must use the approved KMS key (${input.approved_kms_key_arn})."
  }
}
```

`sensitive = true` on an input marks its value sensitive in diagnostics.

### Lifecycle scoping with `operations`

```hcl
resource_policy "aws_s3_bucket" "block_recreate" {
  operations = ["create"]
  enforce {
    condition     = false
    error_message = "Creating new S3 buckets is currently blocked. Use the shared landing-zone module."
  }
}
```

`condition = false` is the idiomatic way to write a hard-block gate. Note that `tfpolicy validate` will exit non-zero with a "Condition not met" diagnostic — that's expected for this pattern (validate statically sees the literal `false`); `tfpolicy test` mocks still work correctly.

Test mocks supply the operation via `meta = { operation = "create" }` (or `"update"` / `"delete"`). When the mock's `meta.operation` is outside the policy's `operations` list, the policy is silently skipped for that mock (no evaluation, no diagnostic). When `operations` is omitted from the policy, it fires for every operation.

```hcl
# .policytest.hcl
resource "aws_s3_bucket" "create_attempt" {
  expect_failure = true
  meta  = { operation = "create" }
  attrs = { bucket = "new-bucket" }
}

resource "aws_s3_bucket" "update_attempt" {     # ignored by the policy above
  meta  = { operation = "update" }
  attrs = { bucket = "existing-bucket" }
}
```

Valid `operations` values: `"create"`, `"update"`, `"delete"`. Anything else fails validate with "Invalid operation". Duplicates fail with "Duplicate operation".

### `prior_attrs` — before/after comparison

`prior_attrs` is the resource's pre-change state. It's only populated during `update` and `delete` operations; the engine requires `operations` to list one or both of those, otherwise it errors at validate with "Missing `operations` for `prior_attrs` reference". Including `create` in `operations` with a `prior_attrs` reference fails validate: "`prior_attrs` cannot be used when `operations` includes `create`".

```hcl
resource_policy "aws_db_instance" "no_downgrade_class" {
  operations = ["update"]

  enforce {
    condition = (
      core::try(attrs.instance_class, "") == core::try(prior_attrs.instance_class, "") ||
      core::startswith(core::try(attrs.instance_class, ""), "db.r")
    )
    error_message = "Cannot downgrade RDS from ${core::try(prior_attrs.instance_class, "?")} to ${core::try(attrs.instance_class, "?")} unless staying on db.r* family."
  }
}
```

In `.policytest.hcl`, supply prior state with a `prior_attrs = { ... }` field alongside `attrs` and `meta`:

```hcl
resource "aws_db_instance" "downgrade_attempt" {
  expect_failure = true
  meta        = { operation = "update" }
  prior_attrs = { instance_class = "db.r6g.large" }
  attrs       = { instance_class = "db.t3.medium" }
}
```

### Multiple `enforce` — show all violations

```hcl
resource_policy "aws_security_group" "checks" {
  locals {
    public_ssh_rules = [
      for r in core::try(attrs.ingress, []) :
      r if r.from_port == 22 && core::contains(core::try(r.cidr_blocks, []), "0.0.0.0/0")
    ]
    has_public_ssh  = core::length(local.public_ssh_rules) > 0
    has_description = core::try(attrs.description, "") != ""
  }

  enforce {
    condition     = !local.has_public_ssh
    error_message = "Security group ${core::try(meta.address, "?")} must not allow SSH from 0.0.0.0/0."
  }

  enforce {
    condition     = local.has_description
    error_message = "Security group ${core::try(meta.address, "?")} must include a description."
  }
}
```

### Advisory / informational

```hcl
resource_policy "aws_lambda_function" "runtime_warn" {
  enforcement_level = "advisory"
  enforce {
    condition    = !core::contains(["nodejs14.x","python3.7"], attrs.runtime)
    info_message = "Runtime ${attrs.runtime} is approved."
    # When the condition fails, the engine prints a Warning rather than an Error; the HCP run is not blocked.
  }
}
```

### Cross-resource enforcement (cached map)

```hcl
locals {
  all_encryption_configs = core::getresources("aws_s3_bucket_server_side_encryption_configuration", {})

  encryption_by_bucket = {
    for cfg in local.all_encryption_configs :
    cfg.bucket => cfg                  # NOTE: top-level access, no `.attrs`
  }
}

resource_policy "aws_s3_bucket" "require_encryption" {
  locals {
    has_encryption = core::try(local.encryption_by_bucket[attrs.bucket], null) != null
  }
  enforce {
    condition     = local.has_encryption
    error_message = "S3 bucket ${attrs.bucket} must have a matching aws_s3_bucket_server_side_encryption_configuration."
  }
}
```

### Resource count limit

```hcl
locals {
  nat_gateways = core::getresources("aws_nat_gateway", {})
  nat_count    = core::length(local.nat_gateways)
  max_allowed  = 3
}

resource_policy "aws_nat_gateway" "limit_count" {
  enforce {
    condition     = local.nat_count <= local.max_allowed
    error_message = "Maximum ${local.max_allowed} NAT gateways allowed; found ${local.nat_count}."
  }
}
```

## Testing — `.policytest.hcl`

A test file declares mock resources / providers / modules and any `expect_failure` / `skip` modifiers.

### Skeleton

```hcl
policytest {
  targets = ["my-policy.policy.hcl"]   # optional; defaults to every policy in the same directory
}

resource "aws_s3_bucket" "passing" {
  attrs = {
    bucket     = "my-secure-bucket"
    versioning = [{ enabled = true }]
  }
}

resource "aws_s3_bucket" "failing" {
  expect_failure = true
  attrs = {
    bucket     = "my-insecure-bucket"
    versioning = [{ enabled = false }]
  }
}
```

Run with `tfpolicy test --policies=./policies --tests=./tests`. Exit 0 = every expectation met; exit 1 = unexpected failure or evaluation error. (See `expect_failure` semantics below — evaluation errors are NOT cleanly caught by `expect_failure`.)

### Mock shape per policy type

| Policy Type       | Test Block                                                                         | Mock fields        |
| ----------------- | ---------------------------------------------------------------------------------- | ------------------ |
| `resource_policy` | `resource "<type>" "<name>" { attrs = { ... } }`                                   | `attrs`            |
| `provider_policy` | `provider "<type>" "<name>" { meta = { source, version, ... } attrs = {...} }`     | `meta` and `attrs` |
| `module_policy`   | `module "<source>" "<name>" { meta = { source, version, address } attrs = {...} }` | `meta` and `attrs` |

### `expect_failure` and `skip`

- `expect_failure = true` — the test framework asserts that at least one policy condition returned `false` for this mock. **Critical: it only catches _condition_ failures, NOT _evaluation errors_.** A policy that throws an error during evaluation (missing attribute, `core::regex` no-match, `core::length` on a string, type mismatch, etc.) still fails the test even with `expect_failure = true`; the diagnostic "Expected failure occurred / This resource caused an error during policy evaluation" appears, but the resource is marked `fail` and the test exits non-zero. Design policies so the condition cleanly returns `false` on bad input — wrap optional/maybe-missing attributes with `core::try`, and avoid functions that error on bad input (`core::regex`, `core::one` on empty, indexing a missing key) inside `condition` without `core::try`.
- `skip = true` — the mock is added to the resource graph and is visible to `core::getresources()`, but no policy evaluates it directly. Use for helper resources that only act as join targets.

### Advisory mocks

If the policy under test is `enforcement_level = "advisory"`, a failing condition produces a `Warning:` line but the resource is still marked `pass`. To assert that the warning was emitted, run with `--evaluate-stage=plan` and grep for `Warning:` in the output rather than relying on `expect_failure`.

### Cross-resource references in tests

Same-file references use `<type>.<name>.<attr>` — **NO `.attrs.` in the middle**. The engine rejects `aws_s3_bucket.test.attrs.bucket` with "This object does not have an attribute named 'attrs'."

```hcl
resource "aws_s3_bucket" "test" {
  expect_failure = true
  attrs = { bucket = "test" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "config" {
  skip = true
  attrs = {
    bucket = aws_s3_bucket.test.bucket          # correct: no `.attrs.`
    rule   = [{ apply_server_side_encryption_by_default = [{ sse_algorithm = "aws:kms" }] }]
  }
}
```

References do not cross file boundaries — keep referrers and referents in the same `.policytest.hcl`.

### Data source mocks

```hcl
data "aws_ami" "ubuntu" {
  attrs = {
    id   = "ami-12345"
    name = "ubuntu-22.04"
  }
}
```

The policy reads them with `core::getdatasource("aws_ami", { ... })`.

### Mock-vs-real meta behaviour

Some `meta` fields behave differently in `tfpolicy test` than in a real `terraform plan --policies=...` run:

| Field                | `tfpolicy test` | Real plan |
| -------------------- | --------------- | --------- |
| `meta.provider_type` | undefined       | populated |
| `meta.address`       | undefined       | populated |
| `meta.type`          | undefined       | populated |

If a policy depends on these, wrap with `core::try(..., "")`.

**Important: `error_message` and `info_message` templates are evaluated and reading `meta.address` directly (i.e., `${meta.address}`) inside them raises "This value is null, so it does not have any attributes" during `tfpolicy test`.** Wrap interpolations with `core::try`:

```hcl
error_message = "Resource ${core::try(meta.address, "<address unknown in mock>")} is non-compliant."
```

This keeps the message readable in real plans while letting tests run cleanly.

### Common test mistakes

- Object where the schema expects a list: `rule = { ... }` ❌ → `rule = [{ ... }]` ✅.
- `skip` on the resource the policy evaluates; `expect_failure` on the helper. Roles are reversed: `expect_failure` belongs on the evaluated resource, `skip = true` on the helper.
- Omitting an attribute the policy reads without `core::try()` — produces a hard "no attribute named X" evaluation error rather than a clean fail.

## CLI

```
tfpolicy validate --policies=./policies [--evaluation-stage=setup|plan]
tfpolicy test     --policies=./policies --tests=./tests [--evaluation-stage=setup|plan]
```

Note: `tfpolicy --help` advertises `--evaluate-stage`; the flag the binary actually accepts is `--evaluation-stage`.

`validate` catches parse errors, schema violations (unknown attributes, invalid `enforcement_level`, missing `operations` for `prior_attrs`, indexing a set), and statically-decidable condition failures (e.g., a hard-block policy with `condition = false`). It defers anything that depends on `attrs` / `meta` / `input`. `test` does everything `validate` does plus runs `.policytest.hcl` mocks.

Trust the exit code, not the trailing "Success!" line — a "Success! Terraform policies validated successfully." can appear even when individual diagnostics raised exit 1.

## Plugins (preview)

A `policy { plugins { source = "..." } }` block configures external plugins. `core::gethttprequest` and similar plugin-backed functions become available once a plugin is loaded. Plugin specifics are out of scope for this reference; consult the engine docs for current plugin schema.

## Complexity Assessment

| Complexity   | Criteria                                                                                                    | Examples                                                  |
| ------------ | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Simple       | Single resource, direct attribute check, no cross-resource deps                                             | EBS encryption, RDS public access, ECS container insights |
| Moderate     | Cross-resource via `core::getresources()`, needs caching                                                    | S3 bucket → encryption config, NIC → NSG association      |
| Complex      | `prior_attrs` diffs, regex-driven validation, many policies in one set                                      | No-downgrade rules, naming conventions across services    |
| Not feasible | Cross-workspace state, mutable state across evaluations, anything that needs to persist beyond a single run | Quotas across runs, "last-modified-by" history checks     |

## Best Practices

- Write conditions that **never raise** — wrap optional access with `core::try`, prefer `core::regex_match` over `core::regex` for predicates, build maps before indexing. This makes `expect_failure = true` cleanly catch the negative case.
- One concern per policy. Multiple focused policies with descriptive names beat one large policy.
- Multiple `enforce` blocks expose every violation in one run.
- Error messages: state the problem AND the fix. Interpolate failing values with `core::try` (raw `${meta.address}` is null in mocks).
- Cite the compliance control (CIS, NIST, FSBP, PCI DSS, etc.) in a comment when applicable.

## Decision Quick Tree

| Question                                     | Answer                                                           |
| -------------------------------------------- | ---------------------------------------------------------------- |
| Comparing versions?                          | `core::semverconstraint()` or `core::semvercmp()`                |
| Calling a built-in function?                 | Prefix with `core::`                                             |
| Reading an optional attribute?               | Wrap with `core::try(attrs.foo, default)`                        |
| Need substring / prefix / suffix?            | `core::contains_substring`, `core::startswith`, `core::endswith` |
| Need regex?                                  | `core::regex_match`, `core::regex`, `core::regexall`             |
| Looking up related resources?                | `core::getresources()` in top-level `locals`, build a map        |
| Comparing previous-state values?             | `prior_attrs` + `operations = ["update"/"delete"]`               |
| Time comparisons inside a single evaluation? | `core::timestamp`, `core::timeadd`, `core::timecmp`              |
| Need to check workspace context?             | `meta.tfe_workspace.tags["..."]` (resource_policy only)          |
| Writing tests?                               | `.policytest.hcl`; `expect_failure` on the evaluated mock        |
| Helper mocks for `getresources()`?           | `skip = true` so they are visible but not evaluated              |
| Want a non-blocking diagnostic?              | `enforcement_level = "advisory"` + `info_message`                |
| Scope a policy to only updates?              | `operations = ["update"]` on the policy block                    |
