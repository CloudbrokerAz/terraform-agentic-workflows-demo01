# IBM Bob port — investigation findings

**Scope:** what it would take to run this repo's SDD workflows (module / provider / consumer /
policy) in IBM Bob, as an *additive* port — no changes to the existing Claude Code, Copilot CLI,
or Cursor packaging.

**Sources:** decompiled `bob-code` extension from
`.bob/IBM-Bob-darwin-arm64-1.121.0+bob2.0.2-insider.1.pkg` (expanded with `pkgutil --expand-full`;
all claims below verified against `extensions/bob-code/dist/extension.js` in that payload), plus a
full inventory of this repo's packaging. Bob's own embedded authoring guides (skill/mode schema
docs extracted verbatim from the binary) are saved alongside this file in
[`bob-builtin-authoring-guides.md`](bob-builtin-authoring-guides.md).

---

## TL;DR

The port is **small and low-risk**. Bob natively reads two of our three content sets:

- **All 36 skills load as-is** — Bob scans workspace `.claude/skills/{*,*/*}/SKILL.md` directly,
  and its frontmatter schema (`name`, `description`, `user-invocable`, `argument-hint`) matches
  ours field-for-field.
- **Workspace-root `AGENTS.md` is Bob's native rules file** — our orchestration and
  context-management rules load automatically.
- **MCP tool naming is identical to Claude Code** (`mcp__<server>__<tool>`), so our
  `mcp__terraform__*` references carry over verbatim; only a config-file copy is needed.

The real work is one dialect directory and a thin overlay:

| Work item | Size |
| --- | --- |
| `.bob/agents/*.md` — 19 agent dialect files (Bob does **not** read `.claude/agents/`) | ~½ day, scriptable |
| `.bob/skills/` overlay of the 8 orchestrator skills (shadow same-name `.claude` skills via precedence) | ~½ day |
| `.bob/mcp.json` (copy of `.mcp.json`, same schema) | minutes |
| `.bob/custom_modes.yaml` — optional orchestrator mode with pinned subagents | ~1 hour |
| README/docs + smoke test in a real Bob install | ~1 day |

Out of scope for the IDE: headless e2e evals (`evals/e2e/` uses `claude -p`; this package has no
headless agent CLI — that would be an IBM Bob *Shell* adapter, a separate product).

---

## 1. What Bob is

| Fact | Value |
| --- | --- |
| Product | **IBM Bob – Insiders** 1.121.0+bob2.0.2-insider.1, a VS Code fork (Electron; launcher binary `bobide-insiders`, data dir `.bobide-insiders`) |
| Agent | Bundled VS Code extension **`bob-code` v2.0.1-insider.1** (publisher IBM), ~14.8 MB minified `extension.js` |
| Lineage | Cline/Roo-Code-family architecture: task loop + **modes** + **MCP hub** + tool approval flow, with IBM additions (skills, file-defined subagents, subtasks, built-in workflows, review findings) |
| Models | Tier-based: `fast` / `premium` / `ultra` (/`explorer`). Providers seen in code: Anthropic, OpenAI, OpenRouter, Bedrock, Gemini, Vertex, xAI, DeepSeek, Ollama, IBM watsonx (`ibm.watsonx.ai`; bundled Granite model ids) |
| Extensibility | File-based: skills, agents, modes, rules, MCP. Plus internal registries (`BobSkillsRegistry`, `BobWorkflowRegistry`, `BobModeRegistry`, `BobToolRegistry`) — workflows are **built-in only** (`create_pr_workflow`, `review_workflow`); no user-definable workflow files |
| Not present | No hook system (no pre/post-tool hooks), no statusline, no headless/CLI agent mode, no plugin marketplace mechanism |

## 2. Bob's extension surface (verified)

### 2.1 Skills — `SKILL.md`, Claude-compatible

- **Workspace roots (precedence order): `.bob` > `.agents` > `.claude`**, glob
  `<root>/skills/{*,*/*}/SKILL.md` (one optional "group" folder level). First-wins dedupe by
  name: workspace > global > builtin.
- **Global roots:** `~/.bob/skills`, `~/.agents/skills`, `~/.claude/skills`.
- ⚠️ **`.agents/skills/` is NOT Bob-private — Copilot CLI reads it too.** Verified in
  `@github/copilot` v0.0.420 (`index.js`, skill-root builder): Copilot scans `.github/skills`,
  `.agents/skills` and `.claude/skills`. So a Bob dialect overlay placed in `.agents/skills/`
  would silently load into Copilot as well and shadow nothing there (different dedupe), mixing
  Bob tool names (`use_skill`, `ask_followup_question`) into Copilot sessions. **Put the Bob
  overlay in `.bob/skills/` only** (§4.2) — `.bob` is read by Bob alone and still wins the
  precedence dedupe.
