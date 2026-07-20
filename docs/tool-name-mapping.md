## Tool Name Mapping — Claude Code vs Copilot CLI vs IBM Bob

Every name below was read out of the shipped binaries, not from vendor documentation.

| Source | Version | Artifact inspected |
| --- | --- | --- |
| GitHub Copilot CLI | **1.0.70** | `@github/copilot-darwin-arm64/app.js` + `prebuilds/darwin-arm64/runtime.node` (Rust builtin tool descriptors, queried directly) |
| IBM Bob | extension `bob-code` **2.0.1** (app `1.121.0+bob2.0.1`) and **2.0.1-insider.1** (app `1.121.0+bob2.0.2-insider.1`) | `IBM Bob*.app/Contents/Resources/app/extensions/bob-code/dist/extension.js` (tool classes carry `id=`/`getId()`, `groups`, `permission`) |
| Claude Code | current session | live tool surface — **not** code-verified like the other two columns |

Copilot's 1.x line is a native binary with a Rust runtime, not the 0.x JS bundle — names below were
re-confirmed against it. Copilot's name-keyed builtin table holds 25 tools, enumerated by brute-forcing
`toolGetBuiltinDescriptor` over every snake_case literal in `app.js`: `apply_patch ask_user
context_board create create_pull_request edit exit_plan_mode fetch_copilot_cli_documentation glob
grep list_agents manage_schedule read_agent read_inbox reply_to_comment send_inbox session_store_sql
skill str_replace_editor task_complete tool_search_tool update_todo view web_fetch write_agent`.

That table is not the whole tool surface. Others are Rust descriptors reached through dedicated
exports rather than by name — the shell family via `toolShellDescriptor` / `toolReadShellDescriptor`
/ `toolStopShellDescriptor` / `toolListShellsDescriptor`, and `report_progress` via
`toolReportProgressDescriptor` — while `lsp` and `task` are registered in JS. Further families exist
outside both (canvas, memory, and `local_shell` as a `bash` alias in dispatch) and are not covered
by this document.

### Core tools

