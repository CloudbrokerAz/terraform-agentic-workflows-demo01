# Claude Code devcontainer — Podman variant

A Podman-hostable variant of [`../claude-code`](../claude-code/devcontainer.json).
It reuses the **same base image, Dockerfile, and lifecycle scripts** — only the
runtime wiring differs so the container can run under **rootless Podman** as the
host engine. The Docker variant is untouched.

## What differs from the Docker variant

| Concern | Docker variant | Podman variant |
|---|---|---|
| Nested runtime | `docker-in-docker` feature | rootless **podman-in-podman** in the image |
| Terraform MCP | `docker run …` (dind) | `docker` → `podman` via `podman-docker` shim |
| User mapping | Docker default | `--userns=keep-id:uid=1000,gid=1000` |
| SELinux on bind mount | n/a | `--security-opt=label=disable` |
| Nested userns | host engine | single-uid mode (node subuids removed) + `unmask=ALL` |
| Nested storage | n/a | vfs + `ignore_chown_errors` |
| Nested networking | host engine | slirp4netns + `--device=/dev/net/tun` |
| Short image names | docker.io implicit | `unqualified-search-registries = ["docker.io"]` |
| Nested sysctls | default | `default_sysctls = []` (read-only `/proc/sys`) |
| UID rebuild | CLI default | `updateRemoteUserUID: false` |
| Named volumes | `claude-code-*` | `claude-code-podman-*` (no clash) |

### Why podman-in-podman (not "drop dind")

The shared, repo-level [`.mcp.json`](../../.mcp.json) launches the Terraform MCP
server with `docker run hashicorp/terraform-mcp-server`. That needs a container
runtime *inside* the dev container. Rather than edit the shared `.mcp.json`, this
variant installs rootless podman plus `podman-docker` (which provides a `docker`
→ `podman` wrapper), so the unchanged `docker run …` command Just Works.

### Rootless-podman-in-rootless-podman specifics

Because the outer container is itself rootless (`--userns=keep-id`), the inner
podman cannot allocate a second sub-uid range via `newuidmap`. The image is
configured for **single-uid mode** (node's `/etc/subuid`/`/etc/subgid` entries
removed) with **vfs + `ignore_chown_errors`** storage so image layers that chown
to other uids still extract. `unmask=ALL` lets the nested container mount its own
`/proc`; `default_sysctls = []` avoids writing `net.ipv4.ping_group_range` to the
read-only `/proc/sys`; `--device=/dev/net/tun` gives slirp4netns outbound
networking; and `unqualified-search-registries` resolves Docker-style short
names. This whole path was validated end-to-end on macOS Podman 5.x — the
Terraform MCP `initialize` handshake succeeds over the nested `docker` shim.

The base image, `post-create.sh`, and `post-start.sh` are shared (build context
`../claude-code`). The local `Dockerfile` mirrors the Docker variant's Claude
Code install and adds the podman layer — keep that block in sync if the Docker
variant's install changes.

## Prerequisites

- Podman 4.x+ (rootless) with the socket service running:
  ```bash
  systemctl --user enable --now podman.socket
  ```
- The Dev Containers CLI / VS Code Dev Containers extension pointed at Podman:
  ```jsonc
  // VS Code settings.json
  "dev.containers.dockerPath": "podman"
  ```
  or for the CLI: `devcontainer up --docker-path podman --workspace-folder . \
    --config .devcontainer/claude-code-podman/devcontainer.json`

## Open it

In VS Code: **Dev Containers: Reopen in Container** → pick
**"… - Claude Code (Podman)"**.

## Notes

- `keep-id` maps your host UID onto the in-container `node` user, so files you
  edit in `/workspace` keep correct ownership instead of landing in the subuid
  range.
- The named volumes are intentionally renamed (`claude-code-podman-*`) so this
  variant never collides with the Docker variant's `claude-code-*` volumes.
- If your host is not SELinux-enforcing, `--security-opt=label=disable` is a
  harmless no-op.
