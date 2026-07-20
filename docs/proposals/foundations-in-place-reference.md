# Proposal: Reference `.foundations/` from the plugin cache instead of copying it

## Problem

The plugin's skills, agents, and scripts reference `.foundations/…` as bare,
repo-relative paths. When the plugin is installed into a consuming repo, those
paths resolve against the consumer's cwd, where `.foundations/` doesn't exist.
The current workaround (`README.md:100`) is to **copy** `.foundations/` into
every consuming repo — which forks the constitutions/templates/scripts away from
the versioned, centrally-maintained plugin and defeats the point of shipping
them as a plugin.

## Goal

Make `.foundations/` resolve to the **installed plugin's own copy in the
versioned cache**, with no per-repo duplication and no edits to the ~40 existing
`.foundations/…` references.

## Key constraints discovered

- `.foundations/` is **read/execute-only** in the real workflow (the sole write
  reference is a comment example in `checkpoint-commit.sh:34`; all generated
  artifacts land in the repo-root `specs/`). So in-place referencing is safe.
- Plugin-root resolution differs by harness and by component. Per the Claude
  Code plugins reference, **skill and agent content substitutes
  `${CLAUDE_PLUGIN_ROOT}` anywhere it appears** — so on Claude Code a workflow
  skill can resolve the plugin root itself, no hook required. Copilot expands
  `${PLUGIN_ROOT}` only in `plugin.json` config fields (not skill content);
  Cursor documents no plugin-root token for content. Those two still need a
  hook.

## Proposed change

**Trigger the link on workflow invocation, not on every session.** Each
`/tf-*-plan` and `/tf-*-implement` skill gains a one-line bootstrap as its first
step, before any `.foundations/…` path is touched:

```bash
LINK="${CLAUDE_PLUGIN_ROOT}/scripts/link-foundations.sh"; [ -f "$LINK" ] && bash "$LINK" || true
```

`scripts/link-foundations.sh` creates a **gitignored symlink**
`.foundations → <plugin>/.foundations` (registered in the consumer's
`.git/info/exclude`, not a committed `.gitignore`, since in this repo
`.foundations/` is the real tracked source).

- **Scoped to actual use** — nothing runs in unrelated sessions; the plugin's
  `/` commands stay available everywhere but inert until invoked.
- **Pointer, not copy** — targets the exact versioned install; plugin upgrades
  re-point on next run. Single source of truth preserved.
- **Zero reference edits** — every existing bare `.foundations/…` path keeps
  resolving because, from cwd, `.foundations` now *is* the cache.
- **Safe in the template repo** — the `[ -f "$LINK" ]` guard makes the bootstrap
  a no-op when `${CLAUDE_PLUGIN_ROOT}` is unset (dev/template mode, where a real
  `.foundations/` already exists).

## Scope of work

1. `scripts/link-foundations.sh` — self-locating resolver + non-destructive
   symlink + `.git/info/exclude` registration. **Done.**
2. One-line bootstrap step in the 8 workflow skills (4 plan + 4 implement).
   **Done.**
3. Copilot / Cursor: deliver the same link via a **scoped hook** (fire on
   workflow-tool invocation, not `SessionStart`), since neither substitutes its
   plugin-root token in skill content. **Follow-up — needs live smoke tests.**
4. `README.md` update: replace the "copy `.foundations/`" instruction with the
   auto-link behavior. **Pending.**

## Fallback

`scripts/link-foundations.sh` can also be run by hand (`/tf-workflows:init`-style)
for contexts with no plugin env — air-gapped CI, or a consumer that vendored a
real `.foundations/`. The bootstrap guard makes both safe.

## Open items

- **Copilot / Cursor**: wire and smoke-test the scoped hook (Copilot event
  name + auto-discovery; Cursor plugin-delivered hook support + file location).
- **Windows consumers**: `ln -s` may be unavailable; may need a copy fallback.

## Risks

Low. No changes to workflow logic or the ~40 references; the bootstrap is one
guarded line per entry skill and a no-op outside plugin installs. Worst case
(root unresolved) links nothing and the manual fallback still applies.

## Implementation status (branch `feat/foundations-in-place-reference`)

| Piece | Status |
|-------|--------|
| `scripts/link-foundations.sh` — self-locating resolver + symlink + git-exclude | **Done, unit-tested** (fresh link, idempotent re-run, stale-link refresh, real-dir left untouched, no-var no-op, SRC==DEST no-op, Copilot/Cursor dest vars, exclude add-once) |
| Bootstrap line in 8 workflow skills (Claude Code) | **Done** — `claude plugin validate .` passes; command fragment tested in both plugin mode (links) and template/dev mode (clean no-op) |
| Copilot CLI + Cursor (scoped hook) | **Follow-up** — not wired yet; needs live smoke tests |
| `README.md` update | Pending |

Design note: the resolver **self-locates its own plugin root via `BASH_SOURCE`**,
so the bootstrap works even where no plugin-root env var exists; the env vars
(`CLAUDE_PLUGIN_ROOT` / `PLUGIN_ROOT` / `CURSOR_PLUGIN_ROOT`) are only a fallback.
The `SessionStart` hook explored earlier was dropped: it ran on every session
regardless of whether the workflows were used, dropping a `.foundations` symlink
into unrelated repos.
