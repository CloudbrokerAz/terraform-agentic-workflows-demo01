---
name: tf-research-policy-aws
description: Research AWS compliance baselines (CIS, NIST, PCI, HIPAA, SOC 2, ISO 27001, AWS FSBP, or any AWS-published standard) and produce a structured YAML rule set that downstream tooling turns into AWS Config rules and Security Hub controls. TRIGGER when AWS is the target cloud AND the goal is to scaffold a YAML policy rule file (not a one-off question, not a Terraform review). Phrases that match include "research <framework> baseline", "extract Config rules from <pack>", "scaffold compliance YAML", "policy research", "compliance baseline", "Security Hub controls reference", "Config rules from conformance pack", "audit framework", or handing over a regulation/benchmark and asking for it as structured rules — even without saying "YAML". SKIP if the user has existing Terraform and wants a security review (use tf-security-baselines), or wants a one-off explanation of a single managed rule, or the cloud is not AWS.
---

# tf-research-policy-aws

Researches AWS-published compliance standards and emits a rich YAML rule set that downstream tooling (or a human policy author) uses to generate **AWS Config rules** and **AWS Security Hub controls**. The skill is the *research + scaffolding* step: it does not deploy policy, it produces the source-of-truth YAML that policy code is generated from.

## Source policy

**AWS-official sources are the default.** AWS-Labs / AWS-CloudFormation GitHub repos and AWS APIs (Security Hub, Audit Manager, Config) are authoritative. Third-party sources (Prowler, Trivy) are opt-in fallbacks for content AWS does not publish — primarily per-control Terraform remediation snippets and verbatim text from external framework owners (CIS, NIST, PCI Council).

Every rule's `provenance` block records where each field came from. Run `validate_yaml.py --strict-aws-official` to fail builds that depend on third-party content. Model-synthesised content (when no AWS API is available) is tagged `manual-model-synthesised` and is **rejected by default** under strict mode — pass `--allow-model-synthesis` if the user accepts model-fidelity-as-source.

## Bundled tooling

### AWS-official fetchers (preferred)

| Script | Source | Provides |
|--------|--------|----------|
| `scripts/parse_conformance_pack.py` | `awslabs/aws-config-rules` GitHub repo | YAML skeleton with authoritative `source.identifier` (AWS Config managed rule), `source.parameters`, `resource_types` |
| `scripts/fetch_security_hub_controls.py` | AWS Security Hub `describe-standards-controls` (subscribed) **or** `list-security-control-definitions` (`--unsubscribed`) | Per-control severity, title, requirement description, remediation URL, cross-framework mappings |
| `scripts/fetch_audit_manager_framework.py` | AWS Audit Manager `get-control` API | Per-control metadata for frameworks Security Hub doesn't carry (HIPAA, GDPR, FedRAMP, GxP, FERPA) |
| `scripts/fetch_guard_registry.py` | `aws-cloudformation/aws-guard-rules-registry` GitHub repo | Real CFN test fixtures (PASS/FAIL pairs) merged as `test_cases[]`; framework mappings for CMMC, MAS, FDA, etc. |
| `scripts/enrich_yaml.py` | (merge tool) | Merges Security Hub or Audit Manager JSON into a YAML skeleton |
| `scripts/merge_yaml.py` | (merge tool) | Joins two YAML rule sets by `framework_control.id` (best-of-both per field, provenance preserved) |
| `scripts/refresh_sh_control_crosswalk.py` | AWS Security Hub controls reference HTML | Maintenance: regenerate `references/sh-control-to-config-rule.json` from per-service controls pages |

### Third-party fallback (opt-in)

| Script | Source | Provides |
|--------|--------|----------|
| `scripts/fetch_prowler_baseline.py` | `prowler-cloud/prowler` (Apache-2.0, **community open-source — not AWS-official**) | Verbatim framework requirement text (CIS, NIST, PCI), per-control Terraform / CLI / console remediation snippets, cross-framework category mappings |

Outputs from this script are tagged `provenance.*: third-party-prowler` and will fail `validate_yaml.py --strict-aws-official`. Use only when the AWS-official path leaves gaps the user needs filled.

