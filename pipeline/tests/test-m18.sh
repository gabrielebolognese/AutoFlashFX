#!/usr/bin/env bash
# test-m18.sh: the acceptance test of M18 (Channels). No model call (the fake claude where a call is needed), no engine call.
#   bash pipeline/tests/test-m18.sh                       all sections (about 25 minutes: every run.sh start pays for the preflight)
#   M18_SECTIONS="1 2 6" bash pipeline/tests/test-m18.sh  only those sections
#
#   1. channel.json and the resolved config: the schema (planted faults), the three-level merge, the safety keys, the engine keys a channel
#      overrides, the config cache that follows an edit at once, the keys that moved out of config.json
#   2. the front door: run.sh without a channel exits 2 and lists the channels, an unknown id exits 2, a disabled channel exits 2 (and runs with
#      --allow-disabled), a second runner of the same channel is refused, add-idea.sh --channel, preflight --channel, doctor, runner-status
#   3. the dummy fingerprint: REELS_DUMMY=all bash run.sh --channel flashfx --once in a temp REELS_ROOT gives the baseline's run tree (names
#      normalized) inside channels/flashfx/runs/ and the baseline's exports tree
#   4. an unfinished fixture run resumes at the same stage
#   5. a fake model edit of channels/flashfx/library/hooks.txt is refused and the file restored; protect.py for every channel
#   6. migrate-channels on the rehearsal fixture: the dry run lists every M18 line, the run verifies, the undo brings back an identical tree
#      (checksums), a second run verifies, a run killed halfway is undone by the next start, a failed check undoes itself, a live runner refuses
#   7. two fixture channels' dummy runners at the same time
#   8. the real migration: build/M18's records, check-manifest.py --after, git check-ignore, preflight --channel flashfx, doctor --quick
#   9. test-isolation.sh part 1; the files M18 changed; no em dash
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SECTIONS="${M18_SECTIONS:-1 2 3 4 5 6 7 8 9}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
T="$(mktemp -d)"
m18_cleanup() { rm -rf "$T" 2>/dev/null || { sleep 2; rm -rf "$T" 2>/dev/null; }; tests_cleanup; }
trap m18_cleanup EXIT
TM="$(mixed "$T")"
PT="$TESTS_DIR"
RM="$(mixed "$REPO_DIR")"
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
CONFIG_PY="$REPO_DIR/pipeline/lib/config.py"
export NO_COLOR=1
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '

run_sh() {  # run_sh <outfile> <args...>: run.sh of the real repo against $SANDBOX as the state root
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 timeout 900 bash "$REPO_DIR/run.sh" "$@" ) > "$out" 2>&1
}
tree() {  # tree <dir>: relative paths, a trailing slash on folders, bytewise sorted, the run stamp replaced (as m17-baseline.sh)
  (cd "$1" 2>/dev/null && find . -mindepth 1 | sed 's#^\./##' | while IFS= read -r p; do if [ -d "$p" ]; then echo "$p/"; else echo "$p"; fi; done) \
    | sed -E 's/20[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{4}/<ts>/g' | LC_ALL=C sort
}
treesum() { python - "$1" <<'PYEOF'
import hashlib, os, sys
root = sys.argv[1]
h = hashlib.sha256()
n = 0
for dp, dn, fn in os.walk(root):
    dn[:] = sorted(d for d in dn if d not in (".git", "build"))
    for f in sorted(fn):
        p = os.path.join(dp, f)
        h.update(os.path.relpath(p, root).replace(chr(92), "/").encode()); h.update(open(p, "rb").read()); n += 1
print(n, h.hexdigest()[:20])
PYEOF
}
pycheck() {  # pycheck "name" args...: the python on stdin passes when its last line is "ok"
  local name="$1"; shift
  local out; out="$(python - "$@" 2>&1)"
  if [ "$(printf '%s\n' "$out" | tail -n 1)" = "ok" ]; then pass "$name"; else fail "$name: $(printf '%s\n' "$out" | tail -n 4 | tr '\n' ' ')"; fi
}
add_channel() {  # add_channel <id> [enabled]: a second channel in the sandbox, a copy of channels/flashfx with its own id and an empty queue
  local id="$1" en="${2:-true}"
  cp -r "$SANDBOX/channels/flashfx" "$SANDBOX/channels/$id"
  rm -rf "$SANDBOX/channels/$id/.cache" "$SANDBOX/channels/$id/runs" "$SANDBOX/channels/$id/logs" "$SANDBOX/channels/$id/.locks"
  mkdir -p "$SANDBOX/channels/$id/logs"; : > "$SANDBOX/channels/$id/ideas.txt"
  python - "$SANDBOX_M/channels/$id/channel.json" "$id" "$en" <<'PYEOF'
import json, sys
p, cid, en = sys.argv[1:4]
d = json.load(open(p, encoding="utf-8"))
d["id"] = cid; d["name"] = cid.capitalize(); d["enabled"] = (en == "true"); d["brand"] = {"display_name": cid.capitalize()}
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
}

if want 1; then
section "1. channel.json and the resolved config"
sandbox_init
CJ="$SANDBOX_CH/channel.json"
assert_rc 0 "$(python "$CONFIG_PY" validate >/dev/null 2>&1; echo $?)" "channel.json of flashfx is valid against pipeline/schemas/channel.schema.json"
bad_channel() {  # bad_channel <name> <python edit of d>: validate fails and names the problem
  local name="$1" edit="$2" out rc
  cp "$CJ" "$T/cj.bak"
  python - "$SANDBOX_M/channels/flashfx/channel.json" <<PYEOF
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
$edit
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
  out="$(python "$CONFIG_PY" validate 2>&1)"; rc=$?
  cp "$T/cj.bak" "$CJ"
  if [ "$rc" = 1 ] && [ -n "$out" ]; then pass "validate fails: $name"; else fail "validate fails: $name (rc $rc, $out)"; fi
}
bad_channel "an id with a capital and a hyphen" 'd["id"] = "Flash-FX"'
bad_channel "an id that is not the folder name" 'd["id"] = "other"'
bad_channel "no platform" 'del d["platform"]'
bad_channel "no format" 'del d["format"]'
bad_channel "a quota that is not a number" 'd["daily_quota"] = "two"'
bad_channel "a channel path key nobody knows" 'd["config"]["paths"]["nonsense"] = "x"'
bad_channel "a safety key of review overridden by the channel" 'd["config"]["review"] = {"protected_paths": []}'
bad_channel "a source folder that is not text" 'd["sources"] = {"refs": 3}'

