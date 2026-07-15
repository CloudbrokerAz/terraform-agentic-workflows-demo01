#!/usr/bin/env python3
"""Extract per-phase timings from a stamped transcript (lib/stamp_lines.py output).

Primary source: Task tool_use events that launch tf-* subagents, paired with
their tool_result events by tool_use id. The workflow phases map from the
subagent role suffix (research/design/test-writer/developer/validator).

Fallback (--specs-dir, used when the transcript yields nothing): file mtimes of
the specs/{FEATURE}/ artifacts relative to the run start.

Output (stdout): {"phases": [{"name", "agent", "start_offset_s", "duration_s", "source"}]}
"""
import argparse
import glob
import json
import os
import re
import sys

ROLE_SUFFIXES = ("research", "design", "test-writer", "developer", "validator")


def phase_for_agent(agent):  # -> str or None (annotation-free for python < 3.10)
    for suffix in ROLE_SUFFIXES:
        if agent.endswith(suffix):
            return suffix
    return None


def iter_events(path: str):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield rec.get("ts"), rec.get("event") or rec


def content_blocks(event: dict):
    message = event.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        yield from (b for b in content if isinstance(b, dict))


def phases_from_transcript(path: str):
    starts = {}   # tool_use_id -> (ts, agent)
    phases = []
    run_start = None
    for ts, event in iter_events(path):
        if ts is None or not isinstance(event, dict):
            continue
        if run_start is None:
            run_start = ts
        for block in content_blocks(event):
            if block.get("type") == "tool_use" and block.get("name") == "Task":
                agent = str((block.get("input") or {}).get("subagent_type", ""))
                if agent.startswith("tf-"):
                    starts[block.get("id")] = (ts, agent)
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in starts:
                start_ts, agent = starts.pop(block["tool_use_id"])
                phases.append({
                    "name": phase_for_agent(agent) or agent,
                    "agent": agent,
                    "start_offset_s": round(start_ts - run_start, 1),
                    "duration_s": round(ts - start_ts, 1),
                    "source": "transcript",
                })
    # Unclosed Task spans (run killed mid-phase) still carry signal.
    for tool_id, (start_ts, agent) in starts.items():
        phases.append({
            "name": phase_for_agent(agent) or agent,
            "agent": agent,
            "start_offset_s": round(start_ts - run_start, 1),
            "duration_s": None,
            "source": "transcript-unclosed",
        })
    phases.sort(key=lambda p: p["start_offset_s"])
    return phases


ARTIFACT_PHASES = [
    ("research", "research-*.md"),
    ("design", "*design*.md"),
    ("validator", "reports/*"),
]


def phases_from_mtimes(specs_dir: str, run_start: float):
    phases = []
    for name, pattern in ARTIFACT_PHASES:
        paths = glob.glob(os.path.join(specs_dir, "*", pattern))
        if not paths:
            continue
        mtime = max(os.path.getmtime(p) for p in paths)
        offset = mtime - run_start
        if offset < 0:
            continue
        phases.append({
            "name": name,
            "agent": None,
            "start_offset_s": None,
            "duration_s": None,
            "completed_offset_s": round(offset, 1),
            "source": "mtime",
        })
    return phases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", nargs="?", help="stamped transcript.jsonl")
    ap.add_argument("--specs-dir", help="workdir specs/ dir for mtime fallback")
    ap.add_argument("--run-start", type=float, help="epoch run start for mtime fallback")
    args = ap.parse_args()

    phases = []
    if args.transcript and os.path.exists(args.transcript):
        phases = phases_from_transcript(args.transcript)
    if not phases and args.specs_dir and args.run_start and os.path.isdir(args.specs_dir):
        phases = phases_from_mtimes(args.specs_dir, args.run_start)

    json.dump({"phases": phases}, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
