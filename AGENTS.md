# AGENTS.md

Operational rules for the orchestrator during workflow execution. Everything else — agent instructions, skill steps, constitution rules — lives in its own file and is loaded automatically.

## Workflows

| Command                                        | Agents                                                                                 | Design Artifact                                 | Constitution                                   |
| ---------------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------- | ---------------------------------------------- |
| `/tf-module-plan` + `/tf-module-implement`     | tf-module-research, tf-module-design, tf-module-test-writer, tf-module-developer       | `specs/{FEATURE}/design.md`                     | `.foundations/memory/module-constitution.md`   |
| `/tf-provider-plan` + `/tf-provider-implement` | tf-provider-research, tf-provider-design, tf-provider-developer, tf-provider-validator | `specs/{FEATURE}/provider-design-{resource}.md` | `.foundations/memory/provider-constitution.md` |
| `/tf-consumer-plan` + `/tf-consumer-implement` | tf-consumer-research, tf-consumer-design, tf-consumer-developer, tf-consumer-validator | `specs/{FEATURE}/consumer-design.md`            | `.foundations/memory/consumer-constitution.md` |

## Context Management

These rules apply to ALL three workflows. Replace `{workflow}` with `module`, `provider`, or `consumer` as appropriate.

1. **NEVER call TaskOutput** to read subagent results. ALL agents — including research agents — write artifacts to disk. The orchestrator verifies expected files exist after each dispatch.
2. **Verify file existence with Glob** after each agent completes — do NOT read file contents into the orchestrator.
3. **Downstream agents read their own inputs from disk.** The orchestrator passes the FEATURE path plus scope via `$ARGUMENTS`. The design agent reads research files from `specs/{FEATURE}/research-*.md` itself.
4. **Research agents: parallel foreground Task calls** (NOT `run_in_background`). Launch ALL research agents in a single message with multiple Task tool calls. Each writes findings to `specs/{FEATURE}/research-{slug}.md`. Verify files exist via Glob before launching the design agent.
5. **Minimal $ARGUMENTS**: Only pass the FEATURE path + a specific question or scope. No exceptions.

### Consumer-Specific Rules

6. **No test-writer agent**: Consumer workflow does NOT have a test-writer agent. Validation is via `terraform validate` and sandbox deployment, not `.tftest.hcl` files.
7. **Validator handles deploy**: The `tf-consumer-validator` agent handles security review, quality scoring, AND sandbox deployment in a single pass. The orchestrator controls whether sandbox deploy is included via `$ARGUMENTS`.
8. **Sandbox destroy is orchestrator-controlled**: The orchestrator (not the validator) prompts the user about destroying sandbox resources after PR creation.
9. Always prioritize private modules.

## Operational Notes

### GitHub Enterprise Authentication

Most `gh` commands (issue, pr, repo, etc.) do NOT accept `--hostname`. Use the `GH_HOST` environment variable instead:

```bash
export GH_HOST=github.enterprise.com
gh issue create --title "Bug report"
# Or inline:
GH_HOST=github.enterprise.com gh pr create --title "Feature"
```

Authentication requires `gh auth login --hostname <hostname>` — standard `gh auth login` only authenticates against github.com.

### Agent Output Persistence

Subagents persist output artifacts to disk. The orchestrator verifies expected files exist after each dispatch.
