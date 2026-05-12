# AWS Config conformance-pack filename index

Maintained map of compliance framework → exact GitHub filename in
[`awslabs/aws-config-rules`](https://github.com/awslabs/aws-config-rules/tree/master/aws-config-conformance-packs).

The skill's `parse_conformance_pack.py` URL is constructed against
`https://raw.githubusercontent.com/awslabs/aws-config-rules/master/aws-config-conformance-packs/<filename>`.
Filenames are NOT inferable from the framework name — AWS uses inconsistent conventions (sometimes `v` prefix, sometimes not; sometimes Level 1/2 suffix; sometimes `including-global-resourcetypes` split). Use this index instead of guessing; check the GitHub directory listing if a framework you need is missing.

## Direct mappings

| Framework | Version | Filename |
|-----------|---------|----------|
| CIS AWS Foundations Benchmark | v1.3 | `Operational-Best-Practices-for-CIS-AWS-Foundations-Benchmark-v1.3.yaml` |
| CIS AWS Foundations Benchmark | v1.4 Level 1 | `Operational-Best-Practices-for-CIS-AWS-v1.4-Level1.yaml` |
| CIS AWS Foundations Benchmark | v1.4 Level 2 | `Operational-Best-Practices-for-CIS-AWS-v1.4-Level2.yaml` |
| CIS AWS Foundations Benchmark | **v3.0.0** | **NOT PUBLISHED** — use v1.4 Level 1 as a skeleton substitute and document in `metadata.notes`. Use Security Hub (with creds) for the v3-specific control IDs. |
| PCI DSS | v4.0 (incl global) | `Operational-Best-Practices-for-PCI-DSS-v4.0-including-global-resourcetypes.yaml` |
| PCI DSS | v4.0 (excl global) | `Operational-Best-Practices-for-PCI-DSS-v4.0-excluding-global-resourcetypes.yaml` |
| PCI DSS | v3.2.1 | `Operational-Best-Practices-for-PCI-DSS.yaml` |
| HIPAA Security Rule | (current) | `Operational-Best-Practices-for-HIPAA-Security.yaml` |
| NIST 800-53 | Rev 5 | `Operational-Best-Practices-for-NIST-800-53-rev-5.yaml` |
| NIST 800-53 | Rev 4 | `Operational-Best-Practices-for-NIST-800-53-rev-4.yaml` |
| NIST 800-171 | (current) | `Operational-Best-Practices-for-NIST-800-171.yaml` |
| NIST 800-181 | (current) | `Operational-Best-Practices-For-NIST-800-181.yaml` (note capital `For` — most other packs use lowercase `for`; this pack and `Operational-Best-Practices-For-Security-Identity-and-Compliance-Services.yaml` are the exceptions) |
| NIST CSF | (current) | `Operational-Best-Practices-for-NIST-CSF.yaml` |
| NIST 1800-25 | (current) | `Operational-Best-Practices-for-NIST-1800-25.yaml` |
| AWS Foundational Security Best Practices (FSBP) | (current) | **No direct conformance pack**. FSBP is a Security Hub standard, not a Config conformance pack. With creds: enable Security Hub standard `aws-foundational-security-best-practices` and use Phase 2b. Without creds: use `Operational-Best-Practices-For-Security-Identity-and-Compliance-Services.yaml` as the closest substitute and document the substitution in `metadata.notes`. |
| AWS Well-Architected Reliability Pillar | (current) | `Operational-Best-Practices-for-AWS-Well-Architected-Reliability-Pillar.yaml` |
| AWS Well-Architected Security Pillar | (current) | `Operational-Best-Practices-for-AWS-Well-Architected-Security-Pillar.yaml` |
| FedRAMP (Low) | (current) | `Operational-Best-Practices-for-FedRAMP-Low.yaml` |
| FedRAMP (Moderate) | (current) | `Operational-Best-Practices-for-FedRAMP-Moderate.yaml` |
| FFIEC | (current) | `Operational-Best-Practices-for-FFIEC.yaml` |
| GxP | EU Annex 11 | `Operational-Best-Practices-for-GxP-EU-Annex-11.yaml` |
| GxP | 21 CFR Part 11 | `Operational-Best-Practices-for-FDA-21CFR-Part-11.yaml` |
| HIPAA Security | (current) | `Operational-Best-Practices-for-HIPAA-Security.yaml` |
| ISO 27001 (2013) | (current) | **NOT PUBLISHED** as a Config conformance pack — `Operational-Best-Practices-for-ISO-27001.yaml` does NOT exist in awslabs/aws-config-rules. AWS Audit Manager DOES carry an ISO/IEC 27001:2013 framework, so with creds use Phase 2c. Without creds, NIST 800-53 Rev 5 is the closest AWS-published analogue — substitute and document the mapping in `metadata.notes`. |
| MAS Notice 655 | (current) | `Operational-Best-Practices-for-MAS-Notice-655.yaml` |
| MAS TRMG | (current) | `Operational-Best-Practices-for-MAS-TRMG.yaml` |
| RBI India (Basic Cyber Security Framework) | (current) | `Operational-Best-Practices-for-RBI-Basic-Cyber-Security-Framework.yaml` |
| RBI India (MasterDirection) | (current) | `Operational-Best-Practices-for-RBI-MasterDirection.yaml` |
| BNM RMiT | (current) | `Operational-Best-Practices-for-BNM-RMiT.yaml` |
| Mexico Banking Cybersecurity | (n/a) | **NOT PUBLISHED** as a Config conformance pack. Refuse and propose NIST 800-53 Rev 5 + AWS FSBP as analogues. |
| Singapore PDPA | (n/a) | **NOT PUBLISHED** as a Config conformance pack. Refuse and propose NIST 800-53 Rev 5 + AWS FSBP as analogues. ABS CCIGv2 (`Operational-Best-Practices-for-ABS-CCIGv2-Standard.yaml`) is the closest Singapore-banking analogue. |
| ABS CCIGv2 (Singapore banking) | (current) | `Operational-Best-Practices-for-ABS-CCIGv2-Standard.yaml` |
| ACSC Essential 8 (Australian) | (current) | `Operational-Best-Practices-for-ACSC-Essential8.yaml` |
| ACSC ISM (Australian) | (current) | `Operational-Best-Practices-for-ACSC-ISM-Part1.yaml`, `...Part2.yaml` |
| APRA CPG 234 (Australian banking) | (current) | `Operational-Best-Practices-for-APRA-CPG-234.yaml` |
| CCCS Medium (Canadian) | (current) | `Operational-Best-Practices-for-CCCS-Medium.yaml` |
| CCN-ENS (Spanish) | High / Medium / Low | `Operational-Best-Practices-for-CCN-ENS-{High,Medium,Low}.yaml` |
| CIS Critical Security Controls v8 | IG1 / IG2 / IG3 | `Operational-Best-Practices-for-CIS-Critical-Security-Controls-v8-{IG1,IG2,IG3}.yaml` |
| CISA Cyber Essentials | (current) | `Operational-Best-Practices-for-CISA-Cyber-Essentials.yaml` |
| CJIS | (current) | `Operational-Best-Practices-for-CJIS.yaml` |
| CMMC 2.0 | Level 1 / Level 2 | `Operational-Best-Practices-for-CMMC-2.0-Level-{1,2}.yaml` |
| ENISA Cybersecurity Guide | (current) | `Operational-Best-Practices-for-ENISA-Cybersecurity-Guide.yaml` |
| FedRAMP (High) | (current) | `Operational-Best-Practices-for-FedRAMP-HighPart1.yaml`, `...HighPart2.yaml` (split into two files) |
| Germany C5 | (current) | `Operational-Best-Practices-for-Germany-C5.yaml` |
| Gramm-Leach-Bliley Act | (current) | `Operational-Best-Practices-for-Gramm-Leach-Bliley-Act.yaml` |
| IRS 1075 | (current) | `Operational-Best-Practices-for-IRS-1075.yaml` |
| KISMS (Korean) | (current) | `Operational-Best-Practices-for-KISMS.yaml` |
| NBC TRMG (Cambodian) | (current) | `Operational-Best-Practices-for-NBC-TRMG.yaml` |
| NCSC CAF (UK) | (current) | `Operational-Best-Practices-for-NCSC-CAF.yaml` |
| NCSC Cloud Security Principles (UK) | (current) | `Operational-Best-Practices-for-NCSC-CloudSec-Principles.yaml` |
| NERC CIP (energy) | (current) | `Operational-Best-Practices-for-NERC-CIP.yaml` |
| NIST 800-172 | (current) | `Operational-Best-Practices-for-NIST-800-172.yaml` |
| NIST Privacy Framework | (current) | `Operational-Best-Practices-for-NIST-Privacy-Framework.yaml` |
| NYDFS 23 NYCRR 500 | (current) | `Operational-Best-Practices-for-NYDFS-23-NYCRR-500.yaml` |
| NZISM (New Zealand) | (current) | `Operational-Best-Practices-for-NZISM-Foundation.yaml`, `...-Extension.yaml` |
| PCI DSS v3.2.1 | (legacy) | `Operational-Best-Practices-for-PCI-DSS.yaml` (note: filename omits `v3.2.1`) |
| SWIFT CSP | (current) | `Operational-Best-Practices-for-SWIFT-CSP.yaml` |

## Frameworks AWS does NOT publish

- **SOX (Sarbanes-Oxley)** — no AWS-published baseline. Refuse and propose NIST 800-53 Rev 5 + AWS FSBP as analogues.
- **ISO 27701** — no AWS-published baseline. Use ISO 27001 + selected NIST 800-53 controls as analogues.
- **SOC 1 / SOC 2** — Security Hub does NOT publish a SOC 2 standard, but Audit Manager has a SOC 2 framework (with creds) and there are mappings via the AWS Audit Manager SOC 2 framework. Without creds, refuse and propose NIST 800-53 Rev 5 + FSBP.

## Filename gotchas

- **Case is significant** — `raw.githubusercontent.com` is case-sensitive. The FSBP substitute is `Operational-Best-Practices-For-Security-Identity-and-Compliance-Services.yaml` (capital `For`, lowercase `and`); `For-...-And-...` 404s. Copy filenames verbatim from this index, do not retype.
- **Hyphens are the rule** — every awslabs pack uses hyphens in filenames, including version segments. Earlier versions of this index incorrectly listed `_rev_5` for NIST 800-53; the live filenames are `-rev-5` / `-rev-4`. Copy filenames verbatim from the table above.
- **Version prefix** — PCI v4 has `v4.0` in the filename; CIS v1.4 packs say `v1.4`; HIPAA omits the version entirely. Don't pattern-match; look up.

## Refresh

This file is hand-curated. To sanity-check that filenames are still correct, run:

```bash
curl -s "https://api.github.com/repos/awslabs/aws-config-rules/contents/aws-config-conformance-packs" \
  | jq -r '.[].name' | sort
```

If a framework is missing from this index but AWS has added a conformance pack, add a new row. AWS occasionally renames packs (the v1.4 CIS pack used a different filename pattern than v1.3) — do not assume continuity.
