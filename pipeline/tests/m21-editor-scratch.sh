#!/usr/bin/env bash
# m21-editor-scratch.sh: the stable editor copy (pipeline/bin/editor-stable.sh) against a SCRATCH editor repository (M21).
#   bash pipeline/tests/m21-editor-scratch.sh      exits 0 when every check passes, prints "m21-editor-scratch: N passed, M failed"
#
# No network, no model call, never the real editor repo and never port 5310 (the test server uses EDITOR_PORT, first free port from 5417; the
# status check only asks what the configured port is). The scratch editor is a tiny node project: `npm run build` writes dist/index.html
# stamped with the commit, `npm run build:cli` writes dist-cli/marker, a FAIL_BUILD file makes the build fail, serve.js is the "preview"
# (the test sets EDITOR_SERVE_COMMAND='node serve.js {port}'). The history:
#   batch-01: progress, batch-01: review (accepted)
#   batch-02: review (in_progress_batch is not none: skipped)
#   batch-03: review (its last review line says needs-work, an earlier one accepted: skipped)
#   batch-04: review (accepted, but the build fails)       added in section 2
#   batch-05: review (accepted, good, package-lock changes)  added in section 3
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
TEST_NAME="m21-editor-scratch"
T="$(mktemp -d)"
TP="$(mixed "$T")"
export NO_COLOR=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid
SCRIPT="$REPO_DIR/pipeline/bin/editor-stable.sh"
free_port() {  # the first port from 5417 up that nothing listens on (the editor's own servers use 53xx)
  local p listening
  listening="$(netstat -ano 2>/dev/null | tr -d '\r' | awk '$1 == "TCP" && $4 == "LISTENING" { n = split($2, a, ":"); print a[n] }')"
  for p in $(seq 5417 5480); do
    printf '%s\n' "$listening" | grep -q -x "$p" || { printf '%s' "$p"; return 0; }
  done
  printf 5417
}
TPORT="${M21_TEST_PORT:-$(free_port)}"
REPO="$T/editor"
STABLE="$T/editor-stable"
ROOT="$T/root"
mkdir -p "$ROOT" "$REPO"
cp "$REPO_DIR/config.json" "$ROOT/config.json"
export REELS_ROOT="$ROOT"
unset REELS_GLOBAL_LOCKS REELS_CHANNEL
export REELS_HEAVY_POLL=1

es() {  # es <args...>: the script against the scratch repo, the scratch stable dir and the test port; every call also checks that
        # editor.repo (HEAD, status, reflog) is exactly as it was (a difference is written to $T/guard-bad)
  local before after rc
  before="$(repo_snap)"
  EDITOR_REPO="$REPO" EDITOR_STABLE_DIR="$STABLE" EDITOR_PORT="$TPORT" EDITOR_SERVE_COMMAND='node serve.js {port}' bash "$SCRIPT" "$@"; rc=$?
  after="$(repo_snap)"
  [ "$before" = "$after" ] || { printf 'es %s: editor.repo changed\n' "$*" >> "$T/guard-bad"; diff <(printf '%s\n' "$before") <(printf '%s\n' "$after") >> "$T/guard-bad"; }
  return "$rc"
}
m21_cleanup() {
  es stop >/dev/null 2>&1 || true
  REELS_ROOT="$T/root2" EDITOR_STABLE_DIR="$T/stable2" EDITOR_REPO="$REPO" EDITOR_PORT="$TPORT" bash "$SCRIPT" stop >/dev/null 2>&1 || true
  sleep 1
  rm -rf "$T" 2>/dev/null || { sleep 2; rm -rf "$T" 2>/dev/null || true; }
  tests_cleanup
}
trap m21_cleanup EXIT

