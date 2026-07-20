#!/usr/bin/env python3
"""Generate the self-contained HTML report for e2e eval runs.

Reads every results/runs/<run_id>/results.jsonl (+ suite.json) and renders one
offline HTML file: header scorecard, per-case cards (phase timeline, cost split,
judge dimension bars, deterministic check grid, assertions), and cross-run
trends. Stdlib only; inline CSS/JS/SVG; no external requests.

Usage: generate_report.py [--results <dir>] [--out <file>]
"""
import argparse
import glob
import html
import json
import os
import sys

# Reference palette (validated — see the dataviz method): categorical slots in
# fixed order, sequential blue, status colors (never reused as series).
PHASE_ORDER = ["research", "design", "test-writer", "developer", "validator"]
CAT_LIGHT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
CAT_DARK = ["#3987e5", "#199e70", "#c98500", "#008300", "#9085e9", "#e66767", "#d55181", "#d95926"]


def esc(v):
    return html.escape(str(v), quote=True)


def fmt_money(v):
    if v is None:
        return "n/a"
    return f"${v:,.2f}"


def fmt_secs(v):
    if v is None:
        return "n/a"
    v = int(v)
    if v < 60:
        return f"{v}s"
    if v < 3600:
        return f"{v // 60}m {v % 60:02d}s"
    return f"{v // 3600}h {(v % 3600) // 60:02d}m"


def fmt_score(v):
    return "n/a" if v is None else f"{v:.1f}"


def load_runs(results_dir):
    runs = []
    for path in sorted(glob.glob(os.path.join(results_dir, "runs", "*", "results.jsonl"))):
        run_dir = os.path.dirname(path)
        run_id = os.path.basename(run_dir)
        cases = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        cases.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"warn: bad line in {path}", file=sys.stderr)
        suite = {}
        suite_path = os.path.join(run_dir, "suite.json")
        if os.path.exists(suite_path):
            with open(suite_path, encoding="utf-8") as fh:
                suite = json.load(fh)
        if cases:
            runs.append({"run_id": run_id, "cases": sorted(cases, key=lambda c: c["case_id"]), "suite": suite})
    return runs  # already sorted by run_id (timestamped)


# ---------------------------------------------------------------- components


def grade_badge(grade):
    if grade == "pass":
        return '<span class="badge badge-pass">✓ PASS</span>'
    return '<span class="badge badge-fail">✗ FAIL</span>'


def stat_tile(label, value, sub=""):
    sub_html = f'<div class="tile-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="tile"><div class="tile-label">{esc(label)}</div>'
        f'<div class="tile-value">{value}</div>{sub_html}</div>'
    )


def phase_color(name):
    try:
        i = PHASE_ORDER.index(name)
    except ValueError:
        i = 5
    return f"var(--series-{i + 1})"


def phase_timeline(phases):
    """Horizontal stacked bar of phase durations, 2px surface gaps, tooltips.
    Falls back to a completion list for mtime-derived phases (no durations)."""
    named = [p for p in (phases or []) if p.get("duration_s")]
    if not named:
        mtimed = [p for p in (phases or []) if p.get("completed_offset_s") is not None]
        if mtimed:
            items = " · ".join(
                f'{esc(p.get("name") or "?")} done at {fmt_secs(p["completed_offset_s"])}'
                for p in mtimed
            )
            return f'<div class="small muted">{items} <span title="derived from artifact mtimes">(mtime)</span></div>'
        return '<div class="muted">no phase data</div>'
    total = sum(p["duration_s"] for p in named)
    segs, legend_names = [], []
    for p in named:
        w = max(p["duration_s"] / max(total, 1) * 100, 0.8)
        name = p.get("name") or "?"
        if name not in legend_names:
            legend_names.append(name)
        tip = f"{name}: {fmt_secs(p['duration_s'])}" + (f" ({esc(p.get('agent') or '')})" if p.get("agent") else "")
        segs.append(
            f'<div class="seg" data-tip="{esc(tip)}" '
            f'style="width:{w:.2f}%;background:{phase_color(name)}"></div>'
        )
    legend = "".join(
        f'<span class="key"><span class="swatch" style="background:{phase_color(n)}"></span>{esc(n)}</span>'
        for n in legend_names
    )
    rows = "".join(
        f"<tr><td>{esc(p.get('name') or '?')}</td><td>{fmt_secs(p['duration_s'])}</td>"
        f"<td>{fmt_secs(p.get('start_offset_s'))}</td></tr>"
        for p in named
    )
    table = (
        '<details class="tbl"><summary>phase table</summary><table>'
        "<tr><th>phase</th><th>duration</th><th>starts at</th></tr>"
        f"{rows}</table></details>"
    )
    return (
        f'<div class="timeline">{"".join(segs)}</div>'
        f'<div class="legend">{legend}<span class="muted key">agent-phase share of {fmt_secs(total)} attributed</span></div>{table}'
    )


