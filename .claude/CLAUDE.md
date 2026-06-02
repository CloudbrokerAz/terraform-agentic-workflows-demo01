# CLAUDE.md

## Primary Reference

See the root `/workspace/AGENTS.md` for the main project documentation, workflow phases, and agent/skill inventory.

## Skill testing with waza (local) — WIP, deferred

We use [microsoft/waza](https://github.com/microsoft/waza) (`waza` v0.33, installed at
`/usr/local/bin/waza`) to evaluate the `.claude/skills/` SKILL.md files locally.

Status / how it's wired:
- `waza init --skills-dir .claude/skills --evals-dir evals` scaffolded eval suites for
  all 33 skills under `evals/<skill>/` (eval.yaml + tasks/ + fixtures/). Tasks are still
  generic placeholders — need tailoring to real per-skill prompts before results are meaningful.
- `waza check <skill>` (free, static) works today: compliance score, agentskills.io spec
  checks, token budget. Note two Claude-Code-vs-waza mismatches it flags: the `user-invocable`
  frontmatter field is "unknown" to the agentskills.io spec, and waza's default SKILL.md hard
  limit is 500 tokens (our skills run larger).

Cost / backend constraint:
- **`claude -p` (Claude Code headless) incurs metered Anthropic API cost — do NOT use it as
  the eval runtime.** waza has only two executors: `copilot-sdk` and `mock` (no generic
  exec/CLI executor).
- waza reaches any **OpenAI-compatible endpoint** via the copilot-sdk BYOK path (setting
  `COPILOT_BASE_URL` fully bypasses GitHub Copilot auth):
  ```bash
  COPILOT_BASE_URL=http://localhost:11434/v1 COPILOT_PROVIDER=openai COPILOT_API_KEY=x \
    waza run evals/<skill>/eval.yaml --model qwen2.5-coder:14b
  ```
  Proven end-to-end against **local Ollama** (free) — harness wiring works; model-call errored
  on first run (likely `COPILOT_WIRE_API` completions/responses handshake) — needs a debug pass.

DEFERRED — Bob Shell as the eval runtime:
- Goal: drive **IBM Bob Shell** (`/opt/homebrew/bin/bob`, agentic CLI, one-shot via positional
  prompt + `--chat-mode ask --hide-intermediary-output`) as waza's model backend so eval runs
  are covered by the IBM license rather than Anthropic API.
- Blocker: Bob is CLI-only (no OpenAI-compatible `serve` mode), and waza can't wrap a raw CLI.
  Bridge needed = a ~30-line OpenAI-compatible shim (`/v1/chat/completions` + `/v1/models`)
  that shells out to `bob` and returns the final output; then point `COPILOT_BASE_URL` at it.
- Caveat: Bob is its own agent (not Claude Code) and won't natively load `.claude/skills/`;
  waza injects the skill into the request, so this tests SKILL.md *content/triggering*, not
  Claude Code runtime loading.
