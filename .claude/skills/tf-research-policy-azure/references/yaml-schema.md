# YAML schema — tf-research-policy-azure output

The skill emits a single YAML document per research run with two top-level keys: `metadata` and `rules`. Every rule is self-contained — a downstream codegen step or human policy author should be able to produce an **Azure Policy definition** and/or an **initiative (policy set) control mapping** without re-doing the research.

This schema is Azure-tailored. It is *not* the `tf-research-policy-aws` schema — `source` describes Azure Policy constructs (definition GUID, effect, mode, policy rule), not AWS Config rules.

## Top-level structure

```yaml
metadata: { ... }   # provenance and framework identity
rules: [ ... ]      # ordered list of rule objects
```

## `metadata` block

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `framework.name` | yes | string | Official name as Microsoft publishes it (e.g., `CIS Microsoft Azure Foundations Benchmark`, `NIST SP 800-53 Rev. 5`, `Microsoft cloud security benchmark`). |
| `framework.version` | yes | string | Verbatim version (e.g., `3.0.0`, `Rev. 5`, `v4.0.1`). |
| `framework.scope` | no | string | If the user scoped down (e.g., `storage`), record it. Otherwise omit. |
| `source` | yes | string (URL) | Primary Microsoft documentation URL the controls were sourced from. |
| `initiative` | no | map | The source built-in initiative: `{ display_name, definition_id, definition_name (GUID), version }`. Present when produced by `parse_builtin_initiative.py`. |
| `generated_by` | yes | string | Always `tf-research-policy-azure`. |
| `generated_at` | yes | string | ISO 8601 date (UTC). |
| `notes` | no | string | Caveats (e.g., "control titles sourced from Learn 'Regulatory Compliance details' page; Defender not enabled in target subscription"). |

## `rules[]` — per-rule schema

Order rules by `framework_control.id` lexicographically unless the user requests otherwise.

### Identity

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `id` | yes | string | Stable, kebab-case, unique within the file. Pattern: `<service>-<short-intent>` (e.g., `storage-https-only`). Do not reuse the policy GUID here — that goes in `source.policy_definition_name`. |
| `title` | yes | string | One-line imperative title (e.g., `Storage accounts must require secure transfer (HTTPS)`). |
| `description` | no | string | Multi-sentence prose if the title isn't enough. |

### Framework mapping

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `framework_control.id` | yes | string | Control ID as the framework publishes it (e.g., `CIS Azure 3.1`, `NIST SC-28`, `PCI DSS 3.5.1`, MCSB `DP-4`). For initiative-sourced rules this is derived from the `policyDefinitionGroups[].name` (the `..._3.1` suffix). |
| `framework_control.title` | no | string | Control title from the framework. Not in initiative JSON — filled from Defender / policyMetadata / Learn. |
| `framework_control.requirement` | yes | string | Verbatim requirement text. Quote the framework — paraphrasing defeats the audit purpose. |
| `related_controls[]` | no | list | Other frameworks this rule satisfies. Each item: `{ framework, version, id }`. MCSB carries rich crosswalks (NIST/PCI/CIS/ISO/SOC2). |

### Severity and applicability

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `severity` | yes | enum | `CRITICAL` \| `HIGH` \| `MEDIUM` \| `LOW` \| `INFORMATIONAL`. Azure Policy itself does not publish a severity; derive from the mapped Defender assessment severity (High/Medium/Low) or MCSB criticality (Must have → HIGH, Should have → MEDIUM, Nice to have → LOW). If none is available set `null` and note it in `metadata.notes`. Manual-effect policies → `INFORMATIONAL`. |
| `service` | yes | string | Azure service slug (`storage`, `keyvault`, `sql`, `compute`, `network`, `aks`, `monitor`, `appservice`, `identity`, ...). |
| `resource_types[]` | yes | list[string] | ARM resource type names (`Microsoft.Storage/storageAccounts`, `Microsoft.Compute/virtualMachines`). Parsed recursively from `policyRule.if` `"field": "type"` clauses. For `AuditIfNotExists`/`DeployIfNotExists` the *evaluated* type goes here; the related `then.details.type` is a secondary type — list both, evaluated type first. |

