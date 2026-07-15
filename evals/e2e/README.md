# E2E Workflow Eval Framework

Evaluates the repo's agentic Terraform workflows **end-to-end**: each eval case
runs a full `/tf-*-plan → /tf-*-implement` cycle headlessly in a throwaway
GitHub repo, then grades the outcome with deterministic checks plus an
**independent judge agent**, and renders a self-contained **HTML report** with
wall-time, cost, and quality metrics.

Covers the **module** and **consumer** tracks today; the core is track-agnostic
(a policy/provider case only needs a case file with its own rubric, checks, and
artifact globs).

This is separate from the per-skill `evals.json` files inside some skills and
from the demo tooling in `.foundations/test-scripts/` (interactive demo drivers,
not scored evals).

## Quick start

```bash
cp evals/e2e/.env.example evals/e2e/.env    # fill in tokens/accounts (.env is git-ignored globally)
# one-time: add `evals/e2e/results/` to .gitignore so run output stays untracked

# $0 plumbing test — no agent, no GitHub, no HCP Terraform
evals/e2e/bin/run-suite.sh --adapter mock --parallel 4

# cheapest real run: module track, no cloud deploy (~$3–8, 30–60 min)
evals/e2e/bin/run-suite.sh --case evals/e2e/cases/module/s3-static-website.json

# consumer suite: real sandbox deploy + guaranteed destroy
evals/e2e/bin/run-suite.sh --tags deploy --parallel 1

# regenerate the report from all recorded runs
python3 evals/e2e/report/generate_report.py

# emergency cleanup of orphaned sandbox workspaces
evals/e2e/bin/sweep-sandboxes.sh --org hashi-demos-apj --pattern 'sandbox_consumer_*' --dry-run
```

Open `evals/e2e/results/report.html` in a browser — it is fully offline
(inline CSS/JS/SVG, no CDNs) and safe to attach to a PR or share.

## How a case runs

```
case JSON ──► render prompt (substitute <GITHUB_REPO_NAME>/{SUFFIX})
          ──► arm teardown trap  (workspace name known BEFORE the agent runs)
          ──► create throwaway repo from EVAL_TEMPLATE_REPO, clone
          ──► adapter runs the agent headlessly (stream-json → stamped transcript)
          ──► harvest: specs/, git diff, TF code, validator self-score, TFE run facts
          ──► deterministic checks: fmt/validate/test/tflint/trivy/issue/PR/checklist
          ──► independent judge (fresh context, read-only, tf-judge-criteria rubric)
          ──► teardown: destroy sandbox workspace, delete throwaway repo
          ──► one line in results.jsonl  ──►  report.html
```

- **Isolation**: every case gets a fresh private repo generated from
  `EVAL_TEMPLATE_REPO` (a template mirror of this repo). The workflow's
  branches/issues/PRs land there; deleting the repo removes all of it.
- **Teardown is trap-armed before provisioning** and idempotent — an
  interrupted or timed-out run still destroys its HCP Terraform workspace.
  A suite-level sweep then catches stragglers, and `sweep-sandboxes.sh`
  exists for manual disaster recovery.
- **Grade**: `pass` ⇔ run finished ∧ all required deterministic checks pass
  ∧ judge overall ≥ `judge.min_score` ∧ no security override
  (tf-judge-criteria D2 < 5.0 forces Not Production Ready).

## The independent judge

`judge/run-judge.sh` launches `.claude/agents/tf-e2e-judge.md` in a **fresh
headless session** — it shares no context with the graded run and is read-only.
It applies the existing `tf-judge-criteria` rubric (6 weighted dimensions per
track + security override) plus the case's `judge.assertions`, and must reply
with a single JSON verdict (one retry, then the case records `judge_error`).

The workflow validator's self-score is deliberately **withheld** from the judge
(anchoring); it is harvested separately and the self-vs-judge drift is charted
in the report. Factual sandbox data (run id, apply status, run-task outcomes,
cost estimate) reaches the judge via `run-facts.json`, stripped of opinion.
Set `JUDGE_MODEL` in `.env` to keep grading on a cheap Sonnet-class model.

## Metrics

