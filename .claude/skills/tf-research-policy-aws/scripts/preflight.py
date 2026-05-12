#!/usr/bin/env python3
"""Phase-1 environment preflight helper.

Single command that probes AWS API access, Security Hub state, and Audit Manager
state, and prints the decision for each subsequent phase. Replaces three separate
`aws` invocations the workflow used to run by hand.

Output is deterministic and human-readable: one line per check + a final
DECISIONS block. No JSON or machine-friendly mode (yet) — the caller is the
operator running the skill, not other tooling.

Usage:
  scripts/preflight.py
  scripts/preflight.py --target-standard cis-aws-foundations-benchmark
  scripts/preflight.py --json    # for downstream automation
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any


def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def check_creds() -> dict[str, Any]:
    if shutil.which("aws") is None:
        return {"ok": False, "reason": "aws CLI not on PATH"}
    rc, out, err = _run(["aws", "sts", "get-caller-identity", "--output", "json"])
    if rc == 0 and out:
        try:
            payload = json.loads(out)
            return {"ok": True, "account": payload.get("Account"), "arn": payload.get("Arn")}
        except json.JSONDecodeError:
            return {"ok": True, "raw": out}
    msg = (err or "no output").splitlines()[0] if (err or out) else "unknown"
    return {"ok": False, "reason": msg}


def check_security_hub(target_arn: str | None = None) -> dict[str, Any]:
    rc, out, err = _run(["aws", "securityhub", "get-enabled-standards", "--output", "json"])
    if rc != 0:
        first = (err or "").splitlines()[:1]
        msg = first[0] if first else "unknown"
        if "InvalidAccessException" in msg or "is not subscribed" in msg.lower():
            return {"mode": "unsubscribed", "reason": "Security Hub catalogue API still works"}
        if "NoCredentials" in msg or "Unable to locate" in msg or "ExpiredToken" in msg:
            return {"mode": "skip", "reason": "no AWS creds"}
        return {"mode": "skip", "reason": msg}
    try:
        standards = json.loads(out).get("StandardsSubscriptions", [])
        names = [s.get("StandardsArn", "").rsplit("/", 1)[0].split("/")[-1] for s in standards]
        target_match = None
        if target_arn:
            for s in standards:
                if target_arn in s.get("StandardsArn", ""):
                    target_match = s
                    break
        return {
            "mode": "subscribed",
            "subscribed_standards": [s.get("StandardsArn") for s in standards],
            "summary": names,
            "target_subscribed": bool(target_match),
        }
    except json.JSONDecodeError:
        return {"mode": "subscribed", "raw": out[:500]}


def check_audit_manager() -> dict[str, Any]:
    rc, out, err = _run([
        "aws", "auditmanager", "list-assessment-frameworks",
        "--framework-type", "Standard", "--output", "json",
    ])
    if rc != 0:
        first = (err or "").splitlines()[:1]
        msg = first[0] if first else "unknown"
        if "AccessDeniedException" in msg or "complete AWS Audit Manager setup" in msg.lower():
            return {"available": False, "reason": "Audit Manager not enabled in this account"}
        if "NoCredentials" in msg or "Unable to locate" in msg or "ExpiredToken" in msg:
            return {"available": False, "reason": "no AWS creds"}
        return {"available": False, "reason": msg}
    try:
        frameworks = json.loads(out).get("frameworkMetadataList", [])
        return {
            "available": True,
            "frameworks": [f.get("name") for f in frameworks],
            "count": len(frameworks),
        }
    except json.JSONDecodeError:
        return {"available": True, "raw": out[:500]}


def decide(creds: dict[str, Any], sh: dict[str, Any], am: dict[str, Any]) -> dict[str, str]:
    """Map the three probe results to per-phase decisions."""
    if not creds["ok"]:
        return {
            "phase_2a_conformance_pack": "use",
            "phase_2b_security_hub": "skip — no creds",
            "phase_2c_audit_manager": "skip — no creds",
            "phase_4_bulk_enrich": "use (snapshot covers managed rules)",
            "summary": "no creds → conformance pack + bulk_enrich; no API enrichment",
        }
    sh_mode = sh.get("mode", "skip")
    am_avail = am.get("available", False)
    return {
        "phase_2a_conformance_pack": "use",
        "phase_2b_security_hub": (
            f"use ({sh_mode} mode)" if sh_mode in ("subscribed", "unsubscribed") else f"skip — {sh.get('reason', 'unknown')}"
        ),
        "phase_2c_audit_manager": (
            "use" if am_avail else f"skip — {am.get('reason', 'unknown')}"
        ),
        "phase_4_bulk_enrich": "use (always; snapshot complements API output)",
        "summary": (
            f"creds OK, security_hub={sh_mode}, audit_manager={'available' if am_avail else 'unavailable'}"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target-standard", default=None,
                    help="Security Hub standard ARN substring (e.g., cis-aws-foundations-benchmark)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    creds = check_creds()
    sh = check_security_hub(args.target_standard) if creds["ok"] else {"mode": "skip", "reason": "no creds"}
    am = check_audit_manager() if creds["ok"] else {"available": False, "reason": "no creds"}
    decisions = decide(creds, sh, am)

    if args.json:
        print(json.dumps({"creds": creds, "security_hub": sh, "audit_manager": am, "decisions": decisions}, indent=2))
        return 0

    print("=== tf-research-policy-aws preflight ===")
    if creds["ok"]:
        account = creds.get("account", "?")
        print(f"AWS creds:       OK (account={account})")
    else:
        print(f"AWS creds:       FAIL ({creds.get('reason', 'unknown')})")
    print(f"Security Hub:    {sh.get('mode', sh.get('reason', '?'))}")
    if "summary" in sh:
        print(f"  standards:     {sh['summary']}")
    if am.get("available"):
        print("Audit Manager:   available")
    else:
        print(f"Audit Manager:   unavailable ({am.get('reason', '?')})")
    print()
    print("=== DECISIONS ===")
    for k, v in decisions.items():
        if k != "summary":
            print(f"  {k}: {v}")
    print(f"\n  → {decisions['summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