### Bulk enrichment (Phase 4 automation — use this)

| Script | Source | Provides |
|--------|--------|----------|
| `scripts/bulk_enrich.py` | `references/managed-rules-metadata.json` (bundled snapshot) | Single-pass fill for severity, framework_control.requirement, condition.{description,logic}, remediation.summary, service, resource_types, source.documentation_url. Tags every filled field with `aws-config-managed-rule-doc` provenance. The `--require-zero-todos` flag exits non-zero if any TODO remains, so the workflow fails fast in production. |
| `scripts/refresh_managed_rules_metadata.py` | AWS Config developer guide pages (per-rule HTML) | Maintenance: rebuild `references/managed-rules-metadata.json` when AWS publishes new managed rules or revises existing ones. Slow; run on a cadence, not per-research-task. |

### Validation and reporting

| Script | Purpose |
|--------|---------|
| `scripts/preflight.py` | Single-command Phase-1 environment probe (creds + Security Hub + Audit Manager) with per-phase decisions |
| `scripts/init_yaml.py` | Empty YAML scaffold with metadata block |
| `scripts/validate_yaml.py` | Schema validation; managed rule identifier check; CFN type check; `condition.logic` trivia heuristic; URL allowlist; `--strict-aws-official` enforces provenance |
| `scripts/summarize_yaml.py` | Rule count, gap count, severity histogram, service breakdown, READY/NOT-READY verdict |
| `scripts/refresh_managed_rules.py` | Maintenance: refresh bundled AWS Config managed rules snapshot (identifier list) |
| `scripts/refresh_cfn_types.py` | Maintenance: refresh bundled CFN resource types snapshot |

All scripts accept `--help`. PyYAML is the only mandatory dependency; the API fetchers also need `boto3`.

## When this skill runs

The user invokes `/tf-research-policy-aws` when they need a structured representation of AWS compliance controls. Typical asks:

- "Research the CIS AWS Foundations Benchmark v3.0 and give me the YAML rules"
- "Pull the PCI DSS v4 controls AWS Security Hub supports"
- "Scaffold rules from the HIPAA security framework AWS Audit Manager publishes"

If the user names a framework AWS does not publish a baseline for (no Security Hub standard, no Audit Manager framework, no awslabs conformance pack), do **not** generate a fabricated rule list. Hand back a one-rule explanatory YAML (`metadata.notes` describes the gap and lists the closest AWS-supported analogues — typically NIST 800-53 Rev 5, AWS FSBP, or a CIS profile) and ask the user to pick one. A fabricated 100-rule SOX YAML is worse than no YAML — it gives auditors a false sense of coverage and embeds invented control language.

## Workflow

### 1. Confirm the research target

Before any tool calls:

- **Framework + version** (e.g., `CIS AWS Foundations Benchmark v3.0.0`, `NIST 800-53 Rev 5`, `PCI DSS v4.0.1`).
- **Scope** — whole standard, a service (e.g., S3-only), or a control family. **If the framework has > 50 controls and the user did not specify a scope, propose three options (whole standard / top services / single service) and ask before proceeding.** A fully-populated 20-rule YAML is more useful than a half-finished 100-rule one.
- **Output file** — default `policy-research/{framework-slug}-{version}.yaml`.
- **Strict-AWS-official mode?** If the user has audit/compliance requirements, they may want to refuse third-party content. This drives whether Prowler is in scope.

#### Environment preflight

Run the bundled preflight script — it probes AWS API access, Security Hub state, and Audit Manager state in one shot and prints the per-phase decision:

```bash
python3 scripts/preflight.py
# or with a target Security Hub standard ARN substring:
python3 scripts/preflight.py --target-standard cis-aws-foundations-benchmark
```

Output:

```
=== tf-research-policy-aws preflight ===
AWS creds:       OK (account=123456789012)
Security Hub:    subscribed
Audit Manager:   available

=== DECISIONS ===
  phase_2a_conformance_pack: use
  phase_2b_security_hub: use (subscribed mode)
  phase_2c_audit_manager: use
  phase_4_bulk_enrich: use (always; snapshot complements API output)
```