- Frontmatter fields are read **either top-level or under `metadata:`** (parser checks both):
  `user-invocable`, `argument-hint`, `disable-model-invocation`, `groups`. `name` is canonically
  the directory name and must match `^[a-z0-9]+(-[a-z0-9]+)*$` (≤64 chars) — invalid names are
  **silently skipped**. `description` drives auto-invocation.
- Every skill is simultaneously a **`/<name>` slash command** and **model-invocable** via the
  `use_skill` tool (unless `disable-model-invocation`). Supporting files next to `SKILL.md`
  (our `scripts/`, `references/`) are available at activation.
- Bob also auto-migrates Claude-style `{.bob,.agents,.claude}/**/commands/*.md` into
  `.bob/skills/` (CommandMigrator) — we don't use `.claude/commands`, so not relevant.
- **`$ARGUMENTS` is NOT substituted** — the only occurrence of the string `ARGUMENTS` in the
  entire binary is a Postgres error-code constant. Slash arguments arrive as user text; skills
  referencing the literal `$ARGUMENTS` depend on model interpretation (works, but overlay copies
  should reword to "the arguments provided with the command").

### 2.2 Agents (subagents) — `.bob/agents/*.md` ONLY

- `WorkspaceAgentsManager` watches **only `<workspace>/.bob/agents/*.md`** — unlike skills,
  `.claude/agents/` and `.agents/agents/` are **not** read. This is the one hard dialect
  requirement of the port. (No global `~/.bob/agents` was observed in code.)
- Note the repo now has a real `.agents/agents/` directory (Copilot dialect files, see §6) —
  Bob still ignores it. `.agents/` is a shared *skills* root across tools, but **not** a shared
  agents root anywhere: Bob reads `.bob/agents/`, Copilot reads `.github/agents/`, Claude reads
  `.claude/agents/`. Three dialect dirs, no overlap.
- File format: YAML frontmatter + markdown body = system prompt. An optional
  `## Output Constraints` heading is split out and handled specially. Parsed by a **flat**
  line-based parser — scalar `key: value` and simple `- item` string lists only; no nested maps.
- Recognized fields (all else silently ignored — `color:`, `skills:`, `tools:` are dropped):

  | Field | Notes |
  | --- | --- |
  | `name` | id (defaults to filename) |
  | `description` | label shown to the model when choosing a subagent |
  | `groups` | tool permission groups; **default `[read, edit, execute]`** |
  | `model` | must be a tier: `fast` \| `premium` \| `ultra` (\| `explorer`); else ignored |
  | `maxTurns`, `rawPrompt`, `allowForkContext` | optional runtime knobs |
  | `allowTools` / `denyTools` | exact tool-id allow/deny lists (works with `mcp__*` ids) |

- Agents become named presets of the **`spawn_subagent`** tool:
  `spawn_subagent(description, name, fork_context)`. Verified semantics:
  - **Multiple `spawn_subagent` calls in one turn run in parallel** (matches AGENTS.md rule 4:
    parallel foreground research agents).
  - **Subagents cannot spawn subagents**, start subtasks, or start workflows
    (`SUBAGENT_FORBIDDEN_TOOLS`) — orchestration must run in the main task (which is how our
    orchestrator skills work).
  - `fork_context: true` passes parent conversation history in; results are summarized back.
  - Built-in presets: `explore` (fast read-only codebase scout, maxTurns 50) and implicit
    `general`.
  - A mode's `allowedSubagents` can pin which presets are spawnable.
- Separate sequential primitive: **`start_subtask`(title, message, todos, mode)** /
  `end_subtask` — fresh-context task chaining with a todo checklist (maps to our phase
  handoffs if ever needed; not required for the port).

### 2.3 Modes — `custom_modes.yaml`

- Workspace `.bob/custom_modes.yaml`; global `~/.bob/settings/custom_modes.yaml` (note the
  asymmetric `settings/` subdir — global file outside it silently never loads).
- Entry fields: `slug`, `name`, `roleDefinition`, `whenToUse`, `description`,
  `customInstructions`, `groups`, `allowedSubagents`.
