# Demo Quickstart

A ~10‑minute path to demonstrating the agentic Terraform workflow live: open a
devcontainer, validate the environment, run one Spec‑Driven Development (SDD)
workflow end‑to‑end, and show the resulting pull request.

> **First time here?** This is the fast demo path. For full account setup,
> tokens, and configuration see [Getting Started](getting_started.md). This
> guide assumes those prerequisites (GitHub token, HCP Terraform team token,
> AWS via HCP) are already in place.

---

## 1. Pick a devcontainer

Four variants ship in `.devcontainer/` — one per AI assistant, each with a
Docker and a rootless‑Podman host engine. Pick the row that matches your setup.

| Assistant | Docker host | Podman host |
|-----------|-------------|-------------|
| **Claude Code** | `.devcontainer/claude-code/` | `.devcontainer/claude-code-podman/` |
| **GitHub Copilot** | `.devcontainer/copilot-cli/` | `.devcontainer/copilot-cli-podman/` |

In VS Code: **Dev Containers: Reopen in Container** → choose the matching entry
(e.g. *"… - Claude Code"* or *"… - Copilot (Podman)"*).

> **Podman host?** Point the Dev Containers tooling at Podman once with
> `"dev.containers.dockerPath": "podman"` (VS Code) — see the variant's
> `readme.md`. The Terraform MCP runs unchanged via rootless podman‑in‑podman.

---

## 2. Validate the environment

Open a terminal in the container and run:

```bash
bash .foundations/scripts/bash/validate-env.sh
```

All **GATE** checks (TFE_TOKEN, GITHUB_TOKEN, Terraform, GitHub CLI) must pass.
The script also initializes TFLint and installs the pre‑commit hooks.

Quick sanity check that the secrets reached the container:

```bash
echo "TFE_TOKEN:    ${TFE_TOKEN:+set}"
echo "GITHUB_TOKEN: ${GITHUB_TOKEN:+set}"
```

> These are injected via the devcontainer's `remoteEnv` from your host
> environment. They appear in the **VS Code integrated terminal** and via
> `devcontainer exec` — a raw `docker exec`/`podman exec` will not carry them.

---

## 3. Authenticate the assistant

- **Claude Code** — run `claude` once and complete `claude login` (or
  `export ANTHROPIC_API_KEY=…`). The login persists in the mounted config volume.
- **GitHub Copilot** — authenticates from the injected `GITHUB_TOKEN`; if
  prompted, run `/login` inside the Copilot TUI.

---

## 4. Run the demo workflow

The **Consumer Provisioning** workflow is the most demo‑friendly: it composes
private‑registry modules and deploys to an HCP Terraform sandbox, ending in a
real PR. Launch your assistant and start the plan.

**Claude Code:**

```text
/tf-consumer-plan
```

**GitHub Copilot** (agent mode):

```text
/tf-consumer-plan
```

Then describe a small target when prompted, for example:

> Provision a single SQS queue with server‑side encryption and a dead‑letter queue.

You'll watch the SDD phases run:

```
🔍 Clarify → 📐 Design → 🧑‍💻 Human Review → 🔨 Implement → ✅ Validate → 🚀 PR
```

When the design (`specs/{feature}/consumer-design.md`) looks good, approve it and
continue:

```text
/tf-consumer-implement
```

This composes the modules, runs the full quality pipeline (`fmt`, `validate`,
`tflint`, `trivy`), deploys to the sandbox workspace, and opens a pull request.

> **Just want to confirm the workflow starts?** Launch the assistant, run
> `/tf-consumer-plan`, watch it begin clarifying/researching, then `Ctrl‑C`.
> No sandbox resources are created until `/tf-consumer-implement`.

---

## 5. Show the result

```bash
gh pr list
gh pr view --web
```

Walk through the generated Terraform, the design document under `specs/`, the
green quality‑gate checks, and the sandbox deployment in HCP Terraform.

---

## Non‑interactive variant (optional)

For an automated, prompt‑driven run that bypasses the interactive questions,
the repo ships an end‑to‑end harness with ready‑made prompts:

```text
/tf-consumer-e2e consumer_sqs
```

Available prompts live in `.claude/skills/tf-consumer-e2e/prompts/`
(`consumer_sqs`, `consumer_ec2`, `consumer_serverless`, `consumer_asg`,
`consumer_cloudfront`, `consumer_elastic`). This runs the full
plan → implement → deploy → PR cycle with test defaults.

---

## Cleanup

- Discard the demo branch/PR if you don't want to keep it (`gh pr close`,
  delete the branch).
- Destroy the sandbox workspace in HCP Terraform once the demo is done.
- Stop the devcontainer from VS Code (**Dev Containers: Reopen Folder Locally**)
  or remove it with the Dev Containers CLI.

---

## Related

- [Getting Started](getting_started.md) — full setup, accounts, and tokens
- [Tool Name Mapping](tool-name-mapping.md) — Claude vs. Copilot tool names
- `.devcontainer/*/readme.md` — per‑variant devcontainer notes (incl. Podman)