DIM_MAX = 10.0


def dimension_bars(judge):
    """Judge dimensions 0–10 — magnitude comparison, one hue; 5.0 security threshold marker."""
    if not judge or not judge.get("dimensions"):
        return '<div class="muted">no judge verdict</div>'
    rows = []
    for key in sorted(judge["dimensions"]):
        score = judge["dimensions"][key]
        if score is None:
            continue
        pct = max(min(score / DIM_MAX, 1.0), 0.0) * 100
        is_sec = key == "d2"
        marker = '<div class="thresh" data-tip="security override threshold (5.0)"></div>' if is_sec else ""
        flag = ' <span class="crit-flag">⚠ override</span>' if is_sec and judge.get("security_override") else ""
        label = f"{key.upper()}{' · security' if is_sec else ''}"
        rows.append(
            f'<div class="dim-row"><div class="dim-label">{esc(label)}</div>'
            f'<div class="dim-track" data-tip="{esc(label)}: {score}/10">{marker}'
            f'<div class="dim-fill" style="width:{pct:.1f}%"></div></div>'
            f'<div class="dim-val">{fmt_score(score)}{flag}</div></div>'
        )
    return '<div class="dims">' + "".join(rows) + "</div>"


CHECK_LABELS = {
    "artifacts": "artifacts", "terraform_fmt": "fmt", "terraform_validate": "validate",
    "terraform_test": "test", "tflint": "tflint", "trivy": "trivy",
    "issue_created": "issue", "pr_created": "PR", "checklist_complete": "checklist",
    "destroy_clean": "destroy",
}


def check_grid(det):
    if not det or not det.get("checks"):
        return '<div class="muted">no checks</div>'
    cells = []
    for name, c in det["checks"].items():
        label = CHECK_LABELS.get(name, name)
        if c.get("skipped"):
            cls, icon = "chk-skip", "−"
        elif c.get("pass"):
            cls, icon = "chk-pass", "✓"
        else:
            cls, icon = "chk-fail", "✗"
        tip = f"{name}: " + ("skipped" if c.get("skipped") else "pass" if c.get("pass") else "fail")
        if c.get("detail"):
            tip += f" — {c['detail'][:120]}"
        cells.append(f'<span class="chk {cls}" data-tip="{esc(tip)}">{icon} {esc(label)}</span>')
    return '<div class="chkgrid">' + "".join(cells) + "</div>"


def assertions_list(judge):
    if not judge:
        return ""
    total = judge.get("assertions_total")
    passed = judge.get("assertions_passed")
    if total is None:
        return ""
    return f'<div class="muted small">assertions: {passed}/{total} passed</div>'


def cost_row(case):
    agent = (case.get("agent") or {}).get("cost_usd")
    judge_cost = (case.get("judge") or {}).get("judge_cost_usd")
    sandbox = (case.get("sandbox") or {}).get("cost_estimate_monthly_usd")
    bits = [f"agent {fmt_money(agent)}"]
    if judge_cost is not None:
        bits.append(f"judge {fmt_money(judge_cost)}")
    if sandbox is not None:
        bits.append(f"infra est. {fmt_money(sandbox)}/mo")
    return " · ".join(bits)