# the keys moved
pycheck "config.json has none of the channel-owned keys and keeps the engine keys and the four safety keys" "$REPO_DIR/config.json" <<'PYEOF'
import json, sys
c = json.load(open(sys.argv[1], encoding="utf-8"))
for k in ("style", "voice", "sfx", "lengths"):
    assert k not in c, k
for k in ("ideas", "runs", "logs", "locks", "library", "hooks", "profile", "voice_dir", "styles", "style_dir", "tokens", "sfx_dir", "motion_lib", "golden"):
    assert k not in c["paths"], k
for k in ("exports", "vendor", "known_issues"):
    assert k in c["paths"], k
for k in ("models", "tts", "caps", "errors", "timeouts", "runner", "render", "preflight", "logs"):
    assert k in c, k
for k in ("reviewer_tools", "fixer_tools", "fixer_paths", "protected_paths"):
    assert k in c["review"], k
assert "channels/*/ideas.txt" in c["review"]["protected_paths"] and "exports" in c["review"]["protected_paths"]
assert c["review"]["fixer_paths"] == ["pipeline", "channels/{channel}/motion-lib/candidates"]
print("ok")
PYEOF
pycheck "channel.json holds style, voice, sfx, lengths and the 14 paths with their old values" "$REPO_DIR/channels/flashfx/channel.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d["id"] == "flashfx" and d["platform"] == "instagram-reels" and d["format"] == "problem-solution-reel" and d["enabled"] is True
c = d["config"]
assert c["style"] == "paper-cards" and c["voice"]["wpm"] == 186 and c["lengths"]["default_s"] == [25, 40] and "map" in c["sfx"]
assert len(c["paths"]) == 14 and c["paths"]["profile"] == "library/profile" and c["paths"]["tokens"] == "styles/paper-cards/tokens.json"
print("ok")
PYEOF

