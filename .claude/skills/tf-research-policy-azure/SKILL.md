---
name: tf-research-policy-azure
description: Research Azure compliance baselines (CIS Azure Foundations, NIST SP 800-53, PCI DSS, ISO 27001, SOC 2, FedRAMP, Microsoft Cloud Security Benchmark, or any Microsoft-published standard) and produce a structured YAML rule set that downstream tooling turns into Azure Policy definitions and initiatives. TRIGGER when Azure is the target cloud AND the goal is to scaffold a YAML policy rule file (not a one-off question, not a Terraform review). Phrases that match include "research <framework> baseline for Azure", "extract Azure Policy rules from <initiative>", "scaffold Azure compliance YAML", "Azure policy research", "Azure compliance baseline", "MCSB controls reference", "Defender for Cloud regulatory compliance to rules", "CIS Azure benchmark as policy", or handing over a regulation/benchmark and asking for it as structured Azure rules — even without saying "YAML". SKIP if the user has existing Terraform and wants a security review (use tf-security-baselines), wants a one-off explanation of a single policy definition, or the cloud is AWS (use tf-research-policy-aws).
---

# tf-research-policy-azure

Researches Microsoft-published Azure compliance standards and emits a rich YAML rule set that downstream tooling (or a human policy author) uses to generate **Azure Policy definitions** and **policy initiatives (policy set definitions)**. The skill is the *research + scaffolding* step: it does not deploy policy, it produces the source-of-truth YAML that policy code is generated from.

This is the Azure counterpart of `tf-research-policy-aws`. The pipeline shape is the same (skeleton → enrich → bulk-fill → validate), but the sources, identifiers, and schema are Azure-native. The output schema is Azure-tailored — see `references/yaml-schema.md`.

## Source policy

**Microsoft-official sources are the default.** The `Azure/azure-policy` GitHub repo (built-in policy definitions and regulatory-compliance initiatives), the Azure Policy ARM API, the Microsoft Defender for Cloud regulatory-compliance API, and the Microsoft Cloud Security Benchmark (MCSB) are authoritative. Third-party sources (Prowler-Azure, AzAdvertizer) are opt-in fallbacks for content Microsoft does not publish in machine-readable form — primarily cross-framework crosswalks and verbatim external framework text.

Every rule's `provenance` block records where each field came from. Run `validate_yaml.py --strict-ms-official` to fail builds that depend on third-party content. Model-synthesised content (when no Microsoft API or repo content covers a field) is tagged `manual-model-synthesised` and is **rejected by default** under strict mode — pass `--allow-model-synthesis` if the user accepts model-fidelity-as-source.

## Bundled tooling

### Microsoft-official fetchers (preferred)

| Script | Source | Provides |
|--------|--------|----------|
| `scripts/parse_builtin_initiative.py` | `Azure/azure-policy` GitHub repo (or `az rest`) | YAML skeleton: one rule per (built-in policy definition × control group) of a regulatory-compliance initiative — `source.policy_definition_id`, `display_name`, `effect`, `mode`, `resource_types`, `condition.policy_rule`, `framework_control.id`, provenance `azure-policy-initiative`/`azure-policy-builtin` |
| `scripts/fetch_defender_compliance.py` | Defender for Cloud `regulatoryComplianceStandards/Controls/Assessments` API via `az rest` | Per-control state, description, and the mapped Defender assessment IDs; populates the `defender_for_cloud` block. Degrades to a clear "not enabled" message — never fabricates |
| `scripts/enrich_yaml.py` | (merge tool) | Merges Defender compliance JSON or `policyMetadata` control titles into a skeleton — fills `framework_control.{title,requirement}`, `related_controls`, `defender_for_cloud` |

### Bulk enrichment (Phase 4 automation — use this)

| Script | Source | Provides |
|--------|--------|----------|
| `scripts/bulk_enrich.py` | `references/builtin-policy-metadata.json` (bundled snapshot) + deterministic heuristics | Single-pass fill for `severity`, `service`, `condition.description`, `remediation.summary`, `tags`, `source.documentation_url`. Tags filled fields `azure-policy-builtin` or `manual-human`. `--require-zero-todos` exits non-zero if any required gap remains |