| Concept | Claude Code | Copilot CLI | IBM Bob |
| --- | --- | --- | --- |
| Read file | `Read` | `view` | `read_file` (also `read_xlsx`) |
| Create file | `Write` | `create` | `write_file` |
| Edit file | `Edit` | `edit`, `str_replace_editor`, `apply_patch` | `apply_diff`, `insert_content`, `search_and_replace` |
| Run shell command | `Bash` | `bash` (`powershell` sibling family exists) | `execute_command` |
| Search file contents | `Grep` | `grep` — genuinely renamed `rg` under model configs that set `grepToolName` (a real tool rename, not prompt text) | `grep` |
| Search file names | `Glob` | `glob` (a `globToolName` rename hook exists alongside `grepToolName`, but no shipped model config sets it) | `glob` (also `list_files`) |
| Code intelligence | `LSP` | `lsp` | _(none)_ |
| Fetch URL | `WebFetch` | `web_fetch` | _(none)_ |
| Web search | `WebSearch` | `web_search` (served by `github-mcp-server`, registered by `configureGitHubMcp` — which the same CLI-mode short-circuit as Playwright skips, so availability is path-dependent) | _(no builtin; the provider's server-side web search may surface — Bob handles both the Anthropic `server_tool_use` and OpenAI `web_search_call` shapes)_ |
| Ask the user | `AskUserQuestion` | `ask_user` | `ask_followup_question` |
| Invoke skill | `Skill` | `skill` | `use_skill` |
| Launch subagent | `Agent` (`subagent_type`) | `task` (agent chosen by `agent_type`) | `spawn_subagent` (agent chosen by `name`) |
| Track progress | `TaskCreate` / `TaskUpdate` | `update_todo` | `update_todo_list` |
| Plan mode | `ExitPlanMode` | `exit_plan_mode` | _(none — `switch_mode` instead)_ |

### Tools unique to one harness

| Tool | Harness | Purpose |
| --- | --- | --- |
| `read_bash`, `write_bash`, `stop_bash`, `list_bash` | Copilot | async shell family (see difference 2) |
| `task_complete` | Copilot | explicit end-of-turn signal |
| `list_agents`, `read_agent`, `write_agent` | Copilot | inspect/author agent files at runtime |
| `tool_search_tool` | Copilot | deferred-tool loading |
| `fetch_copilot_cli_documentation` | Copilot | self-documentation |
| `report_progress` | Copilot | commits locally and updates the PR description — the SWE-agent/coding-agent path, not a normal local CLI tool. Its input schema requires `commitMessage` and `prDescription`; separately, the host wiring throws if no branch name is configured. |
| `create_pull_request`, `reply_to_comment`, `read_inbox`, `send_inbox` | Copilot | agent/PR collaboration surface |
| `start_subtask` / `end_subtask` | Bob | sequential fresh-context task chaining with a todo checklist |
| `switch_mode` | Bob | change the active mode |
| `start_workflow` | Bob | run a built-in workflow (`create_pr_workflow`, `review_workflow`) — user-defined workflows do not exist |
| `create_html_artifact` | Bob | render an HTML artifact |
| `submit_review_findings` | Bob | structured review findings (feature-flagged on `review-flow-enabled`) |
| `list_mcp_resources`, `read_mcp_resource` | Bob | MCP resource access (`groups`/`permission` = `mcp`) |
| `search_bob_docs` | Bob | **insiders build only** — absent from stable 2.0.1 |

### Key differences

1. **Case**: Claude Code uses `PascalCase` (`Bash`, `Grep`). Copilot and Bob both use `snake_case`
   (`bash`, `grep` / `execute_command`, `read_file`).
2. **Async shell**: Copilot has a five-tool shell family. Its shell-config tuple names four —
   `new t("bash","Bash","bash","read_bash","stop_bash","list_bash",…)` — and `write_bash` is
   handled separately in the tool dispatch. Claude Code has one `Bash` tool with a
   `run_in_background` flag. Bob has only synchronous `execute_command`.
3. **File-edit split**: Copilot exposes `view` / `create` / `edit`, plus `str_replace_editor` and
   `apply_patch` as alternatives (`apply_patch` appears under the `editingToolsStyle:"apply-patch"`
   model override). Bob splits editing four ways: `write_file` for whole files, then `apply_diff`,
   `insert_content`, `search_and_replace`.
4. **Subagents**: in Copilot the *tool* is `task`, taking an `agent_type`. Built-in agent names are
   `explore`, `task`, `code-review`, `rubber-duck`, `research`, `rem-agent`, `security-review`,
   `general-purpose` — note `task` is both the tool name and an agent name. Bob's tool is
   `spawn_subagent`; it ships exactly **one** built-in preset, `explore`, and synthesizes `general`
   as a fallback name (when no `general` preset exists it is appended to the choices and resolves to
   hardcoded `["read","edit","execute"]` groups). That is not a ceiling: the tool merges injected
   presets over the built-in map, and `parseAgentFile()` reads `.md` frontmatter agent definitions
   with the same default groups — which is what the `.bob/agents/` dialect dir feeds. A mode's
   `allowedSubagents` gates which are spawnable, and when its allowlist excludes `general` the
   `name` parameter becomes required. Bob subagents cannot nest — `spawn_subagent`, `start_subtask`
   and `start_workflow` are all in its `SUBAGENT_FORBIDDEN_TOOLS`.
5. **MCP naming differs between Copilot and the other two.**
   - Claude Code: `mcp__server__tool`.
   - **Bob: `mcp__<server>__<tool>`** — generated as `` `mcp__${server}__${tool}` `` and stated
     verbatim in its system prompt, so `mcp__terraform__*` pins carry over from Claude Code
     unchanged. Two caveats. Both segments are first **sanitized** — `[^a-zA-Z0-9_-]` becomes `_`,
     runs collapse, empty becomes `unnamed` — which bites more real server names than truncation
     does. Then names are fitted to a 64-char budget (57 usable): the server is capped at 12 chars,
     the tool gets `57 - len(capped server)`, and the server is re-sliced against what the tool
     took. The generator returns a `truncated` flag, so it is detectable rather than silent.
     `terraform` (9 chars) and our longest tool name fit without either applying.
   - **Copilot: `server/tool` with a slash.** Verified by round-tripping the runtime's
     `mcpSplitNamespacedName`: `terraform/search_private_modules` parses into server + tool, while
     `mcp__terraform__search_private_modules` returns `null`. The string `mcp__` occurs zero times
     in either `app.js` or `runtime.node`. Exception: the bundled `github-mcp-server-web_search` is
     hyphen-joined and is special-cased rather than parsed.
6. **Permission model**: Bob gates every tool by a `permission` value baked into the tool class —
   `artifact`, `ask`, `edit`, `execute`, `mcp`, `mode`, `read`, `review`, `skill`, `subagent`,
   `subtask`, `todo`, `workflow` (13). Most tools also carry a matching `groups` value; `ask` and
   `workflow` tools have a `permission` only. A mode granting no groups gets none of the grouped
   tools. Copilot and Claude Code approve per tool call instead.
7. **Browser automation**: Bob has none — zero occurrences of `browser_action`, `playwright` or
   `puppeteer`. Copilot bundles a hardcoded Playwright MCP catalogue of 21 tools (`browser_click`,
   `browser_navigate`, `browser_take_screenshot`, `browser_snapshot`, `browser_evaluate`,
   `browser_fill_form`, …) that `configurePlaywrightMcp()` registers as a default server with
   `tools:["*"]` — **but not on the CLI path**: it is reached only from `readMcpConfigFromEnv()`,
   which short-circuits when `GITHUB_COPILOT_CLI_MODE === "true"` ("CLI mode detected - skipping
   default MCP servers"). So it belongs to the env-driven coding-agent path. Claude Code bundles no
   browser tools.

### Tools that do NOT exist (checked, to stop them being reintroduced)

`report_intent` and `git_apply_patch` — zero occurrences in Copilot 1.0.70 `app.js`, and
`toolGetBuiltinDescriptor` returns `null` for both. Earlier revisions of this document listed them.