# ---- the scratch editor ----
G() { git -C "$REPO" "$@"; }
write_static() {
  cat > "$REPO/build.js" <<'EOF'
const fs = require('fs'), cp = require('child_process');
fs.rmSync('dist', { recursive: true, force: true });
if (fs.existsSync('FAIL_BUILD')) { console.error('build error: FAIL_BUILD is present'); process.exit(1); }
const sha = cp.execSync('git rev-parse HEAD').toString().trim();
fs.mkdirSync('dist');
fs.writeFileSync('dist/index.html', '<html>stable ' + sha + '</html>');
EOF
  cat > "$REPO/build-cli.js" <<'EOF'
const fs = require('fs'), cp = require('child_process');
const sha = cp.execSync('git rev-parse HEAD').toString().trim();
fs.rmSync('dist-cli', { recursive: true, force: true });
fs.mkdirSync('dist-cli');
fs.writeFileSync('dist-cli/marker', sha);
EOF
  cat > "$REPO/serve.js" <<'EOF'
const http = require('http'), fs = require('fs');
http.createServer((req, res) => {
  let body = 'no build';
  try { body = fs.readFileSync('dist/index.html', 'utf8'); } catch (e) {}
  res.writeHead(200, { 'content-type': 'text/html' });
  res.end(body);
}).listen(Number(process.argv[2]), '127.0.0.1');
EOF
}
write_pkg() {  # write_pkg <version>: package.json and a package-lock.json with no dependencies (npm ci needs no network)
  printf '{\n  "name": "fake-editor",\n  "version": "%s",\n  "private": true,\n  "scripts": {\n    "build": "node build.js",\n    "build:cli": "node build-cli.js"\n  }\n}\n' "$1" > "$REPO/package.json"
  printf '{\n  "name": "fake-editor",\n  "version": "%s",\n  "lockfileVersion": 3,\n  "requires": true,\n  "packages": {\n    "": {\n      "name": "fake-editor",\n      "version": "%s"\n    }\n  }\n}\n' "$1" "$1" > "$REPO/package-lock.json"
}
write_progress() {  # write_progress <last_completed> <in_progress> <review lines of the last entry, with \n>
  local n="$1" inp="$2" rev="$3" i
  mkdir -p "$REPO/docs"
  {
    printf '# Progress\n\nlast_completed_batch: %s\nin_progress_batch: %s\nskipped_batches: []\nneeds_human: none\n\n' "$n" "$inp"
    printf '## Known issues\n- review: rejected (a decoy outside any batch entry)\n\n## Batch log\n\n'
    for i in $(seq 1 "$n"); do
      printf '### Batch %02d: Fake batch %s\n- status: done\n- notes: x\n' "$i" "$i"
      if [ "$i" -lt "$n" ]; then printf -- '- review: rejected\n- fix-attempt: done\n- review: accepted (re-review)\n\n'; else printf '%b\n\n' "$rev"; fi
    done
    [ "$inp" != none ] && printf '### Batch %02d: Next batch\n- status: in progress\n\n' "$inp"
  } > "$REPO/docs/PROGRESS.md"
}
commit() {  # commit <subject>: the tracked files of the fake only (wip.txt stays uncommitted)
  G add -A -- . ':(exclude)wip.txt'
  G commit -q --allow-empty -m "$1"
  G rev-parse HEAD
}
repo_snap() { { G rev-parse HEAD; G status --porcelain; G reflog | wc -l; } 2>&1; }

G init -q -b main
G config core.autocrlf false
write_static; write_pkg 1.0.0
write_progress 1 none '- review: accepted (2026-11-10)'
echo "wip" > "$REPO/wip.txt"
commit "batch-01: progress" >/dev/null
SHA1="$(commit "batch-01: review")"
write_progress 2 2 '- review: pending'
SHA2="$(commit "batch-02: review")"
write_progress 3 none '- review: accepted (first)\n- review: needs-work: the export is wrong'
SHA3="$(commit "batch-03: review")"
sg() { git -C "$STABLE" "$@"; }

# ---------------------------------------------------------------------------------------------------------------------------------
section "1. first use: clone, the newest accepted commit (not HEAD), the build, the server"
out="$(es 2>&1)"; rc=$?
echo "$out"
assert_rc 0 "$rc" "first use exits 0"
printf '%s\n' "$out" | grep -q -E "^editor stable: none -> ${SHA1:0:7} \(batch 01\)$" && pass "status line: none -> batch-01 review commit" || fail "status line (got: $out)"
assert_eq "$(sg rev-parse HEAD)" "$SHA1" "the stable copy sits on the batch-01 review commit, not on the clone's HEAD (batch-03)"
assert_ne "$(G rev-parse HEAD)" "$SHA1" "(the scratch repo's own HEAD is newer)"
assert_true "batch-02 (in progress) and batch-03 (needs-work) were skipped" test "$(sg rev-parse HEAD)" != "$SHA2" -a "$(sg rev-parse HEAD)" != "$SHA3"
assert_grep "$SHA1" "$STABLE/dist/index.html" "dist/index.html is stamped with the commit"
assert_grep "$SHA1" "$STABLE/dist-cli/marker" "npm run build:cli ran (package.json has the script)"
assert_grep "stable: npm ci" "$ROOT/logs/editor-stable.log" "npm ci ran (node_modules was missing)"
assert_grep "cloned" "$ROOT/logs/editor-stable.log" "the clone is logged"
assert_file "$ROOT/.locks/editor-restart" "an advance writes the restart marker"
assert_eq "$(mixed "$(sg remote get-url origin)")" "$(mixed "$REPO")" "the stable copy is a clone of editor.repo"
assert_eq "$(es path)" "$STABLE" "path prints the stable dir"
assert_eq "$(es caps)" "" "caps prints nothing while capabilities.json is missing"
echo '{"schemaVersion":1}' > "$STABLE/capabilities.json"
assert_eq "$(es caps)" "$STABLE/capabilities.json" "caps prints the manifest path when it exists"
rm -f "$STABLE/capabilities.json"
assert_no_file "$ROOT/.locks/editor.lock" "the editor lock is released"

