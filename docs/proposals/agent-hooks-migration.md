# Proposal: Re-home `pre-commit` checks to their natural boundary (agent hooks + a native git hook)

**Status:** Accepted — implemented on branch `feat/agent-hooks-migration`
**Author:** Drew Mullen
**Date:** 2026-07-13

## 1. Summary

Stop treating `pre-commit` as one monolithic local gate. Instead, **re-home each
check to the boundary where it actually belongs**:

- **Per-file, as-you-edit checks** (formatting, EOF, YAML syntax) → **agent
  `PostToolUse` hooks** (Claude Code + Copilot), so they fire the moment the agent
  writes a file.
- **Directory/tree, end-of-turn checks** (`terraform validate`, `tflint`, `terraform-docs`,
  `trivy`, private-key scan) → **agent `Stop`/`agentStop` hooks**, run once when the
  agent finishes.
- **Commit-boundary checks** (Vault Radar secret scan, large-file guard, merge-conflict
  markers) → a **native git `pre-commit` hook** (`.githooks/pre-commit`, provisioned by
  the devcontainer), because their real boundary is the commit and their inputs arrive
  via `git`/`Bash`, not the agent's editor.

CI (`.github/workflows/validate.yml`) is unchanged and remains the enforcement gate.

The `pre-commit` **framework** (Python + `pre-commit install`) is removed entirely.
The three commit-boundary checks move to a checked-in native git hook instead — the
framework was only ever solving hook *distribution*, which the devcontainer solves with
one `git config core.hooksPath` line. Vault Radar stays in its first-class
`scan git pre-commit` mode; nothing loses the commit-time boundary.

> **Correction history:** earlier drafts of this proposal (a) wrongly claimed Copilot is
> "blocking-hooks-only" — it has a full lifecycle, see §3; (b) wrongly routed
> secret/large-file/merge checks through `PreToolUse` "block before it hits disk" (for
> none of these is *writing to disk* the harm; the boundary is the commit); and (c)
> proposed keeping a "slim `pre-commit`" framework — unnecessary, since a native
> `.githooks/pre-commit` + devcontainer provisioning covers the three retained checks
> with no Python dependency. §4/§5/§6 reflect the corrected design.

## 2. Why change

| Concern | `pre-commit` today | Agent hooks |
| --- | --- | --- |
| **When it fires** | Only when the agent runs `git commit` — end of a batch | At every `Write`/`Edit`, mid-task |
| **Trigger dependency** | Only if a `git commit` happens *and* `pre-commit install` ran in that clone | Fires on every file write; no install step |
| **Who fixes failures** | The agent — runs the commit, sees output, re-commits (in-loop, coarse) | The agent — failure text fed back per edit |
| **Toolchain** | Separate Python/`pre-commit` install per clone | None — config lives in files the agent already reads |
| **Feedback latency** | Whole staged set, at commit time | Per-file, immediately |

Both are in-loop; the real wins are **granularity** (per-edit vs. per-commit) and
dropping the easily-skipped `pre-commit install` onboarding step for the checks that
don't need a git context. The checks that *do* need a git context stay in the git hook.

## 3. Both agents have near-equivalent hook lifecycles

Claude Code and GitHub Copilot expose the **same hook model** — pre-tool (blocking),
post-tool (fix/inject), and end-of-turn events. Differences are naming, config
location, and a few Copilot-only events. There is **no "blocking-only" limitation**.

| Purpose | Claude Code | GitHub Copilot |
| --- | --- | --- |
| Before a tool — allow/deny/modify | `PreToolUse` | `preToolUse` |
| After a tool succeeds — fix / inject | `PostToolUse` | `postToolUse` (+ `postToolUseFailure`) |
| End of the agent's turn | `Stop` | `agentStop` |
| Session start / end | `SessionStart` / `SessionEnd` | `sessionStart` / `sessionEnd` |
| Prompt submitted | `UserPromptSubmit` | `userPromptSubmitted` |
| Subagent start / stop | `SubagentStart` / `SubagentStop` | `subagentStart` / `subagentStop` |

