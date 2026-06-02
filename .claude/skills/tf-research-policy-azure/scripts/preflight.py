#!/usr/bin/env python3
"""Phase-1 environment probe for tf-research-policy-azure.

Checks, in one shot, whether the GitHub-repo path (always available) and the
optional Azure API / Defender paths are usable, and prints a per-phase
decision. Never fabricates: an unreachable check prints SKIP with the reason.
"""
from __future__ import annotations

import argparse
import sys

from _common import az, http_get


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target-standard", default="",
                    help="Defender standard slug substring to look for")
    args = ap.parse_args()

    print("=== tf-research-policy-azure preflight ===")

    # GitHub repo path — always the default; only needs outbound HTTPS.
    github_ok = True
    try:
        http_get("https://raw.githubusercontent.com/Azure/azure-policy/"
                 "master/built-in-policies/README.md", timeout=15)
        print("GitHub repo:   OK (Azure/azure-policy reachable)")
    except Exception as exc:  # noqa: BLE001
        github_ok = False
        print(f"GitHub repo:   FAIL ({exc})")

    # az CLI present + logged in
    rc, out, _ = az(["account", "show", "--only-show-errors",
                     "--query", "{sub:id,name:name}", "-o", "json"],
                    check=False)
    az_ok = rc == 0
    if az_ok:
        print(f"Azure CLI:     OK ({out.strip()})")
    elif rc == 127:
        print("Azure CLI:     not installed (GitHub-repo path still works)")
    else:
        print("Azure CLI:     not logged in (run `az login`)")

    # Defender for Cloud regulatory compliance reachability
    defender = "unknown"
    if az_ok:
        rc2, out2, _ = az(
            ["rest", "--method", "get", "--only-show-errors", "--url",
             "https://management.azure.com/subscriptions/"
             "{subscriptionId}/providers/Microsoft.Security/"
             "regulatoryComplianceStandards?api-version=2019-01-01-preview"],
            check=False)
        # az expands {subscriptionId} from the logged-in context
        if rc2 == 0 and '"value"' in out2:
            n = out2.count('"name"')
            defender = "reachable" if n else "empty (Defender not initialized)"
            print(f"Defender RC:   {defender}")
            if args.target_standard and args.target_standard.lower() \
                    not in out2.lower():
                print(f"               (target '{args.target_standard}' not "
                      "in assigned standards; discover with "
                      "fetch_defender_compliance.py --list-standards)")
        else:
            defender = "unreachable"
            print("Defender RC:   unreachable (Defender for Cloud likely off)")

    print("\n=== DECISIONS ===")
    print(f"  phase_2a_builtin_initiative: "
          f"{'use (default, no auth)' if github_ok else 'BLOCKED — fix network'}")
    if defender in ("reachable",):
        print("  phase_2b_defender:           use")
    elif defender.startswith("empty"):
        print("  phase_2b_defender:           skip (not initialized) — fill "
              "control titles from Learn / policyMetadata, NOT third-party")
    else:
        print("  phase_2b_defender:           skip (unreachable) — 2a + Learn")
    print("  phase_4_bulk_enrich:         use (always; snapshot + heuristics)")
    print("  phase_3_third_party:         only if 2a AND 2b both yield nothing")

    return 0 if github_ok else 2


if __name__ == "__main__":
    sys.exit(main())