### Validation and reporting

| Script | Purpose |
|--------|---------|
| `scripts/preflight.py` | Phase-1 environment probe: `az` present + logged in + subscription + Defender for Cloud reachability, with a per-phase decision printout |
| `scripts/init_yaml.py` | Empty YAML scaffold with metadata block (for single-control / no-initiative runs) |
| `scripts/validate_yaml.py` | Schema validation; policy GUID/name format; ARM resource-type check; effect enum; URL allowlist; `--strict-ms-official` enforces provenance |
| `scripts/summarize_yaml.py` | Rule count, gap count, severity histogram, service breakdown, effect breakdown, READY / NOT-READY verdict |

All scripts accept `--help`. **PyYAML is the only mandatory dependency.** The API fetchers shell out to the Azure CLI (`az` / `az rest`) and reuse the caller's existing `az login` — they do not import any `azure-*` SDK.

## When this skill runs

The user invokes `/tf-research-policy-azure` when they need a structured representation of Azure compliance controls. Typical asks:

- "Research the CIS Microsoft Azure Foundations Benchmark v3.0.0 and give me the YAML rules"
- "Pull the PCI DSS v4 controls that Azure Policy's regulatory-compliance initiative covers"
- "Scaffold rules from the Microsoft Cloud Security Benchmark"

If the user names a framework Microsoft does not publish an **auditable per-control Azure baseline** for, do **not** generate a fabricated rule list. Two failure modes both count here: (a) no built-in initiative, no Defender standard, no MCSB crosswalk exists at all; and (b) a built-in initiative does exist but it is *undifferentiated* — a single control group with all definitions under it (e.g., the "Sarbanes Oxley Act 2022" initiative `5757cf73-35d1-46d4-8c78-17b7ddd6076a`, ~90 definitions, one group, no per-control taxonomy). An undifferentiated bundle cannot be turned into per-control rules without inventing the control decomposition, which is what this skill must never do.

In either case, hand back a one-rule explanatory YAML (`metadata.notes` describes the gap and lists the closest Microsoft-supported analogues — typically MCSB, NIST SP 800-53 R5, SOC 2 Type 2, or a CIS Azure profile) and ask the user to pick one. A fabricated 100-rule YAML is worse than no YAML — it gives auditors false coverage and embeds invented control language.

## Workflow

### 1. Confirm the research target

Before any tool calls:

- **Framework + version** (e.g., `CIS Microsoft Azure Foundations Benchmark v3.0.0`, `NIST SP 800-53 Rev. 5`, `PCI DSS v4.0.1`, `Microsoft cloud security benchmark`).
- **Scope** — whole standard, a service (e.g., Storage-only), or a control family. **If the initiative has > 50 policy definitions and the user did not specify a scope, propose three options (whole standard / top services / single service) and ask before proceeding.** A fully-populated 20-rule YAML is more useful than a half-finished 200-rule one. (Azure regulatory initiatives are large — NIST R5 has ~696 definitions, MCSB ~223.)
- **Output file** — default `policy-research/{framework-slug}-{version}.yaml`.
- **Strict-MS-official mode?** If the user has audit/compliance requirements, they may want to refuse third-party content. This drives whether Prowler-Azure/AzAdvertizer are in scope.

#### Environment preflight

Run the bundled preflight — it checks the Azure CLI, login state, subscription, and Defender for Cloud reachability in one shot and prints the per-phase decision:

```bash
python3 scripts/preflight.py
# or target a Defender standard slug substring:
python3 scripts/preflight.py --target-standard pci
```

The GitHub-repo path (Phase 2a) needs **no Azure auth** and is the default. `az` is only required for the live Policy API and for Defender regulatory-compliance (Phase 2b). **Do not skip the preflight.** "I can `az account show`, therefore Defender is enabled" is wrong — Defender for Cloud has a separate enablement state; the regulatory-compliance API returns empty `value: []` (not a clean error) when it is not initialized. Misreading that as "the framework has no controls" is the single most common reason a run wrongly falls back to Prowler.

### 2. Microsoft-official pipeline (recommended default)

Order matters — each step enriches the previous output.