**Config:** Claude → `.claude/settings.json` `"hooks"`. Copilot → `.agents/hooks/*.json`
(`{ "version": 1, "hooks": {…} }`), exposed to Copilot via the `.github/hooks`
symlink — Copilot (CLI and cloud agent) only discovers repo hooks at
`.github/hooks/*.json`, so the symlink is what covers CLI + IDE + cloud.
Docs: <https://docs.github.com/en/copilot/reference/hooks-reference>

## 4. Placement principle: match the check to its boundary

Each check has a natural boundary determined by **what it operates on** and **where the
harm actually occurs** — not by "can I block a write."

- **`PostToolUse` (per-file, fix/feedback).** For checks that (a) act on a single file
  and (b) have the full file available on disk after the write. Formatting/EOF *fix*
  and return success; YAML syntax *feeds a parse error back*. Never block — these aren't
  security issues, and blocking whitespace is user-hostile.
- **`Stop` / `agentStop` (directory/tree, end of turn).** For checks that are
  **directory-scoped**, need an **initialized directory** (`terraform init`, `tflint
  --init`), or scan the **whole tree**. Running them per-edit is wasteful and fails
  spuriously mid-resource. Run once when the agent is done; discover changed dirs via
  `git diff --name-only`.
- **Native git `pre-commit` hook (commit boundary).** For checks whose input is the **git
  diff/staged set** or whose subject **arrives via `git`/`Bash`, not the editor** — a
  Write/Edit matcher can't see those. Secret scanning, large binaries/state/plan
  artifacts, and merge-conflict markers all belong here.

**`PreToolUse` is essentially unused.** Nothing here is a case where *writing the
content to disk* is itself the harm, so there's no blocking pre-write gate. (Optional:
an early private-key regex on a `Write`'s full `content` as a bonus catch — but the
authoritative scan is at the commit boundary / end of turn.)

## 5. Mapping: `pre-commit` hook → placement (audited)

| `pre-commit` hook | Nature | Placement | Why not elsewhere |
| --- | --- | --- | --- |
| `terraform_fmt` | per-file mutation | **PostToolUse** (fix, both agents) | file on disk post-write; never errors |
| `end-of-file-fixer` | per-file mutation | **PostToolUse** (fix, both) | same |
| `check-yaml` | per-file validate | **PostToolUse** (feedback, both) | `Edit` gives only a fragment — can't parse the whole file pre-write; parse on disk after. Not a security block. |
| `terraform_docs` | **dir**-scoped mutation | **Stop / agentStop** | regenerates a module README; per-edit would rewrite README on every `.tf` edit (churn). Once per changed module. |
| `terraform_tflint` | **dir**-scoped lint, needs `tflint --init` | **Stop / agentStop** | plugin init + mid-resource spurious failures make per-edit wrong |
| `terraform_validate` | **dir**-scoped, needs `init` | **Stop / agentStop** | needs initialized dir; mid-edit configs are legitimately invalid |
| `terraform_trivy` | tree scan | **Stop / agentStop** | whole-tree; expensive per-edit |
| `detect-private-key` | secret scan | **Stop / agentStop** (+ git hook) | secrets can arrive via `Bash` (`output >`, `curl`, `sed -i`) with no Write/Edit call — scan changed files on disk |
| `vault-radar-scan` | git-diff scanner | **Native git hook** | it *is* `vault-radar scan git pre-commit`; no git state exists pre-write; boundary = commit |
| `check-added-large-files` | staged-size guard | **Native git hook** | binaries/state/plan artifacts come from `Bash`/build, not the editor; boundary = commit |
| `check-merge-conflict` | marker scan | **Native git hook** | conflict markers come from `git merge`/`rebase`, not agent writes |

Sorted into three buckets:

1. **PostToolUse (per-file):** `fmt`, `end-of-file`, `check-yaml`
2. **Stop / agentStop (per-dir / tree, end of turn):** `docs`, `tflint`, `validate`,
   `trivy`, `detect-private-key`
3. **Native git `pre-commit` hook (commit boundary):** `vault-radar`, `large-files`,
   `merge-conflict`

## 6. Architecture

