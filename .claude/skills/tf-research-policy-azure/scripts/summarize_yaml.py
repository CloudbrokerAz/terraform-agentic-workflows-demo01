#!/usr/bin/env python3
"""Summarize a tf-research-policy-azure YAML: rule/gap counts, severity,
service and effect breakdown, provenance mix, and a READY / NOT READY
verdict (READY = zero required-field gaps)."""
from __future__ import annotations

import argparse
import collections
import sys

from _common import REQUIRED_PATHS, get_path, is_gap, load_yaml


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("yaml")
    args = ap.parse_args()
    doc = load_yaml(args.yaml)
    rules = doc.get("rules", []) or []
    md = doc.get("metadata", {})
    fw = md.get("framework", {})

    sev = collections.Counter()
    svc = collections.Counter()
    eff = collections.Counter()
    prov = collections.Counter()
    gap_rules = []
    for i, r in enumerate(rules):
        sev[r.get("severity") or "—"] += 1
        svc[r.get("service") or "—"] += 1
        eff[(r.get("source") or {}).get("effect") or "—"] += 1
        for v in (r.get("provenance") or {}).values():
            for vv in (v if isinstance(v, list) else [v]):
                prov[vv] += 1
        miss = [p for p in REQUIRED_PATHS if is_gap(get_path(r, p))]
        if miss:
            gap_rules.append((r.get("id", f"rule[{i}]"), miss))

    print(f"Framework : {fw.get('name','?')} {fw.get('version','')}"
          f"{' (scope='+fw['scope']+')' if fw.get('scope') else ''}")
    print(f"Rules     : {len(rules)}")
    print(f"Severity  : "
          + ", ".join(f"{k}={v}" for k, v in sev.most_common()))
    print(f"Services  : "
          + ", ".join(f"{k}={v}" for k, v in svc.most_common(12)))
    print(f"Effects   : "
          + ", ".join(f"{k}={v}" for k, v in eff.most_common()))

    strict = {"azure-policy-builtin", "azure-policy-initiative",
              "azure-policy-metadata", "defender-regulatory-compliance",
              "mcsb", "microsoft-learn", "manual-human", "manual"}
    tot = sum(prov.values()) or 1
    ms = sum(v for k, v in prov.items() if k in strict)
    syn = prov.get("manual-model-synthesised", 0)
    tp = sum(v for k, v in prov.items() if str(k).startswith("third-party"))
    print(f"Provenance: ms-official={ms/tot*100:.0f}% "
          f"model-synth={syn/tot*100:.0f}% third-party={tp/tot*100:.0f}% "
          f"(n={sum(prov.values())} field-tags)")

    if gap_rules:
        print(f"\nGaps      : {len(gap_rules)} rule(s) with required gaps")
        for rid, miss in gap_rules[:15]:
            print(f"  {rid}: {', '.join(miss)}")
        if len(gap_rules) > 15:
            print(f"  ... and {len(gap_rules)-15} more")
        print("\nStatus: NOT READY")
        return 1
    print("\nStatus: READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
