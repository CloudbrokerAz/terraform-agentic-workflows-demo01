#!/usr/bin/env bash
# patch-copilot.sh — Neuter undici assert() calls in the GitHub Copilot CLI
# bundle that cause AssertionError crashes during long-lived sessions.
#
# Downstream: github/copilot-cli#1754
#   AssertionError [ERR_ASSERTION] during retrospective generation followed
#   by HTTP/2 GOAWAY connection error (503). Particularly affects sub-agent
#   dispatch via the task tool — crashes after 1-2 tool calls regardless of
#   session duration. Main agent performing identical operations works fine.
#
# ROOT CAUSE
# ----------
# The bundled undici HTTP client has race conditions in its HTTP/2 connection
# pool and dispatch loop that cause state invariant violations:
#
#   - client.js _resume():  assert(client[kPending] === 0)  fires when a
#     client is destroyed while requests are still queued (GOAWAY / timeout).
#   - client-h1.js onHttpSocketClose():  assert(client[kRunning] === 0)
#     fires when socket closes before running requests are drained.
#   - client-h2.js:  assert(!this.completed)  fires when late DATA frames
#     arrive after request completion (nodejs/undici#4843).
#   - Pool/Agent dispatchers:  assert(this.callback)  fires when error-rate
#     spikes cause connection churn (nodejs/undici#4059).
#
# These are known upstream bugs (nodejs/undici#4059, #4843, #4846, #3011).
# Active fix PRs exist (e.g. nodejs/undici#4845) but the Copilot CLI bundles
# an older undici snapshot that predates them.
#
# The assertions are debug invariants, NOT control flow — undici's own
# production builds strip them.  When they fire, the process crashes instead
# of allowing the existing error-recovery paths (retry, reconnect) to run.
#
# STRATEGY
# --------
# 1. ASSERT NEUTERING: Replace undici require("assert") imports with a
#    self-referencing Proxy no-op so assertions become silent no-ops.
#
# 2. UPSTREAM H2 FIXES (nodejs/undici#4845): Apply the actual code fixes
#    from the upstream PR to the minified bundle:
#    a) Guard H2 data handler — early return if request.aborted/completed
#    b) Remove data listeners before onComplete in trailers handler
#
# The Proxy no-op pattern:
#   (()=>{let a=new Proxy(()=>{},{get:()=>a});return a})()
#
# This is callable (assert(expr) → no-op), supports property access
# (assert.strictEqual(a,b) → no-op), and is infinitely chainable
# (assert.strict.ok(expr) → no-op).  Non-undici assert imports (fetch-spec,
# crypto, cache API, tree-sitter, etc.) are left intact.
#
# SCOPE
# -----
# Patches ~25 undici assert imports per bundle (index.js, sdk/index.js).
# Remaining ~32 non-undici imports per bundle are untouched.
# Includes backup, idempotency check, and node --check syntax validation.
#
# REMOVAL
# -------
# Remove this patch when the Copilot CLI ships an undici version containing
# the fixes from nodejs/undici#4845, #4846, #4059 — or when the bundled
# undici drops assert() calls in its production build.
#
# Usage:
#   ./scripts/patch-copilot.sh            # auto-detect install path
#   ./scripts/patch-copilot.sh /path/to/@github/copilot
#   ./scripts/patch-copilot.sh --force     # re-patch even if already patched

set -euo pipefail

FORCE=false
if [[ "${1:-}" == "--force" || "${1:-}" == "-f" ]]; then
  FORCE=true
  shift
fi

# ── Locate the copilot package ────────────────────────────────────────────────
find_package_dir() {
  local npm_root
  npm_root="$(npm root -g 2>/dev/null || true)"
  if [[ -f "$npm_root/@github/copilot/index.js" ]]; then
    echo "$npm_root/@github/copilot"
    return
  fi

  while IFS= read -r bin; do
    local resolved dir
    resolved="$(readlink -f "$bin" 2>/dev/null || true)"
    dir="$(dirname "$resolved")"
    if [[ -f "$dir/index.js" ]]; then
      echo "$dir"
      return
    fi
  done < <(command -v -a copilot 2>/dev/null || true)
}

