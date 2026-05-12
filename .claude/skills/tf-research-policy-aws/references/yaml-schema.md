# YAML schema — tf-research-policy-aws output

The skill emits a single YAML document per research run. The document has two top-level keys: `metadata` and `rules`. Every rule is self-contained — a downstream codegen step or human policy author should be able to produce an AWS Config managed/custom rule and/or a Security Hub control mapping without re-doing the research.

## Top-level structure

```yaml
metadata: { ... }   # provenance and framework identity
rules: [ ... ]      # ordered list of rule objects
```

## `metadata` block

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `framework.name` | yes | string | Official name as AWS publishes it (e.g., `CIS AWS Foundations Benchmark`, `NIST 800-53 Rev 5`). |
| `framework.version` | yes | string | Verbatim version string (e.g., `3.0.0`, `Rev 5`). |
| `framework.scope` | no | string | If the user scoped down (e.g., "S3 only"), record it here. Otherwise omit. |
| `source` | yes | string (URL) | Primary AWS documentation URL the controls were sourced from. |
| `generated_by` | yes | string | Always `tf-research-policy-aws`. |
| `generated_at` | yes | string | ISO 8601 date (UTC). |
| `notes` | no | string | Free-form notes. Use for caveats like "AWS does not publish severity for this standard; severities reflect the analogous Security Hub FSBP control." |

## `rules[]` — per-rule schema

Order rules by `framework_control.id` lexicographically unless the user requests a different ordering.

### Identity

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `id` | yes | string | Stable, kebab-case, globally unique within the file. Pattern: `<service>-<short-summary>` (e.g., `rds-encryption-at-rest`). Do not reuse Security Hub IDs here — those go in `source.identifier`. |
| `title` | yes | string | One-line imperative title (e.g., `RDS instances must have encryption at rest enabled`). |
| `description` | no | string | Multi-sentence prose if the title isn't enough. |

### Framework mapping

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `framework_control.id` | yes | string | Control ID as the framework publishes it (e.g., `CIS 2.3.1`, `PCI DSS 3.5.1`, `NIST AC-2`). |
| `framework_control.title` | no | string | Control title from the framework. |
| `framework_control.requirement` | yes | string | Verbatim requirement text. Quote the framework — paraphrasing here defeats the point. |
| `related_controls[]` | no | list | Other frameworks this rule satisfies. Each item: `{ framework: <name>, version: <version>, id: <control id> }`. |

### Severity and applicability

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `severity` | yes | enum | `CRITICAL` \| `HIGH` \| `MEDIUM` \| `LOW` \| `INFORMATIONAL`. Mirror what AWS publishes. If AWS doesn't publish one, set `null` and add a note in `metadata.notes`. |
| `service` | yes | string | AWS service slug (`s3`, `rds`, `iam`, `ec2`, ...). |
| `resource_types[]` | yes | list[string] | CloudFormation-style resource type names (`AWS::S3::Bucket`, `AWS::RDS::DBInstance`). These align with what AWS Config evaluates. |

### Source mapping (this is what becomes the Config rule / Security Hub control)

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `source.type` | yes | enum | `aws-config-managed-rule` \| `aws-config-custom-rule` \| `security-hub-control` \| `custom-lambda`. |
| `source.identifier` | yes | string | For managed rules: the rule identifier in SCREAMING_SNAKE_CASE (e.g., `RDS_STORAGE_ENCRYPTED`). For Security Hub controls: the dotted ID (e.g., `RDS.3`). For custom rules: a stable identifier you choose. |
| `source.documentation_url` | yes | string (URL) | The canonical AWS page describing the rule/control. |
| `source.parameters` | no | map | Parameters the managed rule accepts (e.g., `{ minRetentionPeriod: 30 }`). Match the names AWS publishes. |
| `security_hub` | no | map | If the rule is also surfaced in Security Hub, capture the dual mapping: `{ standard: aws-foundational-security-best-practices, control_id: RDS.3, documentation_url: ... }`. |

### Condition (the assertion)

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `condition.description` | yes | string | Plain-English description of what "compliant" looks like. |
| `condition.parameters` | no | map | Tunable thresholds the rule exposes (e.g., `min_password_length: 14`). |
| `condition.logic` | yes | string (block) | Pseudocode or property expression describing the check (e.g., `resource.StorageEncrypted == true`). Not executable code — the codegen step turns this into Lambda/Guard/Rego. |