**2a. Skeleton from the built-in regulatory-compliance initiative** (the default; works offline, no Azure auth):

Look up the framework's initiative GUID and repo filename in `references/builtin-initiative-index.md` rather than guessing — Microsoft's filenames are inconsistent (`CIS_Azure_Foundations_v3.0.0.json`, `NIST_SP_800-53_R5.json`, `PCI_DSS_v4.0.1.json`) and MCSB lives under `Security Center/`, not `Regulatory Compliance/`.

```bash
python3 scripts/parse_builtin_initiative.py \
  --initiative 470a962c-86a0-433b-803a-3c176b5ce79c \
  --framework "CIS Microsoft Azure Foundations Benchmark" --version "3.0.0" \
  --output policy-research/cis-azure-3.0.0.yaml
# --initiative accepts a built-in GUID (resolved from GitHub raw, or `az` with --use-az),
# or a direct repo path like "Regulatory Compliance/CIS_Azure_Foundations_v3.0.0.json".
```

`parse_builtin_initiative.py` walks the initiative's `policyDefinitions[]`, fetches each referenced built-in policy definition, and for every (definition × `groupNames` control) emits a rule populating `id`, `title`, `framework_control.id`, `source.{type,policy_definition_id,policy_definition_name,display_name,effect,mode}`, `resource_types` (parsed recursively from `policyRule.if` `type` clauses), `condition.policy_rule`, `references[0]`, and provenance `azure-policy-initiative` / `azure-policy-builtin`. Control **titles/requirements are not in the initiative JSON** — they live behind `additionalMetadataId` (`Microsoft.PolicyInsights/policyMetadata`) — so those land as `TODO:` and are filled in 2b/Phase 4.

If no built-in initiative exists for the framework, use `scripts/init_yaml.py` for an empty scaffold and rely on Defender / MCSB / manual research.

**2b. Enrich with Defender for Cloud regulatory compliance** (control titles, state, assessment mapping) — only when `preflight.py` reports Defender reachable:

```bash
python3 scripts/fetch_defender_compliance.py \
  --subscription <SUB_ID> --standard <slug> --output /tmp/defender.json
python3 scripts/enrich_yaml.py \
  --yaml policy-research/cis-azure-3.0.0.yaml \
  --controls /tmp/defender.json --source defender-regulatory-compliance
```

Discover the exact `--standard` slug at runtime — `fetch_defender_compliance.py --list-standards` prints the slugs assigned in the subscription (they are inconsistent: `Azure-CIS-2.0.0`, `PCI-DSS-4`, `ISO-27001`). Do not hardcode them. `enrich_yaml.py` fills `framework_control.{title,requirement}`, `related_controls`, and the `defender_for_cloud` block; sub-fields get dotted-key provenance so the initiative-sourced `framework_control.id` survives.

**Interpreting the enrichment output.** `enrich_yaml.py` prints `matched N/M rules (P%)`.

- `< 50%` → **stop and diagnose.** Likely a wrong `--standard` slug or a control-ID format mismatch between the initiative group name (`CIS_Azure_Foundations_v3.0.0_3.1.1`) and the Defender control id (`3.1.1`). Sample 3 unmatched rule IDs vs 3 unmatched control IDs.
- `0` → the script exits non-zero. Pass `--allow-empty` only if Defender genuinely doesn't carry this standard.
- `>= 50%` → continue. The unmatched remainder is fed to Phase 4.

If Defender is not enabled, **skip 2b** — do not treat its absence as "the framework is empty". Control titles can still be filled from the Learn "Regulatory Compliance details" page (cite it, tag `microsoft-learn`) or left for Phase-4 Pass B.

### 3. Optional fallback — Prowler-Azure / AzAdvertizer

Only invoke when ALL of the following are true:

- (a) No built-in initiative exists for the framework (2a returned nothing).
- (b) Defender has no matching standard or is not enabled (2b skipped/empty).
- (c) MCSB does not cover the controls (no crosswalk in `references/builtin-initiative-index.md`).
- (d) Phase-4 Pass B (model synthesis with `manual-human` provenance after WebFetch verification of a Microsoft Learn page) is not acceptable to the user.

