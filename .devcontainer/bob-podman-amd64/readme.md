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

## Use Rosetta, not QEMU

**This variant requires Rosetta.** Under QEMU user-mode emulation, Go binaries
inside the container abort during runtime init:

```
runtime: lfstack.push invalid packing: node=0x… -> node=0xffffffff…
fatal error: lfstack.push
```

Go packs a pointer plus a counter into one 64-bit word for its lock-free
stacks, assuming Linux x86-64 userspace addresses fit in 48 bits (bit 47
clear). `qemu-user` on an arm64 host hands the guest addresses above 2^47, so
the unpack sign-extends and the round-trip check fails. It is **selective, not
universal** — Terraform is also Go and survives. `QEMU_RESERVED_VA` does not
help (it fails earlier with `Cannot allocate vsyscall page`).

Rosetta translates under the VM's normal Linux memory layout, so addresses stay
canonical. Measured on Podman 6.0.2 / Apple Silicon:

| Binary | QEMU | Rosetta |
| --- | --- | --- |
| `podman` | `fatal error: lfstack.push` | 4.3.1 |
| `gh` | `fatal error: lfstack.push` | 2.23.0 |
| `go` | `SIGSEGV` | go1.24.13 |
| `terraform` | v1.15.2 | v1.15.2 |

Rosetta can only be enabled when a machine is **created**:

```jsonc
// ~/.config/containers/containers.conf
[machine]
rosetta=true
```
```bash
podman machine rm -f <name>
podman machine init --cpus 6 --memory 8192 --disk-size 100 <name>
```

**Do not trust `podman machine inspect --format '{{.Rosetta}}'`** — on 6.0.2 it
reports `false` even when Rosetta is active. Verify against the VM:

```bash
podman machine ssh <name> 'ls /proc/sys/fs/binfmt_misc/; mount | grep -i rosetta'
```

Working looks like a `rosetta` binfmt entry, a `rosetta on /var/mnt type
virtiofs` mount, and **no** `qemu-x86_64` entry.

## Containers: siblings, not nesting

Even with Rosetta, running a **nested** container inside this one fails. The
image pulls fine, but starting one fails three different ways:

| Attempt | Failure |
| --- | --- |
| default network | `slirp4netns: seccomp_load(): Operation canceled` |
| `--network=host` (crun) | `Failed to re-execute libcrun via memory file descriptor` |
| `--network=host` (runc) | `read init-p: connection reset by peer` |

So this config does what Docker devcontainers do with `/var/run/docker.sock`:
it mounts the **podman-machine socket**, and `docker run` creates *sibling*
containers on the machine instead of nested ones. Those run natively on arm64,
so no translation is involved and the Terraform MCP server works unchanged —
`.bob/mcp.json` needs no edits.

The uid in the socket path is the podman-machine user, **not** your macOS uid:

```bash
podman machine ssh <machine> 'echo $XDG_RUNTIME_DIR/podman/podman.sock'
```

Adjust the `--volume=` entry in [`../devcontainer.json`](../devcontainer.json)
if yours differs. The in-image podman-in-podman stack is left in place for the
native `../bob-podman` variant but is unused here.

## The server-install race

Bob installs its remote-extension-host server into `~/.bobide-server-insiders`
on first attach, and allows the install script roughly **60 seconds**. IBM's QA
endpoint serves the ~110 MB tarball at about 1.9 MB/s — measured at **59s**
from inside the container. Losing that race gives:

```
Failed to connect to the remote extension host server
(Error: Server install script failed with exit code 1)
```

with an empty `~/.bobide-server-insiders/bin/<commit>/` left behind — the same
symptom as a genuinely missing server, which makes it easy to misdiagnose.
Extraction is only 2s; the download is the whole problem.

`../devcontainer.json` mounts a named volume at that path so the server
survives container rebuilds. Fill it once, without the timeout, with:

```bash
bash .devcontainer/scripts/seed-bob-server.sh
```

It derives the version, commit and download URL from the installed Bob app's
`product.json`, so re-run it after Bob updates — the server is keyed by commit.

## Prerequisites

- Podman 4.x+ (rootless) with the socket service running, and **Rosetta enabled**
  (see above)
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
