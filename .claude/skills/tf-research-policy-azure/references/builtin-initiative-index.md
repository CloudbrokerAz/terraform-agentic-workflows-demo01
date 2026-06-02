# Built-in initiative index

Verified framework → built-in Azure Policy initiative (policy set definition) map.
GUIDs and `metadata.version` read from the live `Azure/azure-policy` repo
(`master`) on 2026-05-19. Use this instead of guessing — Microsoft's filenames
are inconsistent (`v` prefix sometimes, underscores vs hyphens, etc.) and the
display names do not match the file names.

All initiative `id` values are `/providers/Microsoft.Authorization/policySetDefinitions/{GUID}`.
Repo raw URL pattern (URL-encode spaces in the category folder as `%20`):

```
https://raw.githubusercontent.com/Azure/azure-policy/master/built-in-policies/policySetDefinitions/{Category}/{FileName}
```

| Framework | Category | FileName | displayName | GUID (`name`) | version | #defs |
|-----------|----------|----------|-------------|---------------|---------|-------|
| **CIS Azure Foundations v3.0.0** *(current CIS Azure)* | Regulatory Compliance | `CIS_Azure_Foundations_v3.0.0.json` | CIS Azure Foundations v3.0.0 | `470a962c-86a0-433b-803a-3c176b5ce79c` | 1.3.0 | 53 |
| CIS Azure Foundations v2.1.0 | Regulatory Compliance | `CIS_Azure_Foundations_v2.1.0.json` | CIS Azure Foundations v2.1.0 | `fe7782e4-6ff3-4e39-8d8a-64b6f7b82c85` | 1.1.0 | 31 |
| CIS Microsoft Azure Foundations Benchmark v2.0.0 | Regulatory Compliance | `CISv2_0_0.json` | CIS Microsoft Azure Foundations Benchmark v2.0.0 | `06f19060-9e68-4070-92ca-f15cc126059e` | 1.10.0 | 108 |
| **NIST SP 800-53 Rev. 5** | Regulatory Compliance | `NIST_SP_800-53_R5.json` | NIST SP 800-53 Rev. 5 | `179d1daa-458f-4e47-8086-2a68d0d6c38f` | 14.19.0 | 696 |
| NIST SP 800-53 R5.1.1 | Regulatory Compliance | `NIST_SP_800-53_R5.1.1.json` | NIST SP 800-53 R5.1.1 | `60205a79-6280-4e20-a147-e2011e09dc78` | 1.7.0 | 223 |
| NIST SP 800-53 Rev. 4 | Regulatory Compliance | `NIST_SP_800-53_R4.json` | NIST SP 800-53 Rev. 4 | `cf25b9c1-bd23-4eb6-bd2c-f4f3ac644a5f` | 17.19.0 | 711 |
| **PCI DSS v4.0.1** *(current)* | Regulatory Compliance | `PCI_DSS_v4.0.1.json` | PCI DSS v4.0.1 | `a06d5deb-24aa-4991-9d58-fa7563154e31` | 1.6.0 | 204 |
| PCI DSS v4 | Regulatory Compliance | `PCI_DSS_V4.0.json` | PCI DSS v4 | `c676748e-3af9-4e22-bc28-50feed564afb` | 1.8.0 | 269 |
| **ISO/IEC 27001:2022** *(current)* | Regulatory Compliance | `ISO_IEC_27001_2022.json` | ISO/IEC 27001 2022 | `5e4ff661-23bf-42fa-8e3a-309a55091cc7` | 1.3.0 | 58 |
| ISO 27001:2013 | Regulatory Compliance | `ISO27001_2013_audit.json` | ISO 27001:2013 | `89c6cddc-1c73-4ac1-b19c-54d1a15a42f2` | 8.8.0 | 450 |
| **SOC 2 Type 2** | Regulatory Compliance | `SOC_2.json` | SOC 2 Type 2 | `4054785f-702b-4a98-9215-009cbd58b141` | 1.12.0 | 307 |
| **FedRAMP Moderate** | Regulatory Compliance | `FedRAMP_M_audit.json` | FedRAMP Moderate | `e95f5a9f-57ad-4d03-bb0b-b1d16db93693` | 17.19.0 | 641 |
| **FedRAMP High** | Regulatory Compliance | `FedRAMP_H_audit.json` | FedRAMP High | `d5264498-16f4-418a-b659-fa7ef418175f` | 17.20.0 | 711 |
| **Microsoft cloud security benchmark (MCSB)** ⚠️ | **Security Center** | `AzureSecurityCenter.json` | Microsoft cloud security benchmark | `1f3afdf9-d0c9-4c3d-847f-89da613e70a8` | 57.56.0 | 223 |