out="$(es serve 2>&1)"; rc=$?
echo "$out"
assert_rc 0 "$rc" "serve exits 0"
assert_eq "$out" "editor server: http://localhost:$TPORT/" "serve prints the server url"
assert_grep "$SHA1" <(curl -s "http://localhost:$TPORT/") "the server answers with the stable build"
assert_no_file "$ROOT/.locks/editor-restart" "serve consumed the restart marker"
assert_file "$ROOT/logs/editor-server.pid" "the pid file is written"
out2="$(es serve 2>&1)"
assert_eq "$out2" "editor server: http://localhost:$TPORT/" "serve again does nothing while the port answers"
out="$(es status)"
assert_grep "port $TPORT, up" <(printf '%s\n' "$out") "status: the server is up on the test port"

[ "${M21_STOP_AFTER:-}" = 1 ] && { [ -f "$T/guard-bad" ] && cat "$T/guard-bad"; test_summary; exit $?; }
# ---------------------------------------------------------------------------------------------------------------------------------
section "2. a build that fails: back to the previous commit, rebuilt, the reason logged; the hour"
touch "$REPO/FAIL_BUILD"
write_progress 4 none '- review: accepted (2026-11-10)'
SHA4="$(commit "batch-04: review")"
out="$(es 2>&1)"; rc=$?
assert_rc 0 "$rc" "advance within the hour exits 0"
assert_eq "$out" "editor stable: current ${SHA1:0:7} (batch 01)" "within the hour nothing is tried: current"
assert_eq "$(sg rev-parse HEAD)" "$SHA1" "the hourly limit: still on batch-01 although batch-04 is accepted"
out="$(es advance --force 2>&1)"; rc=$?
echo "$out"
assert_rc 1 "$rc" "--force with a failing build exits 1"
printf '%s\n' "$out" | grep -q -E "^editor stable: kept ${SHA1:0:7}, build of ${SHA4:0:7} failed" && pass "status line: kept batch-01, the build of batch-04 failed" || fail "kept line (got: $out)"
assert_eq "$(sg rev-parse HEAD)" "$SHA1" "the stable copy went back to the previous commit"
assert_grep "$SHA1" "$STABLE/dist/index.html" "...and rebuilt it (dist is stamped with batch-01 again)"
assert_grep "build of ${SHA4:0:7} failed: npm run build failed: .*FAIL_BUILD" "$ROOT/logs/editor-stable.log" "the reason is in logs/editor-stable.log"
assert_grep "went back to ${SHA1:0:7} and rebuilt it" "$ROOT/logs/editor-stable.log" "the way back is logged"
assert_no_file "$ROOT/.locks/editor-restart" "a failed advance writes no restart marker"
builds="$(grep -c 'stable: npm run build$' "$ROOT/logs/editor-stable.log")"
out="$(EDITOR_ADVANCE_MINUTES=0 es advance 2>&1)"; rc=$?
printf '%s\n' "$out" | grep -q -E "^editor stable: kept ${SHA1:0:7}, ${SHA4:0:7} failed to build earlier" && pass "a commit that failed is not tried again without --force" || fail "failed-before line (got: $out)"
assert_eq "$(grep -c 'stable: npm run build$' "$ROOT/logs/editor-stable.log")" "$builds" "...no build ran"
assert_grep "$SHA1" <(curl -s "http://localhost:$TPORT/") "the server still serves the good build"

# first use against this history: batch-04 (newest accepted) fails, so it lands on batch-01
mkdir -p "$T/root2"; cp "$REPO_DIR/config.json" "$T/root2/config.json"
out="$(REELS_ROOT="$T/root2" EDITOR_STABLE_DIR="$T/stable2" EDITOR_REPO="$REPO" bash "$SCRIPT" 2>&1)"; rc=$?
echo "$out"
assert_rc 0 "$rc" "first use with a failing newest accepted commit exits 0"
assert_eq "$(git -C "$T/stable2" rev-parse HEAD)" "$SHA1" "first use walks back to the newest accepted commit that builds"
assert_grep "build of ${SHA4:0:7} failed" "$T/root2/logs/editor-stable.log" "...and logs the one that failed"

