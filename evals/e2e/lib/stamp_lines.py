#!/usr/bin/env python3
"""Stamp each stdin line (a stream-json event) with its arrival time.

Emits {"ts": <epoch_float>, "event": <parsed event or raw string>} per line.
The wall-clock stamps are what make per-phase timing possible downstream
(parse_transcript.py) without trusting event-internal timestamps.
"""
import json
import sys
import time


def main() -> int:
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = {"type": "raw", "text": line}
        out.write(json.dumps({"ts": time.time(), "event": event}) + "\n")
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