- Permission groups (exact strings; unknown names **silently grant nothing**):
  `read`, `edit` (optionally `fileRegex`-restricted), `execute`, `mcp`, `skill`, `todo`,
  `subagent`, `mode`. Omitting `groups` on a mode gives it none of the grouped tools.
- Whole-file-drop validation traps: duplicate slug, duplicate group, invalid `fileRegex`.

### 2.4 Rules — `AGENTS.md` is native

- Rule loader reads, per workspace: **workspace-root `AGENTS.md`**, `.bob/rules/` (common),
  `.bob/rules-{mode}/` (per mode: `rules-agent`, `rules-plan`, `rules-ask`), plus the global
  `~/.bob/rules*` equivalents. `CLAUDE.md` is **not** loaded as rules.
- ⇒ Our root `AGENTS.md` (shell-safety, workflow entry points, context management) applies in
  Bob with zero work. Its Claude-specific lines ("NEVER call TaskOutput") read as harmless
  no-ops for Bob models but could be generalized someday (out of scope for an additive port).

### 2.5 MCP — same tool naming as Claude Code

- Config: workspace **`.bob/mcp.json`**, global `~/.bob/settings/mcp.json`; `mcpServers`
  key with `command`/`args`/`env` for stdio servers (Cline-compatible schema). Nested-folder
  overrides supported; per-server `groups` restriction and `alwaysAllow` supported.
- **No `${VAR}` expansion** — values are stored verbatim/plaintext. Our `.mcp.json` needs no
  expansion (docker `-e TFE_TOKEN` inherits the process env), so it copies over cleanly.
- Tools surface as **`mcp__<server>__<tool>`** — byte-identical convention to Claude Code, so
  agent `allowTools` pins like `mcp__terraform__search_private_modules` work unchanged provided
  the server keys in `.bob/mcp.json` keep the same names (`terraform`,
  `aws-knowledge-mcp-server`/`aws-documentation-mcp-server` — mind the repo's existing
  aws-knowledge vs aws-documentation naming mismatch; pin whichever the agents reference).

### 2.6 Built-in tool inventory (for translating skill/agent bodies)

| Claude Code | Bob | Notes |
| --- | --- | --- |
| `Read` | `read_file` | also `read_xlsx` |
| `Write` | `write_file` | |
| `Edit` | `apply_diff`, `insert_content`, `search_and_replace` | |
| `Glob` | `glob` | same name |
| `Grep` | `grep` | same name; also `list_files` |
| `Bash` | `execute_command` | user-configurable command allow/deny lists |
| `AskUserQuestion` | `ask_followup_question` | always auto-approved |
| `TodoWrite` | `update_todo_list` | |
| `Skill` | `use_skill` | |
| `Task` (subagents) | `spawn_subagent` | parallel per-turn; no nesting |
| — | `start_subtask` / `end_subtask` | sequential fresh-context chaining |
| — | `switch_mode`, `start_workflow`, `create_html_artifact`, `search_bob_docs`, `submit_review_findings` | Bob-specific |
| `TaskOutput` | n/a | subagents return summaries; our "artifacts on disk + verify via Glob" contract still applies |
| `run_in_background` | n/a | no background subagents; parallel foreground is the default |

Approval model: per-tool approval prompts with "always allow", plus command allow/deny lists for
`execute_command`. `ask_followup_question`, `start_workflow`, `create_html_artifact` are
always-allowed. No checked-in workspace allowlist file — approvals are per-user settings, so the
Bob README section should list the commands to pre-approve (`terraform`, `tflint`, `trivy`,
`gh`, `git`, `.foundations/scripts/bash/*.sh`, `docker`, `uvx`).

---

## 3. Compatibility matrix (repo → Bob)