### Remediation

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `remediation.summary` | yes | string | What a consumer does to fix a non-compliant resource. |
| `remediation.terraform_snippet` | no | string (block) | Minimal HCL showing the compliant configuration. |
| `remediation.aws_cli_snippet` | no | string (block) | When useful (e.g., remediation requires snapshot-and-restore). |
| `remediation.console_steps[]` | no | list[string] | Step-by-step console actions, when CLI/Terraform is awkward. |
| `remediation.notes` | no | string | Caveats (e.g., "RDS encryption can only be enabled at creation time"). |

### Test cases

At least one test case is required so downstream codegen can produce policy unit tests.

```yaml
test_cases:
  - name: encrypted RDS instance passes
    input:
      resource_type: AWS::RDS::DBInstance
      properties:
        StorageEncrypted: true
    expected: COMPLIANT
  - name: unencrypted RDS instance fails
    input:
      resource_type: AWS::RDS::DBInstance
      properties:
        StorageEncrypted: false
    expected: NON_COMPLIANT
```

### Provenance, references, and tags

`provenance` records **where each field's content came from**, so a downstream auditor or codegen step can filter to AWS-official content only or flag rules that depend on third-party data. It is populated automatically by the bundled fetchers and merged by `merge_yaml.py` / `enrich_yaml.py`.

Provenance keys may be plain field names (e.g., `severity`) **or dotted paths** for composite sub-mappings (e.g., `framework_control.title` vs `framework_control.requirement` — useful when the title came from Security Hub but the requirement is paraphrased). The validator walks both forms.

```yaml
provenance:
  framework_control.id:        aws-conformance-pack
  framework_control.title:     aws-security-hub
  framework_control.requirement: aws-security-hub
  severity:                    aws-security-hub
  source.identifier:           aws-conformance-pack
  source.documentation_url:    aws-config-managed-rule-doc
  resource_types:              aws-conformance-pack
  condition.description:       aws-security-hub
  condition.logic:             manual-human
  remediation.terraform_snippet: third-party-prowler   # explicit when content isn't AWS-official
  test_cases:                  aws-guard-registry
  references:                  [aws-security-hub, aws-conformance-pack]
```

Allowed values per field (a string, or a list of strings if mixed). The canonical list lives in `references/aws-official-provenance.json` and is loaded by `validate_yaml.py`:

| Value | Meaning | Strict |
|-------|---------|--------|
| `aws-security-hub` | AWS Security Hub `describe-standards-controls` or `list-security-control-definitions` API | ✅ |
| `aws-audit-manager` | AWS Audit Manager `get-control` API | ✅ |
| `aws-conformance-pack` | AWS Config conformance pack template (awslabs/aws-config-rules) | ✅ |
| `aws-config-managed-rule-doc` | AWS Config developer guide page for a managed rule | ✅ |
| `aws-guard-registry` | AWS CloudFormation Guard Rules Registry test fixtures or mappings | ✅ |
| `manual-human` | Hand-authored by a human reading AWS-official source. Verifiable by an external auditor via cited URLs. | ✅ |
| `manual-model-synthesised` | Generated by a language model from training-corpus AWS knowledge. Not auditor-verifiable; relies on model fidelity. | ❌ (opt in with `--allow-model-synthesis`) |
| `manual` | **Legacy** alias for `manual-human` — kept for backwards compatibility with YAMLs created before the split. New rules should prefer the explicit form. | ✅ |
| `third-party-prowler` | Prowler (prowler-cloud/prowler) — community open-source, not AWS-official | ❌ |
| `third-party-trivy` | Trivy / Aqua Security checks | ❌ |
| `unknown` | Source unrecorded | ❌ |

A rule with **all** provenance values from sources with ✅ in the Strict column is "AWS-official" — pass `--strict-aws-official` to `validate_yaml.py` to enforce this. To allow model-synthesised content (e.g., when no AWS API or conformance pack covers the framework), add `--allow-model-synthesis`.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `provenance` | no | map | Per-field source tracking. See above. |
| `references[]` | yes | list | Each item: `{ title, url }`. Always include the controls reference page **and** the managed rule developer guide page when both apply. |
| `tags[]` | no | list[string] | Free-form classification (`encryption-at-rest`, `network-exposure`, `iam-least-privilege`). Useful for downstream filtering. |

## Complete worked example

