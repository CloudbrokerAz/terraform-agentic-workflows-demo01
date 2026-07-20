# Bob built-in authoring guides (extracted)

> Verbatim contents of the `create-skill`, `create-mode`, and `create-plan` built-in skills,
> extracted from `bob-code` v2.0.1-insider.1 (`dist/extension.js` in the expanded
> `IBM-Bob-darwin-arm64-1.121.0+bob2.0.2-insider.1.pkg`). These are Bob's authoritative
> schema docs for `SKILL.md` and `custom_modes.yaml` — kept here as reference for the port.



===== CREATE_A_SKILL_CONTENT =====

# Create a Bob Skill

Guide the user through authoring a new Bob skill — a self-activating procedural guide stored as a
`SKILL.md` file. Follow these steps in order.

## Step 0 — Decide Whether a Skill Is the Right Fit

Before gathering requirements, apply judgment — a good skill is small, focused, and reusable, and
not every request should become one. Evaluate these, and push back on the user where they don't hold:

- **Is a skill even the right tool?** Skills are for recurring, procedural workflows that benefit
  from self-activation. A one-off task, or something the model already handles well unprompted, does
  not need a skill. If a mode (persona + tool permissions) or just a well-worded prompt fits better,
  say so.
- **Is it one focused capability?** Each skill should do one thing well. If the request spans several
  distinct workflows, propose splitting it into smaller skills that **compose**, rather than one
  sprawling skill.
- **Is it the right size?** A skill that balloons into hundreds of lines of branching instructions is
  a sign the scope is wrong. Keep the body tight and procedural; move bulky reference material into
  supporting files (see Step 4 notes) instead of inlining everything.

Raise these concerns with the user now — do not silently scaffold an over-scoped or unnecessary skill.

## Step 1 — Gather Requirements

Use the `ask_followup_question` tool to understand the skill before writing anything:
- **What should the skill do?** What task or workflow does it guide the model through?
- **When should it activate?** What user phrasing or situation should trigger it? (This becomes the
  description — the single most important field.)
- **Scope:** Global (available in every workspace) or workspace (only this project)?
- **Invocation:** By default a skill is *both* a `/<skill-name>` command **and** auto-invoked by Bob
  whenever its description matches — this is almost always what you want, so it needs no config. The
  only choice worth raising: should it instead run **only** when the user explicitly types
  `/<skill-name>` (no auto-invocation)? That maps to the "Allow Bob to use this skill" toggle
  (`metadata.disable-model-invocation`, see Step 3).

If the answers reveal the skill is really several workflows, return to Step 0 and propose splitting
it before continuing.

## Step 2 — Choose and Validate the Name

The canonical name comes from the **directory** that contains `SKILL.md`, and the directory name
must match:

```
^[a-z0-9]+(-[a-z0-9]+)*$        (lowercase, digits, single dashes between words)   max 64 chars
```

⚠️ **Validation is silent.** An invalid name (uppercase, underscores, spaces, leading/trailing or
doubled dashes) causes the skill to be **skipped with no error**. Confirm the final name with the
user before writing.

## Step 3 — Draft the Frontmatter and Body

A normal skill needs only two frontmatter fields: `name` and `description`. That's it — keep it
simple.

```markdown
---
name: security-review
description: Use when the user wants to review a PR for security issues — walks through auth, input validation, and secrets handling.
---

# Security Review

Follow these steps to review the pull request...
```

- **`name`** — match the directory name. (It's technically inferred from the directory, but writing
  it explicitly is the convention.)
- **`description`** — **the trigger.** This is what drives auto-activation, so write it with
  concrete trigger phrases ("Use when the user wants to…"), not vague intent. If omitted, the first
  body line is used as a fallback, but an explicit description is much better.

The body is the procedural content the model follows when the skill activates. Write it like the
`create-plan` skill: clear, step-numbered, and naming the actual Bob tools to use
(`ask_followup_question`, `write_file`, etc.).

### Optional: advanced `metadata` fields

Most skills need none of these — the default (both a `/` command and auto-invoked by Bob) is
usually right. Add a `metadata:` block only to change that:

