# Bob devcontainer (Podman)

A devcontainer for **IBM Bob Shell** (`bob`, the bobshell CLI) hosted on
**rootless Podman**. It follows the [`../copilot-cli-podman`](../copilot-cli-podman/readme.md)
pattern: the shared `terraform-ai-tools` base image plus rootless
podman-in-podman and the `podman-docker` shim. There is no Docker-hosted Bob
variant — Bob is used with Podman only.

See [`../claude-code-podman/readme.md`](../claude-code-podman/readme.md) for the
full rootless-podman-in-podman rationale; the same config applies here:

| Concern | How it's handled |
|---|---|
| Nested runtime | rootless **podman-in-podman** in the image |
| Terraform MCP / Bob sandbox | `docker` → `podman` via `podman-docker` shim |
| User mapping | `--userns=keep-id:uid=1000,gid=1000` |
| SELinux on bind mount | `--security-opt=label=disable` |
| Nested userns | single-uid mode (node subuids removed) + `unmask=ALL` |
| Nested storage | vfs + `ignore_chown_errors`, pinned via `CONTAINERS_STORAGE_CONF` |
| Nested networking | slirp4netns + `--device=/dev/net/tun` |
| Short image names | `unqualified-search-registries = ["docker.io"]` |
| Nested sysctls | `default_sysctls = []` (read-only `/proc/sys`) |
| UID rebuild | `updateRemoteUserUID: false` |

Bob Shell is installed at the **latest published version**: the Dockerfile
resolves `bobshell-version.txt` from the official install bucket at build time,
and `scripts/post-start.sh` re-checks it on every container start. Bob's own
container sandbox (`docker.io/library/node:25-trixie`, from bobshell's
`sandboxImageUri`) is pre-pulled in post-start and runs through the podman shim.

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
    --config .devcontainer/bob-podman/devcontainer.json
  ```
- From **Bob IDE 2.0**, which has no built-in Dev Containers support, install
  the `mythreyak.open-remote-devcontainer` extension and set
  `"remote.devcontainer.containerBinary": "podman"`.

## Open it

In VS Code: **Dev Containers: Reopen in Container** → pick
**"… - Bob (Podman)"**. In Bob IDE: **Open in Dev Container** (via the
extension above).