def case_card(case):
    sandbox = case.get("sandbox") or {}
    judge = case.get("judge")
    facts = []
    facts.append(f"wall {fmt_secs(case.get('wall_time_s'))}")
    if (case.get("agent") or {}).get("num_turns") is not None:
        facts.append(f"{case['agent']['num_turns']} turns")
    if case.get("validator_self_score") is not None:
        facts.append(f"self-score {fmt_score(case['validator_self_score'])}")
    if judge and judge.get("overall") is not None:
        facts.append(f"judge {fmt_score(judge['overall'])}")
    if case.get("judge_error"):
        facts.append("judge error")
    deploy_html = ""
    if sandbox.get("deployed"):
        destroy = sandbox.get("destroy_status") or "unknown"
        destroy_cls = "chk-pass" if destroy == "clean" else "chk-fail"
        run_link = (
            f' · <a href="{esc(sandbox["run_url"])}">TFC run</a>' if sandbox.get("run_url") else ""
        )
        deploy_html = (
            f'<div class="small">sandbox: <span class="chk {destroy_cls}">'
            f'{"✓" if destroy == "clean" else "✗"} destroy {esc(destroy)}</span>{run_link}</div>'
        )
    repo = case.get("repo") or {}
    repo_html = ""
    if repo.get("full_name"):
        state = "deleted" if repo.get("deleted") else "kept"
        repo_html = f'<div class="small muted">repo {esc(repo["full_name"])} ({state})</div>'
    return f"""
  <div class="card">
    <div class="card-head">
      <div><span class="case-id">{esc(case["case_id"])}</span>
        <span class="pill">{esc(case["track"])}</span>
        <span class="pill">{esc(case["status"])}</span></div>
      {grade_badge(case.get("grade"))}
    </div>
    <div class="small muted">{esc(" · ".join(facts))}</div>
    <div class="small muted">{esc(cost_row(case))}</div>
    {deploy_html}
    <h4>Phases</h4>
    {phase_timeline(case.get("phases"))}
    <h4>Judge dimensions</h4>
    {dimension_bars(judge)}
    {assertions_list(judge)}
    <h4>Deterministic checks</h4>
    {check_grid(case.get("deterministic"))}
    {repo_html}
    <div class="small"><a href="{esc(case.get("artifacts_dir", ""))}">artifacts →</a></div>
  </div>"""


# ------------------------------------------------------------------- trends


def svg_trend(title, runs, case_ids, extract, unit=""):
    """SVG multi-line chart: one line per case_id across runs. 2px lines, ≥8px
    ring-backed markers, legend (color never alone), table view."""
    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 640, 220, 44, 12, 14, 30
    series = {}
    for cid in case_ids:
        pts = []
        for i, run in enumerate(runs):
            case = next((c for c in run["cases"] if c["case_id"] == cid), None)
            v = extract(case) if case else None
            if v is not None:
                pts.append((i, v))
        if pts:
            series[cid] = pts
    if not series:
        return ""
    all_vals = [v for pts in series.values() for _, v in pts]
    vmax = max(all_vals) or 1
    vmin = min(0, min(all_vals))
    span = (vmax - vmin) or 1
    n = max(len(runs) - 1, 1)

    def x(i):
        return PAD_L + i / n * (W - PAD_L - PAD_R)

    def y(v):
        return PAD_T + (1 - (v - vmin) / span) * (H - PAD_T - PAD_B)

    # clean y ticks: 0, half, max (rounded)
    ticks = sorted({round(vmin, 1), round(vmin + span / 2, 1), round(vmax, 1)})
    grid = "".join(
        f'<line x1="{PAD_L}" y1="{y(t):.1f}" x2="{W - PAD_R}" y2="{y(t):.1f}" class="grid"/>'
        f'<text x="{PAD_L - 6}" y="{y(t) + 4:.1f}" class="tick" text-anchor="end">{t:g}</text>'
        for t in ticks
    )
    def anchor(i):
        if i == 0:
            return "start"
        return "end" if i == len(runs) - 1 else "middle"

    xlabels = "".join(
        f'<text x="{x(i):.1f}" y="{H - 8}" class="tick" text-anchor="{anchor(i)}">{esc(run["run_id"][4:13])}</text>'
        for i, run in enumerate(runs)
    )
    body, legend = [], []
    for si, (cid, pts) in enumerate(sorted(series.items())):
        color_i = si % 8 + 1
        path = " ".join(f"{'M' if j == 0 else 'L'}{x(i):.1f},{y(v):.1f}" for j, (i, v) in enumerate(pts))
        dots = "".join(
            f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="6" class="ring"/>'
            f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="var(--series-{color_i})" '
            f'data-tip="{esc(cid)} @ {esc(runs[i]["run_id"])}: {v:g}{unit}"/>'
            for i, v in pts
        )
        body.append(f'<path d="{path}" fill="none" stroke="var(--series-{color_i})" stroke-width="2" stroke-linejoin="round"/>{dots}')
        legend.append(f'<span class="key"><span class="swatch" style="background:var(--series-{color_i})"></span>{esc(cid)}</span>')
    header = "<tr><th>case</th>" + "".join(f"<th>{esc(r['run_id'][:13])}</th>" for r in runs) + "</tr>"
    rows = ""
    for cid, pts in sorted(series.items()):
        by_i = dict(pts)
        rows += f"<tr><td>{esc(cid)}</td>" + "".join(
            f"<td>{by_i[i]:g}{unit}</td>" if i in by_i else "<td>–</td>" for i in range(len(runs))
        ) + "</tr>"
    return f"""
  <div class="chart">
    <h3>{esc(title)}</h3>
    <svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">{grid}{xlabels}{"".join(body)}</svg>
    <div class="legend">{"".join(legend)}</div>
    <details class="tbl"><summary>data table</summary><table>{header}{rows}</table></details>
  </div>"""