If any of (a)–(d) is false, **do not use third-party sources.** Prowler-Azure (`prowler/compliance/azure/*.json`, Apache-2.0) and AzAdvertizer (azadvertizer.net, community) are not Microsoft-official and undermine audit defensibility. When used, tag the affected fields `third-party-prowler` / `third-party-azadvertizer` (both fail `--strict-ms-official`) and document the dependency in `metadata.notes`. AzAdvertizer carries **no** framework crosswalks — it is only useful for Azure Policy metadata and initiative version drift, not control mappings.

### 4. Enrichment — required, not optional

After 2a–2b the YAML carries `TODO:` placeholders in required fields. **Phase 4 must clear every one of them.** A run that hands back a YAML with required-field TODOs is not finished — it is a half-done scaffold and must not be reported as "complete". Downstream consumers expect `validate_yaml.py` to exit 0 and `summarize_yaml.py` to print `READY`.

**Pass A — bulk fill from the bundled snapshot (mandatory):**

```bash
python3 scripts/bulk_enrich.py \
  --yaml policy-research/cis-azure-3.0.0.yaml \
  --require-zero-todos
```

`bulk_enrich.py` reads `references/builtin-policy-metadata.json` and, for every rule whose `source.type` is `azure-policy-builtin`, fills missing `severity`, `service`, `condition.description`, `remediation.summary`, `tags`, and `source.documentation_url`, then derives `service` from the ARM resource type when the snapshot lacks an entry. Filled fields are tagged `azure-policy-builtin` (snapshot-sourced) or `manual-human` (deterministic heuristic).

If `--require-zero-todos` exits non-zero it prints **which rules and which fields** still need attention. Two normal causes:

1. **Policy GUID missing from the snapshot.** Run `scripts/bulk_enrich.py --refresh <GUID1>,<GUID2>` to fetch those definitions (GitHub raw, or `az` with `--use-az`) and merge them into the snapshot, then re-run. Do NOT hand-write metadata into the YAML — the snapshot is the single source of truth and grows as the skill encounters new policies.
2. **Custom policies / manual-attestation controls** (`source.type: azure-policy-custom` or `manual-attestation`) — these need Pass B.

**Pass B — manual fields, only when needed.** For Azure, the common Pass-B case is **Manual-effect policies** (Azure Policy's attestation control type, equivalent to AWS's process-check rules): `bulk_enrich.py` auto-fills these with `severity: INFORMATIONAL`, `condition.description = "Manual attestation required"`, `condition.policy_rule` left as the literal Manual effect, and remediation as the attestation steps — provenance `azure-policy-builtin`. Hand work is only needed for genuine custom policies (a hand-written `condition.policy_rule`), coarse `tags`, opaque `id`s, or framework-specific edge-case `test_cases`. For production runs against Microsoft-published frameworks Pass B is usually a no-op.

**Verify zero TODOs before handoff:**

```bash
python3 scripts/validate_yaml.py policy-research/cis-azure-3.0.0.yaml                                   # must exit 0
python3 scripts/validate_yaml.py policy-research/cis-azure-3.0.0.yaml --strict-ms-official --allow-model-synthesis  # exit 0 if audit-grade
python3 scripts/summarize_yaml.py policy-research/cis-azure-3.0.0.yaml                                   # must read READY
```

If any fail, do not hand back. Either run another `bulk_enrich` (with `--refresh`) cycle or, for legitimately uncoverable frameworks, refuse and explain (see "When this skill runs").

**Provenance values** (canonical list in `references/ms-official-provenance.json`):

| Value | Strict-MS-official |
|-------|--------------------|
| `azure-policy-builtin`, `azure-policy-initiative`, `azure-policy-metadata`, `defender-regulatory-compliance`, `mcsb`, `microsoft-learn` | ✅ |
| `manual-human` | ✅ |
| `manual-model-synthesised` | ❌ (opt-in via `--allow-model-synthesis`) |
| `third-party-prowler`, `third-party-azadvertizer` | ❌ |
| `unknown` | ❌ |