| Repo component | Bob mechanism | Verdict |
| --- | --- | --- |
| 36 skills in `.claude/skills/` | native `.claude` skill root | ✅ **load as-is** — all names pass Bob's regex; frontmatter fields match exactly |
| 8 orchestrator skills' Claude-isms (`AskUserQuestion` ×9 in the four `*-plan` skills, `TaskOutput` ×1, `run_in_background` ×1, `$ARGUMENTS`, `Glob` mentions) | `.bob/skills/` overlay shadows same-name `.claude` skill (precedence `.bob` > `.claude`) | 🟡 **small overlay** — copy + ~10–20 line dialect edits each; existing files untouched |
| 21 agents in `.claude/agents/` | **not read** — needs `.bob/agents/*.md` | 🔴 **dialect dir required** (19 files; skip CI-only `module-upgrade-remediation`, `tf-e2e-judge`, mirroring the Copilot port) |
| Agent `tools:` allowlists | `groups` + `allowTools` (`mcp__*` ids identical) | ✅ mechanical translation |
| Agent `skills:` preload | not parsed — add "use skill X" body line + `skill` group | ✅ same trick the Copilot dialect already uses |
| Agent `model: opus` | `model: premium` (or `ultra`) | ✅ tier mapping |
| Root `AGENTS.md` | native rules file | ✅ zero work |
| `.foundations/` constitutions, templates, scripts | plain file reads / `execute_command` | ✅ zero work (repo/template-level; no manifest carries them on any platform) |
| `.mcp.json` (terraform + AWS docs servers) | `.bob/mcp.json`, same `mcpServers` schema | ✅ copy |
| Checkpoint/progress scripts (`checkpoint-commit.sh`, `post-issue-progress.sh`) | invoked from skill text via `execute_command` | ✅ portable (they're not hooks) |
| Claude plugin hooks/statusline | no hook system in Bob | ⚪ n/a — nothing to port |
| Plugin/marketplace distribution | none in Bob | ⚪ Bob support = in-repo directories (this repo already doubles as a working template) |
| `evals/e2e/` headless evals | no headless mode in the IDE | 🔴 gap — would need an IBM Bob **Shell** adapter under `evals/e2e/adapters/` (separate effort) |

## 4. The port, concretely

### 4.1 `.bob/agents/` — 19 dialect agent files (the only hard requirement)

Template (translation of `tf-module-research`):

```markdown
---
name: tf-module-research
description: Investigate cloud service provider resources via docs, Terraform provider docs, and registry patterns. Each instance answers ONE research question. Use during planning phase to resolve resource behavior, best practices, and architectural unknowns.
model: premium
groups:
  - read
  - edit
  - execute
  - mcp
  - skill
allowTools:
  - mcp__terraform__search_modules
  - mcp__terraform__get_module_details
  - mcp__terraform__search_private_modules
  - mcp__terraform__get_private_module_details
  - mcp__terraform__search_providers
  - mcp__terraform__get_provider_details
  - mcp__aws-knowledge-mcp-server__aws___search_documentation
  - mcp__aws-knowledge-mcp-server__aws___read_documentation
---

First call `use_skill` with `skill_name: "tf-research"` to load research strategies.

<body copied from .claude/agents/tf-module-research.md>

## Output Constraints
Write findings to `specs/{FEATURE}/research-{slug}.md`; return only a one-paragraph summary.
```

Rules for the conversion (scriptable):
- `tools:` → `groups:` (`Read/Grep/Glob`→`read`, `Write/Edit`→`edit`, `Bash`→`execute`,
  any `mcp__*`→`mcp`, `Skill`→`skill`) + keep the exact `mcp__*` ids under `allowTools:`.
- `skills:` list → `use_skill` instruction line(s) at the top of the body (Copilot-port
  precedent: its dialect files start with "use skill tf-research").
- `model: opus` → `premium` (orchestrator-critical agents — design/developer/validator — could
  use `ultra` if the configured provider offers it); drop `color:`.
- Frontmatter must stay **flat** (scalars + string lists) — Bob's parser handles nothing nested.
- Optionally move each agent's "write to disk, return summary" contract into the
  `## Output Constraints` section Bob treats specially.

### 4.2 `.bob/skills/` — overlay the 8 orchestrators

Because `.bob` wins the name-dedupe over `.claude`, placing an edited copy at
`.bob/skills/tf-module-plan/SKILL.md` shadows the original for Bob **without touching it** —
Claude Code doesn't read `.bob/`, so the platforms stay isolated. Edits per file:

- `AskUserQuestion` → `ask_followup_question` (9 call sites across the four `*-plan` skills).
- "Launch N concurrent `tf-X-research` subagents (parallel foreground Task calls)" →
  "spawn N parallel `spawn_subagent` calls with `name: "tf-X-research"` in a single turn".
- `TaskOutput` prohibition (tf-policy-implement) → "never rely on the subagent's returned
  summary for content — verify `specs/{FEATURE}/…` files exist with `glob`".
- `$ARGUMENTS` → "the arguments provided with the slash command".
- Leave everything else (phases, scripts, checkpoints, constitutions) untouched — it's
  platform-neutral.

Knowledge skills (26) need **no** overlay — they're procedural/reference content with no
Claude-specific tool names, and Bob loads them from `.claude/skills/` directly. The 2 e2e
harness skills should be skipped (headless-coupled).

### 4.3 `.bob/mcp.json`

Copy of `.mcp.json` (`mcpServers` schema is compatible: `command`/`args`/`env`). Keep server
key `terraform` so `mcp__terraform__*` ids resolve; add the AWS docs server under the name the
agents actually pin (`aws-knowledge-mcp-server` in Claude agents vs
`aws-documentation-mcp-server` in root `.mcp.json` — resolve to one name in the Bob files).
`TFE_TOKEN` must be present in Bob's process environment (no `${VAR}` expansion exists).

### 4.4 `.bob/custom_modes.yaml` (optional but recommended)

A `tf-orchestrator` mode as guardrails for the implement phases:

```yaml
customModes:
  - slug: tf-orchestrator
    name: Terraform SDD Orchestrator
    roleDefinition: >-
      You orchestrate the SDD workflows. You dispatch subagents and verify their
      artifacts exist on disk; you never write Terraform code yourself and never
      read artifact contents into your own context.
    whenToUse: Running /tf-module-plan, /tf-module-implement and the other SDD entry points.
    groups: [read, edit, execute, mcp, skill, todo, subagent]
    allowedSubagents: [tf-module-research, tf-module-design, tf-module-test-writer,
      tf-module-developer, tf-module-validator, tf-provider-research, tf-provider-design,
      tf-provider-test-writer, tf-provider-developer, tf-provider-validator,
      tf-consumer-research, tf-consumer-design, tf-consumer-developer, tf-consumer-validator,
      tf-policy-research, tf-policy-design, tf-policy-test-writer, tf-policy-developer,
      tf-policy-validator]
```

(Watch the traps in §2.3: exact group strings, unique slug, ASCII only.)

### 4.5 Docs & housekeeping

- README "Install as a plugin" gains an **IBM Bob** subsection: clone the template, open in
  Bob → skills auto-load from `.claude/skills/` (Bob-dialect orchestrators from
  `.bob/skills/`), agents from `.bob/agents/`, MCP from `.bob/mcp.json`; recommended command
  approvals; models: configure a premium-tier provider.
- Add `.bob/*.pkg` to `.gitignore` (the 211 MB installer shouldn't be committed); the rest of
  `.bob/` (agents/skills/mcp.json/custom_modes.yaml + these findings) is checked in as the
  fourth platform packaging.
- AGENTS.md component inventory: add the Bob dialect dirs (note: AGENTS.md is live context in
  Bob, so keep additions lean).

## 5. Risks & open questions

1. **`$ARGUMENTS` / slash-arg mechanics** — not substituted by Bob; exact delivery of `/cmd args`
   text needs one interactive test. Mitigated by rewording in the overlays.
2. **Global agents** — only workspace `.bob/agents/` was found in code; if per-user agents are
   wanted, that needs testing on a live install.
3. **Model quality** — the workflows are tuned for Opus-class models. Bob's behavior depends
   entirely on the configured provider/tier; Granite-class models may struggle with the long
   orchestrations. Recommend documenting Anthropic/Bedrock `premium`+ for orchestrator,
   design, developer, and validator agents.
4. **Cost/turn budgets** — Bob tasks carry `maxTurns`/`maxCost` budgets that can pause long
   implement phases with warnings; users may need to raise defaults.
5. **Insider churn** — this is an insider build (2.0.2-insider.1); the skill/agent/mode file
   contracts look stable (they ship with authoring guides) but could shift between builds.
6. **Skill `groups` frontmatter** — exists in the parser; semantics (restricting tools while a
   skill is active) unverified. Not needed for the port.
7. **Subagent no-nesting** — orchestrator skills must run in the main task. They do today; the
   e2e harness pattern (skill → orchestrator) must also stay in the main task if ever ported.

## 6. Repo layout change (2026-07-20) — `.agents/` now exists

Independently of the Bob port, the Copilot dialect **agent** files moved to a canonical
location, with `.github/agents` kept as a symlink:

```
.agents/agents/*.md   (19 Copilot dialect agent files)   <- .github/agents  (symlink)
.github/hooks/*.json  (2 Copilot hook configs)           real directory, not moved
```

Hooks deliberately stayed put. `.agents/` earns its keep only for content more than one harness
reads; hooks are Copilot-only (Bob has no hook system at all — see §2), so a canonical dir plus
symlink would have been indirection with no second consumer.

Verified by reading the Copilot CLI implementation rather than the docs, on **two** versions —
the previously installed `@github/copilot` **v0.0.420** (single `index.js` JS bundle) and, after
`npm i -g @github/copilot@latest`, **v1.0.70**. The 1.x line is a different architecture: a
per-platform native package (`@github/copilot-darwin-arm64`) with `app.js` plus Rust-backed
`runtime.node`, where convention-directory resolution runs through a **native fast path**
(`configLoaderCollectConventionDirs`). Discovery roots are identical across both versions:

- **Repo hooks load from exactly one path.** v0.0.420: `join(gitRoot,".github","hooks")` globbed
  `**/*.json`. v1.0.70: `getHooksDir()` → `join(gitRoot,".github","hooks")`. No `.agents/hooks`
  code path in either.
- **Project agents load from two roots only.** v1.0.70 states it as a literal convention table —
  `[{convention:".github"},{convention:".claude"}]` with component `"agents"`. No `.agents/agents`
  code path in either version.
- **Skills are the exception** — `.github/skills`, `.agents/skills`, `.claude/skills`; v1.0.70's
  own `/skills` help text repeats all three (see the warning in §2.1).
- **The agents symlink works in both implementations.**
  - v0.0.420 (JS): agents use `readdir(dir,{withFileTypes:true})`,
    which resolves the symlinked dir (19 entries, all `isFile()`); the loader also explicitly
    stats symlinked *files*.
  - v1.0.70 (native): calling `runtime.node`'s `configLoaderCollectConventionDirs` directly
    against this repo returns both `.github/agents` and `.github/hooks`. Control cases
    (`.nope/agents`, `.github/nosuch`) return empty, proving it stats real directories rather
    than string-joining — so the native path follows the symlink too. Stronger still, the
    agent-file glob inside that root is called with `{follow:true}`, an explicit symlink opt-in
    rather than an incidental one.
  - Note the v0.0.420 evidence above is no longer reproducible — that version has been replaced
    by 1.0.70 locally. The 1.0.70 evidence is the live, checkable one.
- **Correction to the public docs:** Copilot does *not* require the `.agent.md` extension. The
  loader globs `**/*.md` and tags `isAgentMd` for the `.agent.md` spelling, then
  `customAgentsResolveFilesByPriority` picks a winner per id. Called directly with
  `[foo.md, foo.agent.md, bar.md]` it returns `foo.agent.md` and `bar.md` — so plain `.md` is
  accepted and `.agent.md` only wins a collision. Our plain `.md` files are fine.
- **Not verified:** a live end-to-end `copilot` session. This org's policy blocks headless runs
  ("Access denied by policy settings") and disables third-party MCP servers, so verification
  stops at the loader level. The Copilot **cloud agent** is server-side and likewise unverifiable
  here; it clones with git, which preserves symlinks, so it should behave the same — inference,
  not evidence.

Consequences for the Bob port: none to the plan above — Bob reads neither `.agents/agents/`
nor `.github/`, and the `.bob/` dialect dirs are unaffected. Three knock-ons worth remembering:
`.agents/skills/` is now a live shared root (don't put Bob overlays there); the `.gitignore`
line in §4.5 for `.bob/*.pkg` is still outstanding; and this org's Copilot policy disables
**third-party MCP servers** in the CLI ("Only built-in servers are available") — so the
`mcp__terraform__*` tooling the workflows depend on is currently unusable on the Copilot path,
which strengthens the case for the Bob (or Claude Code) route where MCP is locally configured.

## 7. Effort summary

| Item | Effort |
| --- | --- |
| Conversion script + 19 `.bob/agents/` files | ~½ day |
| 8 orchestrator skill overlays in `.bob/skills/` | ~½ day |
| `.bob/mcp.json`, `.bob/custom_modes.yaml`, `.gitignore` | ~1 hour |
| README/AGENTS.md docs | ~1–2 hours |
| Interactive smoke test on a live Bob install (skills load, `/tf-module-plan` end-to-end with a premium model, MCP servers up, parallel research spawn) | ~1 day |
| (Separate, optional) Bob Shell adapter for `evals/e2e/` | not scoped here |

Total for a working Bob port of the interactive workflows: **≈ 2–3 days**, of which the majority
is validation on a real install rather than authoring.
