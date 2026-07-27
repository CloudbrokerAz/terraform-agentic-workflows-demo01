# Bob IDE devcontainer (Podman, amd64)

Attaches the **IBM Bob IDE GUI** to a devcontainer on rootless Podman.
[`../bob-podman`](../bob-podman/readme.md) targets **Bob Shell** (the `bob` CLI)
*inside* the container; this variant is what the graphical IDE needs.

Selected via the root [`../devcontainer.json`](../devcontainer.json) — the Bob
extension can only read that one path. See its header for the full list of
devcontainer.json keys the extension ignores.

## Why a separate amd64 image

Bob's GUI attaches by installing its remote-extension-host (REH) server inside
the container. IBM publishes that server for **linux/x64 only**:

| `…/update/reh/ibm-bob/linux/<arch>/<version>` | Result |
| --- | --- |
| `x64` | `302` → `ibm-bob-reh-linux-x64-<version>.tar.gz` (~110 MB) |
| `arm64`, `aarch64`, `armhf`, all `alpine` | `404 {"detail":"REH server not found"}` |

On an Apple Silicon Mac the Podman machine is arm64, so the container is
`aarch64`, the install script requests the arm64 REH, and Bob reports:

```
Failed to connect to the remote extension host server
(Error: Server install script failed with exit code 1)
```

Pinning to `linux/amd64` makes the container `x86_64` under QEMU, so the
published x64 REH is the one requested. The platform is pinned **twice** — in
this `Dockerfile`'s `FROM --platform` and in the root config's `runArgs` —
because the extension does not pass `--platform` to `podman build`, and Podman
6 removed the global `--override-arch`.

Everything below the `FROM` line is identical to
[`../bob-podman/Dockerfile`](../bob-podman/Dockerfile). **Keep the two in sync.**

## Known limitations under emulation

Verified on Podman 6.0.2 / Apple Silicon:

| | |
| --- | --- |
| ✅ Works | Bob GUI attach, Terraform, node, npm, git, python3, `keep-id` UID mapping, bind-mount writes |
| ❌ Broken | nested `podman`/`docker`, `gh` |

Affected binaries abort during Go runtime init:

```
runtime: lfstack.push invalid packing: node=0x… -> node=0xffffffff…
fatal error: lfstack.push
```

Go packs pointers into 48 bits assuming Linux x86-64 userspace addresses; QEMU
hands out addresses above that range. It is **selective, not universal** —
Terraform is also Go and works fine. `QEMU_RESERVED_VA` does not help (it fails
earlier with `Cannot allocate vsyscall page`).

Practical impact: **no Terraform MCP server, no Bob Shell sandbox, no `gh`
CLI** in this container. `post-start.sh` probes the runtime and skips the image
pre-pulls rather than emitting a ~100-line goroutine trace per pull.

Run those on the host, or keep a native `../bob-podman` container alongside.

## Prerequisites

- Podman 4.x+ (rootless) with the socket service running
- The `mythreyak.open-remote-devcontainer` extension installed in Bob, with:
  ```jsonc
  // Bob User/settings.json — absolute path, not bare "podman": a Dock-launched
  // GUI inherits launchd's PATH, which excludes /opt/homebrew/bin.
  "remote.devcontainer.containerBinary": "/opt/homebrew/bin/podman"
  ```
- Grant the extension the proposed APIs it needs, then **fully restart Bob**:
  ```jsonc
  // ~/.bobide-insiders/argv.json
  "enable-proposed-api": ["mythreyak.open-remote-devcontainer"]
  ```
  Without this Bob logs `CANNOT USE these API proposals 'resolvers,
  contribViewsRemote'`.

## Open it

Command palette → **Devcontainer: Open Folder in container**.
Use **Devcontainer: Show Log** to watch the `podman build` output.

Because the extension ignores `remoteEnv`, tokens are passed as `--env` entries
in the root config's `runArgs` and are read from Bob's process environment at
`podman run` time — export them before launching Bob, and rebuild the container
after changing them.
