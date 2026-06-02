# Podman variant of ../copilot-cli/DockerFile.
#
# Mirrors the Copilot variant (same base image + Copilot CLI + pre-commit) and
# adds a rootless podman-in-podman runtime plus the `podman-docker` shim. The
# shim provides a `docker` -> `podman` wrapper so the unchanged Terraform MCP
# config in devcontainer.json (`command: "docker", args: ["run", ...]`) and the
# `docker image pull` in post-start.sh work via podman.
#
# Keep the Copilot install block in sync with ../copilot-cli/DockerFile.
FROM srlynch1/terraform-ai-tools:latest

# --- Copilot CLI + pre-commit (mirrors ../copilot-cli/DockerFile) -----------
RUN npm install -g @github/copilot && \
    npm cache clean --force

RUN uv tool install pre-commit --with pre-commit-uv

RUN echo 'alias copiloty="copilot --yolo --disable-builtin-mcps"' >> /home/node/.zshrc && \
    echo "alias copilota='copilot --autopilot --allow-tool=\"write,edit,shell(git:*),shell(terraform:*),shell(ls),shell(cat),shell(grep)\" --disable-builtin-mcps'" >> /home/node/.zshrc && \
    chown node:node /home/node/.zshrc

# --- Rootless podman-in-podman -----------------------------------------------
# podman + podman-docker provides the `docker` CLI shim so the inline Terraform
# MCP config (`command: "docker", args: ["run", ...]`) resolves to podman.
# slirp4netns gives the nested container outbound networking (the MCP fetches
# registry data over the network).
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
# Docker Hub, matching Docker's behaviour so the inline MCP config works unchanged.
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
RUN sed -i '/^node:/d' /etc/subuid /etc/subgid && \
    mkdir -p /home/node/.config/containers && \
    printf '[storage]\ndriver = "vfs"\n[storage.options]\nignore_chown_errors = "true"\n' \
        > /home/node/.config/containers/storage.conf && \
    chown -R node:node /home/node/.config

USER node