### Source mapping (this is what becomes the Azure Policy definition / initiative entry)

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `source.type` | yes | enum | `azure-policy-builtin` \| `azure-policy-custom` \| `azure-policy-initiative` \| `defender-assessment` \| `manual-attestation`. |
| `source.policy_definition_name` | yes | string | The policy definition **GUID** (the `name` field). For built-ins this is the stable identifier. For custom rules, a stable GUID/name you choose. |
| `source.policy_definition_id` | no | string | Full ARM id `/providers/Microsoft.Authorization/policyDefinitions/{GUID}` for built-ins. Omit for not-yet-created custom policies. |
| `source.display_name` | yes | string | Policy definition display name (Microsoft's, for built-ins). |
| `source.effect` | yes | enum | `Audit` \| `Deny` \| `AuditIfNotExists` \| `DeployIfNotExists` \| `Modify` \| `Append` \| `Disabled` \| `Manual`. Resolve from the `effect` parameter's `defaultValue` (fall back to `allowedValues[0]` minus `Disabled`). |
| `source.mode` | yes | enum | `Indexed` \| `All` \| a Resource-Provider mode (e.g., `Microsoft.Kubernetes.Data`). From the definition's `properties.mode`. |
| `source.parameters` | no | map | Policy parameters and their defaults (e.g., `{ minimumTlsVersion: "TLS1_2" }`). Match Microsoft's parameter names. |
| `source.documentation_url` | yes | string (URL) | Canonical Microsoft page describing the policy/control. |
| `initiative` | no | map | When the rule comes from a regulatory-compliance initiative: `{ display_name, definition_id, definition_name, group_name }` (`group_name` is the `policyDefinitionGroups[].name`). |
| `defender_for_cloud` | no | map | Defender regulatory-compliance mapping: `{ standard, control_id, assessment_id, documentation_url }`. The Azure analogue of the AWS `security_hub` block. |

### Condition (the assertion)

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `condition.description` | yes | string | Plain-English description of what "compliant" looks like. |
| `condition.parameters` | no | map | Tunable thresholds the policy exposes (e.g., `minimum_tls_version: TLS1_2`). |
| `condition.policy_rule` | yes | string (block) | The Azure Policy `if`/`then` rule. For built-ins, the verbatim `properties.policyRule` JSON (as a YAML block string). For custom rules, a faithful hand-authored `if/then` with an `effect`. Must contain an `effect` and at least one `field`/condition. Manual-effect policies record the literal `{ "if": {...}, "then": { "effect": "Manual" } }`. |
| `condition.aliases[]` | no | list[string] | Azure Policy aliases the rule references (e.g., `Microsoft.Storage/storageAccounts/supportsHttpsTrafficOnly`). Useful for downstream codegen and for confirming the targeted property exists. |

### Remediation

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `remediation.summary` | yes | string | What a consumer does to fix a non-compliant resource. |
| `remediation.terraform_snippet` | no | string (block) | Minimal `azurerm` HCL showing the compliant configuration. |
| `remediation.azure_cli_snippet` | no | string (block) | When useful (e.g., `az storage account update --https-only true`). |
| `remediation.bicep_snippet` | no | string (block) | Minimal Bicep, when useful. |
| `remediation.portal_steps[]` | no | list[string] | Step-by-step Azure portal actions, when CLI/Terraform is awkward. |
| `remediation.notes` | no | string | Caveats (e.g., "changing TLS version may break legacy clients"). |

### Test cases

At least one test case is required so downstream codegen can produce policy unit tests.

```yaml
test_cases:
  - name: storage account with HTTPS-only enabled passes
    input:
      resource_type: Microsoft.Storage/storageAccounts
      properties:
        supportsHttpsTrafficOnly: true
    expected: COMPLIANT
  - name: storage account allowing HTTP fails
    input:
      resource_type: Microsoft.Storage/storageAccounts
      properties:
        supportsHttpsTrafficOnly: false
    expected: NON_COMPLIANT
```

`expected` is `COMPLIANT` | `NON_COMPLIANT` (for `Manual`-effect policies, `expected: MANUAL`).

### Provenance, references, and tags

`provenance` records **where each field's content came from**, so an auditor or codegen step can filter to Microsoft-official content only or flag third-party dependence. It is populated by the bundled fetchers and merged by `enrich_yaml.py`.

Keys may be plain field names (`severity`) **or dotted paths** for composite sub-mappings (`framework_control.title` vs `framework_control.requirement`). The validator walks both forms.

```yaml
provenance:
  framework_control.id:          azure-policy-initiative
  framework_control.title:       defender-regulatory-compliance
  framework_control.requirement: microsoft-learn
  severity:                      defender-regulatory-compliance
  source.policy_definition_name: azure-policy-initiative
  source.effect:                 azure-policy-builtin
  source.documentation_url:      azure-policy-builtin
  resource_types:                azure-policy-builtin
  condition.policy_rule:         azure-policy-builtin
  condition.description:         manual-human
  remediation.summary:           manual-human
  test_cases:                    manual-human
  references:                    [azure-policy-initiative, microsoft-learn]
```

Allowed values (string, or list of strings if mixed). Canonical list: `references/ms-official-provenance.json`, loaded by `validate_yaml.py`:

| Value | Meaning | Strict |
|-------|---------|--------|
| `azure-policy-builtin` | `Azure/azure-policy` built-in policy definition JSON, or `az policy definition show` | ✅ |
| `azure-policy-initiative` | `Azure/azure-policy` built-in policy set definition (regulatory-compliance initiative) JSON | ✅ |
| `azure-policy-metadata` | `Microsoft.PolicyInsights/policyMetadata` (control title/category resource) | ✅ |
| `defender-regulatory-compliance` | Microsoft Defender for Cloud `regulatoryCompliance*` API | ✅ |
| `mcsb` | Microsoft Cloud Security Benchmark (Learn pages / v1 spreadsheet) | ✅ |
| `microsoft-learn` | A Microsoft Learn docs page, hand-verified. Auditor-verifiable via the cited URL. | ✅ |
| `manual-human` | Hand-authored by a human reading Microsoft-official source. Auditor-verifiable via cited URLs. | ✅ |
| `manual-model-synthesised` | Generated by a language model from training-corpus Azure knowledge. Not auditor-verifiable. | ❌ (opt in `--allow-model-synthesis`) |
| `third-party-prowler` | Prowler-Azure (`prowler-cloud/prowler`, Apache-2.0) — community, not Microsoft-official | ❌ |
| `third-party-azadvertizer` | AzAdvertizer (azadvertizer.net) — community resource | ❌ |
| `unknown` | Source unrecorded | ❌ |

A rule whose **every** provenance value has ✅ is "Microsoft-official" — `validate_yaml.py --strict-ms-official` enforces this. Add `--allow-model-synthesis` to also accept `manual-model-synthesised`.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `provenance` | no | map | Per-field source tracking. See above. |
| `references[]` | yes | list | Each item `{ title, url }`. Include the policy definition page **and** the framework/initiative page when both apply. |
| `tags[]` | no | list[string] | Free-form classification (`encryption-in-transit`, `network-exposure`, `identity-least-privilege`). |

## Conventions and gotchas

- **Quote requirements verbatim.** `framework_control.requirement` is the regulatory anchor. Don't paraphrase.
- **Stable IDs.** `id` should not change when regenerated against a newer framework version. Prefer `<service>-<intent>` over hashes.
- **Resolve the effect concretely.** `"[parameters('effect')]"` is not an effect — record the resolved default (`Audit`, `Deny`, `Modify`, ...). Downstream codegen needs the concrete value.
- **`condition.policy_rule` is the asset.** For built-ins, copy the real `policyRule` — it is the highest-fidelity artifact and removes guesswork from codegen. For custom rules, be explicit about the alias/field checked.
- **Initiative ≠ definition.** One initiative control can map to several policy definitions and one definition can appear in many controls/frameworks. Use `source.*` for the definition and `initiative` / `defender_for_cloud` for the aggregator mappings.
- **Test cases drive policy unit tests.** A single `expected: NON_COMPLIANT` test is worth more than long prose remediation.
