# linux/amd64 variant of ../bob-podman/Dockerfile, for attaching the IBM Bob
# IDE (GUI) to this devcontainer from an Apple Silicon Mac.
#
# WHY THIS FILE EXISTS
# Bob's GUI attaches to a container by installing its remote-extension-host
# (REH) server inside it. IBM publishes that server for linux/x64 ONLY:
#   .../update/reh/ibm-bob/linux/x64/<ver>   -> 302, real ~110 MB tarball
#   .../update/reh/ibm-bob/linux/arm64/<ver> -> 404 {"detail":"REH server not found"}
# On an arm64 Podman machine the container is aarch64, the install script asks
# for the arm64 REH, gets a 404, and Bob reports
#   "Server install script failed with exit code 1".
# Pinning the platform to amd64 makes the container x86_64 (via QEMU emulation
# in the Podman machine), so the published x64 REH is the one requested.
#
# Everything below line 8 is IDENTICAL to ../bob-podman/Dockerfile -- only the
# FROM line differs. KEEP THE TWO IN SYNC when either is edited.
#
# Trade-off: the whole image, including the nested rootless podman runtime,
# runs under emulation. Expect slow builds and sluggish runtime.
FROM --platform=linux/amd64 srlynch1/terraform-ai-tools:latest

# --- Bob Shell + pre-commit --------------------------------------------------
RUN version=$(curl -fsSL --connect-timeout 10 --max-time 30 https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-version.txt) && \
    npm install -g "https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-${version}.tgz" && \
    npm cache clean --force

RUN uv tool install pre-commit --with pre-commit-uv

# --- Rootless podman-in-podman -----------------------------------------------
# podman + podman-docker provides the `docker` CLI shim so `docker run`/`docker
# image pull` calls (Terraform MCP, Bob's sandbox) resolve to podman.
# slirp4netns gives the nested container outbound networking.
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        podman \
        podman-docker \
        slirp4netns && \
    rm -rf /var/lib/apt/lists/* && \
    # Silence the "Emulate Docker CLI using podman" banner so MCP stdio stays clean.
    touch /etc/containers/nodocker

# Resolve Docker-style short names (`hashicorp/terraform-mcp-server`) against
# Docker Hub, matching Docker's behaviour so the MCP config works unchanged.
RUN printf 'unqualified-search-registries = ["docker.io"]\n' \
        > /etc/containers/registries.conf

# Clear podman's default container sysctls. The default sets
# net.ipv4.ping_group_range, which the nested container cannot write to the
# read-only /proc/sys of the outer rootless container (crun would error).
RUN printf '[containers]\ndefault_sysctls = []\n' \
        > /etc/containers/containers.conf

# Rootless-podman-in-rootless-podman: the OUTER container already runs in a user
# namespace (--userns=keep-id on the host), so the inner podman cannot allocate a
# second sub-uid range via newuidmap. Remove node's subuid/subgid ranges so the
# inner podman runs in single-uid mode (no newuidmap), and use the vfs storage
# driver with ignore_chown_errors so image layers that chown to other uids
# (e.g. /etc/shadow -> 42) extract cleanly under the single mapping.
#
# storage.conf lives in /etc and is pinned via CONTAINERS_STORAGE_CONF: the
# devcontainer sets XDG_CONFIG_HOME=/workspace, and rootless podman resolves
# its storage config from XDG_CONFIG_HOME *without* falling back to
# /etc/containers/storage.conf when the file is absent (verified: graphOptions
# stay empty and chown-heavy image pulls fail). The env var overrides the
# lookup unconditionally.
RUN sed -i '/^node:/d' /etc/subuid /etc/subgid && \
    printf '[storage]\ndriver = "vfs"\n[storage.options]\nignore_chown_errors = "true"\n' \
        > /etc/containers/storage.conf
# Pin every podman config lookup to /etc. With XDG_CONFIG_HOME=/workspace,
# podman would otherwise honor config placed under the (repo-controlled)
# workspace — $XDG_CONFIG_HOME/containers/{storage,containers,registries}.conf —
# letting checked-out content redirect registries or engine settings.
ENV CONTAINERS_STORAGE_CONF=/etc/containers/storage.conf \
    CONTAINERS_CONF=/etc/containers/containers.conf \
    CONTAINERS_REGISTRIES_CONF=/etc/containers/registries.conf

USER node