# the merge: engine, then the channel (objects key by key, arrays and scalars replace)
python - "$SANDBOX_M/channels/flashfx/channel.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["config"]["models"] = {"script": {"effort": "low"}}
d["config"]["runner"] = {"poll_seconds": 7}
d["config"]["lengths"]["default_s"] = [10, 20]
d["config"]["review"] = {"wer_max_pct": 9}
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
python "$CONFIG_PY" resolve --out "$TM/resolved.json"
pycheck "the resolved config merges engine and channel: objects key by key, arrays replace, safety keys untouched" "$TM/resolved.json" "$SANDBOX_M/config.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8")); e = json.load(open(sys.argv[2], encoding="utf-8"))
assert r["models"]["script"]["effort"] == "low" and r["models"]["script"]["model"] == e["models"]["script"]["model"]
assert r["models"]["gate"] == e["models"]["gate"]
assert r["runner"]["poll_seconds"] == 7 and r["runner"]["lock_stale_seconds"] == e["runner"]["lock_stale_seconds"]
assert r["lengths"]["default_s"] == [10, 20] and "list_s" in r["lengths"]
assert r["review"]["wer_max_pct"] == 9 and r["review"]["protected_paths"] == e["review"]["protected_paths"]
assert r["voice"]["wpm"] == 186 and r["style"] == "paper-cards"
print("ok")
PYEOF
python - "$SANDBOX_M/channels/flashfx/channel.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["config"]["review"]["protected_paths"] = []
d["config"]["review"]["fixer_paths"] = ["/"]
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
python "$CONFIG_PY" resolve --out "$TM/resolved2.json"
pycheck "a channel cannot override a safety key: the resolved config ignores it" "$TM/resolved2.json" "$SANDBOX_M/config.json" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8")); e = json.load(open(sys.argv[2], encoding="utf-8"))
assert r["review"]["protected_paths"] == e["review"]["protected_paths"] and r["review"]["fixer_paths"] == e["review"]["fixer_paths"]
print("ok")
PYEOF
ovr="$(python "$CONFIG_PY" overrides 2>&1 | tr '\n' ' ')"
assert_true "overrides lists the engine keys the channel sets (models, runner), not the channel's own or the format's" bash -c "case '$ovr' in *models.script.effort*runner.poll_seconds*|*runner.poll_seconds*models.script.effort*) case '$ovr' in *lengths*|*review*) exit 1 ;; esac; exit 0 ;; *) exit 1 ;; esac"
out="$(bash "$REPO_DIR/pipeline/bin/doctor" --quick --channel flashfx 2>&1)"
printf '%s\n' "$out" > "$T/doctor.txt"
assert_grep '^WARN  this channel overrides engine keys: .*models.script.effort' "$T/doctor.txt" "doctor prints every engine key the channel overrides"
cp "$T/cj.bak" "$CJ"
# the cache follows an edit at once (cfg re-reads when channel.json or config.json is newer)
cfg_wpm() { env REELS_ROOT="$SANDBOX_M" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; source "'"$REPO_DIR"'/pipeline/lib/config.sh"; cfg voice.wpm'; }
assert_eq "$(cfg_wpm)" "186" "cfg reads voice.wpm from channel.json (the resolved config)"
python "$REPO_DIR/pipeline/lib/voiceprofile.py" set-wpm --config "$SANDBOX_CH_M/channel.json" --wpm 201 >/dev/null
assert_eq "$(cfg_wpm)" "201" "an edit of channel.json shows at the next cfg call (the resolved file is made again)"
python - "$SANDBOX_M/config.json" <<'PYEOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8")); d["runner"]["poll_seconds"] = 33
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
poll() { env REELS_ROOT="$SANDBOX_M" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; source "'"$REPO_DIR"'/pipeline/lib/config.sh"; cfg runner.poll_seconds'; }
assert_eq "$(poll)" "33" "an edit of config.json shows at the next cfg call too"
assert_eq "$(env -u REELS_CHANNEL REELS_ROOT="$SANDBOX_M" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; source "'"$REPO_DIR"'/pipeline/lib/config.sh"; cfg runner.poll_seconds')" "33" "without a channel cfg reads the engine config.json"
fi

if want 2; then
section "2. the front door: run.sh, add-idea.sh, preflight, runner-status, doctor"
sandbox_init
printf '{Idea A: a channel test}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
add_channel second
add_channel off false
env -u REELS_CHANNEL bash "$REPO_DIR/run.sh" --once > "$T/nochan.out" 2>&1; rc=$?
assert_rc 2 "$rc" "run.sh without a channel exits 2"
assert_grep 'no channel given' "$T/nochan.out" "run.sh without a channel says so"
assert_grep 'flashfx: FlashFX \(instagram-reels, problem-solution-reel, enabled\)' "$T/nochan.out" "run.sh without a channel lists flashfx with platform, format and status"
assert_grep 'off: Off \(instagram-reels, problem-solution-reel, disabled\)' "$T/nochan.out" "the list shows a disabled channel as disabled"
assert_eq "$(ls "$SANDBOX/channels/flashfx/runs" 2>/dev/null | wc -l | tr -d ' ')" "0" "nothing ran"
env -u REELS_CHANNEL bash "$REPO_DIR/run.sh" --channel nonexistent --once > "$T/unknown.out" 2>&1; rc=$?
assert_rc 2 "$rc" "run.sh --channel with an unknown id exits 2"
assert_grep "unknown channel 'nonexistent'" "$T/unknown.out" "an unknown id is named"
env -u REELS_CHANNEL bash "$REPO_DIR/run.sh" --channel "Bad-Id" --once > "$T/badid.out" 2>&1; rc=$?
assert_rc 2 "$rc" "run.sh --channel with a malformed id exits 2"
env -u REELS_CHANNEL bash "$REPO_DIR/run.sh" --channel off --once > "$T/off.out" 2>&1; rc=$?
assert_rc 2 "$rc" "run.sh --channel with a disabled channel exits 2"
assert_grep 'is disabled' "$T/off.out" "the refusal says the channel is disabled"
assert_grep 'allow-disabled' "$T/off.out" "the refusal names --allow-disabled"
( cd "$SANDBOX" && env -u REELS_CHANNEL NO_COLOR=1 timeout 900 bash "$REPO_DIR/run.sh" --channel off --once --allow-disabled ) > "$T/offrun.out" 2>&1; rc=$?
assert_rc 0 "$rc" "--allow-disabled runs the disabled channel (an empty queue, --once: exit 0)"
assert_grep 'channel: off' "$T/offrun.out" "and its banner names it"
REELS_CHANNEL=nonexistent bash "$REPO_DIR/run.sh" --once > "$T/envunknown.out" 2>&1; rc=$?
assert_rc 2 "$rc" "REELS_CHANNEL with an unknown id exits 2 as well"
bash "$REPO_DIR/run.sh" --bogus > "$T/bogus.out" 2>&1; rc=$?
assert_rc 1 "$rc" "an unknown option still exits 1"
assert_not_grep '^FAIL' "$T/nochan.out" "no failure lines in the listing"

# a second runner of the same channel refuses; another channel is not affected
sleep 120 & holder=$!
mkdir -p "$SANDBOX/channels/flashfx/.locks/runner"; printf '%s %s\n' "$holder" "$(date +%s)" > "$SANDBOX/channels/flashfx/.locks/runner/pid"
run_sh "$T/second.out" --channel flashfx --once; rc=$?
assert_rc 1 "$rc" "a second runner of the same channel refuses (exit 1)"
assert_grep 'another runner is already running' "$T/second.out" "the refusal says another runner is running"
assert_eq "$(cat "$SANDBOX/channels/flashfx/.locks/runner/pid" | cut -d' ' -f1)" "$holder" "the first runner's lock is untouched"
assert_no_file "$SANDBOX/channels/second/.locks/runner" "the other channel has no lock"
kill "$holder" 2>/dev/null; wait "$holder" 2>/dev/null
rm -rf "$SANDBOX/channels/flashfx/.locks"

# add-idea.sh --channel writes the channel's own queue
printf '' > "$SANDBOX/channels/second/ideas.txt"
out="$(bash "$REPO_DIR/pipeline/bin/add-idea.sh" --channel second "{A second-channel idea}" 2>&1)"
assert_eq "$out" "added 1 idea to ideas.txt (queue: 1)" "add-idea.sh --channel second: the script's own one-line answer"
assert_grep 'A second-channel idea' "$SANDBOX/channels/second/ideas.txt" "the idea is in channels/second/ideas.txt"
assert_not_grep 'second-channel' "$SANDBOX/channels/flashfx/ideas.txt" "and not in flashfx's queue"
out="$(env -u REELS_CHANNEL bash "$REPO_DIR/pipeline/bin/add-idea.sh" "{no channel with three channels}" 2>&1)"; rc=$?
assert_rc 2 "$rc" "add-idea.sh without a channel, with several channels, exits 2"
assert_true "and lists them" bash -c "printf '%s' '$out' | grep -q 'flashfx'"
out="$(REELS_CHANNEL=second bash "$REPO_DIR/pipeline/bin/add-idea.sh" "{via the environment}" 2>&1)"
assert_eq "$out" "added 1 idea to ideas.txt (queue: 2)" "REELS_CHANNEL picks the channel too"

# preflight, runner-status and doctor per channel
out="$(env -u REELS_CHANNEL bash "$REPO_DIR/pipeline/bin/preflight" 2>&1)"; rc=$?
assert_rc 2 "$rc" "preflight without a channel exits 2 and lists them"
out="$(bash "$REPO_DIR/pipeline/bin/preflight" --channel nonexistent 2>&1)"; rc=$?
assert_rc 2 "$rc" "preflight --channel with an unknown id exits 2"
env -u REELS_CHANNEL bash "$REPO_DIR/pipeline/bin/runner-status" > "$T/rs.txt" 2>&1; rc=$?
assert_rc 0 "$rc" "runner-status without arguments exits 0"
assert_grep '^== channel flashfx ==$' "$T/rs.txt" "runner-status prints a block for flashfx"
assert_grep '^== channel second ==$' "$T/rs.txt" "runner-status prints a block for the second channel"
assert_grep '^global locks ' "$T/rs.txt" "runner-status prints the global locks"
bash "$REPO_DIR/pipeline/bin/runner-status" --channel second 5 > "$T/rs2.txt" 2>&1
assert_not_grep '== channel flashfx ==' "$T/rs2.txt" "runner-status --channel prints that channel only"
bash "$REPO_DIR/pipeline/bin/doctor" --quick --channel second > "$T/doc2.txt" 2>&1; rc=$?
assert_grep '== channel second: channel.json' "$T/doc2.txt" "doctor --channel checks that channel"
assert_not_grep '== channel flashfx' "$T/doc2.txt" "doctor --channel leaves the other channels out"
assert_grep '^== versions' "$T/doc2.txt" "doctor checks the engine once"
env -u REELS_CHANNEL bash "$REPO_DIR/pipeline/bin/doctor" --quick > "$T/doc3.txt" 2>&1
assert_eq "$(grep -c '^== versions' "$T/doc3.txt")" "1" "doctor without a channel checks the engine once"
assert_grep '== channel flashfx: runner' "$T/doc3.txt" "doctor without a channel goes through flashfx"
assert_grep '== channel second: runner' "$T/doc3.txt" "doctor without a channel goes through the second channel"
fi

if want 3; then
section "3. the dummy fingerprint of M17 inside channels/flashfx/runs/"
sandbox_init
fast_mode
printf '{Claude Code'"'"'s frontend-design skill: it makes websites built with AI stop looking AI-generated. Show what it does and how to install it.}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all timeout 900 bash "$REPO_DIR/run.sh" --channel flashfx --once ) > "$T/dummy.out" 2>&1; rc=$?
assert_rc 0 "$rc" "REELS_DUMMY=all bash run.sh --channel flashfx --once exits 0"
tree "$SANDBOX/channels/flashfx/runs" > "$T/run-tree.txt"
tree "$SANDBOX/exports" > "$T/exports-tree.txt"
if cmp -s "$T/run-tree.txt" "$REPO_DIR/build/M17/baseline/fingerprint-run.txt"; then pass "the run folder tree equals the baseline's ($(grep -c . "$T/run-tree.txt") entries, names normalized)"
else fail "the run folder tree differs from the baseline: $(diff "$T/run-tree.txt" "$REPO_DIR/build/M17/baseline/fingerprint-run.txt" | head -n 6 | tr '\n' ' ')"; fi
if cmp -s "$T/exports-tree.txt" "$REPO_DIR/build/M17/baseline/fingerprint-exports.txt"; then pass "the exports tree equals the baseline's (the export names change in M19)"
else fail "the exports tree differs from the baseline: $(diff "$T/exports-tree.txt" "$REPO_DIR/build/M17/baseline/fingerprint-exports.txt" | head -n 6 | tr '\n' ' ')"; fi
assert_no_file "$SANDBOX/runs" "no runs/ at the root of the state root"
assert_no_file "$SANDBOX/ideas.txt" "no ideas.txt at the root of the state root"
assert_file "$SANDBOX/channels/flashfx/logs/runner.log" "the runner log is in the channel's logs/"
assert_file "$SANDBOX/channels/flashfx/logs/history.txt" "history.txt is in the channel's logs/"
assert_grep '\| exported 1$' "$SANDBOX/channels/flashfx/logs/history.txt" "the history line says exported 1"
assert_grep "root: .* \| channel: flashfx \|" "$T/dummy.out" "the banner names the channel"
assert_eq "$(ls "$SANDBOX/channels/flashfx/.locks" 2>/dev/null | wc -l | tr -d ' ')" "0" "no lock is left behind"
fi

if want 4; then
section "4. an unfinished run resumes at the same stage"
sandbox_init
fast_mode
export REELS_DUMMY=all REELS_DUMMY_SECONDS=0.1
RD="$(printf '{Idea R: resume test}' | python "$STATE_PY" new --runs "$SANDBOX_CH_M/runs" --id resume-test | python -c 'import json, sys; print(json.load(sys.stdin)["run_dir"])')"
printf '{Idea R: resume test}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
for st in 01-research 02-expansion 03-gate; do
  python "$STATE_PY" stage-start "$RD" "$st" >/dev/null
  REELS_DUMMY_SECONDS=0 bash "$REPO_DIR/pipeline/stages/$st/dummy.sh" "$RD" >/dev/null 2>&1
  python "$STATE_PY" stage-done "$RD" "$st" --schemas "$REPO_DIR/pipeline/stages" >/dev/null 2>&1
done
python "$STATE_PY" stage-start "$RD" 04-angle >/dev/null
assert_eq "$(python "$STATE_PY" get "$RD" stages.04-angle.status)" "running" "the planted run is interrupted in 04-angle"
assert_file "$RD/03-gate/.done" "the stages before it are done"
( cd "$SANDBOX" && env NO_COLOR=1 timeout 900 bash "$REPO_DIR/run.sh" --channel flashfx --once ) > "$T/resume.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the runner finishes the moved run"
assert_grep "START  idea 1/1 \"Idea R.*\" -> runs/[^ ]*resume-test \(resumed at .*, 3 stages done\)$" "$T/resume.out" "the START line says it resumes after 3 stages"
assert_not_grep 'researching facts done' "$T/resume.out" "the finished stages are not run again"
assert_grep 'DONE   exported #1' "$T/resume.out" "the resumed run exports"
assert_eq "$(ls "$SANDBOX/channels/flashfx/runs" | wc -l | tr -d ' ')" "1" "no second run folder"
assert_eq "$(python "$STATE_PY" get "$RD" stages.01-research.attempts)" "1" "research ran once"
unset REELS_DUMMY
fi

if want 5; then
section "5. a model edit of a protected file is refused; protect.py for every channel"
sandbox_init --with-pipeline
fake_claude_on
add_channel second
DRIVER="$TESTS_DIR/ai-driver.sh"
RD="$(printf '{Idea P}' | python "$STATE_PY" new --runs "$SANDBOX_CH_M/runs" --id protect-test | python -c 'import json, sys; print(json.load(sys.stdin)["run_dir"])')"
SD="$RD/10-build"; mkdir -p "$SD"; printf 'Reply with the single word ok.\n' > "$SD/prompt.md"
for target in "channels/flashfx/library/hooks.txt" "channels/second/library/hooks.txt" "channels/flashfx/styles/paper-cards/style.md" "channels/second/ideas.txt"; do
  before="$(cat "$SANDBOX/$target" 2>/dev/null)"
  out="$(FAKE_CLAUDE_TAMPER_FILE="$SANDBOX_M/$target" FAKE_CLAUDE_MODE=tamper bash "$DRIVER" indexer "$SD" "$SD/prompt.md" --tools "" 2>>"$T/driver.err" | tail -n 1)"
  rc="$(printf '%s\n' "$out" | tr '\t' '\n' | sed -n 's/^rc=//p')"
  assert_eq "$rc" "1" "a model call that edits $target is a code error"
  assert_eq "$(cat "$SANDBOX/$target" 2>/dev/null)" "$before" "$target is restored from the snapshot"
  assert_true "the error names the protected file" grep -q "protected files .*$target" <<<"$(printf '%s\n' "$out" | tr '\t' '\n' | sed -n 's/^error=//p')"
done
FAKE_CLAUDE_MODE=ok bash "$DRIVER" indexer "$SD" "$SD/prompt.md" --tools "" > "$T/ok.out" 2>&1
fake_calls() { python -c 'import json, sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG"; }
python - "$FAKE_CLAUDE_LOG" <<'PYEOF' > "$T/disallowed.txt"
import json, sys
last = None
for line in open(sys.argv[1], encoding="utf-8"):
    if line.strip():
        last = json.loads(line)
print(last.get("disallowed", ""))
PYEOF
assert_grep 'Edit\(channels/\*/ideas.txt\)' "$T/disallowed.txt" "the call denies Edit on every channel's ideas.txt"
assert_grep 'Write\(channels/\*/library/\*\*\)' "$T/disallowed.txt" "and Write on every channel's library"
assert_grep 'Edit\(channels/\*/styles/\*\*\)' "$T/disallowed.txt" "and Edit on every channel's styles"
assert_grep 'Edit\(exports/\*\*\)' "$T/disallowed.txt" "and on exports/"
# protect.py itself
PR="$REPO_DIR/pipeline/lib/protect.py"
mkdir -p "$SANDBOX/exports/flashfx-1"; printf 'x' > "$SANDBOX/exports/flashfx-1/flashfx-1.mp4"
python "$PR" snapshot --root "$SANDBOX_M" --repo "$SANDBOX_M" --dir "$TM/pr" > "$T/snap.json"
assert_true "protect.py snapshots the files of both channels" bash -c "python -c 'import json; d=json.load(open(\"$TM/pr/manifest.json\")); k=list(d[\"files\"]); import sys; sys.exit(0 if any(x.startswith(\"channels/flashfx/\") for x in k) and any(x.startswith(\"channels/second/\") for x in k) else 1)'"
hooks_sha="$(cat "$SANDBOX/channels/second/library/hooks.txt" | sha1sum | cut -c1-12)"
printf 'changed\n' >> "$SANDBOX/channels/second/library/hooks.txt"
rm -f "$SANDBOX/channels/flashfx/ideas.txt"
printf 'new\n' > "$SANDBOX/channels/second/library/profile/injected.md"
python "$PR" check --root "$SANDBOX_M" --repo "$SANDBOX_M" --dir "$TM/pr" --restore > "$T/chk.json"; rc=$?
assert_rc 1 "$rc" "protect.py reports a change in another channel's library"
assert_file "$SANDBOX/channels/flashfx/ideas.txt" "a deleted ideas.txt is restored"
assert_no_file "$SANDBOX/channels/second/library/profile/injected.md" "a file added to a channel's library is removed"
assert_eq "$(cat "$SANDBOX/channels/second/library/hooks.txt" | sha1sum | cut -c1-12)" "$hooks_sha" "a changed hooks file is restored"
assert_grep 'channels/second/library/hooks.txt' "$T/chk.json" "the report names the file with its channel path"
fake_claude_off
# the fixer's paths: pipeline and the run's channel only
out="$(env REELS_CHANNEL=second REELS_ROOT="$SANDBOX_M" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; source "'"$REPO_DIR"'/pipeline/lib/config.sh"; source "'"$REPO_DIR"'/pipeline/lib/review.sh" 2>/dev/null; review_fixer_paths' | tr -s ' ')"
assert_eq "$out" "pipeline channels/second/motion-lib/candidates" "review_fixer_paths: pipeline and the run's channel's candidates folder"
fi

if want 6; then
section "6. migrate-channels on the rehearsal fixture"
MC="$REPO_DIR/pipeline/bin/migrate-channels"
new_fx() {  # new_fx <name> [old-gitignore]: a fixture folder with the NEW .gitignore committed (as the real flow does)
  local d="$T/$1"
  python "$PT/m17-fixture.py" "$(mixed "$d")" >/dev/null || return 1
  if [ "${2:-new}" = new ]; then
    cp "$REPO_DIR/.gitignore" "$d/.gitignore"
    # the legacy root rules stay until the move is done (as in the real flow, DECISIONS.md 350): the data still at the root stays ignored
    printf '%s\n' 'library/voice/*' '!library/voice/README.txt' 'library/.hooks.index.json' 'styles/*/refs/' 'styles/*/analysis/' 'styles/sfx/**/*.wav' \
      'motion-lib/.harness/' 'golden/*/golden.mp4' >> "$d/.gitignore"
    git -C "$d" add -A && git -C "$d" commit -q -m "new gitignore" || return 1
  fi
}
assert_true "the rehearsal fixture builds" new_fx fx
FX="$TM/fx"
sum0="$(treesum "$FX")"
bash "$MC" --dry-run --ms M18 --root "$FX" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/dry.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the dry run exits 0"
nlines="$(python - "$FX/build/M18/move-manifest.tsv" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[0].rsplit("/", 1)[0])
rows = [l for l in open(sys.argv[1], encoding="utf-8").read().split("\n")[1:] if l.strip()]
print(sum(1 for r in rows if r.split("\t")[1] == "M18"))
PYEOF
)"
assert_eq "$(grep -c '^STEP ' "$T/dry.out")" "$nlines" "the dry run lists every M18 line of the manifest ($nlines)"
assert_grep '^DRY RUN: nothing changed' "$T/dry.out" "the dry run says nothing changed"
assert_eq "$(treesum "$FX")" "$sum0" "the dry run changed nothing in the tree (checksums)"
assert_file "$FX/build/M18/manifest-diff.md" "the dry run writes manifest-diff.md"
rm -rf "$FX/build/M18"
bash "$MC" --ms M18 --root "$FX" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/run1.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the run exits 0"
assert_grep '^migrate M18: verified' "$T/run1.out" "the run ends verified"
assert_grep $'\tverified\t' "$FX/build/M18/migration-log.tsv" "the migration log has its final verified line"
assert_file "$FX/build/M18/undo-migration.sh" "the undo script is written"
assert_file "$FX/build/M18/premigrate/runs/2026-11-01_1000_done-idea/01-research/research.json" "a rewritten file was copied to premigrate/ first, at its old path"
for d in library styles motion-lib golden runs; do assert_no_file "$FX/$d" "$d is gone from the old place"; done
assert_file "$FX/channels/flashfx/library/hooks.txt" "hooks.txt is in the channel"
assert_file "$FX/channels/flashfx/runs/2026-11-02_1100_open-idea/state.json" "the unfinished run moved with its channel"
assert_file "$FX/channels/flashfx/logs/history.txt" "history.txt moved"
assert_file "$FX/logs/limits.log" "the shared limits.log stays at the root"
assert_file "$FX/voicetests/a.wav" "the user's voicetests stay"
assert_eq "$(git -C "$FX" status --porcelain | grep -v '^R ' | grep -v 'build/' | wc -l | tr -d ' ')" "0" "git status shows only renames (and build/)"
assert_true "a file that was ignored is still ignored at its new path" git -C "$FX" check-ignore -q channels/flashfx/library/voice/engine.txt
assert_true "so are the reference videos" git -C "$FX" check-ignore -q channels/flashfx/styles/paper-cards/refs/a.mp4
pycheck "the rewritten run files name the channel paths in every form and no old path" "$FX/channels/flashfx/runs/2026-11-01_1000_done-idea/01-research/research.json" "$FX/channels/flashfx/runs/2026-11-02_1100_open-idea/01-research/research.json" "$FX/channels/flashfx/runs/2026-11-02_1100_open-idea/01-research/stage.log" <<'PYEOF'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
assert a["relative"].startswith("channels/flashfx/runs/"), a
assert "/channels/flashfx/styles/paper-cards/style.md" in a["mixed"], a
assert "/channels/flashfx/library/hooks.txt" in a["posix"], a
b = json.load(open(sys.argv[2], encoding="utf-8"))
assert "channels\\flashfx\\styles" in b["backslash"], b
assert "channels\\flashfx\\logs" in open(sys.argv[3], encoding="utf-8").read()
raw = sys.argv[1].replace("research.json", "calls/001.out.json")
assert open(raw, encoding="utf-8").read().strip() == '{"raw": "runs/2026-11-01_1000_done-idea"}', "the raw model output must not be rewritten"
print("ok")
PYEOF
assert_grep 'RUN$' "$FX/exports/1/1captions.txt" "the captions file keeps its sections"
assert_grep '^channels/flashfx/runs/2026-11-01_1000_done-idea$' "$FX/exports/1/1captions.txt" "the RUN path of the captions file follows"
python - "$FX/build/M18/move-manifest.tsv" "$TM/m18-only.tsv" <<'PYEND'
import sys
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
keep = [lines[0]] + [l for l in lines[1:] if l.split("\t")[1:2] == ["M18"]]
open(sys.argv[2], "w", encoding="utf-8", newline="\n").write("\n".join(keep) + "\n")
PYEND
assert_true "check-manifest --after passes on the migrated fixture (the M18 lines)" python "$PT/check-manifest.py" --after --root "$FX" --manifest "$TM/m18-only.tsv"
sum1="$(treesum "$FX")"
# a second run verifies
bash "$MC" --ms M18 --root "$FX" > "$T/run2.out" 2>&1; rc=$?
assert_rc 0 "$rc" "a second run exits 0"
assert_grep 'second verification passed' "$T/run2.out" "a second run verifies and moves nothing"
assert_eq "$(treesum "$FX")" "$sum1" "a second run changed nothing"
# the undo brings back an identical tree
bash "$MC" --undo --ms M18 --root "$FX" > "$T/undo.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the undo exits 0"
assert_grep 'UNDO verified: the folder is back as it was' "$T/undo.out" "the undo checks the folder against the before-listing"
assert_eq "$(treesum "$FX")" "$sum0" "the undo brings back an identical tree (checksums)"
assert_eq "$(git -C "$FX" status --porcelain | grep -v 'build/' | wc -l | tr -d ' ')" "0" "and git status is clean again"
# the undo script alone does the same
bash "$MC" --ms M18 --root "$FX" > "$T/run3.out" 2>&1
bash "$FX/build/M18/undo-migration.sh" > "$T/undosh.out" 2>&1
assert_eq "$(treesum "$FX")" "$sum0" "the generated undo-migration.sh also brings back an identical tree"
# a run killed halfway is undone by the next start
rm -rf "$FX/build/M18"
MIGRATE_KILL_AFTER=3 bash "$MC" --ms M18 --root "$FX" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/kill.out" 2>&1
assert_grep 'ending the process after 3 move' "$T/kill.out" "the planted kill ends the run after 3 moves"
assert_true "the folder is half moved (library is in the channel, runs is not)" bash -c "[ -d '$FX/channels/flashfx/library' ] && [ -d '$FX/runs' ] && [ ! -d '$FX/library' ]"
bash "$MC" --ms M18 --root "$FX" > "$T/restart.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the next start exits 0"
assert_grep 'without its final .verified. line: undoing it first' "$T/restart.out" "the next start undoes the killed attempt first"
assert_grep 'UNDO verified' "$T/restart.out" "and checks the folder against that attempt's before-listing"
assert_grep '^migrate M18: verified' "$T/restart.out" "then migrates and verifies"
bash "$MC" --undo --ms M18 --root "$FX" >/dev/null 2>&1
assert_eq "$(treesum "$FX")" "$sum0" "after kill, restart and undo the tree is identical again"
# a live runner refuses
sleep 120 & holder=$!
mkdir -p "$FX/channels/x/.locks/runner" 2>/dev/null; printf '%s %s\n' "$holder" "$(date +%s)" > "$FX/channels/x/.locks/runner/pid"
bash "$MC" --ms M18 --root "$FX" > "$T/alive.out" 2>&1; rc=$?
assert_rc 5 "$rc" "a live video runner refuses the migration (exit 5)"
assert_grep 'stop the video runner \(Ctrl\+C in its window\), then run bash build-runner.sh again' "$T/alive.out" "and says what to do"
kill "$holder" 2>/dev/null; wait "$holder" 2>/dev/null
rm -rf "$FX/channels"
# uncommitted changes refuse
printf 'x\n' >> "$FX/pipeline/lib/x.sh"
bash "$MC" --ms M18 --root "$FX" > "$T/dirty.out" 2>&1; rc=$?
assert_rc 2 "$rc" "uncommitted changes outside build/ refuse the migration"
assert_grep 'uncommitted git changes' "$T/dirty.out" "and say so"
git -C "$FX" checkout -q -- pipeline/lib/x.sh
# a failed check undoes itself: a .gitignore with only the old root rules leaves the moved ignored files unignored
assert_true "a second fixture with the old .gitignore builds" new_fx fx2 old
FX2="$TM/fx2"; sumo="$(treesum "$FX2")"
bash "$MC" --ms M18 --root "$FX2" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/bad.out" 2>&1; rc=$?
assert_rc 3 "$rc" "a failed check ends with exit 3"
assert_grep '^FAIL .*not ignored at the new path' "$T/bad.out" "the failed check is the git check-ignore one"
assert_grep '^BLOCKED:' "$T/bad.out" "the run says BLOCKED with the reason"
assert_grep 'UNDO verified' "$T/bad.out" "it undid everything and checked the folder"
assert_eq "$(treesum "$FX2")" "$sumo" "the folder is identical to before"
fi

if want 7; then
section "7. two channels' dummy runners at the same time"
sandbox_init
fast_mode
add_channel second
printf '{Idea one for the first channel: gh in 60 seconds}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
printf '{Idea two for the second channel: uv in one tool}\n' > "$SANDBOX/channels/second/ideas.txt"
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_DUMMY_SECONDS=0.5 timeout 1200 bash "$REPO_DIR/run.sh" --channel flashfx --once ) > "$T/par-a.out" 2>&1 &
pa=$!
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_DUMMY_SECONDS=0.5 timeout 1200 bash "$REPO_DIR/run.sh" --channel second --once ) > "$T/par-b.out" 2>&1 &
pb=$!
wait "$pa"; rca=$?; wait "$pb"; rcb=$?
assert_rc 0 "$rca" "the flashfx runner exits 0"
assert_rc 0 "$rcb" "the second channel's runner exits 0"
assert_eq "$(ls "$SANDBOX/channels/flashfx/runs" | wc -l | tr -d ' ')" "1" "flashfx has its run folder"
assert_eq "$(ls "$SANDBOX/channels/second/runs" | wc -l | tr -d ' ')" "1" "the second channel has its run folder"
assert_eq "$(ls "$SANDBOX/exports" | grep -c '^[0-9]*$')" "2" "two exports (numbered one after the other: the numbering lock is global)"
assert_grep 'DONE   exported #[12]' "$T/par-a.out" "flashfx printed its DONE line"
assert_grep 'DONE   exported #[12]' "$T/par-b.out" "the second channel printed its DONE line"
assert_grep 'channel: flashfx' "$T/par-a.out" "each banner names its channel (flashfx)"
assert_grep 'channel: second' "$T/par-b.out" "each banner names its channel (second)"
assert_grep '\| exported [12]$' "$SANDBOX/channels/flashfx/logs/history.txt" "flashfx's history has its export"
assert_grep '\| exported [12]$' "$SANDBOX/channels/second/logs/history.txt" "the second channel's history has its export"
assert_not_grep 'gh in 60' "$SANDBOX/channels/second/logs/history.txt" "the histories do not mix"
assert_not_grep 'uv in one' "$SANDBOX/channels/flashfx/logs/history.txt" "the histories do not mix (2)"
assert_eq "$(find "$SANDBOX/channels/flashfx/.locks" "$SANDBOX/channels/second/.locks" "$SANDBOX/.locks" -mindepth 1 2>/dev/null | wc -l | tr -d ' ')" "0" "no lock is left behind, in any channel or at the root"
fi