| Metric | Source |
|---|---|
| wall time | runner clock, cross-checked vs the runtime's `duration_ms` |
| per-phase timings | `Task` tool_use→tool_result spans in the stamped transcript (fallback: specs/ file mtimes) |
| agent cost (USD) | Claude Code `result` event `total_cost_usd` |
| judge cost (USD) | judge session result envelope |
| sandbox cost estimate | TFE API cost-estimate for the apply run (fallback: deployment report) |
| quality | judge overall + 6 dimensions + assertion pass rate + deterministic gates |
| self-vs-judge drift | validator self-score vs judge overall |

Results are JSONL (one line per case) under `results/runs/<run_id>/`; the HTML
report is derived from **all** recorded runs, so history accumulates by simply
keeping the run directories.

## Runtime adapters

The runner never invokes an agent CLI directly. `adapters/<name>.sh` implements:

```
adapters/<name>.sh run --prompt-file F --workdir D --out-dir O --timeout-secs N [--model M] [--max-turns K]
```

and must write a normalized `agent-result.json` (+ optional `transcript.jsonl`).
`claude-code.sh` is the real runtime; `mock.sh` fabricates a run for free
pipeline tests. To evaluate another agent runtime, add an adapter — nothing
else changes.

## Case files

`cases/<track>/<name>.json` — documented by `cases/_schema.json`; run-suite
enforces the required fields at selection time.
Prompts stay canonical in `.claude/skills/tf-{module,consumer}-e2e/prompts/`;
cases reference them by repo-relative path. `{SUFFIX}` in
`sandbox.workspace_pattern` and `<GITHUB_REPO_NAME>` in the prompt receive the
same run-unique value, which is how the runner knows the workspace to destroy
without trusting the agent to report it.

## Costs & cautions

- A full 8-case suite is **multi-hour and tens of dollars** of metered API cost
  plus AWS sandbox spend. Default to single cases or `--tags cheap`.
- Deploy cases default to `--parallel 1` etiquette — concurrent applies in one
  HCP project can queue; raise with care.
- A failed destroy **fails the case** and is flagged loudly in the report and
  logs; it never fails silently. A TFE network/auth error during teardown is
  reported as `failed`, never as clean.
- `--keep-repos` preserves throwaway repos for debugging (delete them manually).

## Runner environment requirements

- **Normal path: a Linux container** (e.g. `docker run` with the repo mounted)
  launched from any host shell — the scripts are `bash`-shebanged, so invoking
  them from macOS zsh works unchanged.
- **Native macOS is supported**: the scripts are bash-3.2-compatible and shim
  the GNU-only tools (`flock` → mkdir lock, `timeout` → `gtimeout` or a bash
  watchdog, `setsid` → direct child kill with SIGPIPE fallback; no `sed -i`).
  Interrupt handling is strongest where `setsid`/`timeout` exist — inside the
  container. Required on the runner either way: `jq`, `git`, `gh`, `curl`,
  `python3`, plus `terraform`/`tflint`/`trivy` for the deterministic checks
  (missing tools record as `skip`).
- The gh token must carry the **`delete_repo` scope**
  (`gh auth refresh -h github.com -s delete_repo`) or pass `--keep-repos`.
- `EVAL_TEMPLATE_REPO` must mirror this repo **including `.claude/`** — the
  throwaway clone is where both the workflow and the judge find their skills
  and agent definitions.
- Module-track cases run `terraform test` as a required check; the runner
  environment needs AWS credentials for any test that plans real providers.
- The suite refuses to start real runs when `gh`/`TFE_TOKEN`/env validation
  fails; case files are structurally checked (id, track, prompt_file,
  timeout_minutes, judge.min_score, deterministic_checks, sandbox.deploy)
  before anything launches.

## CI (later)

A `workflow_dispatch` GitHub Action can wrap `run-suite.sh` (mirror
`terraform-claude-review.yml`'s claude-code-action auth wiring + `TFE_TOKEN` +
a PAT that can create/delete repos), upload `results/runs/<run_id>` and
`report.html` as artifacts, serialize suites with a concurrency group, and run
`sweep-sandboxes.sh` on a nightly schedule as a destroy backstop.
