# Azure compliance sources

Curated, verified entry points (checked 2026-05-19). Microsoft-official first;
third-party fallbacks last and clearly marked.

## Microsoft-official — primary

### Azure/azure-policy GitHub repo (no Azure auth needed — default path)

- Repo: `https://github.com/Azure/azure-policy`
- Built-in policy definitions: `built-in-policies/policyDefinitions/{Category}/{File}.json`
- Built-in initiatives: `built-in-policies/policySetDefinitions/{Category}/{File}.json`
- Raw URL (URL-encode spaces as `%20`):
  `https://raw.githubusercontent.com/Azure/azure-policy/master/built-in-policies/policySetDefinitions/Regulatory%20Compliance/{File}.json`
- Enumerate a folder (no manifest file exists in the repo):
  `https://api.github.com/repos/Azure/azure-policy/contents/built-in-policies/policySetDefinitions/Regulatory%20Compliance`
- Human index (generated, not a repo file):
  - Built-in definitions: `https://learn.microsoft.com/azure/governance/policy/samples/built-in-policies`
  - Built-in initiatives: `https://learn.microsoft.com/azure/governance/policy/samples/built-in-initiatives`

### Azure Policy ARM API (needs `az login`; Reader role)

| Operation | `az` | REST (`az rest --method get --url`) |
|-----------|------|--------------------------------------|
| List built-in initiatives | `az policy set-definition list --query "[?policyType=='BuiltIn']"` | `https://management.azure.com/providers/Microsoft.Authorization/policySetDefinitions?api-version=2025-11-01&$filter=category eq 'Regulatory Compliance'` |
| Get an initiative by GUID | `az policy set-definition show --name <GUID>` | `https://management.azure.com/providers/Microsoft.Authorization/policySetDefinitions/<GUID>?api-version=2025-11-01` |
| Get a policy definition by GUID | `az policy definition show --name <GUID>` | `https://management.azure.com/providers/Microsoft.Authorization/policyDefinitions/<GUID>?api-version=2025-11-01` |
| Control title metadata | — | `https://management.azure.com/providers/Microsoft.PolicyInsights/policyMetadata/<id>?api-version=2019-01-01` |

- Policy api-version: `2025-11-01` (latest stable). `2023-04-01` is a safe widely-documented fallback.
- ⚠️ `policyMetadata` api-version `2019-01-01` is the documented one but confirm at use time; if it fails, fall back to the Learn "Regulatory Compliance details" page for control titles.
- In zsh/bash, escape `$filter` as `\$filter` in `az rest --url`, or single-quote the whole URL.

### Defender for Cloud regulatory compliance (needs `az login` + Defender for Cloud)

Resource provider `Microsoft.Security`, **api-version `2019-01-01-preview`** (the only one; preview but stable for years — there is no GA version).

| Operation | REST URL (`https://management.azure.com` prefix) | `az` |
|-----------|--------------------------------------------------|------|
| List standards | `/subscriptions/{sub}/providers/Microsoft.Security/regulatoryComplianceStandards?api-version=2019-01-01-preview` | `az security regulatory-compliance-standards list` |
| List controls | `/subscriptions/{sub}/providers/Microsoft.Security/regulatoryComplianceStandards/{std}/regulatoryComplianceControls?api-version=2019-01-01-preview` | `az security regulatory-compliance-controls list --standard-name {std}` |
| List assessments | `.../regulatoryComplianceControls/{ctrl}/regulatoryComplianceAssessments?api-version=2019-01-01-preview` | `az security regulatory-compliance-assessments list --standard-name {std} --control-name {ctrl}` |

- Subscription-scoped only (no tenant/management-group variant).
- Standard slugs are inconsistent (`Azure-CIS-2.0.0`, `PCI-DSS-4`, `ISO-27001`, `SOC-TSP`) and per-subscription — **discover at runtime** from the standards-list call; do not hardcode.
- A control item: `{ name (control id), properties: { description, state, passedAssessments, failedAssessments } }`. Mapped assessment IDs require the per-control assessments call.
- ⚠️ Not enabled → empty `value: []` (not a clear error). MCSB is assessed free under Foundational CSPM; other standards usually need a Defender plan. Available-standards list: `https://learn.microsoft.com/azure/defender-for-cloud/concept-regulatory-compliance-standards`.

### Microsoft Cloud Security Benchmark (MCSB)

- Docs hub: `https://learn.microsoft.com/security/benchmark/azure/`
- GitHub: `https://github.com/MicrosoftDocs/SecurityBenchmarks`
- Machine-readable v1 spreadsheet (stable raw URL):
  `https://raw.githubusercontent.com/MicrosoftDocs/SecurityBenchmarks/master/Microsoft%20Cloud%20Security%20Benchmark/Microsoft_cloud_security_benchmark_v1.xlsx`
- Control IDs: `<DOMAIN>-<n>` (`NS-1`, `IM-2`, `DP-3`). Domains: NS, IM, PA, DP, AM, LT, IR, PV, ES, BR, DS (v2 adds AI).
- Carries crosswalks: NIST SP 800-53 R5, PCI-DSS v4, CIS Controls v8.1, NIST CSF v2.0, ISO/IEC 27001:2022, SOC 2 — exactly the `related_controls[]` content.
- v1 = current GA; v2 = preview, **no machine-readable spreadsheet yet** — use v1 XLSX or the MCSB Policy initiative (`1f3afdf9-d0c9-4c3d-847f-89da613e70a8`).

### ARM resource types

- `az provider list --query "[].{ns:namespace, types:resourceTypes[].resourceType}" -o json`
- `az provider show --namespace Microsoft.Storage --query "resourceTypes[].resourceType" -o tsv`
- REST: `https://management.azure.com/subscriptions/{sub}/providers/Microsoft.Storage?api-version=2022-09-01`
- Canonical format: `Microsoft.Storage/storageAccounts`, `Microsoft.Compute/virtualMachines`, nested `Microsoft.Storage/storageAccounts/blobServices/containers`. Prefer `az provider` (version-agnostic) over hardcoding the REST api-version.

## Third-party fallbacks — opt-in, not Microsoft-official

- **Prowler-Azure** — `https://github.com/prowler-cloud/prowler`, **Apache-2.0**. Azure compliance JSON: `prowler/compliance/azure/` — `cis_2.0_azure`, `cis_3.0_azure`, `cis_4.0_azure`, `iso27001_2022_azure`, `pci_4.0_azure`, `soc2_azure`, `hipaa_azure`, `nis2_azure`, `ens_rd2022_azure`, `c5_azure`, `rbi_cyber_security_framework_azure`, … Useful as a cross-framework crosswalk source. No native MCSB framework. Tag `third-party-prowler` (fails `--strict-ms-official`).
- **AzAdvertizer** — `https://www.azadvertizer.net/`, community resource (not OSS-licensed; consume as reference, don't vendor). Provides Azure Policy / initiative metadata, effect types, GA-vs-preview state, and **initiative version drift** (e.g., MCSB version history). ⚠️ Carries **no** CIS/NIST/PCI framework crosswalks. Tag `third-party-azadvertizer`.

## Sources Microsoft does NOT publish for Azure

No built-in initiative, no Defender standard, no MCSB crosswalk exists for SOX, ISO 27701, or bespoke internal corporate control sets. Do not fabricate. Hand back a one-rule explanatory YAML recommending MCSB, NIST SP 800-53 R5, or a CIS Azure profile as the closest Microsoft-supported analogue.
