# IBM Bob Shell devcontainer image for a rootless Podman host.
#
# Shared base image + Bob Shell + pre-commit, plus a rootless podman-in-podman
# runtime and the `podman-docker` shim. The shim provides a `docker` -> `podman`
# wrapper so the Terraform MCP `docker run` config, the image pulls in
# post-start.sh, and Bob Shell's own container sandbox
# (docker.io/library/node:25-trixie) all resolve to podman.
FROM srlynch1/terraform-ai-tools:latest

# --- Bob Shell + pre-commit --------------------------------------------------
RUN version=$(curl -fsSL https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-version.txt) && \
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
ENV CONTAINERS_STORAGE_CONF=/etc/containers/storage.conf

USER node
