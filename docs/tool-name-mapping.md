## Tool Name Mapping — Claude Code vs Copilot CLI vs IBM Bob

Every name below was read out of the shipped binaries, not from vendor documentation.

| Source | Version | Artifact inspected |
| --- | --- | --- |
| GitHub Copilot CLI | **1.0.70** | `@github/copilot-darwin-arm64/app.js` + `prebuilds/darwin-arm64/runtime.node` (Rust builtin tool descriptors, queried directly) |
| IBM Bob | extension `bob-code` **2.0.1** (app `1.121.0+bob2.0.1`) and **2.0.1-insider.1** (app `1.121.0+bob2.0.2-insider.1`) | `IBM Bob*.app/Contents/Resources/app/extensions/bob-code/dist/extension.js` (tool classes carry `id=`/`getId()`, `groups`, `permission`) |
| Claude Code | current session | live tool surface |

Copilot's 1.x line is a native binary with a Rust runtime, not the 0.x JS bundle — names below were
re-confirmed against it. Copilot's static builtin set (25 tools, enumerated by brute-forcing
`toolGetBuiltinDescriptor`) is: `apply_patch ask_user context_board create create_pull_request edit
exit_plan_mode fetch_copilot_cli_documentation glob grep list_agents manage_schedule read_agent
read_inbox reply_to_comment send_inbox session_store_sql skill str_replace_editor task_complete
tool_search_tool update_todo view web_fetch write_agent`, plus `lsp`, `task` and the shell family,
which are registered in JS rather than as Rust descriptors.

### Core tools

| Concept | Claude Code | Copilot CLI | IBM Bob |
| --- | --- | --- | --- |
| Read file | `Read` | `view` | `read_file` (also `read_xlsx`) |
| Create file | `Write` | `create` | `write_file` |
| Edit file | `Edit` | `edit`, `str_replace_editor`, `apply_patch` | `apply_diff`, `insert_content`, `search_and_replace` |
| Run shell command | `Bash` | `bash` (`powershell` sibling family exists) | `execute_command` |
| Search file contents | `Grep` | `grep` — but renamed `rg` under model configs that set `grepToolName` | `grep` |
| Search file names | `Glob` | `glob` | `glob` (also `list_files`) |
| Code intelligence | `LSP` | `lsp` | _(none)_ |
| Fetch URL | `WebFetch` | `web_fetch` | _(none)_ |
| Web search | `WebSearch` | `web_search` (served by the built-in `github-mcp-server`) | _(no builtin; the provider's server-side web search may surface — Bob handles both the Anthropic `server_tool_use` and OpenAI `web_search_call` shapes)_ |
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
   `spawn_subagent`; it ships exactly **one** preset, `explore`, and synthesizes `general` as a
   fallback name (when no `general` preset exists it is appended to the choices and resolves to
   hardcoded `["read","edit","execute"]` groups). Bob subagents cannot nest — `spawn_subagent`,
   `start_subtask` and `start_workflow` are all in its `SUBAGENT_FORBIDDEN_TOOLS`.
5. **MCP naming differs between Copilot and the other two.**
   - Claude Code: `mcp__server__tool`.
   - **Bob: `mcp__<server>__<tool>`** — generated as `` `mcp__${server}__${tool}` `` and stated
     verbatim in its system prompt, so `mcp__terraform__*` pins carry over from Claude Code
     unchanged. Caveat: names are truncated to a 64-char limit with the **server segment capped at
     12 characters** and the tool segment given `57 - len(server)`. `terraform` (9) and our longest
     tool name fit, but a server name over 12 characters would be silently mangled.
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
   `puppeteer`. Copilot ships a hardcoded Playwright MCP catalogue (`browser_click`,
   `browser_navigate`, `browser_take_screenshot`, `browser_snapshot`, `browser_evaluate`,
   `browser_fill_form`, …) that `configurePlaywrightMcp()` auto-registers as a default server with
   `tools:["*"]` — technically MCP rather than builtin, but bundled and enabled without user setup.
   Claude Code bundles no browser tools.

### Tools that do NOT exist (checked, to stop them being reintroduced)

`report_intent` and `git_apply_patch` — zero occurrences in Copilot 1.0.70 `app.js`, and
`toolGetBuiltinDescriptor` returns `null` for both. Earlier revisions of this document listed them.
