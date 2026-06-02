"""Shared helpers for tf-research-policy-azure scripts.

Only mandatory dependency: PyYAML. Network access uses urllib (stdlib);
Azure API access shells out to `az` (the caller's existing `az login`).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required: pip install pyyaml\n")
    raise

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "references")

GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
POLICY_DEF_ID_RE = re.compile(
    r"^/providers/Microsoft\.Authorization/policyDefinitions/[0-9a-fA-F-]{36}$")

EFFECTS = {"Audit", "Deny", "AuditIfNotExists", "DeployIfNotExists",
           "Modify", "Append", "Disabled", "Manual", "DenyAction"}
MODES = {"Indexed", "All"}  # plus RP modes like Microsoft.Kubernetes.Data
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}
SOURCE_TYPES = {"azure-policy-builtin", "azure-policy-custom",
                "azure-policy-initiative", "defender-assessment",
                "manual-attestation"}

# Required rule paths. A `TODO:` value or null/empty in any of these is a
# deliverable gap (validate_yaml errors; summarize reports NOT READY).
REQUIRED_PATHS = [
    "id", "title",
    "framework_control.id", "framework_control.requirement",
    "severity", "service", "resource_types",
    "source.type", "source.policy_definition_name", "source.display_name",
    "source.effect", "source.mode", "source.documentation_url",
    "condition.description", "condition.policy_rule",
    "remediation.summary",
    "test_cases", "references",
]
# Optional fields where a TODO: placeholder is intentional, not a gap.
OPTIONAL_TODO_OK = {
    "description", "framework_control.title", "source.policy_definition_id",
    "remediation.terraform_snippet", "remediation.azure_cli_snippet",
    "remediation.bicep_snippet", "remediation.portal_steps",
    "condition.aliases", "tags",
}

GITHUB_RAW = ("https://raw.githubusercontent.com/Azure/azure-policy/master/"
              "built-in-policies")


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def dump_yaml(doc: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True,
                       default_flow_style=False, width=100)


def get_path(obj: dict, dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def is_gap(value: Any) -> bool:
    """A required value counts as a gap if null/empty or a TODO: placeholder."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == "" or value.strip().startswith("TODO:")
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def http_get(url: str, accept: str | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "tf-research-policy-azure",
        **({"Accept": accept} if accept else {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def http_get_json(url: str, accept: str | None = None) -> Any:
    return json.loads(http_get(url, accept=accept).decode("utf-8"))


def az(args: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run `az ...`. Returns (rc, stdout, stderr). Never raises on non-zero
    unless check=True; callers usually want to degrade gracefully."""
    try:
        p = subprocess.run(["az", *args], capture_output=True, text=True,
                            timeout=120)
    except FileNotFoundError:
        return 127, "", "az CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, "", "az call timed out"
    if check and p.returncode != 0:
        raise RuntimeError(f"az {' '.join(args)} failed: {p.stderr.strip()}")
    return p.returncode, p.stdout, p.stderr


def az_rest_get(url: str) -> Any | None:
    """GET an ARM URL via `az rest`. Returns parsed JSON, or None on failure
    (caller decides whether that is fatal)."""
    rc, out, _ = az(["rest", "--method", "get", "--url", url,
                     "--only-show-errors"], check=False)
    if rc != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


_GUID_INDEX_CACHE: dict | None = None


def load_guid_index() -> dict | None:
    """Load the bundled GUID -> repo-path index (offline fetch lookup).
    Returns None if the index isn't present (skill not refreshed yet)."""
    global _GUID_INDEX_CACHE
    if _GUID_INDEX_CACHE is not None:
        return _GUID_INDEX_CACHE
    path = os.path.join(REF, "policy-def-guid-index.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        _GUID_INDEX_CACHE = json.load(fh)
    return _GUID_INDEX_CACHE


def fetch_definition_offline(guid: str) -> dict | None:
    """Resolve a built-in policy definition body by GUID via the bundled
    index + raw.githubusercontent.com. No Azure auth required. Returns the
    full Azure Policy JSON ({id,name,properties}) or None if the GUID is
    absent from the index or the network fetch fails."""
    idx = load_guid_index()
    if not idx:
        return None
    path = idx.get("definitions", {}).get(guid) or idx.get(
        "initiatives", {}).get(guid)
    if not path:
        return None
    url = idx["raw_url_prefix"] + path.replace(" ", "%20")
    try:
        return json.loads(http_get(url))
    except Exception:  # noqa: BLE001
        return None


def load_provenance_table() -> dict:
    with open(os.path.join(REF, "ms-official-provenance.json"),
              encoding="utf-8") as fh:
        return json.load(fh)["values"]


def kebab(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", s) or "rule"


def collect_resource_types(policy_rule: Any) -> list[str]:
    """Recursively pull every concrete value compared against `field: type`
    in a policyRule.if tree. Parameter/alias refs are skipped."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if not isinstance(node, dict):
            return
        if node.get("field") == "type":
            for op in ("equals", "in", "like", "contains"):
                if op in node:
                    val = node[op]
                    vals = val if isinstance(val, list) else [val]
                    for v in vals:
                        if isinstance(v, str) and "/" in v \
                                and not v.startswith("["):
                            found.append(v)
        for key in ("allOf", "anyOf", "not", "if", "then", "details"):
            if key in node:
                walk(node[key])

    walk(policy_rule.get("if") if isinstance(policy_rule, dict) else policy_rule)
    # secondary type for *IfNotExists effects
    then = policy_rule.get("then") if isinstance(policy_rule, dict) else None
    if isinstance(then, dict):
        det = then.get("details")
        if isinstance(det, dict) and isinstance(det.get("type"), str):
            found.append(det["type"])
    # de-dup, preserve order
    seen: set[str] = set()
    return [t for t in found if not (t in seen or seen.add(t))]


def _norm_effect(e: str) -> str:
    """Normalize effect string to the canonical Azure Policy casing
    (Microsoft's own JSON occasionally uses lowercase 'audit' / 'deny')."""
    if not e:
        return "Audit"
    canonical = {x.lower(): x for x in EFFECTS}
    return canonical.get(e.lower(), e)


def resolve_effect(props: dict) -> str:
    """Concrete effect from a policy definition's parameters/policyRule."""
    params = props.get("parameters") or {}
    eff = params.get("effect") or {}
    if isinstance(eff, dict):
        if eff.get("defaultValue"):
            return _norm_effect(str(eff["defaultValue"]))
        allowed = [a for a in (eff.get("allowedValues") or [])
                   if a != "Disabled"]
        if allowed:
            return _norm_effect(str(allowed[0]))
    rule = props.get("policyRule") or {}
    then = rule.get("then") or {}
    e = then.get("effect")
    if isinstance(e, str) and not e.startswith("["):
        return _norm_effect(e)
    return "Audit"
