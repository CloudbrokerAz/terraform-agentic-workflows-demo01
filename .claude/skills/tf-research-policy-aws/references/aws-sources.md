# AWS sources for compliance research

Curated entry points and search patterns for AWS-published compliance baselines. AWS documentation moves; treat URLs here as starting points and verify the page is current via `recommend` before extracting controls.

## Primary sources (priority order)

### 1. AWS Security Hub Standards

The most useful single source — every standard has a "controls reference" page that lists every control with severity, requirement, and the underlying Config rule.

- **Landing**: `https://docs.aws.amazon.com/securityhub/latest/userguide/standards-reference.html`
- **AWS Foundational Security Best Practices (FSBP)**: `https://docs.aws.amazon.com/securityhub/latest/userguide/fsbp-standard.html`
- **CIS AWS Foundations Benchmark**: `https://docs.aws.amazon.com/securityhub/latest/userguide/cis-aws-foundations-benchmark.html`
- **NIST SP 800-53 Rev. 5**: `https://docs.aws.amazon.com/securityhub/latest/userguide/nist-standard.html`
- **PCI DSS**: `https://docs.aws.amazon.com/securityhub/latest/userguide/pcidss-standard.html`
- **Service-Managed Standard: AWS Control Tower**: `https://docs.aws.amazon.com/securityhub/latest/userguide/service-managed-standard-aws-control-tower.html`

The per-service controls pages (e.g., `s3-controls.html`, `rds-controls.html`, `iam-controls.html`) give you the most parseable per-control detail when you already know the service scope.

### 2. AWS Config Conformance Packs

Sample templates that bundle Config rules per framework. **The canonical source is the public GitHub repo `awslabs/aws-config-rules`** — version-controlled, no scraping, and consumed directly by `scripts/parse_conformance_pack.py`. The doc pages mirror these templates but are harder to parse.

- **GitHub repo (preferred)**: `https://github.com/awslabs/aws-config-rules/tree/master/aws-config-conformance-packs`
- **Raw template URL pattern**: `https://raw.githubusercontent.com/awslabs/aws-config-rules/master/aws-config-conformance-packs/<template-name>.yaml`
- **List available templates**: `gh api repos/awslabs/aws-config-rules/contents/aws-config-conformance-packs --jq '.[].name'`
- **Sample templates index (docs mirror)**: `https://docs.aws.amazon.com/config/latest/developerguide/conformancepack-sample-templates.html`
- **Operational Best Practices for HIPAA Security**: `https://docs.aws.amazon.com/config/latest/developerguide/operational-best-practices-for-hipaa_security.html`
- **Operational Best Practices for PCI DSS**: `https://docs.aws.amazon.com/config/latest/developerguide/operational-best-practices-for-pci-dss.html`
- **Operational Best Practices for NIST 800-53**: `https://docs.aws.amazon.com/config/latest/developerguide/operational-best-practices-for-nist-800-53_rev_5.html`
- **Operational Best Practices for FedRAMP**: `https://docs.aws.amazon.com/config/latest/developerguide/operational-best-practices-for-fedramp-low.html`
- **Operational Best Practices for ISO 27001**: `https://docs.aws.amazon.com/config/latest/developerguide/operational-best-practices-for-iso-27001-2013.html`
- **Operational Best Practices for SOC 2**: `https://docs.aws.amazon.com/config/latest/developerguide/operational-best-practices-for-soc-2.html`
- **Operational Best Practices for CIS Benchmark**: `https://docs.aws.amazon.com/config/latest/developerguide/operational-best-practices-for-cis-benchmark-level-1.html`

### 3. AWS Audit Manager Frameworks

Useful when Security Hub doesn't carry a standard but Audit Manager does (e.g., GDPR, GxP, FERPA, HIPAA, SOC 2, ISO 27001, FedRAMP). For deterministic extraction prefer the API: `scripts/fetch_audit_manager_framework.py --list-frameworks` then `--framework <name> --output ...`.

- **Standard frameworks library**: `https://docs.aws.amazon.com/audit-manager/latest/userguide/framework-overviews.html`
- **API**: `aws auditmanager list-assessment-frameworks --framework-type Standard` and `aws auditmanager get-control --control-id <id>`

### 3b. AWS Security Hub Standards (API)

Mirror of the doc pages in the API. Authoritative for severity, control description, related-framework mappings, and remediation URLs. Wrapped by `scripts/fetch_security_hub_controls.py`.

- **API**: `aws securityhub describe-standards` then `aws securityhub describe-standards-controls --standards-subscription-arn <arn>`
- **Prerequisite**: Security Hub must be enabled in the target account/region and the standard must be subscribed.

### 4. AWS Config Managed Rules catalog

Canonical reference for what each managed rule actually checks, its parameters, and its evaluated resource types. Use this to verify any `source.identifier: aws-config-managed-rule` value.

- **Catalog (alphabetical)**: `https://docs.aws.amazon.com/config/latest/developerguide/managed-rules-by-aws-config.html`
- **By region availability**: `https://docs.aws.amazon.com/config/latest/developerguide/managing-rules-by-region-availability.html`

### 5. Service-specific security pages (fallback)

When a control has no managed rule and you need to spec a custom rule, the service security pages tell you what properties to inspect.

- Pattern: `https://docs.aws.amazon.com/<service>/latest/userguide/security.html` (S3, EC2, etc.)
- Or: `https://docs.aws.amazon.com/<service>/latest/userguide/security-best-practices.html`

## Search patterns that work

| Goal | Query |
|------|-------|
| Find a standard's controls reference | `Security Hub <framework name> controls reference` |
| Find a specific control | `Security Hub control <ID>` (e.g., `Security Hub control RDS.3`) |
| Find a managed rule by intent | `AWS Config rule <intent>` (e.g., `AWS Config rule S3 bucket SSL`) |
| Find a conformance pack | `AWS Config operational best practices <framework>` |
| Verify a managed rule identifier | `<RULE_IDENTIFIER>` (e.g., `RDS_STORAGE_ENCRYPTED`) — search will land on the dev guide page |

Avoid generic queries like `"AWS compliance"` — they return marketing pages, not the controls catalog.

## Discovering new controls

AWS revises Security Hub standards regularly. Two reliable signals:

1. **`recommend` on the standard's landing page** — surfaces the **New** section showing recently added or revised controls.
2. **Control IDs with letter suffixes** (e.g., `IAM.6.A`) usually indicate a revision; check the change log on the controls reference page.

If a user asks for the *latest* version of a standard, run `recommend` first to confirm AWS hasn't added controls since your last research pass.

## When AWS doesn't publish a baseline

Some frameworks (e.g., FFIEC, internal corporate baselines) aren't published as Security Hub standards or conformance packs. Options in priority order:

1. Check **Audit Manager** — frameworks there often map to existing Config rules.
2. Use **AWS FSBP** as a base and tag rules with the user's framework's control IDs as `related_controls` entries.
3. Mark rules as `source.type: aws-config-custom-rule` and let the user supply the framework-specific control IDs.

Don't fabricate AWS-published mappings that don't exist. Be explicit in `metadata.notes` when the framework isn't natively covered.
