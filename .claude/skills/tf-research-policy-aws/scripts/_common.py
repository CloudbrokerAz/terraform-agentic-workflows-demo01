"""Shared utilities for tf-research-policy-aws scripts.

Surface kept deliberately narrow. Add functions here only when they are reused
in three or more scripts AND have a single canonical implementation. Argparse
boilerplate, provenance mutation, and CLI message formatting all live in their
respective scripts because their semantics differ across callers.
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
import urllib.error  # noqa: F401  (re-exported for callers that catch HTTPError)
import urllib.request
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCES = REPO_ROOT / "references"


def is_todo(value: Any) -> bool:
    """True if value is a TODO placeholder string."""
    return isinstance(value, str) and value.strip().startswith("TODO")


def non_todo(value: Any) -> bool:
    """True if value is non-empty and not a TODO placeholder."""
    if value is None or value == "" or value == [] or value == {}:
        return False
    return not is_todo(value)


def kebab(s: str) -> str:
    """Lower-kebab-case slug. ASCII letters and digits only; runs collapse to a single hyphen."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", (s or "")).strip("-").lower()


def screaming_to_kebab(s: str) -> str:
    """Convert SCREAMING_SNAKE_CASE managed-rule identifiers to the kebab form used in catalogue snapshots."""
    return (s or "").replace("_", "-").lower()


def safe_dump_yaml(doc: Any, path: pathlib.Path | None = None) -> str:
    """Write or return a YAML doc with the skill's standard formatting."""
    text = yaml.safe_dump(
        doc, sort_keys=False, width=100, default_flow_style=False, allow_unicode=True
    )
    if path is not None:
        path.write_text(text, encoding="utf-8")
    return text


def _cfn_constructor(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    """Render CloudFormation intrinsic functions (!Ref, !If, !Sub) as plain dicts."""
    name = "Fn::" + tag_suffix if tag_suffix != "Ref" else "Ref"
    if isinstance(node, yaml.ScalarNode):
        return {name: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {name: loader.construct_sequence(node)}
    return {name: loader.construct_mapping(node)}


class CfnLoader(yaml.SafeLoader):
    """YAML loader that preserves CloudFormation intrinsic shorthand (!Ref, !If, !Sub, ...)."""


CfnLoader.add_multi_constructor("!", _cfn_constructor)
CfnLoader.add_multi_constructor("tag:yaml.org,2002:!", _cfn_constructor)


def http_get(url: str, *, accept: str | None = None, timeout: int = 30) -> str:
    """GET a URL with the skill's standard User-Agent. Returns decoded text. Raises urllib.error.HTTPError on non-2xx."""
    headers = {"User-Agent": "tf-research-policy-aws/1"}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def load_text_snapshot(path: pathlib.Path) -> set[str]:
    """Load a one-entry-per-line text snapshot, skipping '#' comments and blanks."""
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def load_json_remap(path: pathlib.Path) -> dict[str, str]:
    """Load a flat-shape JSON remap file, dropping `_`-prefixed metadata keys."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        k: v
        for k, v in raw.items()
        if isinstance(k, str) and isinstance(v, str) and not k.startswith("_")
    }


def snapshot_age_days(path: pathlib.Path) -> int | None:
    """Return age in days from the '# Refreshed: YYYY-MM-DD' header, or None if missing."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines()[:10]:
        m = re.match(r"^#\s*Refreshed:\s*(\d{4}-\d{2}-\d{2})", line.strip())
        if m:
            try:
                ref = _dt.date.fromisoformat(m.group(1))
                return (_dt.date.today() - ref).days
            except ValueError:
                pass
    return None