Use the Microsoft-official value that best matches *where the field's content actually came from*. Don't tag a field `azure-policy-initiative` if the value was hand-derived from a Learn page — use `microsoft-learn`. Don't relabel synthesis as `azure-policy-builtin` to "look official" — it sets up an auditor for a bad time.

### 5. Validate and hand back

By this step Phase 4 should already have driven the file to `READY`. Re-run validators as a final check, then report.

```bash
python3 scripts/validate_yaml.py policy-research/<slug>-<v>.yaml                                          # exit 0
python3 scripts/validate_yaml.py policy-research/<slug>-<v>.yaml --strict-ms-official --allow-model-synthesis  # exit 0 if any field is model-synthesis
python3 scripts/validate_yaml.py policy-research/<slug>-<v>.yaml --strict-ms-official                     # exit 0 if every field is ms-official or manual-human (audit-grade)
python3 scripts/summarize_yaml.py policy-research/<slug>-<v>.yaml                                         # status: READY
```

Hand back with these specific items:

- **File path**, **framework + version**, **rule count**
- **Validator outcome**: `validate_yaml.py` exits 0 (yes/no); `--strict-ms-official` exits 0 (yes/no, separated from `--allow-model-synthesis` so the auditor knows whether any field is model-synthesis).
- **`summarize_yaml.py` status**: `READY` or `NOT READY`. If `NOT READY`, surface why and what would clear it — don't hand back a `NOT READY` deliverable silently.
- **Provenance breakdown**: % `ms-official` (strict-passing), % `manual-human`, % `manual-model-synthesised`, % `third-party-*` (must be 0 in audit-grade runs).
- **Gap list**: rules where any required field is null/empty/TODO. Empty list is the goal.

## Common workflow shapes

### Single-control / minimal-scope research

When the user wants one rule (e.g., "enforce HTTPS-only on storage accounts") rather than a full framework, skip the initiative:

```bash
python3 scripts/init_yaml.py --framework "Azure Policy built-in" --version "single-control" \
  --source "https://learn.microsoft.com/azure/storage/common/storage-require-secure-transfer" \
  --output policy-research/storage-https-only.yaml
# Add one rule with source.policy_definition_name set to the built-in GUID
# (e.g., 404c3081-a854-4457-ae30-26a93ef643f9 — secure transfer); bulk_enrich fills the rest.
python3 scripts/bulk_enrich.py --yaml policy-research/storage-https-only.yaml --require-zero-todos
python3 scripts/validate_yaml.py policy-research/storage-https-only.yaml
```

### Scope-narrowed research (e.g., Storage-only slice of CIS Azure)

Run the full initiative through Phase 2/4, then filter deterministically:

```bash
python3 scripts/parse_builtin_initiative.py --initiative <GUID> --framework "CIS ..." --version "3.0.0" --output /tmp/cis-full.yaml
python3 scripts/bulk_enrich.py --yaml /tmp/cis-full.yaml --require-zero-todos
python3 - <<'PY'
import yaml
d = yaml.safe_load(open("/tmp/cis-full.yaml"))
d["metadata"]["framework"]["scope"] = "storage"
d["rules"] = [r for r in d["rules"] if (r.get("service") or "").lower() == "storage"]
yaml.safe_dump(d, open("policy-research/cis-azure-storage.yaml", "w"), sort_keys=False)
PY
python3 scripts/validate_yaml.py policy-research/cis-azure-storage.yaml
```

The full enrichment runs once; the filter is a deterministic post-step.

### Snapshot extension during a run

If `bulk_enrich.py --require-zero-todos` reports policy GUIDs missing from `references/builtin-policy-metadata.json`, extend the bundled snapshot in place:

```bash
python3 scripts/bulk_enrich.py --refresh GUID_A,GUID_B          # fetch + merge into snapshot
python3 scripts/bulk_enrich.py --yaml policy-research/<file>.yaml --require-zero-todos
```

This mutates the bundled snapshot. That is intentional and the documented workflow — the snapshot is the single source of truth and grows as the skill encounters new policies. `--refresh` is idempotent and additive.

## Common pitfalls