def drift_dumbbells(latest):
    """Validator self-score vs judge score, latest run — dumbbell, 1 hue 2 shades."""
    rows = []
    for case in latest["cases"]:
        self_s = case.get("validator_self_score")
        judge_s = (case.get("judge") or {}).get("overall")
        if self_s is None or judge_s is None:
            continue
        lo, hi = sorted((self_s, judge_s))
        rows.append(
            f'<div class="dim-row"><div class="dim-label">{esc(case["case_id"])}</div>'
            f'<div class="dumbbell">'
            f'<div class="db-bar" style="left:{lo * 10:.1f}%;width:{max((hi - lo) * 10, 0.5):.1f}%"></div>'
            f'<div class="db-dot db-self" style="left:{self_s * 10:.1f}%" data-tip="self-score {self_s:g}"></div>'
            f'<div class="db-dot db-judge" style="left:{judge_s * 10:.1f}%" data-tip="judge {judge_s:g}"></div>'
            f'</div><div class="dim-val">Δ {judge_s - self_s:+.1f}</div></div>'
        )
    if not rows:
        return ""
    return f"""
  <div class="chart">
    <h3>Self-score vs judge (latest run)</h3>
    <div class="legend">
      <span class="key"><span class="swatch" style="background:var(--seq-light)"></span>validator self-score</span>
      <span class="key"><span class="swatch" style="background:var(--series-1)"></span>independent judge</span>
    </div>
    <div class="dims">{"".join(rows)}</div>
  </div>"""


def grade_matrix(runs, case_ids):
    if len(runs) < 2:
        return ""
    header = "<tr><th>case</th>" + "".join(f"<th>{esc(r['run_id'][:13])}</th>" for r in runs) + "</tr>"
    rows = ""
    for cid in case_ids:
        cells = ""
        for run in runs:
            case = next((c for c in run["cases"] if c["case_id"] == cid), None)
            if case is None:
                cells += '<td class="muted">–</td>'
            elif case.get("grade") == "pass":
                score = (case.get("judge") or {}).get("overall")
                cells += f'<td class="chk-pass">✓ {fmt_score(score) if score is not None else "pass"}</td>'
            else:
                cells += '<td class="chk-fail">✗ fail</td>'
        rows += f"<tr><td>{esc(cid)}</td>{cells}</tr>"
    return f'<div class="chart"><h3>Run × case grades</h3><table class="matrix">{header}{rows}</table></div>'


# --------------------------------------------------------------------- page


def scorecard(latest):
    cases = latest["cases"]
    passed = sum(1 for c in cases if c.get("grade") == "pass")
    judged = [c["judge"]["overall"] for c in cases if c.get("judge") and c["judge"].get("overall") is not None]
    mean_judge = sum(judged) / len(judged) if judged else None
    cost = sum(c["agent"]["cost_usd"] or 0 for c in cases if c.get("agent"))
    wall = sum(c.get("wall_time_s") or 0 for c in cases)
    deployed = [c for c in cases if (c.get("sandbox") or {}).get("deployed")]
    clean = sum(1 for c in deployed if (c["sandbox"].get("destroy_status") == "clean"))
    destroy_val = f"{clean}/{len(deployed)} clean" if deployed else "n/a"
    destroy_sub = "" if not deployed or clean == len(deployed) else '<span class="crit-flag">⚠ orphans — run sweep-sandboxes.sh</span>'
    grade_cls = "tile-good" if passed == len(cases) else "tile-bad"
    return f"""
  <div class="tiles">
    <div class="tile {grade_cls}"><div class="tile-label">cases passed</div>
      <div class="tile-value">{passed}<span class="tile-of">/{len(cases)}</span></div></div>
    {stat_tile("mean judge score", fmt_score(mean_judge))}
    {stat_tile("agent cost", fmt_money(cost))}
    {stat_tile("wall time", fmt_secs(wall))}
    {stat_tile("sandbox destroys", destroy_val, destroy_sub)}
  </div>"""


