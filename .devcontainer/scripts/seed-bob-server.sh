#!/usr/bin/env bash
# Seed Bob's remote-extension-host (REH) server into a named podman volume.
#
# WHY
# Bob installs its REH server into ~/.bobide-server-insiders the first time it
# attaches to a devcontainer, and allows the install script roughly 60 seconds.
# IBM's QA endpoint serves the ~110 MB tarball at about 1.9 MB/s -- measured at
# 59s from inside the container, i.e. right on the limit. Losing that race:
#
#   Failed to connect to the remote extension host server
#   (Error: Server install script failed with exit code 1)
#
# and leaves an empty ~/.bobide-server-insiders/bin/<commit>/ behind. Extraction
# takes only 2s; the download is the entire problem.
#
# devcontainer.json mounts a named volume at that path so the server survives
# container rebuilds. This script fills it with no timeout pressure, so the
# race happens at most once per Bob version -- and after running this, never.
#
# Run on the HOST (macOS), not inside the container:
#   bash .devcontainer/scripts/seed-bob-server.sh
#
# Re-run it after Bob updates: the server is keyed by commit, so a new Bob
# version needs a new download.
set -euo pipefail

VOLUME="${BOB_SERVER_VOLUME:-bob-server-insiders}"
APP="${BOB_APP:-/Applications/IBM Bob - Insiders.app}"
PRODUCT_JSON="${APP}/Contents/Resources/app/product.json"
IMAGE="${BOB_SEED_IMAGE:-docker.io/library/debian:trixie-slim}"

if [[ ! -f "${PRODUCT_JSON}" ]]; then
    echo "error: cannot find ${PRODUCT_JSON}" >&2
    echo "       set BOB_APP if Bob is installed elsewhere" >&2
    exit 1
fi

# Derive everything from the installed app so this tracks Bob upgrades rather
# than pinning a version that silently goes stale.
read -r COMMIT VERSION SERVER_DIR SERVER_APP <<EOF
$(python3 -c "
import json
p = json.load(open('${PRODUCT_JSON}'))
print(p['commit'], p['version'], p['serverDataFolderName'], p['serverApplicationName'])
")
EOF

URL="$(python3 -c "
import json
p = json.load(open('${PRODUCT_JSON}'))
print(p['serverDownloadUrlTemplate']
      .replace('\${os}', 'linux')
      .replace('\${arch}', 'x64')
      .replace('\${quality}', p.get('quality', ''))
      .replace('\${version}', p['version'])
      .replace('\${commit}', p['commit']))
")"

echo "Bob server seed"
echo "  version: ${VERSION}"
echo "  commit:  ${COMMIT}"
echo "  volume:  ${VOLUME}"

podman volume create "${VOLUME}" >/dev/null 2>&1 || true

# linux/amd64 because IBM publishes the REH for x64 only; on Apple Silicon the
# container runs it under Rosetta. See ../bob-podman-amd64/readme.md.
podman run --rm --platform=linux/amd64 \
    --userns=keep-id:uid=1000,gid=1000 \
    --security-opt=label=disable \
    -v "${VOLUME}:/server" \
    "${IMAGE}" \
    bash -c "
        set -e
        DEST=/server/bin/${COMMIT}
        if [ -x \"\$DEST/bin/${SERVER_APP}\" ]; then
            echo '  already seeded for this commit'
            exit 0
        fi
        command -v curl >/dev/null 2>&1 || {
            apt-get update -qq >/dev/null 2>&1
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends curl >/dev/null 2>&1
        }
        mkdir -p \"\$DEST\"
        echo '  downloading (~110 MB, expect roughly a minute)...'
        curl -sSLf --max-time 900 -o /tmp/reh.tgz '${URL}'
        tar -xzf /tmp/reh.tgz -C \"\$DEST\"
        rm -f /tmp/reh.tgz
        echo '  seeded'
    "

echo "Done. '${SERVER_DIR}' volume '${VOLUME}' is ready; Bob will attach without downloading."
