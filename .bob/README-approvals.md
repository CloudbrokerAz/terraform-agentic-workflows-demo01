# Running these workflows in Bob IDE without constant approval prompts

The skills in this repo drive long tool chains — foundation scripts, `git`,
`gh`, `terraform`, MCP servers. With Bob's default approval settings almost
every step raises an approval card, which makes the workflows impractical to
demo and painful to develop against.

This directory ships [`settings.example.json`](./settings.example.json), a
reference approval profile that runs these workflows unattended.

> **This is a dev/demo profile.** It auto-approves `bash`, `python3`, `uvx` and
> `pip`, which together permit arbitrary code execution with no prompt. Use it
> on throwaway clones. Do not leave it enabled on a tree holding long-lived
> cloud or TFC credentials.

## Where the config actually lives

```
~/.bob/settings/settings.json      <- approval config goes here
~/.bob/settings.json               <- licence / instance / auth state, NOT approvals
```

Those are two different files and the nested one is easy to miss. Approval
config written to `~/.bob/settings.json` is silently ignored.

Editing Allowed Commands through **Chat Settings → Execute** writes to the
nested file, so the UI and the file are the same store — you can use either.

## There is no `--yolo` for the IDE

The Bob Shell CLI has blanket approval flags:

```bash
bob --yolo                  # auto-accept all actions
bob --approval-mode=yolo    # same
bob --approval-mode=auto_edit
```

`bobide-insiders` has **no equivalent**. It is the standard VS Code launcher —
`--diff`, `--goto`, `--new-window`, `--profile` and so on. The IDE agent is
governed only by `~/.bob/settings/settings.json` plus the per-task Permissions
picker, so the allowlist below is the only lever.

If you only need the workflow to run and don't need it visible in the IDE,
`bob --yolo` from the repo root is the safer option: it is scoped to that one
session and leaves no persistent global config behind.

## The matching rules that trip people up

**The wildcard is the bare binary name.** There is no `*`, no regex. `gh` on
its own matches every `gh` subcommand. Writing out `gh issue create`,
`gh pr view`, … one at a time is unnecessary.

| You allow | Auto-approves | Does not auto-approve |
|---|---|---|
| `git` | `git status`, `git -C repo log` | `hub sync`, `echo git` |
| `git status` | `git status --short` | `git log`, bare `git` |
| `ls` | `ls -la` | `gls` |

**Longer patterns win.** This is what makes bare binaries safe to use: allow
the family, then deny the specific dangerous members. The example profile
allows `gh` and `terraform` but denies `gh repo delete` and
`terraform destroy`.

**Every segment of a compound command must match.** Bob splits on pipes, `&&`
and `;` first. The skills in this repo emit lines like:

```bash
LINK="$CLAUDE_PLUGIN_ROOT/scripts/link-foundations.sh"; [ -f "$LINK" ] && bash "$LINK" || true && bash ./.foundations/scripts/bash/validate-env.sh --json
```

That is four segments — `[`, `bash`, `true`, `bash` — which is why `[` and
`true` appear in the allowlist. They are real executables (`/bin/[` is the same
program as `/bin/test`), not syntax, and the conditional prompts without them.

**Denied entries are hard blocks**, not "ask first" — they are cancelled
outright and cannot be approved from the card. Keep genuinely destructive
things there, but don't put anything the workflow legitimately needs in the
denied list expecting a prompt.

## Two things the allowlist cannot fix

**Script wrappers bypass the deny list entirely.** Bob only inspects parsed
top-level segments, so `bash .foundations/scripts/bash/checkpoint-commit.sh`
runs every `git commit` and `git push` inside it without those ever appearing
as segments. Allowlisting a script means trusting everything it does.

**Command Security Verification can override the allowlist.** It runs commands
through a security model and fails closed, so a flagged command is forced to
manual approval even when allowlisted, and "Approve for task" is not offered.
`python3 -c` with outbound network calls is a common trigger. Toggle it in
Chat Settings → Execute if it blocks a demo, and turn it back on afterwards.

## Tool groups are per task

Group toggles (Read, Edit, Execute, MCP, …) live on the **task**, not globally.
A new task clones the current global config as its starting point, but a task
already in flight keeps the groups it started with. After changing these
settings, start a new task — or flip the group in the in-chat Permissions
picker. Changing Settings mid-task will not rescue the running one.

## Env vars and the devcontainers

The devcontainer configs here resolve `${localEnv:GITHUB_TOKEN}`,
`${localEnv:TFE_TOKEN}`, `${localEnv:AWS_ACCESS_KEY_ID}` and friends against
**the IDE process's own environment**. On macOS an app launched from Finder or
the Dock gets a minimal `launchd` environment, not your shell's, so those
resolve empty and the container starts without credentials.

Launch the IDE from a shell that has them exported:

```bash
# install the CLI once: Command Palette -> Shell Command: Install 'bobide-insiders' command in PATH
bobide-insiders /path/to/repo
```

Bob must be **fully quit** first (Cmd+Q). A running instance is handed the
folder over IPC and keeps its original environment, so the new window still
sees no variables. Verify with `env | grep GITHUB_TOKEN` in the integrated
terminal before reopening in the container.

## Reference

- [How Tool Approval Works in IBM Bob](https://pages.github.ibm.com/Markus-Eisele/bob-book/poster/how-to-tool-approval/)