if want 8; then
section "8. the real migration"
B="$REPO_DIR/build/M18"
for f in dry-run.txt move-manifest.tsv manifest-diff.md migration-log.tsv undo-migration.sh before-listing.tsv migration-run.txt; do assert_file "$B/$f" "build/M18/$f exists"; done
assert_grep $'\tverified\t' "$B/migration-log.tsv" "the migration's log ends verified"
assert_grep '^DRY RUN: nothing changed' "$B/dry-run.txt" "the saved dry run says nothing changed"
# the folder keeps living after the move (the runner's log and status lines, the gallery and test runs write into motion-lib): the live check may differ
# in the bytes of those, never in a missing path, a path left at its old place or a count of files
python "$PT/check-manifest.py" --after --root "$RM" --manifest "$B/move-manifest.tsv" > "$T/after.out" 2>&1
assert_eq "$(grep '^FAIL' "$T/after.out" | grep -v -E 'checksum of channels/flashfx/logs/(runner.log|status.txt) changed|bytes, the manifest says' | wc -l | tr -d ' ')" "0" "check-manifest.py --after on the real folder: no missing path, no old path left, no other count differs"
assert_grep '0 problem' "$B/after-check.txt" "the check right after the migration (build/M18/after-check.txt) had no problem"
for d in library styles motion-lib golden; do assert_no_file "$REPO_DIR/$d" "$d is not at the root any more"; done
assert_no_file "$REPO_DIR/ideas.txt" "ideas.txt is not at the root any more"
for p in channels/flashfx/channel.json channels/flashfx/ideas.txt channels/flashfx/library/hooks.txt channels/flashfx/styles/paper-cards/style.md channels/flashfx/motion-lib/catalog.json channels/flashfx/golden/test-idea/plan.json channels/flashfx/logs/runner.log; do assert_file "$REPO_DIR/$p" "$p exists"; done
assert_true "the files that were ignored are ignored at the new path (voice, refs, analysis, sfx audio, renders)" bash -c "cd '$REPO_DIR' && git check-ignore -q channels/flashfx/library/voice/engine.txt && git check-ignore -q channels/flashfx/styles/paper-cards/analysis/x.json && git check-ignore -q channels/flashfx/styles/sfx/x.mp3 && git check-ignore -q channels/flashfx/golden/test-idea/golden.mp4 && git check-ignore -q channels/flashfx/motion-lib/.harness/x.html && git check-ignore -q channels/flashfx/runs/x/state.json"
assert_eq "$(cd "$REPO_DIR" && git status --porcelain | grep -v 'build/' | wc -l | tr -d ' ')" "0" "git status of the real folder is clean (the moves are committed)"
assert_not_grep 'LEGACY-ROOT-RULES' "$REPO_DIR/.gitignore" "the legacy root ignore rules are gone"
pycheck "no tracked file outside build/ names an old root path of the moved data in a way code would build" "$REPO_DIR" <<'PYEOF'
import re, subprocess, sys
root = sys.argv[1]
files = subprocess.run(["git", "-C", root, "ls-files", "-z", "channels"], capture_output=True).stdout.split(b"\0")
bad = []
for f in files:
    f = f.decode()
    if "gallery/play/" in f or f.endswith("webgl.json"):
        t = open(root + "/" + f, encoding="utf-8", errors="replace").read()
        if re.search(r"instagramReels[/\\]+motion-lib", t):
            bad.append(f)