0. **Handing back a YAML with required-field TODO placeholders.** A `NOT READY` deliverable is not a deliverable. TODOs leak straight through to Azure Policy generation, where they fail at deploy time or get hand-edited inconsistently. Phase 4 is mandatory. *What "TODO" means here*: only `TODO:` strings inside **required** fields (per `validate_yaml.py`'s required-paths list) count as gaps. `TODO:` in optional/scaffolding fields (`framework_control.title`, `test_cases[].name`, `remediation.bicep_snippet`, …) are intentional placeholders the validator and `summarize_yaml.py` ignore. A clean `validate_yaml.py` exit + `Status: READY` is production-ready even if `grep TODO` shows residual optional-field hits.

1. **"`az account show` works, therefore Defender is enabled."** A valid Azure login does not imply Microsoft Defender for Cloud is initialized. The regulatory-compliance API returns empty `value: []` (not a clear error) until Defender is onboarded; MCSB is assessed free under Foundational CSPM but other standards usually need Defender CSPM. Always run `preflight.py`. The Microsoft-official workaround before any third-party source is the GitHub-repo initiative path (2a) — it needs no Azure account at all.

2. **MCSB is not under "Regulatory Compliance".** The Microsoft Cloud Security Benchmark initiative (`1f3afdf9-d0c9-4c3d-847f-89da613e70a8`) has `metadata.category = "Security Center"`, not `Regulatory Compliance`. A category filter for regulatory packs will miss it — special-case it by GUID (it's flagged in `references/builtin-initiative-index.md`).

3. **Using deprecated Azure Security Benchmark.** ASB v1/v2 are deprecated (displayName prefixed `[Deprecated]:`). Target MCSB instead. The index file lists only current initiatives.

4. **Control titles are not in the initiative JSON.** The initiative carries only `policyDefinitionGroups[].name` (the control number) and an `additionalMetadataId`. Don't invent control titles — fill them from Defender (2b), the `policyMetadata` resource, or the Learn "Regulatory Compliance details" page (tag `microsoft-learn`), or leave the optional `framework_control.title` as a placeholder. `framework_control.id` (required) is always available from the group name.

5. **Inventing policy definition GUIDs.** `validate_yaml.py` flags `policy_definition_name` values that aren't valid GUIDs and `policy_definition_id`s that don't match the ARM pattern. When you cannot resolve a built-in, set `source.type: azure-policy-custom`, keep the name, and explain in `metadata.notes` + the rule's `provenance`. A non-validating YAML is not a deliverable — downstream generators trust `source.type` and emit broken policy.

6. **Treating Prowler/AzAdvertizer as Microsoft-official.** Both are third-party. With audit requirements, run `validate_yaml.py --strict-ms-official` and treat any non-zero error as a hard stop.

7. **Hardcoding Defender standard slugs.** They are inconsistent and per-subscription. Discover them at runtime via `fetch_defender_compliance.py --list-standards`.

## References

- `references/yaml-schema.md` — field-by-field Azure-tailored schema, the `provenance` block, and a complete worked example.
- `references/example-rules.yaml` — worked CIS Azure Storage example with mixed provenance; a reference for the model when producing larger outputs.
- `references/azure-sources.md` — curated Microsoft documentation entry points, the canonical GitHub repos, and the API/api-version table.
- `references/ms-official-provenance.json` — canonical provenance values and which pass `--strict-ms-official`.
- `references/ms-domain-allowlist.txt` — Microsoft-owned domains for URL-allowlist validation under strict mode.
- `references/builtin-initiative-index.md` — verified framework-name → initiative GUID + `Azure/azure-policy` repo filename map (filenames are inconsistent; use this instead of guessing). Includes the MCSB special case.
- `references/arm-resource-types.txt` — seed list of ARM resource provider types used by the validator. Refresh with `az provider list` (documented in the file header).
- `references/builtin-policy-metadata.json` — bundled snapshot of built-in policy metadata (severity, service, condition, remediation) consumed by `bulk_enrich.py`. SINGLE SOURCE OF TRUTH for policy-field content — do not hand-edit rule fields in the YAML; extend the snapshot (`bulk_enrich.py --refresh`) and re-enrich.

For previous-iteration outputs and eval artifacts, see the sibling `tf-research-policy-azure-workspace/` directory — useful when debugging regressions or comparing against earlier runs.