| Field | Default | Notes |
|---|---|---|
| `metadata.disable-model-invocation` | `false` | `true` ⇒ Bob will **not** auto-invoke it; it runs only when the user types `/<skill-name>`. This is the "Allow Bob to use this skill" toggle in settings. |
| `metadata.argument-hint` | — | Autocomplete hint shown after `/skill-name`, e.g. `"[issue-number]"`. |
| `metadata.user-invocable` | `true` | Advanced: `false` ⇒ agent-only (no `/` command), but Bob can still auto-invoke it. Rarely wanted for user skills; this is how built-ins like `create-plan` work. |

## Step 4 — Decide Whether Supporting Scripts Are Needed

Before writing any files, evaluate whether the skill's workflow involves steps that are better
handled by a script than by Bob reasoning through them freeform each time.

**Reach for a supporting script when the skill needs to:**
- Fetch or transform data from an external source (APIs, databases, files)
- Parse structured output into a consistent format (JSON, CSV, XML)
- Run a sequence of shell commands and return a single clean result
- Generate boilerplate or scaffolding from a template
- Perform any logic where free-form model reasoning would produce inconsistent results

**Keep it in prose instructions when:**
- The steps are simple, linear, and tool-call based
- The output is open-ended (summaries, explanations, plans)
- There is no external data to fetch or process

If a script is warranted, write it alongside `SKILL.md` in the same skill directory. The
`SKILL.md` body should then instruct Bob to run the script using `execute_command` and act on its
output, rather than trying to replicate the logic in natural language.

A script can be in any language the user's system supports — shell, Python, Node.js, etc. Keep it
focused: one script, one responsibility. If the skill needs multiple distinct data-gathering steps,
prefer multiple small scripts over one large one.

Example layout:
```
.bob/skills/my-skill/
  SKILL.md          ← procedural instructions that call the script
  fetch-data.sh     ← does the programmatic work, prints structured output
```

## Step 5 — Write the Files

Place `SKILL.md` in a directory named exactly after the skill. Use the `write_file` tool. Write
any supporting scripts to the same directory in the same step.

**Always default to the `.bob` folder.** It's the canonical Bob location and makes onboarding
straightforward for new users:

```
Global:    ~/.bob/skills/<skill-name>/SKILL.md
Workspace: .bob/skills/<skill-name>/SKILL.md
```

Only use `.agents` or `.claude` instead if the user's workspace clearly shows they are already
working in that ecosystem (e.g. an existing `.agents/` or `.claude/` directory with content).
Never mention or suggest these alternatives unprompted — the goal is a smooth first-run experience,
not a folder-choice decision for someone just getting started.

If the user does use an alternative root, the precedence order is .bob > .agents > .claude, and the
same sub-path applies: `<root>/skills/<skill-name>/SKILL.md`.

## Step 6 — Confirm

Tell the user the skill will be available in the **next task** — start a new conversation to use it.
If it does not appear, the most likely cause is an invalid name (Step 2); re-check the name against
the regex.

## Notes for power users

- **First-wins deduplication by name:** workspace > global > builtin. A workspace skill silently
  overrides a global one with the same name.
- **Grouped skills:** a skill may live one level deeper inside a "group" folder
  (`skills/<group>/<skill-name>/SKILL.md`). The name still comes from the immediate parent
  directory, not the group folder. Useful for organizing many related skills.
- **Supporting files:** any file placed alongside `SKILL.md` is available to the skill at
  activation time — scripts, static reference data, templates, etc.

## Reminders

- Always ask questions using the `ask_followup_question` tool.
- Confirm the final name and scope with the user before writing.
- Never include information without evidence.



===== CREATE_A_MODE_CONTENT =====

# Create a Bob Mode

Guide the user through authoring a new custom mode — a persona with its own system prompt and tool
permissions, defined as an entry in `custom_modes.yaml`. Follow these steps in order.

## Step 1 — Gather Requirements

Use the `ask_followup_question` tool before writing anything:
- **Purpose & persona:** What is this mode for? What role/behavior should it embody? (This becomes
  `roleDefinition` — the primary differentiator. Push for a focused, specific persona, not a
  generic one.)
