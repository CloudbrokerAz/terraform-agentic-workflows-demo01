#!/usr/bin/env python3
"""Phase-4 bulk fill from references/builtin-policy-metadata.json + heuristics.

For every rule, fill missing severity, service, condition.description,
remediation.summary, tags, source.documentation_url:
  - exact match on source.policy_definition_name in the snapshot, else
  - derive `service` from the ARM resource-type namespace, and
  - supply deterministic generic severity/description/remediation by effect.
Manual-effect policies get the attestation treatment. Filled fields are
tagged `azure-policy-builtin` (snapshot) or `manual-human` (heuristic).

--refresh GUID[,GUID...]  fetch those definitions via `az` and merge derived
                          metadata into the bundled snapshot (single source
                          of truth; do not hand-edit YAML rule fields).
--require-zero-todos      exit non-zero (listing rule/field) if any required
                          gap remains.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from _common import (REF, az, collect_resource_types, dump_yaml,
                     fetch_definition_offline, is_gap, load_yaml,
                     resolve_effect)

SNAP = os.path.join(REF, "builtin-policy-metadata.json")

GENERIC_REMEDIATION = {
    "Deny":  "Reconfigure the resource so the property the policy checks "
             "satisfies the required value; non-compliant creates/updates "
             "are blocked.",
    "Audit": "Reconfigure the resource so the audited property meets the "
             "required value; audit surfaces non-compliance without "
             "blocking.",
    "AuditIfNotExists": "Ensure the required related resource/configuration "
                        "exists for the target resource.",
    "DeployIfNotExists": "Allow the policy's remediation task to deploy the "
                         "required configuration, or configure it manually.",
    "Modify": "Allow the policy to modify the resource to the compliant "
              "value, or set it explicitly.",
    "Append": "Allow the policy to append the required field, or set it "
              "explicitly.",
    "Manual": "Record a manual attestation that the control is satisfied; "
              "this policy cannot be evaluated automatically.",
}
SEV_BY_EFFECT = {"Deny": "HIGH", "Modify": "MEDIUM", "Append": "LOW",
                 "Audit": "MEDIUM", "AuditIfNotExists": "MEDIUM",
                 "DeployIfNotExists": "MEDIUM", "Manual": "INFORMATIONAL",
                 "Disabled": "LOW"}


def load_snapshot() -> dict:
    with open(SNAP, encoding="utf-8") as fh:
        return json.load(fh)


def refresh(guids: list[str]) -> None:
    """Fetch policy definitions and merge derived metadata into the bundled
    snapshot. Tries `az policy definition show` first (live, authoritative);
    falls back to the bundled GUID->path index + raw.githubusercontent.com
    when `az` is unavailable or the user isn't logged in. Either path yields
    the same authoritative Azure/azure-policy JSON, so the fallback is not a
    quality regression."""
    snap = load_snapshot()
    pol = snap.setdefault("policies", {})
    svc_map = snap.get("service_by_namespace", {})
    added = 0
    used_offline = 0
    for g in guids:
        d: dict | None = None
        rc, out, err = az(["policy", "definition", "show", "--name", g,
                           "-o", "json", "--only-show-errors"], check=False)
        if rc == 0 and out.strip():
            d = json.loads(out)
        else:
            d = fetch_definition_offline(g)
            if d:
                used_offline += 1
        if not d:
            sys.stderr.write(
                f"  {g}: neither `az` nor offline index resolved this GUID "
                f"(az said: {err.strip()[:80]})\n")
            continue
        p = d.get("properties", {})
        rts = collect_resource_types(p.get("policyRule", {}))
        ns = rts[0].split("/")[0] if rts else ""
        pol[g] = {
            "display_name": p.get("displayName", ""),
            "service": svc_map.get(ns, ns.replace("Microsoft.", "").lower()
                                   or "general"),
            "severity": SEV_BY_EFFECT.get(resolve_effect(p), "MEDIUM"),
            "condition_description": p.get("description", "").strip()
            or "See policy rule.",
            "remediation_summary": GENERIC_REMEDIATION.get(
                resolve_effect(p), GENERIC_REMEDIATION["Audit"]),
            "documentation_url": "https://learn.microsoft.com/azure/"
            "governance/policy/samples/built-in-policies",
            "tags": [],
        }
        added += 1
    with open(SNAP, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2)
        fh.write("\n")
    suffix = (f" ({used_offline} via offline GitHub index)"
              if used_offline else "")
    print(f"Snapshot refreshed: +{added}/{len(guids)} policy(ies){suffix}.")


def enrich(path: str, require_zero: bool) -> int:
    snap = load_snapshot()
    pol = snap.get("policies", {})
    svc_map = snap.get("service_by_namespace", {})
    doc = load_yaml(path)
    rules = doc.get("rules", [])

    for r in rules:
        prov = r.setdefault("provenance", {})
        src = r.setdefault("source", {})
        guid = src.get("policy_definition_name", "")
        effect = src.get("effect") if src.get("effect") and not str(
            src.get("effect")).startswith("TODO") else "Audit"
        meta = pol.get(guid, {})

        def fill(field_obj, key, value, prov_key, prov_val):
            if key not in field_obj or is_gap(field_obj.get(key)):
                if value:
                    field_obj[key] = value
                    prov[prov_key] = prov_val

        if meta:
            fill(r, "severity", meta.get("severity"), "severity",
                 "azure-policy-builtin")
            fill(r, "service", meta.get("service"), "service",
                 "azure-policy-builtin")
            fill(r, "title", meta.get("display_name"), "title",
                 "azure-policy-builtin")
            cond = r.setdefault("condition", {})
            fill(cond, "description", meta.get("condition_description"),
                 "condition.description", "azure-policy-builtin")
            rem = r.setdefault("remediation", {})
            fill(rem, "summary", meta.get("remediation_summary"),
                 "remediation.summary", "azure-policy-builtin")
            fill(src, "documentation_url", meta.get("documentation_url"),
                 "source.documentation_url", "azure-policy-builtin")
            if is_gap(r.get("tags")) and meta.get("tags"):
                r["tags"] = meta["tags"]
                prov["tags"] = "azure-policy-builtin"

        # Heuristic fallbacks (deterministic; manual-human provenance)
        rts = [t for t in (r.get("resource_types") or [])
               if isinstance(t, str) and "/" in t and not
               t.startswith("TODO")]
        if is_gap(r.get("service")) and rts:
            ns = rts[0].split("/")[0]
            r["service"] = svc_map.get(
                ns, ns.replace("Microsoft.", "").lower() or "general")
            prov["service"] = "manual-human"
        if is_gap(r.get("severity")):
            r["severity"] = SEV_BY_EFFECT.get(effect, "MEDIUM")
            prov["severity"] = "manual-human"
        cond = r.setdefault("condition", {})
        if is_gap(cond.get("description")):
            cond["description"] = ("Manual attestation required."
                                   if effect == "Manual" else
                                   f"The resource must satisfy the policy "
                                   f"rule ({effect}).")
            prov["condition.description"] = "manual-human"
        rem = r.setdefault("remediation", {})
        if is_gap(rem.get("summary")):
            rem["summary"] = GENERIC_REMEDIATION.get(
                effect, GENERIC_REMEDIATION["Audit"])
            prov["remediation.summary"] = "manual-human"
        if is_gap(src.get("documentation_url")):
            src["documentation_url"] = ("https://learn.microsoft.com/azure/"
                                        "governance/policy/samples/"
                                        "built-in-policies")
            prov["source.documentation_url"] = "manual-human"
        if effect == "Manual":
            src.setdefault("type", "manual-attestation")
            if is_gap(r.get("severity")) or r.get("severity", "").startswith(
                    "TODO"):
                r["severity"] = "INFORMATIONAL"

    dump_yaml(doc, path)

    # Gap check on required paths
    from _common import REQUIRED_PATHS, get_path
    gaps: list[str] = []
    for i, r in enumerate(rules):
        for p in REQUIRED_PATHS:
            if is_gap(get_path(r, p)):
                gaps.append(f"  rule[{i}] {r.get('id','?')}: {p}")
    if gaps:
        print(f"{len(gaps)} required gap(s) remain:")
        print("\n".join(gaps[:40]))
        if len(gaps) > 40:
            print(f"  ... and {len(gaps)-40} more")
        print("Fix: snapshot-miss -> `bulk_enrich.py --refresh <GUID,...>` "
              "then re-run; custom policy -> Pass B (hand-write "
              "condition.policy_rule).")
        if require_zero:
            return 1
    else:
        print(f"All required fields filled across {len(rules)} rule(s).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yaml")
    ap.add_argument("--refresh", help="comma-separated GUIDs to fetch+merge "
                    "into the bundled snapshot (needs `az login`)")
    ap.add_argument("--require-zero-todos", action="store_true")
    args = ap.parse_args()
    if args.refresh:
        refresh([g.strip() for g in args.refresh.split(",") if g.strip()])
        if not args.yaml:
            return 0
    if not args.yaml:
        ap.error("--yaml is required (or use --refresh alone)")
    return enrich(args.yaml, args.require_zero_todos)


if __name__ == "__main__":
    sys.exit(main())
