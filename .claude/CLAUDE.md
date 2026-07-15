# CLAUDE.md

## Primary Reference

See the root `AGENTS.md` for the main project documentation: workflow entry
points, orchestration rules, constitutions, and context management. The full
agent/skill inventory lives in its "Component Inventory" section.

## E2E workflow evals — `evals/e2e/`

End-to-end evals for the module/consumer workflows live in `evals/e2e/`
(see `evals/e2e/README.md`). Each case runs a full plan→implement cycle
headlessly in a throwaway GitHub repo, applies deterministic checks plus an
independent judge agent (`.claude/agents/tf-e2e-judge.md`, reusing
`tf-judge-criteria`), always destroys consumer sandbox deployments, and renders
a self-contained HTML report (wall time, cost, quality). `--adapter mock` runs
the whole pipeline for $0. E2E runs use `claude -p` as the runtime (metered API
cost); the runtime sits behind `evals/e2e/adapters/` so other agent CLIs can be
slotted in.

## Plugin packaging

The repo doubles as an installable plugin for Claude Code
(`.claude-plugin/`), GitHub Copilot CLI (`.github/plugin/`), and Cursor
(`.cursor-plugin/`) — see "Install as a plugin" in the README. Run
`claude plugin validate .` after changing skills, agents, or manifests.
Copilot rejects skill descriptions over 1024 characters; keep frontmatter
descriptions under that.

## Per-skill testing with waza — deferred idea, NOT in use

Nothing in this repo uses [microsoft/waza](https://github.com/microsoft/waza)
today: no scaffolds are committed, no CI integration exists, and the earlier
local experiments were not adopted. If per-skill evals are revisited: waza has
only `copilot-sdk` and `mock` executors (no generic CLI executor); its
copilot-sdk BYOK path can reach any OpenAI-compatible endpoint via
`COPILOT_BASE_URL` (proven wired against local Ollama, model handshake still
unresolved), and wrapping a CLI-only agent (e.g. IBM Bob Shell) would need a
small OpenAI-compatible HTTP shim. Note waza validates SKILL.md against the
agentskills.io spec, which flags our `user-invocable` field as unknown and
enforces a 500-token default budget our skills exceed.