assert not bad, bad[:3]
print("ok")
PYEOF
out="$(bash "$REPO_DIR/pipeline/bin/preflight" --channel flashfx 2>&1)"; rc=$?
assert_rc 0 "$rc" "preflight --channel flashfx passes ($(printf '%s' "$out" | tail -n 1 | cut -c1-90))"
out="$(bash "$REPO_DIR/pipeline/bin/doctor" --quick 2>&1)"; rc=$?
assert_rc 0 "$rc" "doctor --quick passes ($(printf '%s' "$out" | tail -n 1))"
fi

if want 9; then
section "9. test-isolation part 1, the files M18 changed, no em dash"
ISOLATION_PARTS="1" bash "$PT/test-isolation.sh" > "$T/iso.out" 2>&1; rc=$?
assert_rc 0 "$rc" "test-isolation.sh part 1 passes ($(tail -n 1 "$T/iso.out"))"
bash "$PT/test-no-emdash.sh" > "$T/em.out" 2>&1; rc=$?
assert_rc 0 "$rc" "no em dash in any file ($(tail -n 1 "$T/em.out"))"
assert_true "pipeline/bin/migrate-channels, paths.sh, paths.py, config.py and the channel schema exist" bash -c "cd '$REPO_DIR' && test -x pipeline/bin/migrate-channels && test -f pipeline/lib/paths.sh && test -f pipeline/lib/paths.py && test -f pipeline/lib/config.py && test -f pipeline/schemas/channel.schema.json"
assert_eq "$(cd "$REPO_DIR" && grep -il flashfx pipeline/lib/paths.sh pipeline/lib/paths.py pipeline/lib/config.py pipeline/lib/migrate.py pipeline/lib/common.sh pipeline/lib/runner.sh pipeline/lib/protect.py pipeline/lib/preflight.sh pipeline/lib/config.sh pipeline/bin/migrate-channels pipeline/bin/runner-status pipeline/bin/doctor pipeline/bin/preflight pipeline/bin/add-idea.sh run.sh | tr '
' ' ')" "" "the engine code M18 wrote names no channel id (14.5: the engine never hard-codes a channel)"
fi

test_summary