if [[ $# -ge 1 ]]; then
  COPILOT_DIR="$1"
else
  COPILOT_DIR="$(find_package_dir)"
  if [[ -z "$COPILOT_DIR" ]]; then
    echo "❌  Could not locate the @github/copilot npm package." >&2
    echo "    Pass the package directory explicitly: $0 /path/to/@github/copilot" >&2
    exit 1
  fi
fi

if [[ ! -d "$COPILOT_DIR" ]]; then
  echo "❌  Directory not found: $COPILOT_DIR" >&2
  exit 1
fi

echo "📦  Copilot package: $COPILOT_DIR"

# ── Patch a single JS bundle file ────────────────────────────────────────────
patch_bundle() {
  local file="$1"
  local label
  label="$(basename "$(dirname "$file")")/$(basename "$file")"

  if [[ ! -f "$file" ]]; then
    return 0
  fi

  if grep -q '__UNDICI_ASSERT_PATCH__' "$file" 2>/dev/null; then
    if [[ "$FORCE" != true ]]; then
      echo "  ✅  $label — already patched (use --force to re-apply)"
      return 0
    fi
    echo "  🔄  $label — force re-patching from backup"
    local backup="${file}.bak"
    if [[ -f "$backup" ]]; then
      cp "$backup" "$file"
    else
      echo "  ❌  $label — no backup found, cannot force re-patch" >&2
      return 1
    fi
  fi

  # Backup
  local backup="${file}.bak"
  if [[ ! -f "$backup" ]]; then
    cp "$file" "$backup"
    echo "  💾  Backup: $backup"
  fi

  local tmp
  tmp="$(mktemp /tmp/patch-copilot-XXXXXX)"
  cp "$file" "$tmp"

  # Apply patch: replace undici assert imports with no-ops
  local patched
  patched=$(python3 - "$tmp" <<'PYEOF'
import re, sys
path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()

# Detect which require alias this bundle uses (ve or z)
# by checking which one appears with "node:assert"
req_fn = None
for candidate in ['ve', 'z']:
    if f'{candidate}("node:assert")' in content or f'{candidate}("assert")' in content:
        req_fn = candidate
        break
if req_fn is None:
    print(0)
    sys.exit(0)

# Undici keyword fingerprints — if any appear within 2000 chars of the
# assert import, we know it belongs to undici (not some other module).
UNDICI_KEYWORDS = [
    'kRunning', 'kPending', 'kSize', 'kBusy', 'kConnected', 'kFree',
    'kUrl', 'kClose', 'kDestroy', 'kDispatch', 'kNeedDrain',
    'kKeepAliveTimeout', 'kSocket', 'kClient', 'kHeadersList',
    'kDestroyed', 'kBodyUsed',
    'RequestAbortedError', 'NotSupportedError', 'InvalidArgumentError',
    'SocketError', 'kRetryHandlerDefaultRetry',
    'addSignal', 'removeSignal',
]

# No-op replacement: a callable Proxy whose property access returns itself,
# so both  assert(expr)  and  assert.strictEqual(a,b)  become no-ops.
NOOP = '(()=>{let a=new Proxy(()=>{},{get:()=>a});return a})()'

# ── Collect all replacements as (start, end, text) tuples ────────────────
# All patterns scan the ORIGINAL content. Replacements are applied in a
# single O(n) pass at the end, eliminating O(n*m) intermediate string copies.
replacements = []
counts = {'assert': 0, 'h2_data': 0, 'h2_trailers': 0, 'resume': 0, 'callback': 0}

# ── Assert neutering ────────────────────────────────────────────────────
# Match every  REQFN("assert")  /  REQFN("node:assert")  occurrence.
assert_pat = re.compile(re.escape(req_fn) + r'\("(?:node:)?assert"\)')
for m in assert_pat.finditer(content):
    ctx = content[m.start():m.start()+2000]
    if any(kw in ctx for kw in UNDICI_KEYWORDS):
        replacements.append((m.start(), m.end(), NOOP))
        counts['assert'] += 1

# ── Upstream fix: nodejs/undici#4845 ─────────────────────────────────────
# Fix 1: Guard H2 data handler — skip late DATA frames after completion.
#   Before:  STREAM.on("data",CHUNK=>{REQUEST.onData(CHUNK)===!1&&STREAM.pause()})
#   After:   STREAM.on("data",CHUNK=>{if(REQUEST.aborted||REQUEST.completed)return;REQUEST.onData(CHUNK)===!1&&STREAM.pause()})
#
# Uses literal-anchored search (.on("data",) then targeted regex at each
# candidate — avoids backreference regex scan over the full 15+ MB bundle.
H2_DATA_ANCHOR = '.on("data",'
pos = 0
while True:
    idx = content.find(H2_DATA_ANCHOR, pos)
    if idx == -1:
        break
    # Walk back to find STREAM identifier
    si = idx - 1
    while si >= 0 and content[si].isalpha():
        si -= 1
    si += 1
    stream = content[si:idx]
    if not stream:
        pos = idx + 1
        continue
    # Try to match the full pattern in a small window
    window = content[si:idx+200]
    lm = re.match(
        re.escape(stream) + r'\.on\("data",([a-zA-Z]+)=>\{([a-zA-Z]+)\.onData\(\1\)===!1&&'
        + re.escape(stream) + r'\.pause\(\)\}\)',
        window
    )
    if lm:
        chunk, req = lm.group(1), lm.group(2)
        match_end = si + lm.end()
        # Only patch H2 client contexts (near HTTP/2-specific patterns)
        ctx = content[max(0,si-800):si+800]
        if 'onComplete' in ctx and ('trailers' in ctx or 'openStreams' in ctx
                or '.request(' in ctx or 'onHeaders' in ctx):
            repl = (
                f'{stream}.on("data",{chunk}=>{{if({req}.aborted||{req}.completed)return;'
                f'{req}.onData({chunk})===!1&&{stream}.pause()}})'
            )
            replacements.append((si, match_end, repl))
            counts['h2_data'] += 1
    pos = idx + 1

# Fix 2: Remove data listeners before onComplete in trailers handler.
#   Before:  STREAM.once("trailers",VAR=>{REQUEST.aborted||REQUEST.completed||REQUEST.onComplete(VAR)})
#   After:   STREAM.once("trailers",VAR=>{REQUEST.aborted||REQUEST.completed||(STREAM.removeAllListeners("data"),REQUEST.onComplete(VAR))})
H2_TRAILER_ANCHOR = '.once("trailers",'
pos = 0
while True:
    idx = content.find(H2_TRAILER_ANCHOR, pos)
    if idx == -1:
        break
    si = idx - 1
    while si >= 0 and content[si].isalpha():
        si -= 1
    si += 1
    stream = content[si:idx]
    if not stream:
        pos = idx + 1
        continue
    window = content[si:idx+300]
    lm = re.match(
        re.escape(stream) + r'\.once\("trailers",([a-zA-Z]+)=>\{([a-zA-Z]+)\.aborted\|\|\2\.completed\|\|'
        r'\2\.onComplete\(\1\)\}\)',
        window
    )
    if lm:
        var, req = lm.group(1), lm.group(2)
        match_end = si + lm.end()
        repl = (
            f'{stream}.once("trailers",{var}=>{{{req}.aborted||{req}.completed||'
            f'({stream}.removeAllListeners("data"),{req}.onComplete({var}))}})'
        )
        replacements.append((si, match_end, repl))
        counts['h2_trailers'] += 1
    pos = idx + 1

# ── Upstream fix: nodejs/undici#4846 ─────────────────────────────────────
# Fix 3: Null guard in _resume after fetching request from queue.
#   Before:  let VAR=t[QUEUE][t[PENDING]];if(t[URL].protocol==="https:"&&t[SN]!==VAR.servername)
#   After:   let VAR=t[QUEUE][t[PENDING]];if(!VAR)return;if(t[URL].protocol==="https:"&&t[SN]!==VAR.servername)
# This prevents TypeError: Cannot read properties of null (reading 'servername')
# when H2 stream completion nulls a queue slot and kResume is called.
resume_null = re.compile(
    r'let (?P<var>[a-zA-Z])=t\[(?P<queue>\w+)\]\[t\[(?P<pending>\w+)\]\];'
    r'if\(t\[(?P<url>\w+)\]\.protocol==="https:"&&t\[(?P<sn>\w+)\]!==(?P=var)\.servername\)'
)
for m in resume_null.finditer(content):
    original = m.group(0)
    v = m.group('var')
    let_end = original.index(';') + 1
    repl = original[:let_end] + f'if(!{v})return;' + original[let_end:]
    replacements.append((m.start(), m.end(), repl))
    counts['resume'] += 1

# ── Upstream fix: nodejs/undici#4059 ─────────────────────────────────────
# Fix 4: Guard onConnect when callback is null (onError raced ahead).
#   Before:  ASSERT(this.callback),this.abort=VAR,this.context=...}
#   After:   if(!this.callback){VAR(new Error("request aborted"));return}this.abort=VAR,this.context=...}
# This prevents TypeError when onError fires before onConnect under high
# error rates, nullifying this.callback before the assert check.
#
# Uses literal-anchored search to avoid expensive \w+ backreference scan.
CB_ANCHOR = 'this.callback),this.abort='
pos = 0
while True:
    idx = content.find(CB_ANCHOR, pos)
    if idx == -1:
        break
    # Walk back past the opening paren to find the assert function name
    paren = idx - 1  # should be '('
    if paren < 0 or content[paren] != '(':
        pos = idx + 1
        continue
    fi = paren - 1
    while fi >= 0 and content[fi].isalpha():
        fi -= 1
    fi += 1
    assert_fn = content[fi:paren]
    if not assert_fn:
        pos = idx + 1
        continue
    # Extract VAR (single char after this.abort=)
    after = idx + len(CB_ANCHOR)
    if after >= len(content) or not content[after].isalpha():
        pos = idx + 1
        continue
    var = content[after]
    # Find ,this.context=CTX}
    ctx_marker = ',this.context='
    ctx_idx = content.find(ctx_marker, after + 1)
    if ctx_idx == -1 or ctx_idx > after + 20:
        pos = idx + 1
        continue
    ci = ctx_idx + len(ctx_marker)
    ce = ci
    while ce < len(content) and content[ce].isalpha():
        ce += 1
    if ce >= len(content) or content[ce] != '}':
        pos = idx + 1
        continue
    ctx_val = content[ci:ce]
    match_end = ce + 1
    repl = (
        f'if(!this.callback){{{var}(new Error("request aborted"));return}}'
        f'this.abort={var},this.context={ctx_val}}}'
    )
    replacements.append((fi, match_end, repl))
    counts['callback'] += 1
    pos = idx + 1

# ── Single-pass string rebuild ───────────────────────────────────────────
replacements.sort(key=lambda r: r[0])
# Validate no overlaps
for i in range(1, len(replacements)):
    if replacements[i][0] < replacements[i-1][1]:
        sys.stderr.write(
            f'  ⚠️  Overlapping replacements at {replacements[i-1][0]}-{replacements[i-1][1]}'
            f' and {replacements[i][0]}-{replacements[i][1]}\n'
        )
parts = []
last = 0
for start, end, repl in replacements:
    parts.append(content[last:start])
    parts.append(repl)
    last = end
parts.append(content[last:])
content = ''.join(parts)

total = sum(counts.values())
with open(path, 'w') as f:
    f.write(content)
print(f'{total}')
sys.stderr.write(
    f'  🔧  H2 data guards: {counts["h2_data"]}, trailers fixes: {counts["h2_trailers"]}, '
    f'resume null guards: {counts["resume"]}, onConnect guards: {counts["callback"]}\n'
)
PYEOF
)

  if [[ "$patched" -eq 0 ]]; then
    echo "  ⚠️   $label — no undici assert imports found (already clean or different build)"
    rm -f "$tmp"
    return 0
  fi

  echo "  🔍  $label — neutered $patched undici assert import(s)"

  echo "" >> "$tmp"
  echo "// __UNDICI_ASSERT_PATCH__" >> "$tmp"

  # Syntax check
  if ! node --check "$tmp" 2>/dev/null; then
    echo "  ❌  $label — syntax check failed, restoring backup" >&2
    cp "$backup" "$file"
    rm -f "$tmp"
    return 1
  fi

  mv "$tmp" "$file"
  echo "  ✅  $label — patched successfully"
}

# ── Patch all known bundle files ─────────────────────────────────────────────
ERRORS=0
patch_bundle "$COPILOT_DIR/index.js"     || ERRORS=$((ERRORS + 1))
patch_bundle "$COPILOT_DIR/sdk/index.js" || ERRORS=$((ERRORS + 1))

if [[ "$ERRORS" -gt 0 ]]; then
  echo ""
  echo "❌  $ERRORS bundle(s) failed to patch." >&2
  exit 1
fi

echo ""
echo "✅  All bundles patched successfully."
