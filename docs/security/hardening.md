# DevContainer Security Hardening Plan — Claude Code (Podman / Docker)

**Scope:** `.devcontainer/` configurations that run Claude Code (and Copilot CLI) as
coding agents inside a container, with bind-mounted source, cloud/HCP credentials in
the environment, and nested container runtimes (docker-in-docker / podman-in-podman).

**Threat model.** The primary risk is not a malicious *user* — it is the agent itself
acting on untrusted input. Claude Code executes shell commands, reads web content,
and runs MCP servers; a prompt-injection payload in a fetched page, a dependency, a
Terraform module, or an MCP response can cause the agent to exfiltrate the credentials
mounted into the container (AWS keys, `TFE_TOKEN`, `GITHUB_TOKEN`) or pivot through the
nested container runtime. The container boundary is the blast-radius control. Anthropic
is explicit that the devcontainer's value depends on a **default-deny egress firewall**
combined with `--dangerously-skip-permissions`, and that *"no system is completely immune
to all attacks"* — defence in depth is required.
([Claude Code devcontainer docs](https://code.claude.com/docs/en/devcontainer))

---

## Current posture (what was reviewed)

Files reviewed under `.devcontainer/`:

| Area | Observation |
|---|---|
| Egress firewall | **Absent.** `iptables`/`ipset` are installed in `base-image/Dockerfile` and `--cap-add=NET_ADMIN --cap-add=NET_RAW` is granted, but **no `init-firewall.sh` exists and nothing runs it.** Egress is fully open. |
| Capabilities | `NET_ADMIN` + `NET_RAW` added on both Docker and Podman variants; podman variant also retains them "for parity" with no consumer. |
| Podman security opts | `seccomp=unconfined`, `label=disable` (SELinux off), `unmask=ALL` (full `/proc`) — three confinement layers disabled at once. |
| Privilege | `node` has passwordless `sudo` (`%wheel NOPASSWD: ALL`) baked into the base image. |
| Secrets | AWS keys, `TFE_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN` injected as **long-lived process env vars**; `TFE_TOKEN` also written to `~/.terraform.d/credentials.tfrc.json`. |
| Bypass aliases | `clauded="claude --dangerously-skip-permissions"` and `claudea`/`copiloty --yolo` shipped in `.zshrc` — full-autonomy modes one keystroke away, with no compensating egress control. |
| Base image | `FROM srlynch1/terraform-ai-tools:latest` and `node:25.7.0-slim` — **unpinned `latest` / floating tags**, no digest pinning, personal Docker Hub namespace. |
| Supply chain | `curl … bun.sh/install | bash` and `wget -O- … zsh-in-docker.sh` piped to a shell, unverified. |
| Nested runtime | docker-in-docker (Docker) / rootless podman-in-podman (Podman) — expands attack surface; the Podman variant is rootless (good) but Docker DinD is effectively root-capable. |
| Telemetry | OTEL endpoint and tokens sourced from `localEnv` — fine, but `OTEL_EXPORTER_OTLP_ENDPOINT` is unvalidated egress if the firewall lands. |

**Headline gap:** the configuration *looks* hardened (NET_ADMIN + iptables present) but the
actual lockdown step is missing, so the capabilities are pure added attack surface with no
benefit. Closing that gap is item **P0-1**.

---

## Prioritised recommendations

Priority key: **P0** = do now (removes a real exfiltration/escape path), **P1** = high,
**P2** = medium / hygiene, **P3** = optional hardening. Each item lists a **Source** and
**Provenance** (why it applies *here*).

### P0 — Critical

#### P0-1 · Ship and enforce a default-deny egress firewall
The single most important control. Add `init-firewall.sh` that flushes rules, sets
`OUTPUT`/`FORWARD` default-DROP, allows only DNS, the host loopback, the devcontainer's own
subnet, and an **allowlist** resolved at runtime: `api.anthropic.com`, `registry.npmjs.org`,
`statsig.anthropic.com`, GitHub IP ranges from `https://api.github.com/meta`, plus the
endpoints this repo actually needs — `app.terraform.io` / your TFE host, `registry.terraform.io`,
AWS API/STS endpoints for your region, and `docker.io`/`ghcr.io` for image pulls. Run it from
`postStartCommand` (root, before the agent starts) and **verify** it (e.g. assert a
non-allowlisted host like `example.com` times out and `api.anthropic.com` succeeds), failing the
start if verification fails.
- **Why P0:** without it, `NET_ADMIN`/`NET_RAW`/iptables are dead weight and the agent can POST
  the mounted AWS/TFE/GitHub credentials anywhere. This is the control Anthropic's reference
  exists to provide.
- **Source:** [anthropics/claude-code `init-firewall.sh`](https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh) ·
  [Claude Code devcontainer docs](https://code.claude.com/docs/en/devcontainer)
- **Provenance:** your base image already installs `iptables ipset aggregate dnsutils` and grants
  the caps — the scaffolding is present; only the script and its invocation are missing.

#### P0-2 · Scope and shorten the injected credentials
Treat the mounted secrets as the crown jewels the firewall protects.
- AWS: require **temporary STS session credentials** (`AWS_SESSION_TOKEN` is already wired) — never
  long-lived `AWS_ACCESS_KEY_ID` users. Keep `AWS_SESSION_EXPIRATION` short (≤1h).
- Prefer a **fine-grained, read-mostly `GITHUB_TOKEN`** scoped to the repos in play, not a classic
  PAT with org-wide scope.
- `TFE_TOKEN` should be a **team token** scoped to the needed workspaces, not a user token.
- **Why P0:** the firewall reduces *where* secrets can go; scoping reduces *what they're worth* if
  egress is ever bypassed (DNS exfil, an allowlisted-host SSRF, a compromised MCP server).
- **Source:** [AWS IAM temporary security credentials best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp.html) ·
  [GitHub fine-grained PAT docs](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- **Provenance:** `devcontainer.json` injects all four token families as plain `remoteEnv`; nothing
  currently bounds their scope or lifetime.

#### P0-3 · Don't ship `--dangerously-skip-permissions` without the firewall
The `clauded` / `claudea` / `copiloty --yolo` aliases pre-stage full-autonomy execution. Anthropic
only sanctions `--dangerously-skip-permissions` **inside a network-restricted container**. Gate the
aliases behind a check that the firewall is active (e.g. the alias runs `init-firewall.sh --verify`
first, or refuses if egress to `example.com` succeeds).
- **Why P0:** bypass-permissions + open egress + mounted cloud creds is the exact combination
  Anthropic warns against.
- **Source:** [Claude Code devcontainer docs — "skip permissions safely"](https://code.claude.com/docs/en/devcontainer) ·
  [Claude Code security](https://docs.anthropic.com/en/docs/claude-code/security)
- **Provenance:** both Claude Dockerfiles write these aliases into `.zshrc`; no compensating control
  gates them today.

### P1 — High

#### P1-1 · Stop disabling three confinement layers on the Podman variant
`seccomp=unconfined` + `label=disable` + `unmask=ALL` together strip syscall filtering, SELinux,
and `/proc` masking. Re-introduce them incrementally:
- Replace `seccomp=unconfined` with a **custom seccomp profile** that adds back only the syscalls
  the nested rootless podman needs, rather than disabling the filter wholesale.
- Replace `label=disable` with proper SELinux volume relabeling (`:Z`/`:z` on the bind mount) on
  RHEL/Fedora hosts instead of turning SELinux off for the container.
- Narrow `unmask=ALL` to the specific `/proc` paths the nested container mounts.
- **Why P1:** `seccomp=unconfined` "dramatically increases risk and should only be used in
  well-understood scenarios"; you've disabled it for *convenience of the nested runtime*, which is a
  recognised but reducible trade-off.
- **Source:** [Podman least-privilege / seccomp guidance](https://docs.podman.io/en/latest/markdown/podman-run.1.html) ·
  [Docker seccomp docs](https://docs.docker.com/engine/security/seccomp/) ·
  [Red Hat — container security with seccomp](https://www.redhat.com/en/blog/container-security-seccomp)
- **Provenance:** `claude-code-podman/devcontainer.json` documents each opt's reason — those reasons
  are nested-runtime workarounds, each replaceable with a narrower control.

#### P1-2 · Pin base images by digest, drop `:latest`
`FROM srlynch1/terraform-ai-tools:latest` and `node:25.7.0-slim` (and `astral/uv:latest`,
`golang:1.24-bookworm`) are mutable tags. Pin to `…@sha256:<digest>` and prefer an
organisation-owned registry over a personal Docker Hub namespace.
- **Why P1:** `latest` means a non-reproducible build and a silent supply-chain swap point; CIS
  Docker Benchmark requires images be referenced immutably.
- **Source:** [CIS Docker Benchmark §4 (image trust/pinning)](https://www.cisecurity.org/benchmark/docker) ·
  [Docker — image best practices](https://docs.docker.com/build/building/best-practices/)
- **Provenance:** every Dockerfile in `.devcontainer/` uses a floating tag, including a personal
  namespace (`srlynch1/…`).

#### P1-3 · Verify piped-to-shell installers
`curl -fsSL https://bun.sh/install | bash` and `wget -O- …/zsh-in-docker.sh` execute remote code
unverified at build time. Pin to a released artifact + checksum (or vendored installer), or install
bun from a pinned release tarball with a verified SHA256.
- **Why P1:** classic `curl | bash` supply-chain exposure inside the image the agent runs in.
- **Source:** [OWASP — CI/CD & supply-chain (CICD-SEC) guidance](https://owasp.org/www-project-top-10-ci-cd-security-risks/) ·
  [SLSA supply-chain framework](https://slsa.dev/)
- **Provenance:** `claude-code/Dockerfile` and `base-image/Dockerfile` both pipe network content
  straight into a shell.

#### P1-4 · Reconsider passwordless root `sudo` for `node`
`%wheel NOPASSWD: ALL` means the agent can trivially become root, undoing rootless Podman's main
benefit and letting it edit the firewall it's supposed to be confined by. If sudo is only needed for
a handful of post-create steps (the `containerd` pin, `chown`), restrict the sudoers rule to those
exact commands.
- **Why P1:** least privilege; an agent with passwordless root can flush the P0-1 firewall.
- **Source:** [CIS Docker Benchmark §5 (least privilege / no new privileges)](https://www.cisecurity.org/benchmark/docker) ·
  [NIST SP 800-190 §4.2](https://csrc.nist.gov/pubs/sp/800/190/final)
- **Provenance:** `base-image/Dockerfile` grants blanket `NOPASSWD: ALL`; `post-create.sh` only uses
  sudo for `apt-get`/`apt-mark`/`chown`.

### P2 — Medium / hygiene

#### P2-1 · Drop `NET_ADMIN`/`NET_RAW` from any variant that doesn't run the firewall
Once P0-1 lands, only the process that *applies* iptables needs these caps. If the firewall runs as
a one-shot at start, consider dropping the caps from the long-lived agent context, or at minimum
remove them from the Podman variant's "parity" note where nothing consumes them.
- **Source:** [Docker — runtime privilege & Linux capabilities](https://docs.docker.com/engine/containers/run/#runtime-privilege-and-linux-capabilities)
- **Provenance:** podman `devcontainer.json` comments admit the caps are kept only "for parity".

#### P2-2 · Add `--security-opt=no-new-privileges` and a read-only-where-possible posture
Set `no-new-privileges` so setuid binaries can't escalate; mount `tmpfs` for scratch and keep the
workspace the only writable bind. Consider `--cap-drop=ALL` then add back the minimum.
- **Source:** [CIS Docker Benchmark §5.25](https://www.cisecurity.org/benchmark/docker) ·
  [Docker security docs](https://docs.docker.com/engine/security/)
- **Provenance:** neither variant sets `no-new-privileges`; default cap set is kept.

#### P2-3 · Constrain and pin MCP servers
`.mcp.json` runs `hashicorp/terraform-mcp-server:latest` (mutable) and `uvx …@latest` for AWS docs.
Pin MCP server images by digest/version, and remember `ENABLE_TF_OPERATIONS=true` lets the MCP run
real Terraform operations with the mounted `TFE_TOKEN` — treat MCP responses as untrusted input that
can drive the agent.
- **Source:** [Anthropic MCP security / trust guidance](https://modelcontextprotocol.io/docs/concepts/transports#security-considerations) ·
  [Claude Code MCP docs](https://docs.anthropic.com/en/docs/claude-code/mcp)
- **Provenance:** `.mcp.json` uses `:latest` and enables TF operations; MCP output is a documented
  prompt-injection vector.

#### P2-4 · Resource limits to bound denial-of-wallet / runaway agents
Set `--memory`, `--pids-limit`, and `--cpus` (or compose equivalents). Agent swarms
(`CLAUDE_CODE_AGENT_SWARMS=true`, `EXPERIMENTAL_AGENT_TEAMS`) can fan out many processes.
- **Source:** [CIS Docker Benchmark §5.10–5.12](https://www.cisecurity.org/benchmark/docker)
- **Provenance:** swarm/teams flags are enabled in `remoteEnv`; no resource caps are set.

#### P2-5 · Verify the internal-CA injection path
`setup-internal-certs.sh` adds a CA from `INTERNAL_CA_*` env and sets `NODE_EXTRA_CA_CERTS`. Ensure
the CA source is authenticated (fetched over a trusted channel / checksum-verified), since a rogue CA
would let an on-path actor MITM the agent's "allowlisted" TLS.
- **Source:** [Mozilla CA / TLS trust guidance](https://wiki.mozilla.org/CA) ·
  general TLS trust-store hygiene
- **Provenance:** `post-create.sh` trusts `INTERNAL_CA_HOST`/`INTERNAL_CA_IP` from `localEnv`.

### P3 — Optional / defence-in-depth

- **P3-1 · Egress allowlist tests in CI.** Run a smoke test that boots the container and asserts the
  firewall blocks a known-bad host and allows the required ones, so P0-1 can't silently regress
  (note the documented gotcha that the `claude-code` devcontainer *feature* can overwrite a custom
  `init-firewall.sh` — pin the feature or guard the path).
  **Source:** [claude-code#32113 — feature overwrites custom init-firewall.sh](https://github.com/anthropics/claude-code/issues/32113)
- **P3-2 · Image/filesystem scanning.** Run `trivy`/`checkov` (already in the base image) against the
  built devcontainer image in CI, not just the Terraform.
  **Source:** [Aqua Trivy docs](https://aquasecurity.github.io/trivy/)
- **P3-3 · Don't persist secrets to disk.** `TFE_TOKEN` is written to
  `~/.terraform.d/credentials.tfrc.json` on a named volume that outlives the session — prefer
  `TF_TOKEN_app_terraform_io` env-only auth so nothing lands in a persistent volume.
  **Source:** [Terraform CLI credentials env var docs](https://developer.hashicorp.com/terraform/cli/config/config-file#environment-variable-credentials)
- **P3-4 · Telemetry endpoint allowlisting.** When P0-1 lands, add only the trusted OTEL collector to
  the allowlist; don't leave `OTEL_EXPORTER_OTLP_ENDPOINT` as an open egress carve-out.

---

## Suggested sequencing

1. **P0-1** firewall script + verification (unblocks safe use of bypass modes).
2. **P0-2 / P0-3** credential scoping + gate the `clauded`/yolo aliases on the firewall.
3. **P1-1 … P1-4** re-tighten Podman confinement, pin images, verify installers, scope sudo.
4. **P2 / P3** hygiene and CI regression guards.

After P0 + P1, the container matches Anthropic's reference posture (default-deny egress +
permission bypass only inside isolation) and closes the rootless-Podman confinement-disabling and
supply-chain gaps that go beyond the reference.

---

## Sources

- [anthropics/claude-code — `.devcontainer/init-firewall.sh`](https://github.com/anthropics/claude-code/blob/main/.devcontainer/init-firewall.sh)
- [Claude Code — Development containers docs](https://code.claude.com/docs/en/devcontainer)
- [Claude Code — Security](https://docs.anthropic.com/en/docs/claude-code/security)
- [claude-code#32113 — devcontainer feature overwrites custom init-firewall.sh](https://github.com/anthropics/claude-code/issues/32113)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [NIST SP 800-190 — Application Container Security Guide](https://csrc.nist.gov/pubs/sp/800/190/final)
- [Docker — Seccomp security profiles](https://docs.docker.com/engine/security/seccomp/)
- [Podman — `podman run` (security-opt, capabilities)](https://docs.podman.io/en/latest/markdown/podman-run.1.html)
- [Red Hat — Improving Linux container security with seccomp](https://www.redhat.com/en/blog/container-security-seccomp)
- [Docker — Building best practices (image pinning)](https://docs.docker.com/build/building/best-practices/)
- [OWASP Top 10 CI/CD Security Risks](https://owasp.org/www-project-top-10-ci-cd-security-risks/)
- [SLSA — Supply-chain Levels for Software Artifacts](https://slsa.dev/)
- [AWS — Temporary security credentials best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp.html)
- [GitHub — Fine-grained personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Model Context Protocol — security considerations](https://modelcontextprotocol.io/docs/concepts/transports#security-considerations)