## Notes and special cases

- **MCSB special case** ⚠️ — the Microsoft Cloud Security Benchmark initiative is the Defender-for-Cloud *default* initiative. It lives under category `Security Center` (file `Security%20Center/AzureSecurityCenter.json`), **not** `Regulatory Compliance`. A category filter for regulatory packs will miss it — reference it by GUID `1f3afdf9-d0c9-4c3d-847f-89da613e70a8`. MCSB carries the richest cross-framework crosswalks (NIST 800-53 R5, PCI v4, CIS v8.1, NIST CSF v2, ISO 27001:2022, SOC 2).
- **Deprecated — do not use**: Azure Security Benchmark v1 (`asb_audit.json`) and v2 (`asb_v2.json`) — displayName prefixed `[Deprecated]:`, version suffixed `-deprecated`. MCSB supersedes them.
- **The Regulatory Compliance folder holds ~70 initiative files** (CMMC, HIPAA/HITRUST, SWIFT CSCF, RBI, Spanish ENS, NIS2, DORA, EU AI Act, UK NHS/OFFICIAL, etc.). For any framework not in the table above, enumerate the folder via the GitHub Contents API and read `name` + `properties.displayName` + `properties.metadata.version` from the live JSON rather than guessing the GUID:
  ```
  https://api.github.com/repos/Azure/azure-policy/contents/built-in-policies/policySetDefinitions/Regulatory%20Compliance
  ```
- **Control mapping inside an initiative JSON**: `properties.policyDefinitionGroups[].name` declares each control (the suffix is the control number, e.g. `CIS_Azure_Foundations_v3.0.0_3.1`). `properties.policyDefinitions[]` binds each policy definition to one or more controls via `groupNames[]`. Control titles/descriptions are **not** in the JSON — they sit behind `policyDefinitionGroups[].additionalMetadataId` (`Microsoft.PolicyInsights/policyMetadata`). Fill them in Phase 2b/4.
- **`definitionVersion`** in `policyDefinitions[]` uses range syntax (`"1.*.*"`). The concrete bundled definition `properties.version` is the authoritative one to record.
- **Frameworks with no auditable per-control Azure baseline** — two flavours, both trigger the refuse-don't-fabricate path:
  - **No initiative at all** (e.g., ISO 27701, bespoke internal corporate controls): no built-in initiative, no Defender standard, no MCSB crosswalk.
  - **Undifferentiated single-group initiative**: Microsoft publishes a built-in initiative but with one control group covering every policy, so there is no per-control taxonomy to map. Example: **`5757cf73-35d1-46d4-8c78-17b7ddd6076a` Sarbanes Oxley Act 2022** — `Regulatory Compliance/Sarbanes_Oxley_Act_(1)_2022.json`, ~90 definitions, one group. Decomposing it into per-control rules would require inventing the control structure, which this skill must not do. The closest auditor-recognized proxies for SOX ITGC scope are **SOC 2 Type 2** (`4054785f-...`), **MCSB** (`1f3afdf9-...`), or **NIST SP 800-53 R5** (`179d1daa-...`).
  In either flavour, hand back a one-rule explanatory YAML pointing at MCSB / SOC 2 / NIST 800-53 R5 / CIS Azure as analogues.
