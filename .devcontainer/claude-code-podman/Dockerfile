# Podman variant of ../claude-code/Dockerfile.
#
# Mirrors the Docker variant (same base image + Claude Code install) and adds a
# rootless podman-in-podman runtime plus the `podman-docker` shim. The shim
# installs a `docker` -> `podman` wrapper so the shared, unmodified .mcp.json
# (which launches the Terraform MCP via `docker run hashicorp/terraform-mcp-server`)
# works unchanged inside this container.
#
# Keep the Claude Code install block in sync with ../claude-code/Dockerfile.
FROM srlynch1/terraform-ai-tools:latest

USER root

# --- Claude Code (mirrors ../claude-code/Dockerfile) -------------------------
ENV BUN_INSTALL="/usr/local"
RUN curl -fsSL https://bun.sh/install | bash && \
    su node -c 'BUN_INSTALL="/home/node/.local" bun install -g @anthropic-ai/claude-code' && \
    mkdir -p /home/node/.claude && \
    touch /home/node/.claude/.claude.json && \
    chmod 700 /home/node/.claude && \
    chmod 600 /home/node/.claude/.claude.json && \
    chown -R node:node /home/node/.claude

COPY scripts/claude-statusline.sh /usr/local/bin/claude-statusline.sh
RUN chmod +x /usr/local/bin/claude-statusline.sh && \
    echo 'alias clauded="claude --dangerously-skip-permissions"' >> /home/node/.zshrc && \
    echo 'alias claudea="claude --permission-mode auto"' >> /home/node/.zshrc && \
    chown node:node /home/node/.zshrc

# --- Rootless podman-in-podman -----------------------------------------------
# podman + podman-docker provides the `docker` CLI shim so `docker run ...` in
# .mcp.json resolves to podman. slirp4netns gives the nested container outbound
# networking (the Terraform MCP fetches registry data over the network).
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        podman \
        podman-docker \
        slirp4netns && \
    rm -rf /var/lib/apt/lists/* && \
    # Silence the "Emulate Docker CLI using podman" banner so MCP stdio stays clean.
    touch /etc/containers/nodocker

# Resolve Docker-style short names (`hashicorp/terraform-mcp-server`) against
# Docker Hub, matching Docker's behaviour so the shared .mcp.json works unchanged.
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
ENV PATH="/home/node/.local/bin:${PATH}"