The script never fabricates output — if creds fail, it prints `FAIL` and tells the caller to skip the API phases. **Do not skip the preflight.** Security Hub and Audit Manager have separate enablement states; a successful `get-caller-identity` does not imply they are reachable. Misreading "creds work, so the service must be enabled" is the single most common reason Phase 2 ends up over-relying on Prowler.

### 2. AWS-official pipeline (recommended default)

Order matters — each step enriches the previous output.

**2a. Skeleton from AWS Config conformance pack** (if one exists for the framework):

```bash
python3 scripts/parse_conformance_pack.py \
  https://raw.githubusercontent.com/awslabs/aws-config-rules/master/aws-config-conformance-packs/<filename>.yaml \
  --framework "<name>" --version "<v>" \
  --output policy-research/<slug>-<v>.yaml
```

The exact filename varies per framework. Use the lookup in `references/conformance-pack-index.md` rather than guessing — common gotchas:

- **CIS v3.0.0 has no AWS conformance pack.** Only `Operational-Best-Practices-for-CIS-AWS-v1.4-Level1.yaml` and `...v1.4-Level2.yaml` (plus v1.3) exist. When asked for v3, use v1.4 Level 1 as the closest available skeleton, document the substitute in `metadata.notes`, and rely on Security Hub (which DOES carry CIS v3 if you have creds) for the v3-specific control IDs in Phase 2b.
- **PCI DSS v4** has both `Operational-Best-Practices-for-PCI-DSS-v4.0-including-global-resourcetypes.yaml` and `...-excluding-global-resourcetypes.yaml`. Use the *including* variant unless the user is specifically excluding global resources from scope.
- **HIPAA** is just `Operational-Best-Practices-for-HIPAA-Security.yaml` (no version in the filename).

`parse_conformance_pack.py` populates `id`, `source.type`, `source.identifier` (authoritative AWS Config managed rule), `source.documentation_url`, `source.parameters`, `condition.parameters`, `resource_types`, `references[0]`, and `provenance.{source.identifier,resource_types}: aws-conformance-pack`. The remaining fields (severity, requirement, condition.{description,logic}, remediation) are populated in Phase 4 by `bulk_enrich.py` from the bundled metadata snapshot — see Phase 4 below.

If no conformance pack exists, use `scripts/init_yaml.py` for an empty scaffold and rely on Security Hub / Audit Manager for the rule list.

**2b. Enrich with Security Hub** — pick by Phase-1 outcome:

| Preflight result | Use this |
|------------------|----------|
| `get-enabled-standards` lists the target standard | **Subscribed mode** below |
| `get-enabled-standards` returns `InvalidAccessException` OR the standard isn't subscribed | **Unsubscribed mode** below |
| Account has no AWS creds at all | Skip 2b; go to 2c or Phase-4 |

**Subscribed mode:**

```bash
python scripts/fetch_security_hub_controls.py \
  --standard "<standard-name>" --output /tmp/sh-controls.json
```

**Unsubscribed mode** (catalogue API; no Security Hub subscription required):

```bash
python scripts/fetch_security_hub_controls.py \
  --standard-arn arn:aws:securityhub:us-east-1::standards/<slug>/v/<version> \
  --unsubscribed --output /tmp/sh-controls.json
```

Standard ARN slugs: `aws-foundational-security-best-practices`, `cis-aws-foundations-benchmark`, `pci-dss`, `nist-800-53` — examples printed by `--list-standards` in subscribed mode, or constructible from the AWS docs URL pattern. The output JSON's `standard.mode` records which mode was used so downstream tools can tell.

Then in either mode:

```bash
python scripts/enrich_yaml.py \
  --yaml policy-research/<slug>-<v>.yaml \
  --controls /tmp/sh-controls.json \
  --source aws-security-hub
```

Populates `severity`, `framework_control.title`, `framework_control.requirement`, `related_controls`, references, and the `security_hub` mapping block. Sub-fields get dotted-key provenance (`framework_control.title: aws-security-hub` rather than collapsing onto the parent), so the conformance-pack-sourced `framework_control.id` survives intact.