CSS = """
:root {
  --surface-1: #fcfcfb; --surface-2: #f4f4f2; --border: #e4e3df;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #8a897f;
  --series-1: #2a78d6; --series-2: #1baf7a; --series-3: #eda100; --series-4: #008300;
  --series-5: #4a3aa7; --series-6: #e34948; --series-7: #e87ba4; --series-8: #eb6834;
  --seq-light: #9ec5f4; --track: #cde2fb;
  --good: #0ca30c; --critical: #d03b3b; --grid: #e9e8e4;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-1: #1a1a19; --surface-2: #242423; --border: #3a3a37;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #8a897f;
    --series-1: #3987e5; --series-2: #199e70; --series-3: #c98500; --series-4: #008300;
    --series-5: #9085e9; --series-6: #e66767; --series-7: #d55181; --series-8: #d95926;
    --seq-light: #1c5cab; --track: #184f95;
    --good: #0ca30c; --critical: #d03b3b; --grid: #2e2e2c;
  }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 24px; background: var(--surface-1); color: var(--text-primary);
  font: 14px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
.wrap { max-width: 1100px; margin: 0 auto; }
h1 { font-size: 20px; margin: 0 0 4px; }
h3 { font-size: 15px; margin: 0 0 8px; }
h4 { font-size: 12px; margin: 14px 0 6px; color: var(--text-secondary);
  text-transform: uppercase; letter-spacing: .04em; font-weight: 600; }
a { color: var(--series-1); }
.muted { color: var(--text-muted); } .small { font-size: 12px; }
.sub { color: var(--text-secondary); margin-bottom: 20px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin-bottom: 24px; }
.tile { background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 14px; }
.tile-label { font-size: 12px; color: var(--text-secondary); }
.tile-value { font-size: 26px; font-weight: 600; }
.tile-of { font-size: 15px; color: var(--text-muted); font-weight: 400; }
.tile-sub { font-size: 11px; }
.tile-good .tile-value { color: var(--good); } .tile-bad .tile-value { color: var(--critical); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: 16px; margin-bottom: 28px; }
.card { background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px; }
.card-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
.case-id { font-weight: 600; font-size: 15px; }
.pill { font-size: 11px; border: 1px solid var(--border); border-radius: 99px;
  padding: 1px 8px; color: var(--text-secondary); margin-left: 6px; }
.badge { font-size: 12px; font-weight: 700; border-radius: 6px; padding: 2px 8px; white-space: nowrap; }
.badge-pass { color: var(--good); border: 1px solid var(--good); }
.badge-fail { color: var(--critical); border: 1px solid var(--critical); }
.timeline { display: flex; gap: 2px; height: 18px; border-radius: 4px; overflow: hidden; }
.seg { height: 100%; min-width: 3px; border-radius: 2px; }
.legend { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; font-size: 12px;
  color: var(--text-secondary); }
.key { display: inline-flex; align-items: center; gap: 5px; }
.swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.dims { display: flex; flex-direction: column; gap: 5px; }
.dim-row { display: grid; grid-template-columns: 110px 1fr 74px; gap: 8px; align-items: center; }
.dim-label { font-size: 12px; color: var(--text-secondary); }
.dim-val { font-size: 12px; font-variant-numeric: tabular-nums; }
.dim-track { position: relative; height: 12px; background: var(--track); border-radius: 3px; }
.dim-fill { position: absolute; inset: 0 auto 0 0; background: var(--series-1);
  border-radius: 3px 4px 4px 3px; max-width: 100%; }
.thresh { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 2px;
  background: var(--critical); z-index: 1; }
.crit-flag { color: var(--critical); font-weight: 600; font-size: 11px; }
.chkgrid { display: flex; flex-wrap: wrap; gap: 6px; }
.chk { font-size: 12px; border-radius: 5px; padding: 2px 7px; border: 1px solid var(--border); }
.chk-pass { color: var(--good); } .chk-fail { color: var(--critical); font-weight: 600; }
.chk-skip { color: var(--text-muted); }
.chart { background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px; margin-bottom: 16px; }
svg { width: 100%; height: auto; display: block; }
.grid { stroke: var(--grid); stroke-width: 1; }
.tick { fill: var(--text-muted); font-size: 10px; }
.ring { fill: var(--surface-2); }
table { border-collapse: collapse; font-size: 12px; margin-top: 6px; width: 100%; }
th, td { text-align: left; padding: 3px 10px 3px 0; border-bottom: 1px solid var(--border);
  font-variant-numeric: tabular-nums; }
th { color: var(--text-secondary); font-weight: 600; }
.matrix td, .matrix th { padding: 4px 12px 4px 0; }
.tbl summary { font-size: 11px; color: var(--text-muted); cursor: pointer; margin-top: 6px; }
.dumbbell { position: relative; height: 14px; background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 3px; }
.db-bar { position: absolute; top: 5px; height: 2px; background: var(--text-muted); }
.db-dot { position: absolute; top: 2px; width: 8px; height: 8px; border-radius: 50%;
  border: 2px solid var(--surface-2); transform: translateX(-50%); }
.db-self { background: var(--seq-light); } .db-judge { background: var(--series-1); }
#tip { position: fixed; pointer-events: none; background: var(--text-primary);
  color: var(--surface-1); font-size: 12px; padding: 4px 8px; border-radius: 5px;
  max-width: 320px; z-index: 10; display: none; }
footer { color: var(--text-muted); font-size: 11px; margin-top: 24px; }
"""

