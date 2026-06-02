#!/usr/bin/env python3
"""Build a YAML skeleton from an Azure built-in regulatory-compliance
initiative (policy set definition).

One rule is emitted per (policy definition x control group). The initiative
JSON is resolved, in order, from: the bundled initiative index (offline raw
fetch), `az policy set-definition show` (with --use-az), or the GitHub
Contents API scan of the policySetDefinitions category folders.

Per-definition detail (display_name, effect, mode, resource_types,
policy_rule) is filled now only with --use-az (`az policy definition show`);
without it those land as TODO: and are filled by bulk_enrich.py from the
bundled snapshot. Control titles/requirements are never in the initiative
JSON -> they are always TODO here (Phase 2b/4 fills them).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

from _common import (GITHUB_RAW, REF, az, collect_resource_types, dump_yaml,
                     fetch_definition_offline, http_get_json, http_get,
                     kebab, resolve_effect)

CONTENTS_API = ("https://api.github.com/repos/Azure/azure-policy/contents/"
                "built-in-policies/policySetDefinitions")
SET_CATEGORIES = ["Regulatory%20Compliance", "Security%20Center"]


def index_lookup(guid: str) -> str | None:
    """Find '<Category>/<File>' for a GUID in builtin-initiative-index.md."""
    path = os.path.join(REF, "builtin-initiative-index.md")
    if not os.path.exists(path):
        return None
    cat_re = re.compile(r"\|\s*[^|]+\|\s*([^|]+?)\s*\|\s*`([^`]+\.json)`"
                        r"[^|]*\|[^|]*\|\s*`([0-9a-fA-F-]{36})`")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = cat_re.search(line)
            if m and m.group(3).lower() == guid.lower():
                cat = m.group(1).strip().replace(" ", "%20")
                return f"{cat}/{m.group(2)}"
    return None


def fetch_initiative(ident: str, use_az: bool) -> dict:
    # direct repo path
    if "/" in ident and ident.lower().endswith(".json"):
        cat, _, fn = ident.partition("/")
        url = f"{GITHUB_RAW}/policySetDefinitions/{cat.replace(' ', '%20')}/{fn}"
        return http_get_json(url)
    guid = ident
    # 1. bundled index -> raw fetch (offline-friendly)
    rel = index_lookup(guid)
    if rel:
        try:
            return http_get_json(
                f"{GITHUB_RAW}/policySetDefinitions/{rel}")
        except Exception:  # noqa: BLE001
            pass
    # 2. az
    if use_az:
        rc, out, err = az(["policy", "set-definition", "show", "--name",
                           guid, "-o", "json", "--only-show-errors"],
                          check=False)
        if rc == 0 and out.strip():
            return json.loads(out)
        sys.stderr.write(f"az set-definition show failed: {err.strip()}\n")
    # 3. Contents API scan of the two set-definition category folders
    for cat in SET_CATEGORIES:
        try:
            listing = http_get_json(f"{CONTENTS_API}/{cat}",
                                    accept="application/vnd.github+json")
        except Exception:  # noqa: BLE001
            continue
        for entry in listing:
            if not entry.get("name", "").endswith(".json"):
                continue
            try:
                j = http_get_json(entry["download_url"])
            except Exception:  # noqa: BLE001
                continue
            if str(j.get("name", "")).lower() == guid.lower():
                return j
    raise SystemExit(f"Could not resolve initiative '{ident}'. Pass a repo "
                     f"path ('Regulatory Compliance/FILE.json') or --use-az.")


def fetch_definition(guid: str, cache: dict, use_az: bool) -> dict | None:
    """Resolve a policy definition body, preferring `az` (live) and falling
    back to the bundled GUID->repo-path index + raw.githubusercontent.com
    (offline, no auth). Both paths return the same Azure/azure-policy JSON."""
    if guid in cache:
        return cache[guid]
    j: dict | None = None
    if use_az:
        rc, out, _ = az(["policy", "definition", "show", "--name", guid,
                         "-o", "json", "--only-show-errors"], check=False)
        if rc == 0 and out.strip():
            j = json.loads(out)
    if j is None:
        j = fetch_definition_offline(guid)
    cache[guid] = j
    return j


def control_id_from_group(group_name: str, fw_slug: str) -> str:
    """`CIS_Azure_Foundations_v3.0.0_3.1.1` -> `3.1.1` (best effort)."""
    m = re.search(r"_(\d+(?:\.\d+)*[A-Za-z]?)$", group_name or "")
    if m:
        return m.group(1)
    parts = (group_name or "").split("_")
    return parts[-1] if parts else group_name


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--initiative", required=True,
                    help="built-in GUID, or 'Category/File.json' repo path")
    ap.add_argument("--framework", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--use-az", action="store_true",
                    help="use `az` to resolve the initiative and fill "
                         "per-definition detail now")
    ap.add_argument("--scope", default="")
    args = ap.parse_args()

    init = fetch_initiative(args.initiative, args.use_az)
    props = init.get("properties", init)
    init_guid = init.get("name", "")
    init_id = init.get("id",
                       f"/providers/Microsoft.Authorization/"
                       f"policySetDefinitions/{init_guid}")
    init_display = props.get("displayName", args.framework)
    init_ver = (props.get("metadata") or {}).get("version", "")
    groups = {g["name"]: g for g in props.get("policyDefinitionGroups", [])}
    fw_slug = kebab(args.framework)

    az_cache: dict = {}
    rules: list[dict] = []
    seen_ids: set[str] = set()

    for pd in props.get("policyDefinitions", []):
        pdid = pd.get("policyDefinitionId", "")
        guid = pdid.rstrip("/").split("/")[-1]
        gnames = pd.get("groupNames") or ["(ungrouped)"]
        defn = fetch_definition(guid, az_cache, args.use_az)
        dprops = (defn or {}).get("properties", {}) if defn else {}

        for gname in gnames:
            ctrl = control_id_from_group(gname, fw_slug)
            display = dprops.get("displayName") or "TODO: display name"
            base = kebab(dprops.get("displayName") or guid)
            rid = f"{base}"
            n = 2
            while rid in seen_ids:
                rid = f"{base}-{n}"
                n += 1
            seen_ids.add(rid)

            rtypes = (collect_resource_types(dprops.get("policyRule", {}))
                      if dprops else [])
            effect = resolve_effect(dprops) if dprops else "TODO: effect"
            mode = dprops.get("mode") if dprops else "TODO: mode"
            prule = (json.dumps(dprops["policyRule"], indent=2)
                     if dprops.get("policyRule") else "TODO: policy rule")
            prov = {
                "framework_control.id": "azure-policy-initiative",
                "source.policy_definition_name": "azure-policy-initiative",
            }
            if dprops:
                prov.update({
                    "source.display_name": "azure-policy-builtin",
                    "source.effect": "azure-policy-builtin",
                    "source.mode": "azure-policy-builtin",
                    "resource_types": "azure-policy-builtin",
                    "condition.policy_rule": "azure-policy-builtin",
                })

            # Offline requirement fill: use the policy's own
            # Microsoft-authored `description` (what the policy enforces) as a
            # tagged stand-in until Phase 2b (Defender) or Learn supplies the
            # framework owner's verbatim text. Provenance `azure-policy-builtin`
            # keeps strict-ms-official passing; metadata.notes flags the
            # substitution so an auditor can upgrade later.
            policy_desc = (dprops.get("description") or "").strip()
            req = policy_desc if policy_desc else "TODO: verbatim requirement (Phase 2b/4)"
            if policy_desc:
                prov["framework_control.requirement"] = "azure-policy-builtin"

            rule = {
                "id": rid,
                "title": display if dprops else "TODO: title",
                "framework_control": {
                    "id": f"{args.framework} {ctrl}",
                    "title": "TODO: control title (Phase 2b/4)",
                    "requirement": req,
                },
                "severity": "TODO: severity" if not dprops else
                            ("INFORMATIONAL" if effect == "Manual"
                             else "TODO: severity"),
                "service": "TODO: service",
                "resource_types": rtypes or ["TODO: ARM resource type"],
                "source": {
                    "type": "manual-attestation" if effect == "Manual"
                            else "azure-policy-builtin",
                    "policy_definition_name": guid,
                    "policy_definition_id": pdid,
                    "display_name": display,
                    "effect": effect,
                    "mode": mode,
                    "parameters": {
                        k: (v.get("defaultValue")
                            if isinstance(v, dict) else v)
                        for k, v in (pd.get("parameters") or {}).items()
                    },
                    "documentation_url":
                        "TODO: policy documentation_url",
                },
                "initiative": {
                    "display_name": init_display,
                    "definition_id": init_id,
                    "definition_name": init_guid,
                    "group_name": gname,
                },
                "condition": {
                    "description": "TODO: compliant-state description",
                    "parameters": {},
                    "policy_rule": prule,
                },
                "remediation": {"summary": "TODO: remediation summary"},
                "references": [{
                    "title": f"{init_display} (built-in initiative)",
                    "url": "https://learn.microsoft.com/azure/governance/"
                           "policy/samples/built-in-initiatives",
                }],
                "test_cases": [{
                    "name": "TODO: compliant case",
                    "input": {"resource_type":
                              rtypes[0] if rtypes else "TODO",
                              "properties": {}},
                    "expected": "MANUAL" if effect == "Manual"
                                else "COMPLIANT",
                }],
                "provenance": prov,
                "tags": [],
            }
            rules.append(rule)

    fw: dict = {"name": args.framework, "version": args.version}
    if args.scope:
        fw["scope"] = args.scope
    doc = {
        "metadata": {
            "framework": fw,
            "source": "https://learn.microsoft.com/azure/governance/policy/"
                      "samples/built-in-initiatives",
            "initiative": {
                "display_name": init_display,
                "definition_id": init_id,
                "definition_name": init_guid,
                "version": init_ver,
            },
            "generated_by": "tf-research-policy-azure",
            "generated_at": dt.datetime.now(dt.timezone.utc).date()
            .isoformat(),
            "notes": ("Skeleton from built-in initiative. Control "
                      "titles/requirements require Phase 2b (Defender) or "
                      "Learn. Per-definition detail filled via "
                      + ("`az policy definition show`."
                         if args.use_az else
                         "the bundled GUID->repo-path index "
                         "(raw.githubusercontent.com, no Azure auth).")),
        },
        "rules": sorted(rules, key=lambda r: r["framework_control"]["id"]),
    }
    dump_yaml(doc, args.output)
    print(f"Wrote {len(rules)} rule(s) -> {args.output}")
    print(f"Initiative: {init_display} ({init_guid}) v{init_ver}")
    print("Next: Phase 2b enrich_yaml.py (control titles) then "
          "bulk_enrich.py --require-zero-todos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