`enrich_yaml.py` automatically loads `references/sh-control-to-config-rule.json` — a curated `control_id → AWS Config rule` crosswalk — to bridge the gap that the catalogue API exposes. Without it, unsubscribed mode produces zero matches because the `RelatedRequirements` field is empty in the catalogue. Pass `--no-crosswalk` to disable; pass `--crosswalk <path>` to point at a custom one.

**Interpreting the enrichment output.** `enrich_yaml.py` prints `matched N/M rules (P%)` plus a per-strategy breakdown.

- `< 50%` matched → **stop and diagnose.** Likely causes: wrong `--standard-arn`, missing crosswalk entries (extend `references/sh-control-to-config-rule.json` or run `scripts/refresh_sh_control_crosswalk.py`), or the conformance pack uses identifiers the catalogue mode doesn't expose. Sample 3 unmatched rule IDs vs 3 unmatched control IDs to identify the gap.
- `0` matched → the script exits non-zero. Pass `--allow-empty` only if you have a deliberate reason (e.g., the standard truly isn't covered by Security Hub).
- `>= 50%` → continue to 2c/2d. The unmatched remainder is fed to Phase-4 Pass A.

**2c. Enrich with Audit Manager** (frameworks Security Hub doesn't carry):

```bash
python scripts/fetch_audit_manager_framework.py \
  --framework "HIPAA" --output /tmp/am-framework.json
python scripts/enrich_yaml.py \
  --yaml policy-research/<slug>-<v>.yaml \
  --controls /tmp/am-framework.json \
  --source aws-audit-manager
```

**2d. Add real test fixtures** from the AWS Guard Rules Registry:

```bash
python scripts/fetch_guard_registry.py \
  --framework <guard-framework-id> \
  --mode merge --yaml policy-research/<slug>-<v>.yaml
```

Populates `test_cases[]` with real CFN snippets and PASS/FAIL expectations. Provenance: `aws-guard-registry`.

### 3. Optional fallback — Prowler

Only invoke when ALL of the following are true:

- (a) No conformance pack exists for the framework (2a returned nothing).
- (b) Security Hub `--unsubscribed` returned no controls (2b matched 0).
- (c) Audit Manager has no matching framework (2c skipped or empty).
- (d) Phase-4 Pass B (model synthesis with `manual-human` provenance after WebFetch verification) is not acceptable to the user.

If any of (a)–(d) is false, **do not run Prowler.** Prowler is third-party and undermines audit defensibility.

```bash
python scripts/fetch_prowler_baseline.py \
  --framework <prowler-framework-id> \
  --output policy-research/<slug>-prowler.yaml

# Combine with the AWS-official YAML, taking AWS-official precedence
python scripts/merge_yaml.py \
  --primary policy-research/<slug>-<v>.yaml \
  --secondary policy-research/<slug>-prowler.yaml \
  --output policy-research/<slug>-merged.yaml
```

`merge_yaml.py` propagates provenance per-field, so a downstream `validate_yaml.py --strict-aws-official` sees exactly which fields trace to Prowler.

### 4. Enrichment — required, not optional

After 2a–2d the YAML carries `TODO:` placeholders. **Phase 4 must clear every one of them.** A run that hands back a YAML with TODOs is not finished — it is a half-done scaffold and must not be reported to the user as "complete". The skill's downstream consumers expect `validate_yaml.py` to exit 0 and `summarize_yaml.py` to print `READY`. Anything less is failure.

The work is split into a single bulk pass plus a short manual cleanup, in that order:

**Pass A — bulk fill from the bundled snapshot (mandatory):**

```bash
python3 scripts/bulk_enrich.py \
  --yaml policy-research/<slug>-<v>.yaml \
  --require-zero-todos
```

`bulk_enrich.py` reads `references/managed-rules-metadata.json` and, for every rule whose `source.type` is `aws-config-managed-rule`, fills missing `severity`, `framework_control.{title,requirement}`, `condition.{description,logic}`, `remediation.summary`, `service`, `resource_types`, and `source.documentation_url`. Every filled field is tagged `aws-config-managed-rule-doc` provenance.

If `--require-zero-todos` exits non-zero, the script prints **which rules and which fields** still need attention. The two normal causes are:

1. **Rule identifier missing from the snapshot.** Run `scripts/refresh_managed_rules_metadata.py --rule-ids <ID1>,<ID2> --merge` to fetch and add it to the snapshot, then re-run `bulk_enrich.py`. Do NOT hand-write metadata into the YAML; the snapshot is the single source of truth.
2. **Custom rules** (`source.type: aws-config-custom-rule`). These won't be in the snapshot — they need Pass B.

**Pass B — manual fields, only when needed.** `bulk_enrich.py` already covers two custom-rule cases out of the box:

1. **AWS_CONFIG_PROCESS_CHECK custom rules** (the most common variety in CIS / Audit-Manager packs): the script auto-fills title, framework_control, severity (`INFORMATIONAL`, since AWS doesn't publish a severity for process attestations), `condition.logic = "manual_attestation_required == true"`, remediation, service, and resource_types — provenance tagged `aws-conformance-pack` or `manual-human` per field.
2. **AWS-published managed rules** in the bundled snapshot.

Pass B is only needed when:

- **Non-process-check custom rules** (rare; mostly CUSTOM_LAMBDA-backed bespoke checks) need a hand-written `condition.logic`. Must contain a comparison or membership operator (`==`, `!=`, `in`, `contains`, `AND`, `OR`). Tag `manual-human` after verifying against AWS documentation; tag `manual-model-synthesised` if generated without verification.
- **`tags`** are too coarse — refine the auto-derived ones.
- **Stable `id`** — the kebab ID from `parse_conformance_pack.py` is usually fine; rename only when the pack's name is genuinely opaque.
- **Edge-case `test_cases`** — supplement Guard registry fixtures with framework-specific edge cases. Tag `[aws-guard-registry, manual-human]` when extending existing fixtures.

For production-grade runs against AWS-published frameworks, Pass B is usually a no-op. If `bulk_enrich.py --require-zero-todos` exits 0, you're done.

**Verify zero TODOs before handoff:**

```bash
python3 scripts/validate_yaml.py policy-research/<slug>-<v>.yaml                    # must exit 0
python3 scripts/validate_yaml.py policy-research/<slug>-<v>.yaml --strict-aws-official --allow-model-synthesis  # must exit 0 if user wants audit-grade
python3 scripts/summarize_yaml.py policy-research/<slug>-<v>.yaml                   # must read READY
```

If any of these fail, do not hand back. Either run another `bulk_enrich`/`refresh_managed_rules_metadata` cycle or, for legitimately uncoverable cases (e.g., framework AWS does not publish), refuse the run and explain — see the "Frameworks AWS does not publish" section.

**Frameworks AWS does not publish** (e.g., SOX, ISO 27701, internal corporate controls): there is no Security Hub standard, no Audit Manager framework, and no awslabs conformance pack. Do not fabricate rules. Hand back a one-rule explanatory YAML (`metadata.notes` describes the gap and lists the closest AWS-supported analogues — typically NIST 800-53 Rev 5, AWS FSBP, or a CIS profile) and recommend the user pick one of those frameworks instead.

**Provenance values** (canonical list in `references/aws-official-provenance.json`):

| Value | Strict-AWS-official |
|-------|---------------------|
| `aws-security-hub`, `aws-audit-manager`, `aws-conformance-pack`, `aws-config-managed-rule-doc`, `aws-guard-registry` | ✅ |
| `manual-human` (or legacy `manual`) | ✅ |
| `manual-model-synthesised` | ❌ (opt-in via `--allow-model-synthesis`) |
| `third-party-prowler`, `third-party-trivy` | ❌ |
| `unknown` | ❌ |

Use the AWS-official value that best matches *where the field's content actually came from*. Don't tag a field `aws-conformance-pack` if the value was hand-derived from the Config developer guide — use `aws-config-managed-rule-doc`. Don't tag synthesis as `aws-conformance-pack` to "look more official" — it sets up an auditor for a bad time.

### 5. Validate and hand back

By the time you reach this step, Phase 4 should already have driven the file to `READY`. Re-run validators as a final check, then report.

```bash
python3 scripts/validate_yaml.py policy-research/<slug>-<v>.yaml                                            # exit must be 0
python3 scripts/validate_yaml.py policy-research/<slug>-<v>.yaml --strict-aws-official --allow-model-synthesis  # exit 0 if any field is manual-model-synthesised
python3 scripts/validate_yaml.py policy-research/<slug>-<v>.yaml --strict-aws-official                       # exit 0 if every field is aws-* or manual-human (audit-grade)
python3 scripts/summarize_yaml.py policy-research/<slug>-<v>.yaml                                            # status: READY
```

Hand back to the user with these specific items:

- **File path**
- **Framework + version**
- **Rule count**
- **Validator outcome**: `validate_yaml.py` exits 0 (yes/no). `--strict-aws-official` exits 0 (yes/no, separated from `--allow-model-synthesis` so the auditor knows whether any field is model-synthesis).
- **`summarize_yaml.py` status**: `READY` or `NOT READY`. If `NOT READY`, surface why and what would clear it (extend snapshot? Pass B for which custom rule? Recall a Phase 2c with creds?). Don't hand back a `NOT READY` deliverable silently.
- **Provenance breakdown**: % of fields tagged `aws-*` strict-mode-passing, % `manual-human`, % `manual-model-synthesised`, % `third-party-*` (must be 0 in audit-grade runs).
- **Gap list**: rules where any required field is null/empty/TODO. Empty list is the goal.

## Common workflow shapes

The default workflow is "research one whole framework, produce one YAML". Three other shapes come up often enough to call out:

### Cross-framework merge (one YAML covering N frameworks)

When the user wants a single YAML that satisfies two or more frameworks, run the workflow per-framework and merge the outputs. `merge_yaml.py` handles this end-to-end — including the case where rules from different frameworks reference the same AWS Config managed rule (e.g., `S3_BUCKET_VERSIONING_ENABLED` appears in both CIS and HIPAA). Those collide on `rule.id` and merge into a single rule with `related_controls` cross-references; provenance for each field is preserved per side.

```bash
python3 scripts/parse_conformance_pack.py <cis-pack-url> --framework "CIS ..." --version "1.4" --output policy-research/cis.yaml
python3 scripts/bulk_enrich.py --yaml policy-research/cis.yaml --require-zero-todos
python3 scripts/parse_conformance_pack.py <hipaa-pack-url> --framework "HIPAA ..." --version "(current)" --output policy-research/hipaa.yaml
python3 scripts/bulk_enrich.py --yaml policy-research/hipaa.yaml --require-zero-todos
python3 scripts/merge_yaml.py --primary policy-research/cis.yaml --secondary policy-research/hipaa.yaml --output policy-research/cis-and-hipaa.yaml
python3 scripts/validate_yaml.py policy-research/cis-and-hipaa.yaml          # must exit 0
python3 scripts/summarize_yaml.py policy-research/cis-and-hipaa.yaml         # READY
```

You do **not** need to manually re-prefix `framework_control.id` values before merging — `merge_yaml.py` falls back to `rule.id` when `framework_control.id` is missing or a `TODO:` placeholder, so cross-framework merges work without hand-edits.

### Single-control / minimal-scope research

When the user wants just one rule (e.g., "enforce IMDSv2") rather than a full framework, skip the conformance pack:

```bash
python3 scripts/init_yaml.py --framework "AWS Config managed rule" --version "single-control" \
  --source "https://docs.aws.amazon.com/config/latest/developerguide/ec2-imdsv2-check.html" \
  --output policy-research/imdsv2-only.yaml
# Hand-add a single rule entry with source.identifier=EC2_IMDSV2_CHECK and the required scaffolding;
# bulk_enrich will fill the rest from the snapshot.
python3 scripts/bulk_enrich.py --yaml policy-research/imdsv2-only.yaml --require-zero-todos
python3 scripts/validate_yaml.py policy-research/imdsv2-only.yaml
```

### Scope-narrowed research (e.g., IAM-only slice of CIS)

For "give me the IAM controls from CIS v1.4", run the full pack through Phase 2/4 and then filter:

```bash
python3 scripts/parse_conformance_pack.py <cis-pack-url> --framework "CIS ..." --version "1.4" --output /tmp/cis-full.yaml
python3 scripts/bulk_enrich.py --yaml /tmp/cis-full.yaml --require-zero-todos
# Now filter to IAM-only and add metadata.scope:
python3 - <<'PY'
import yaml
d = yaml.safe_load(open("/tmp/cis-full.yaml"))
d["metadata"]["scope"] = "iam"
d["metadata"]["framework"]["scope"] = "iam"
d["rules"] = [r for r in d["rules"] if (r.get("service") or "").lower() == "iam"]
yaml.safe_dump(d, open("policy-research/cis-iam-scoped.yaml", "w"), sort_keys=False)
PY
python3 scripts/validate_yaml.py policy-research/cis-iam-scoped.yaml
```

The full enrichment runs once on the entire pack; the filter is a deterministic post-step. Rules that don't fit the user's scope drop out cleanly without re-running enrichment.

### Snapshot extension during a run

If `bulk_enrich.py --require-zero-todos` reports rules missing from `references/managed-rules-metadata.json`, extend the bundled snapshot in place:

```bash
python3 scripts/refresh_managed_rules_metadata.py --rule-ids RULE_A,RULE_B --merge
python3 scripts/bulk_enrich.py --yaml policy-research/<file>.yaml --require-zero-todos
```

This mutates the bundled `references/managed-rules-metadata.json`. That is intentional and the documented workflow — the snapshot is the single source of truth and grows as the skill encounters new rules. Multiple concurrent runs extending the snapshot is safe; `--merge` is idempotent and additive.

## Common pitfalls

0. **Handing back a YAML with TODO placeholders.** A `NOT READY` deliverable is not a deliverable. The skill's whole purpose is producing audit-defensible policy YAML — TODOs leak straight through to AWS Config rule generation, where they fail at deploy time or, worse, get hand-edited inconsistently across services. **Phase 4 (`bulk_enrich.py` + manual cleanup for custom rules) is mandatory.** If `bulk_enrich.py --require-zero-todos` exits non-zero, fix the snapshot or the custom rule definitions before reporting back.

   *What "TODO" means in this skill*: only `TODO:` strings inside **required** fields (per `validate_yaml.py`'s required-paths list) count as deliverable gaps. `TODO:` strings in optional / scaffolding fields (`framework_control.id`, `framework_control.title`, `test_cases[].name`, `test_cases[].input.resource_type`, `remediation.terraform_snippet`, `remediation.aws_cli_snippet`, `remediation.console_steps`) are intentional placeholders the validator and `summarize_yaml.py` ignore. A YAML with a clean `validate_yaml.py` exit and `Status: READY` from `summarize_yaml.py` is production-ready even if `grep TODO` shows residual hits — those are the optional-field placeholders, not gaps.

1. **"Creds exist therefore the service is enabled."** A successful `aws sts get-caller-identity` does not imply Security Hub or Audit Manager is enabled in the account. Always run the Phase-1 environment preflight before deciding which mode to use. Security Hub returns `InvalidAccessException` on `get_enabled_standards` until the account onboards; Audit Manager returns `AccessDeniedException: Please complete AWS Audit Manager setup` until you complete its setup wizard. **Both have AWS-official workarounds before Prowler is on the table** — for Security Hub, use `fetch_security_hub_controls.py --unsubscribed`; for Audit Manager, fall back to the conformance pack.
2. **Empty `RelatedRequirements` in `--unsubscribed` mode.** The catalogue API does not populate cross-framework references. Without `references/sh-control-to-config-rule.json` the curated crosswalk, `enrich_yaml.py` matches zero rules. If you see `matched 0/N`, confirm `--no-crosswalk` wasn't passed and that the bundled crosswalk has entries for the controls in your standard. If the standard's controls are mostly unmapped, run `scripts/refresh_sh_control_crosswalk.py` to extend it.
3. **Validator rejects pseudo-resource-types.** Conformance packs sometimes use synthetic types like `AWS::::Account` or `AWS::IAM::AccountPasswordPolicy`. These are listed in `references/aws-config-pseudo-types.txt` and accepted by `validate_yaml.py`. If you see a pseudo-type rejection, add it to the file rather than rewriting the rule.
4. **Treating Prowler as AWS-official.** Prowler is community open-source. If the user has audit requirements, run `validate_yaml.py --strict-aws-official` and treat any non-zero error count as a hard stop.
5. **Inventing managed rule identifiers.** `validate_yaml.py` flags identifiers not in `references/managed-rules.txt`. The error message lists three actions: fix a typo, demote to `aws-config-custom-rule`, or refresh the snapshot. Pick deliberately — refreshing the snapshot is the right action when AWS has shipped a new rule since the snapshot was generated. **Do not hand back a YAML that asserts an unknown identifier is `aws-config-managed-rule` "so the validator will tell the user about it".** A non-validating YAML is not a deliverable — downstream policy generators will trust the `source.type` field and emit broken AWS Config rule code, or worse, the YAML will be rubber-stamped through review because it "looks fine". When you cannot resolve the identifier from the snapshot, default to (b): set `source.type: aws-config-custom-rule`, leave `source.identifier` unchanged, and explain the demotion in `metadata.notes` plus the rule's own `provenance` block. The user can then choose to fix the typo or implement the custom rule themselves; either way they get a YAML that validates.
6. **Citing one URL only.** Cite the controls reference page **and** the managed rule developer guide page — both authoritative for different facets.
7. **Ignoring Guard registry test fixtures.** They're real PASS/FAIL CFN snippets from AWS — don't write synthetic test cases when AWS already published them.

## References

- `references/yaml-schema.md` — field-by-field schema, including the `provenance` block and a complete worked example.
- `references/example-rules.yaml` — five-rule CIS S3 worked example with mixed provenance, useful as a reference for the model when producing larger outputs.
- `references/aws-sources.md` — curated AWS documentation entry points and the canonical GitHub repos for AWS-official content.
- `references/aws-official-provenance.json` — canonical list of provenance values and which pass `--strict-aws-official`.
- `references/aws-domain-allowlist.txt` — AWS-owned domains for URL-allowlist validation under strict mode.
- `references/managed-rules.txt` — bundled AWS Config managed rule identifiers (used by validator). Refresh with `scripts/refresh_managed_rules.py`.
- `references/cfn-resource-types.txt` — bundled CFN resource type names (used by validator). Refresh with `scripts/refresh_cfn_types.py`.
- `references/aws-config-pseudo-types.txt` — synthetic Config-only resource types accepted by the validator.
- `references/legacy-identifier-remap.json` — old → canonical AWS Config managed-rule identifier mappings for stale conformance packs.
- `references/legacy-cfn-type-remap.json` — old → canonical CFN resource type names.
- `references/sh-control-to-config-rule.json` — curated Security Hub `control_id → AWS Config rule kebab` crosswalk used by `enrich_yaml.py` Strategy 0. Refresh with `scripts/refresh_sh_control_crosswalk.py`.
- `references/managed-rules-metadata.json` — bundled snapshot of AWS Config managed-rule metadata (severity, condition, remediation, etc.) consumed by `bulk_enrich.py`. Refresh with `scripts/refresh_managed_rules_metadata.py`. This is the SINGLE SOURCE OF TRUTH for managed-rule field content — do not hand-edit individual rule fields in the YAML; extend the snapshot and re-enrich.
- `references/conformance-pack-index.md` — curated framework-name → exact GitHub filename map for `awslabs/aws-config-rules` conformance packs. The actual filenames are inconsistent (`v` prefix sometimes, `Level 1/2` suffix sometimes, etc.); use this map instead of guessing.

For previous-iteration outputs and eval artifacts, see the sibling `tf-research-policy-aws-workspace/` directory at the parent skill root — useful when debugging regressions or comparing today's output against earlier runs.