- **Tool access:** What should it be allowed to do — read files, edit files, run commands, use the
  browser, use MCP servers? (This maps to `groups`.)
- **Scope:** Global (available in every workspace) or workspace (only this project)?
- **Display details:** A human-readable `name` for the picker, and optionally `whenToUse`
  (tooltip) and a short `description`.

## Step 2 — Choose and Validate the Slug

The `slug` is the mode's unique identifier. It must match:

```
^[a-zA-Z0-9-]+$        (letters, digits, and dashes only — no underscores, no spaces)
```

⚠️ **Keep slugs unique — avoid reusing one.** A duplicate slug *within the same file* fails schema
validation and the **entire file is dropped** (no modes load from it). Reusing a slug that already
exists in another scope is also best avoided — one entry will silently shadow the other. Before
writing, read the target file (Step 4) and confirm the slug isn't already taken.

## Step 3 — Draft the YAML Entry

Each mode is one object under the top-level `customModes` array. Fields:

| Field | Required | Notes |
|---|---|---|
| `slug` | ✅ | Unique id, regex above. |
| `name` | ✅ | Display name shown in the mode picker. |
| `roleDefinition` | ✅ | Core system prompt / persona. Where most design effort goes. |
| `whenToUse` | No | Tooltip in the mode picker. |
| `description` | No | Short description. |
| `customInstructions` | No | Appended to the system prompt after `roleDefinition`. |
| `groups` | No | Tool permission groups (see below). **List explicitly** — omitting `groups` gives the mode *none* of the grouped tools (it can't read, edit, run commands, etc.), **not** full access. |
| `allowedSubagents` | No | **Trap:** if set, restricts sub-agent spawning to only the named presets. Omit unless you specifically need that restriction. |


### Tool permission groups

The supported group values are:

| Group | Allows |
|---|---|
| `read` | File reading and symbol lookup |
| `edit` | File writing and modification |
| `execute` | Shell command execution |
| `mcp` | MCP server tools |
| `skill` | `use_skill` tool (load skill instructions) |
| `todo` | `update_todo_list` tool |
| `subagent` | `spawn_subagent` tool |
| `mode` | `switch_mode` tool |

A group can carry a `fileRegex` restriction (tuple form):

```yaml
groups:
  - read
  - - edit
    - fileRegex: ".*\\.md$"   # this mode may only edit markdown files
```

⚠️ **Use only the exact group names above.** Group names are free-form strings to the schema, so an
unrecognized value (e.g. `command` instead of `execute`, or `write`, `shell`, `run`) is
**not** a validation error — the file loads fine, but that line matches no tool and **silently grants
nothing**. The result is a mode quietly missing a capability you thought you granted, with no error
anywhere. Double-check each group against the table; the most common slip is `command` for shell
access, which must be `execute`.

⚠️ Two validations beyond the slug rule will drop the whole file if violated: **duplicate group
names** are rejected, and any `fileRegex` must **compile as a valid regular expression**.

Example entry:

```yaml
customModes:
  - slug: docs-writer
    name: Docs Writer
    roleDefinition: >-
      You are a technical writer who produces clear, concise documentation.
      You favor examples over prose and never edit source code.
    whenToUse: Use when writing or revising documentation.
    groups:
      - read
      - - edit
        - fileRegex: ".*\\.(md|mdx)$"
```

⚠️ **Use plain ASCII.** The loader strips problematic unicode (curly quotes " " ' ', em/en
dashes, non-breaking spaces) — copy-pasting YAML from a rich editor often introduces these. Type
straight quotes and hyphens.

## Step 4 — Write the File (read-then-append)

The file's top-level key is `customModes` (an array). Use `read_file` first; if the file exists,
**append** your new entry to the existing `customModes` array and write the whole thing back with
`write_file`. If it doesn't exist, create it with a single-entry `customModes` array.

```
Global:    ~/.bob/settings/custom_modes.yaml   (available in all workspaces)
Workspace: .bob/custom_modes.yaml              (only when this workspace is open)
```

⚠️ **The two scopes are not symmetric.** Global modes live under a `settings/` sub-directory
(`~/.bob/settings/custom_modes.yaml`), but workspace modes do **not** (`.bob/custom_modes.yaml`,
no `settings/`). Writing a global mode to `~/.bob/custom_modes.yaml` puts it in a directory
nothing watches, so it silently never loads. Use the exact paths above.

Never overwrite an existing file blind — you would delete the user's other modes.

## Step 5 — Confirm

Tell the user the mode appears in the **mode picker immediately** (hot-reload, no restart). If it
doesn't appear, the file likely failed validation and was dropped — re-check the slug regex,
slug uniqueness, group names, and any `fileRegex`.

## Reminders

- Always ask questions using the `ask_followup_question` tool.
- Read the target file and confirm slug uniqueness before writing.
- Prefer workspace scope (`.bob/custom_modes.yaml`) unless the user wants the mode everywhere.
- Never include information without evidence.



===== PLAN_SKILL_CONTENT =====

# Create Plan

Follow this structured workflow to produce a high-quality, actionable plan.

## Step 1 — Gather Requirements

Ask the user clarifying questions to fully understand the task:
- What is the goal and expected outcome?
- Are there constraints, preferences, or non-goals?
- Which parts of the codebase are likely involved?
- Any related issues or requirement documents?

Do not proceed until you have enough context to scope the work, be critical of vague intent or requirements.

## Step 2 — Code Search via Sub-Agent

Spawn a `spawn_subagent` of type `"explore"` to research the codebase. The sub-agent should:
- Locate relevant files, symbols, and patterns related to the task
- Identify existing utilities or abstractions that should be reused
- Identify existing design patterns
- Surface any constraints or conventions (e.g. patterns in similar files)

Use the sub-agent's findings to ground your plan in the actual code.

## Step 3 — Clarify Design Intention

Based on the requirements and code research:
- Always confirm your understanding of the intended design with the user
- Raise any open questions or trade-offs that need a decision
- Adjust scope if the code research revealed complexity or simplifications

Do not begin writing the plan document until design intent is confirmed.

## Step 4 — Write the Plan File

Write a structured plan to a markdown file (e.g. `{short-plan-name}-plan.md`). The plan must NOT go into low-level code detail — focus on *what* needs to happen and *why*.

The plan file must include:

### Top-Level Overview
A concise summary of the goal, scope, and approach.

### Sub-Tasks
Break the work into sub-tasks. Each sub-task must have:
- **Intent** — what this sub-task achieves and why
- **Expected Outcomes** — observable results when this sub-task is complete
- **Todo List** — ordered, specific steps to achieve the outcome
- **Relevant Context** — pointers to relevant files, symbols, or patterns
- **Status** — `[ ] pending` (updated to `[x] done` after completion)

Design each sub-task to be processed independently, one at a time, so changes stay focused and reviewable.

## Step 5 — Plan Validation

Before moving to implementation, ensure that the user has fully read the plan. Always ask the user targeted questions to verify the plan is correct and complete:
- Does this plan capture the full scope of the task?
- Are the sub-task boundaries and ordering correct?
- Is any context missing that would be needed during implementation?

Use Mermaid diagrams in chat responses where they clarify architecture or workflow, but do not place Mermaid diagrams directly in the plan file. Avoid double quotes and parentheses inside square brackets in Mermaid syntax.

Refine the plan file based on the user's answers.

## Step 6 — Implementation

Only after the user confirms the plan, recommend implementation by calling the `switch_mode` tool to `agent`.

When explaining how to implement the plan in agent mode:
- Using the `start_subtask` tool, create a new task for each subtask in the <plan-file>.
- In the prompt for the subtask make sure it reads the plan-file to gain the full context around the task.
- After each sub task is complete update the task status in the <plan-file>
- Add any context needed for the next subtask in the <plan-file>
- Wait for the user to check and ok the changes before moving on to the next subtask.

## Reminders

- Ask questions always using the "ask_followup_question" tool
- Never include information without evidence
- Don't include time estimates