```yaml
metadata:
  framework:
    name: CIS AWS Foundations Benchmark
    version: "3.0.0"
  source: https://docs.aws.amazon.com/securityhub/latest/userguide/cis-aws-foundations-benchmark.html
  generated_by: tf-research-policy-aws
  generated_at: 2026-05-08
  notes: Severities mirror Security Hub's mapping of CIS controls onto FSBP equivalents.

rules:
  - id: rds-encryption-at-rest
    title: RDS instances must have encryption at rest enabled
    description: >-
      Storage encryption protects data at rest in the underlying storage of an
      RDS DB instance, its automated backups, read replicas, and snapshots.
    framework_control:
      id: CIS 2.3.1
      title: Ensure that encryption-at-rest is enabled for RDS instances
      requirement: >-
        Amazon RDS encrypted DB instances use the industry standard AES-256
        encryption algorithm to encrypt your data on the server that hosts your
        Amazon RDS DB instances. After your data is encrypted, Amazon RDS
        handles authentication of access and decryption of your data
        transparently with a minimal impact on performance.
    related_controls:
      - framework: NIST 800-53 Rev 5
        version: Rev 5
        id: SC-28
      - framework: PCI DSS
        version: "4.0"
        id: "3.5.1"
    severity: MEDIUM
    service: rds
    resource_types:
      - AWS::RDS::DBInstance
      - AWS::RDS::DBCluster
    source:
      type: aws-config-managed-rule
      identifier: RDS_STORAGE_ENCRYPTED
      documentation_url: https://docs.aws.amazon.com/config/latest/developerguide/rds-storage-encrypted.html
      parameters: {}
    security_hub:
      standard: aws-foundational-security-best-practices
      control_id: RDS.3
      documentation_url: https://docs.aws.amazon.com/securityhub/latest/userguide/rds-controls.html#rds-3
    condition:
      description: >-
        The DB instance or cluster must report StorageEncrypted = true.
      parameters: {}
      logic: |
        resource.StorageEncrypted == true
    remediation:
      summary: >-
        Enable encryption at rest by setting StorageEncrypted = true at
        creation time. RDS encryption cannot be toggled on an existing
        instance — you must create an encrypted snapshot copy and restore.
      terraform_snippet: |
        resource "aws_db_instance" "example" {
          # ...
          storage_encrypted = true
          kms_key_id        = aws_kms_key.rds.arn
        }
      aws_cli_snippet: |
        aws rds copy-db-snapshot \
          --source-db-snapshot-identifier <unencrypted-snapshot> \
          --target-db-snapshot-identifier <encrypted-snapshot> \
          --kms-key-id <kms-key-arn>
      notes: >-
        For existing unencrypted instances, plan a maintenance window for
        snapshot, copy-with-encryption, restore, and cutover.
    references:
      - title: AWS Config managed rule rds-storage-encrypted
        url: https://docs.aws.amazon.com/config/latest/developerguide/rds-storage-encrypted.html
      - title: Security Hub control RDS.3
        url: https://docs.aws.amazon.com/securityhub/latest/userguide/rds-controls.html#rds-3
      - title: CIS AWS Foundations Benchmark v3.0.0 (Security Hub mapping)
        url: https://docs.aws.amazon.com/securityhub/latest/userguide/cis-aws-foundations-benchmark.html
    test_cases:
      - name: encrypted RDS instance passes
        input:
          resource_type: AWS::RDS::DBInstance
          properties:
            StorageEncrypted: true
        expected: COMPLIANT
      - name: unencrypted RDS instance fails
        input:
          resource_type: AWS::RDS::DBInstance
          properties:
            StorageEncrypted: false
        expected: NON_COMPLIANT
    tags:
      - encryption-at-rest
      - data-protection
      - rds
```

## Conventions and gotchas

- **Quote requirements verbatim.** The `framework_control.requirement` field is the legal/regulatory anchor. Don't paraphrase.
- **Stable IDs.** `id` should not change if the same rule is regenerated against a newer framework version. Hash-style IDs are discouraged — prefer `<service>-<intent>`.
- **Custom rules need full condition.logic.** Without a managed rule identifier, the codegen step has nothing to fall back on. Be explicit about which resource property is checked and how.
- **Test cases drive policy unit tests.** A single `expected: NON_COMPLIANT` test is more valuable than a long prose remediation — it's executable.
- **Don't conflate Security Hub and Config.** Security Hub controls *aggregate* Config rule findings; one Security Hub control may map to multiple Config rules and vice versa. Use `source` for the rule itself and `security_hub` for the aggregator mapping.
