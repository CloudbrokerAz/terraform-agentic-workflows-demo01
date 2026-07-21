# Bob devcontainer — Podman variant

A Podman-hostable variant of [`../bob`](../bob/devcontainer.json) (IBM Bob
Shell). It reuses the **same base image and lifecycle scripts** — only the
runtime wiring differs so the container can run under **rootless Podman** as
the host engine. The Docker variant is untouched.

See [`../claude-code-podman/readme.md`](../claude-code-podman/readme.md) for the
full rationale; this is the Bob equivalent.

## What differs from the Docker variant

| Concern | Docker variant | Podman variant |
|---|---|---|
| Nested runtime | `docker-in-docker` feature | rootless **podman-in-podman** in the image |
| Terraform MCP / Bob sandbox | `docker run …` (dind) | `docker` → `podman` via `podman-docker` shim |
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

Bob Shell is installed at the **latest published version**: the Dockerfile
resolves `bobshell-version.txt` from the official install bucket at build time,
and `post-start.sh` re-checks it on every container start. Bob's own container
sandbox (`docker.io/library/node:25-trixie`, from bobshell's `sandboxImageUri`)
is pre-pulled in post-start and runs through the same podman shim.

> Keep the Bob install block in the local `Dockerfile` in sync with
> `../bob/Dockerfile` if that variant's install changes.

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

## Open it

In VS Code: **Dev Containers: Reopen in Container** → pick
**"… - Bob (Podman)"**.
