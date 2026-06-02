#!/usr/bin/env python3
"""Validate a tf-research-policy-azure YAML.

Checks: schema/required fields, policy GUID + ARM id format, effect/mode/
severity/source.type enums, ARM resource-type membership, reference URL
host allowlist, and (with --strict-ms-official) per-field provenance.

Exit 0 = valid. Non-zero = do not hand back.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from urllib.parse import urlparse

from _common import (EFFECTS, GUID_RE, POLICY_DEF_ID_RE, REF, REQUIRED_PATHS,
                     SEVERITIES, SOURCE_TYPES, get_path, is_gap, load_yaml,
                     load_provenance_table)


def load_resource_types() -> set[str]:
    p = os.path.join(REF, "arm-resource-types.txt")
    out: set[str] = set()
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(line.lower())
    return out


def load_allowlist() -> list[str]:
    p = os.path.join(REF, "ms-domain-allowlist.txt")
    out: list[str] = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line.lower())
    return out


def host_allowed(url: str, allow: list[str]) -> bool:
    try:
        u = urlparse(url)
        host = (u.netloc or "").lower()
        full = host + u.path.lower()
    except Exception:  # noqa: BLE001
        return False
    for a in allow:
        if "/" in a:                       # host+path-prefix entry
            if full.startswith(a):
                return True
        elif host == a or host.endswith("." + a):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("yaml")
    ap.add_argument("--strict-ms-official", action="store_true")
    ap.add_argument("--allow-model-synthesis", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="treat unknown ARM resource types as errors")
    ap.add_argument("--add-resource-type",
                    help="append a type to arm-resource-types.txt and exit")
    args = ap.parse_args()

    if args.add_resource_type:
        with open(os.path.join(REF, "arm-resource-types.txt"), "a",
                  encoding="utf-8") as fh:
            fh.write(args.add_resource_type.strip() + "\n")
        print(f"Added {args.add_resource_type}")
        return 0

    doc = load_yaml(args.yaml)
    errors: list[str] = []
    warnings: list[str] = []

    md = doc.get("metadata", {})
    for f in ("framework", "source", "generated_by", "generated_at"):
        if not md.get(f):
            errors.append(f"metadata.{f} missing")
    if (md.get("framework") or {}).get("name") in (None, ""):
        errors.append("metadata.framework.name missing")

    rtypes = load_resource_types()
    allow = load_allowlist()
    prov_table = load_provenance_table()
    strict_ok = {k for k, v in prov_table.items() if v.get("strict")}
    if args.allow_model_synthesis:
        strict_ok.add("manual-model-synthesised")

    rules = doc.get("rules", [])
    if not isinstance(rules, list):
        errors.append("rules must be a list")
        rules = []

    ids: set[str] = set()
    for i, r in enumerate(rules):
        tag = f"rule[{i}] {r.get('id','?')}"
        for p in REQUIRED_PATHS:
            if is_gap(get_path(r, p)):
                errors.append(f"{tag}: required '{p}' missing/TODO/empty")
        rid = r.get("id", "")
        if rid in ids:
            errors.append(f"{tag}: duplicate id")
        ids.add(rid)

        src = r.get("source", {}) or {}
        st = src.get("type")
        if st and st not in SOURCE_TYPES:
            errors.append(f"{tag}: source.type '{st}' invalid")
        pdn = src.get("policy_definition_name", "")
        if pdn and not is_gap(pdn) and not GUID_RE.match(str(pdn)):
            if st in ("azure-policy-builtin", "defender-assessment"):
                errors.append(f"{tag}: source.policy_definition_name "
                              f"'{pdn}' is not a GUID (built-ins are GUIDs; "
                              f"demote to azure-policy-custom if bespoke)")
            else:
                warnings.append(f"{tag}: policy_definition_name not a GUID "
                                f"(ok for {st})")
        pid = src.get("policy_definition_id")
        if pid and not is_gap(pid) and not POLICY_DEF_ID_RE.match(str(pid)):
            errors.append(f"{tag}: source.policy_definition_id malformed "
                          f"('{pid}')")
        eff = src.get("effect")
        if eff and not is_gap(eff) and eff not in EFFECTS:
            errors.append(f"{tag}: source.effect '{eff}' not a valid Azure "
                          f"Policy effect")
        sev = r.get("severity")
        if sev and not is_gap(sev) and sev not in SEVERITIES:
            errors.append(f"{tag}: severity '{sev}' invalid")

        for rt in (r.get("resource_types") or []):
            if not isinstance(rt, str) or is_gap(rt):
                continue
            key2 = "/".join(rt.lower().split("/")[:2])
            if rt.lower() not in rtypes and key2 not in rtypes:
                msg = (f"{tag}: resource_type '{rt}' not in "
                       f"arm-resource-types.txt (add via "
                       f"--add-resource-type or `az provider list`)")
                (errors if args.strict else warnings).append(msg)

        refs = r.get("references")
        if refs is not None and not isinstance(refs, list):
            errors.append(f"{tag}: references must be a list of "
                          f"{{title,url}} maps")
            refs = []
        for ref in (refs or []):
            if not isinstance(ref, dict):
                errors.append(f"{tag}: references[] item must be a map with "
                              f"title+url (got {type(ref).__name__})")
                continue
            url = str(ref.get("url", ""))
            if args.strict_ms_official and url and not host_allowed(
                    url, allow):
                errors.append(f"{tag}: reference URL host not in "
                              f"ms-domain-allowlist.txt: {url}")

        if args.strict_ms_official:
            prov = r.get("provenance", {}) or {}
            for k, v in prov.items():
                vals = v if isinstance(v, list) else [v]
                for val in vals:
                    if val not in strict_ok:
                        errors.append(f"{tag}: provenance '{k}={val}' fails "
                                      f"--strict-ms-official")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(rules)} rule(s): {len(errors)} error(s), "
          f"{len(warnings)} warning(s).")
    if errors:
        print("NOT VALID — do not hand back.")
        return 1
    print("VALID" + (" (strict-ms-official)" if args.strict_ms_official
                      else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