One **shared dispatcher** holds all logic; three surfaces invoke it (Claude hooks,
Copilot hooks, and the native git hook) so there is a single source of truth. Because
it is shared across all three — not Claude-specific — it lives under `scripts/`, not
`.claude/`:

```
scripts/hooks/
  tf-guard.sh        # modes: fix | verify | commit ; normalizes each caller's payload
  checks/
    fmt.sh           # terraform fmt / terraform-docs / eof   (fix)
    yaml.sh          # yaml parse-check                       (feedback)
    lint.sh          # tflint (--init aware)                  (verify)
    validate.sh      # terraform init -backend=false + validate (verify)
    trivy.sh         # trivy config scan                      (verify)
    secrets.sh       # detect-private-key / vault-radar       (verify + commit)
    hygiene.sh       # large-file / merge-conflict            (commit)
```

- **Claude** `.claude/settings.json`: `PostToolUse` → `tf-guard.sh fix`; `Stop` →
  `tf-guard.sh verify`.
- **Copilot** `.agents/hooks/tf-guard.json`: `postToolUse` → `tf-guard.sh fix`;
  `agentStop` → `tf-guard.sh verify`.
- **Native git hook** (`.githooks/pre-commit`, one line): `tf-guard.sh commit` →
  `vault-radar` + `large-files` + `merge-conflict`.

`verify` and `commit` both discover their targets from `git diff --name-only` rather
than a single file path.

### 6a. Claude Code (`.claude/settings.json`, checked in)

```jsonc
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Write|Edit|MultiEdit",
        "hooks": [ { "type": "command", "command": "scripts/hooks/tf-guard.sh fix", "timeout": 60 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "scripts/hooks/tf-guard.sh verify", "timeout": 120 } ] }
    ]
  }
}
```

`fix` → `fmt`/`docs`(if the module has a README)/`eof` silently (exit 0); `check-yaml`
exits `2` on a parse error so it's fed back. `verify` → `validate` + `tflint` + `trivy`
+ private-key scan over changed dirs.

> **Blocker cleared:** `.claude/settings.local.json` previously set
> `"disableAllHooks": true` (now `false`) — otherwise no Claude hook runs. The shared
> hooks live in the checked-in `.claude/settings.json`, not the developer-local
> `settings.local.json`.

### 6b. Copilot (`.agents/hooks/tf-guard.json`, checked in)

Copilot **auto-discovers** any `.github/hooks/*.json` in the repo — no explicit
registration; file presence is the wiring, and the cloud agent reads only this path.
In this repo the files live in `.agents/hooks/`, with `.github/hooks` as a symlink
to keep Copilot discovery working. Windows caveat: without `core.symlinks=true`
(needs Developer Mode or admin), git checks the symlinks out as plain text files
and Copilot discovery silently breaks — use the devcontainers or enable symlinks.
Each entry uses `type: "command"` with a `bash` command (add `powershell` for Windows);
the payload arrives on **stdin**. Note there is **no tool matcher** — `postToolUse`
fires for every tool, so the script self-gates (`fix` exits 0 when the payload has no
edited file path, e.g. for a `bash` tool call).

```jsonc
{
  "version": 1,
  "hooks": {
    "postToolUse": [
      { "type": "command", "bash": "bash scripts/hooks/tf-guard.sh fix", "timeoutSec": 60 }
    ],
    "agentStop": [
      { "type": "command", "bash": "bash scripts/hooks/tf-guard.sh verify", "timeoutSec": 120 }
    ]
  }
}
```

### 6c. Native git hook (`.githooks/pre-commit`, no framework)

The three commit-boundary checks run from a checked-in native git hook — no Python, no
`pre-commit install`. The hook is a thin shim into the shared dispatcher:

```bash
#!/usr/bin/env bash
# .githooks/pre-commit — commit-boundary checks (vault-radar, large-files, merge-conflict)
exec scripts/hooks/tf-guard.sh commit
```

`tf-guard.sh commit` runs, over the staged set:
- `vault-radar scan git pre-commit` (its first-class client mode) when
  `VAULT_RADAR_LICENSE` is set — same invocation as today;
- a staged-file size guard (`git diff --cached` + size threshold);
- a merge-conflict-marker check.