JS = """
const tip = document.getElementById('tip');
document.addEventListener('mouseover', e => {
  const t = e.target.closest('[data-tip]');
  if (!t) { tip.style.display = 'none'; return; }
  tip.textContent = t.getAttribute('data-tip');
  tip.style.display = 'block';
});
document.addEventListener('mousemove', e => {
  if (tip.style.display === 'none') return;
  const x = Math.min(e.clientX + 12, window.innerWidth - tip.offsetWidth - 8);
  const y = Math.min(e.clientY + 14, window.innerHeight - tip.offsetHeight - 8);
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
});
document.addEventListener('mouseout', e => {
  if (e.target.closest && e.target.closest('[data-tip]')) tip.style.display = 'none';
});
"""


def build(runs):
    latest = runs[-1]
    case_ids = sorted({c["case_id"] for r in runs for c in r["cases"]})
    cards = "".join(case_card(c) for c in latest["cases"])
    trends = ""
    if len(runs) > 1:
        trends = (
            svg_trend("Judge score by run", runs, case_ids,
                      lambda c: (c.get("judge") or {}).get("overall"))
            + svg_trend("Agent cost by run (USD)", runs, case_ids,
                        lambda c: (c.get("agent") or {}).get("cost_usd"), unit="$")
            + svg_trend("Wall time by run (minutes)", runs, case_ids,
                        lambda c: round(c["wall_time_s"] / 60, 1) if c.get("wall_time_s") is not None else None,
                        unit="m")
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>E2E Workflow Evals</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>E2E workflow eval report</h1>
  <div class="sub">latest run <strong>{esc(latest["run_id"])}</strong>
    · {len(runs)} run(s) on record
    · git {esc(latest["suite"].get("git_sha", "?"))}
    · adapter {esc(latest["suite"].get("adapter", "?"))}</div>
  {scorecard(latest)}
  <div class="cards">{cards}</div>
  {drift_dumbbells(latest)}
  {trends}
  {grade_matrix(runs, case_ids)}
  <footer>Generated by evals/e2e/report/generate_report.py — fully offline.</footer>
</div>
<div id="tip"></div>
<script>{JS}</script>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser()
    default_results = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    ap.add_argument("--results", default=default_results)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    results_dir = os.path.abspath(args.results)
    out = args.out or os.path.join(results_dir, "report.html")
    runs = load_runs(results_dir)
    if not runs:
        print(f"no results found under {results_dir}/runs/", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build(runs))
    print(f"report: {out} ({len(runs)} run(s), {sum(len(r['cases']) for r in runs)} case result(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
