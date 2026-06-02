# Copilot devcontainer — Podman variant

A Podman-hostable variant of [`../copilot-cli`](../copilot-cli/devcontainer.json)
(GitHub Copilot CLI). It reuses the **same base image and lifecycle scripts** —
only the runtime wiring differs so the container can run under **rootless
Podman** as the host engine. The Docker variant is untouched.

See [`../claude-code-podman/readme.md`](../claude-code-podman/readme.md) for the
full rationale; this is the Copilot equivalent.

## What differs from the Docker variant

| Concern | Docker variant | Podman variant |
|---|---|---|
| Nested runtime | `docker-in-docker` feature | rootless **podman-in-podman** in the image |
| Terraform MCP | `docker run …` (dind) | `docker` → `podman` via `podman-docker` shim |
| `docker image pull` (post-start) | dockerd | podman via the shim |
| User mapping | Docker default | `--userns=keep-id:uid=1000,gid=1000` |
| SELinux on bind mount | n/a | `--security-opt=label=disable` |
| Nested userns | host engine | single-uid mode (node subuids removed) + `unmask=ALL` |
| Nested storage | n/a | vfs + `ignore_chown_errors` |
| Nested networking | host engine | slirp4netns + `--device=/dev/net/tun` |
| Short image names | docker.io implicit | `unqualified-search-registries = ["docker.io"]` |
| Nested sysctls | default | `default_sysctls = []` (read-only `/proc/sys`) |
| UID rebuild | CLI default | `updateRemoteUserUID: false` |

See [`../claude-code-podman/readme.md`](../claude-code-podman/readme.md#rootless-podman-in-rootless-podman-specifics)
for why each of the nested-podman settings is needed — the same config applies here.

The MCP config lives **inline** in this variant's `devcontainer.json` (Copilot
reads `customizations.vscode.mcp`, unlike Claude Code which reads the repo-level
`.mcp.json`). It is copied verbatim from the Docker variant and left unchanged —
the `podman-docker` shim makes `command: "docker"` resolve to podman. The base
image, `post-create.sh`, and `post-start.sh` are shared with the Docker variant.

> Keep the Copilot install block in the local `Dockerfile` in sync with
> `../copilot-cli/DockerFile` if that variant's install changes.

## Prerequisites

- Podman 4.x+ (rootless) with the socket service running:
  ```bash
  systemctl --user enable --now podman.socket
  ```
- Point the Dev Containers tooling at Podman:
  ```jsonc
  // VS Code settings.json
  "dev.containers.dockerPath": "podman"
  ```
  or for the CLI:
  ```bash
  devcontainer up --docker-path podman --workspace-folder . \
    --config .devcontainer/copilot-cli-podman/devcontainer.json
  ```

## Open it

In VS Code: **Dev Containers: Reopen in Container** → pick
**"… - Copilot (Podman)"**.