**Distribution — the devcontainer provisions it.** `.git/hooks/` isn't cloned, so the
existing `post-create.sh` (already run via each variant's `postCreateCommand`) sets:

```bash
git config core.hooksPath .githooks
```

`core.hooksPath` points git at the tracked `.githooks/` dir, so the hook ships with the
repo and versions with it. For contributors **not** using the devcontainer, the same
one-liner is the only bootstrap step (document it in `AGENTS.md` / README, or a
`make setup`).

This also **closes the human-edit coverage gap**: anything a person edits by hand (or a
`Bash` step generates) is still caught at commit, regardless of the agent.

> Notes: `core.hooksPath` replaces the default `.git/hooks` entirely — fine here, since
> the framework (the only prior occupant) is being removed. Still bypassable with
> `git commit --no-verify`; CI remains the enforcement gate. `pre-receive` (server-side)
> or the `scan ci` mode are the only non-`pre-commit` Vault Radar options — there is no
> native `pre-push` Vault Radar mode.

## 7. What stays as-is

- **CI (`validate.yml`)** — enforcement gate; `fmt -check`, `validate`, `tflint`,
  `trivy` keep running on every PR. Unchanged.
- **`.tflint.hcl`, `trivy` config, `terraform-docs` config** — reused by the hook
  scripts; no policy duplication.

## 8. Migration plan

1. **Add** `scripts/hooks/` dispatcher + `checks/` (ported 1:1 from `.pre-commit-config.yaml`).
2. **Add** `.claude/settings.json` (Claude) and `.agents/hooks/tf-guard.json` (Copilot).
3. **Add** `.githooks/pre-commit` (native shim → `tf-guard.sh commit`) and set
   `git config core.hooksPath .githooks` in each variant's `post-create.sh`.
4. **Remove** `"disableAllHooks": true` from `.claude/settings.local.json`; prune stale
   `Bash(pre-commit ...)` allow-list entries.
5. **Soak:** keep the old `.pre-commit-config.yaml` in place and run the new hooks
   alongside it for one or two feature cycles across both agents; confirm finding parity.
6. **Delete** `.pre-commit-config.yaml` and remove the `pre-commit install` step from
   onboarding/devcontainer docs — the framework and its Python dependency are gone.
   *(This edit is currently blocked by a `deny` rule on `.pre-commit-config.yaml` in
   `settings.local.json`; lift it or make this deletion by hand.)*
7. **Update** `AGENTS.md` / `.claude/CLAUDE.md` to document the split and the
   `core.hooksPath` bootstrap for non-devcontainer users.

## 9. Risks & tradeoffs

- **Coverage gap for `Stop`-only checks:** the private-key scan and lint run on *agent*
  turns; a hand-edit committed without an agent turn is caught by the native git hook
  and CI, not the `Stop` hook. Acceptable — the git hook is the belt-and-suspenders.
- **`core.hooksPath` distribution:** the native hook only auto-applies where the
  devcontainer's `post-create.sh` runs. Non-devcontainer contributors need the one-line
  `git config core.hooksPath .githooks` bootstrap; until they run it, only CI gates them.
- **Changed-dir discovery:** `verify`/`commit` rely on `git diff --name-only`; needs to
  handle new/untracked dirs and map a changed `.tf` to its root module for `init`.
- **`init` cost at `Stop`:** first `validate`/`tflint` per module downloads providers/
  plugins. Cache in `.terraform`; run `-backend=false`. One-time per module per session.
- **Minor per-agent differences:** event names and exit-code conventions differ (§3);
  the dispatcher absorbs them so `checks/` stay single-sourced.

## 10. Recommendation

Re-home the checks and drop the framework. Move per-file checks to `PostToolUse` and
directory/tree checks to `Stop`/`agentStop` in **both** agents via one shared
dispatcher; run the commit-boundary family (secrets, large files, merge markers) from a
**native `.githooks/pre-commit`** provisioned by the devcontainer — no Python, no
`pre-commit install`. CI stays the enforcement gate. Net: faster per-file feedback, the
`pre-commit` framework removed entirely, and no loss of the commit-boundary guarantees.