# ---------------------------------------------------------------------------------------------------------------------------------
section "3. an accepted good batch: advance, npm ci for the changed lock, restart marker, restart of the server"
rm -f "$REPO/FAIL_BUILD"
write_pkg 1.1.0
write_progress 5 none '- review: accepted (2026-11-10)'
SHA5="$(commit "batch-05: review")"
out="$(es 2>&1)"
assert_eq "$out" "editor stable: current ${SHA1:0:7} (batch 01)" "the hourly limit: a second advance within the hour does nothing"
assert_eq "$(sg rev-parse HEAD)" "$SHA1" "...the stable copy did not move"
ci_before="$(grep -c 'stable: npm ci' "$ROOT/logs/editor-stable.log")"
out="$(es advance --force 2>&1)"; rc=$?
echo "$out"
assert_rc 0 "$rc" "--force advances"
assert_eq "$out" "editor stable: ${SHA1:0:7} -> ${SHA5:0:7} (batch 05)" "status line: batch-01 -> batch-05"
assert_eq "$(sg rev-parse HEAD)" "$SHA5" "the stable copy sits on the batch-05 review commit"
assert_grep "$SHA5" "$STABLE/dist/index.html" "dist is rebuilt for batch-05"
assert_grep "$SHA5" "$STABLE/dist-cli/marker" "build:cli ran again"
assert_eq "$(grep -c 'stable: npm ci' "$ROOT/logs/editor-stable.log")" "$((ci_before + 1))" "npm ci ran because package-lock.json changed"
assert_file "$ROOT/.locks/editor-restart" "the restart marker is written after an advance"
assert_grep "editor stable: ${SHA1:0:7} -> ${SHA5:0:7}" "$ROOT/logs/engine.log" "the advance is in the shared engine.log"
out="$(es status)"
assert_grep "restart pending: yes" <(printf '%s\n' "$out") "status shows the pending restart"
out="$(es serve 2>&1)"
assert_eq "$out" "editor server: http://localhost:$TPORT/" "serve restarts the server after an advance"
assert_grep "$SHA5" <(curl -s "http://localhost:$TPORT/") "the restarted server serves the new build"
assert_no_file "$ROOT/.locks/editor-restart" "the marker is gone after the restart"
out="$(EDITOR_ADVANCE_MINUTES=0 es advance 2>&1)"
assert_eq "$out" "editor stable: current ${SHA5:0:7} (batch 05)" "nothing newer: current"
out="$(es serve --restart 2>&1)"
assert_eq "$out" "editor server: http://localhost:$TPORT/" "serve --restart works without a marker"
assert_grep "$SHA5" <(curl -s "http://localhost:$TPORT/") "...and serves the same build"
out="$(es stop 2>&1)"
assert_eq "$out" "editor server: stopped" "stop stops the server"
assert_false "nothing answers on the test port after stop" curl -s -o /dev/null --max-time 2 "http://localhost:$TPORT/"

# the global editor lock: a live holder makes the script wait with a WAIT line
mkdir -p "$ROOT/.locks/editor.lock"
sleep 120 &
hp=$!
printf '%s %s %s %s %s
' "$hp" "$EPOCHSECONDS" other editor "editor advance" > "$ROOT/.locks/editor.lock/holder"
es advance > "$T/wait.out" 2>&1 &
ap=$!
for _ in $(seq 1 60); do grep -q "WAIT" "$T/wait.out" 2>/dev/null && break; sleep 1; done
assert_grep "WAIT   editor: other editor advance holds it" "$T/wait.out" "a held editor lock prints a WAIT line"
kill "$hp" 2>/dev/null; wait "$hp" 2>/dev/null; wait "$ap" 2>/dev/null
assert_grep "editor stable: current" "$T/wait.out" "...and goes on when the holder is gone"
assert_eq "$(grep -c WAIT "$T/wait.out")" "1" "one WAIT line for the whole wait"

# the default port
out="$(env -u EDITOR_PORT -u EDITOR_SERVE_COMMAND EDITOR_REPO="$REPO" EDITOR_STABLE_DIR="$STABLE" bash "$SCRIPT" status 2>&1)"
assert_grep "port 5310" <(printf '%s\n' "$out") "status reports the configured port 5310 by default"
assert_grep "http://localhost:5310/" <(printf '%s\n' "$out") "...and the configured url"

# the editor repo was only read
assert_no_file "$T/guard-bad" "no call of the script changed editor.repo (HEAD, status, stash, reflog, branch checked around every call)"
[ -f "$T/guard-bad" ] && cat "$T/guard-bad"
assert_eq "$(G rev-parse HEAD)" "$SHA5" "editor.repo's HEAD is the commit the test made last"
assert_grep '^\?\? wip.txt$' <(G status --porcelain) "editor.repo still shows only its uncommitted wip.txt"
assert_eq "$(G stash list | wc -l | tr -d ' ')" "0" "editor.repo has no stash"
assert_eq "$(G branch --show-current)" "main" "editor.repo is still on its branch"
assert_true "editor.repo has no node_modules or dist (nothing was built in it)" test ! -e "$REPO/node_modules" -a ! -e "$REPO/dist"

test_summary
