#!/usr/bin/env bash
# test-isolation.sh: channels never touch each other (BUILD_SPEC.md 14.5). No model call, no engine call.
#   bash pipeline/tests/test-isolation.sh                    part 1 (the default)
#   ISOLATION_PARTS="1 2" bash pipeline/tests/test-isolation.sh    both parts (M19; part 2 takes a few minutes)
#
#   part 1 (static, M18): no literal path to library/, styles/, motion-lib/, golden/, ideas.txt, runs/, logs/ or exports/ in pipeline/, run.sh
#          or tools/ outside paths.sh and paths.py (pipeline/tests/isolation_scan.py; the exceptions are one by one in
#          pipeline/tests/isolation-allowlist.txt, each with its reason); paths.sh and paths.py give the same answers for every variable; the
#          path module refuses (exit 3 and an ERROR line) a path inside another channel's folder and another channel's export folder, in
#          bash and in Python; REELS_PATH_TRACE logs every path chpath resolves
#   part 2 (canary, M19): two fixture channels in a temp REELS_ROOT, each with a unique canary word in every curated file (profile, voice.md,
#          hooks.txt, the style files, the brand kit, ideas.txt, channel.json brand). For every model-calling stage that can reach its call
#          from the frozen test run, the real stage runs against the recorder (the fake claude with FAKE_CLAUDE_RECORD_DIR: the whole prompt and
#          every argument of the call); no canary of B is in anything recorded for A, and the reverse, and the canary of a channel does reach
#          its own prompts. With REELS_PATH_TRACE=1 a dummy run of A logs only paths inside the engine, channels/A/ or exports/A-*/.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
PARTS="${ISOLATION_PARTS:-1}"
FROZEN="$REPO_DIR/pipeline/tests/fixtures/runs/test-idea"
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
want() { case " $PARTS " in *" $1 "*) return 0 ;; esac; return 1; }
T="$(mktemp -d)"
iso_cleanup() { rm -rf "$T" 2>/dev/null || { sleep 2; rm -rf "$T" 2>/dev/null; }; tests_cleanup; }
trap iso_cleanup EXIT
TM="$(mixed "$T")"

if want 1; then
section "part 1. the static check and the path module"
out="$(python "$REPO_DIR/pipeline/tests/isolation_scan.py" 2>&1)"; rc=$?
assert_rc 0 "$rc" "isolation_scan.py: no literal path to channel data outside the paths module ($(printf '%s' "$out" | tail -n 1))"
assert_true "every allowlist entry has a reason and is used" bash -c "python '$REPO_DIR/pipeline/tests/isolation_scan.py' --list | grep -q -v 'unused entry'"

# a planted violation is found
mkdir -p "$T/plant/pipeline/lib" "$T/plant/pipeline/tests"
printf '#!/usr/bin/env bash\nHOOKS="$REELS_ROOT/library/hooks.txt"\n' > "$T/plant/pipeline/lib/x.sh"
printf 'import os\np = os.path.join(root, "styles")\nq = "runs/" + rid\n' > "$T/plant/pipeline/lib/y.py"
printf '' > "$T/plant/pipeline/tests/isolation-allowlist.txt"
out="$(python "$REPO_DIR/pipeline/tests/isolation_scan.py" --root "$TM/plant" 2>&1)"; rc=$?
assert_rc 1 "$rc" "a planted literal path fails the scan"
assert_true "the scan names the shell file and the Python file" bash -c "printf '%s' '$out' | grep -q 'x.sh:2' && printf '%s' '$out' | grep -q 'y.py:2' && printf '%s' '$out' | grep -q 'y.py:3'"
printf 'pipeline/lib/x.sh | REELS_ROOT/library | a planted exception with a reason\n' > "$T/plant/pipeline/tests/isolation-allowlist.txt"
out="$(python "$REPO_DIR/pipeline/tests/isolation_scan.py" --root "$TM/plant" 2>&1)"
assert_true "an allowlist entry lets exactly its line through" bash -c "! printf '%s' '$out' | grep -q 'x.sh' && printf '%s' '$out' | grep -q 'y.py:2'"
printf 'pipeline/lib/x.sh | REELS_ROOT/library |\n' > "$T/plant/pipeline/tests/isolation-allowlist.txt"
assert_false "an allowlist entry without a reason is refused" python "$REPO_DIR/pipeline/tests/isolation_scan.py" --root "$TM/plant"

# M20 (BUILD_SPEC.md 14.5, 14.12): no channel, brand or style name in a shared stage; the format's own stages may name them
mkdir -p "$T/plantn/pipeline/stages/12-review" "$T/plantn/pipeline/stages/03-gate" "$T/plantn/pipeline/lib/review" "$T/plantn/pipeline/tests"
printf 'You review a FlashFX reel in the paper-cards look.
' > "$T/plantn/pipeline/stages/12-review/prompt.md"
printf 'the FlashFX rules of the gate
' > "$T/plantn/pipeline/stages/03-gate/prompt.md"
printf '# the Gabryverse check
' > "$T/plantn/pipeline/lib/review/x.py"
: > "$T/plantn/pipeline/tests/isolation-allowlist.txt"
out="$(python "$REPO_DIR/pipeline/tests/isolation_scan.py" --root "$TM/plantn" 2>&1)"; rc=$?
assert_rc 1 "$rc" "a planted FlashFX name in a shared stage fails the scan"
assert_true "the scan names the shared prompt and the review module, not the gate (a format's own stage)" bash -c "printf '%s' '$out' | grep -q '12-review/prompt.md:1' && printf '%s' '$out' | grep -q 'lib/review/x.py:1' && ! printf '%s' '$out' | grep -q '03-gate'"
assert_true "the shared stages and engine files of the repo name no channel, brand or style" bash -c "python '$REPO_DIR/pipeline/tests/isolation_scan.py' | tail -n 1 | grep -q '0 violation(s) (0 of them names)'"

# paths.sh and paths.py agree
mkdir -p "$T/root/channels/alpha" "$T/root/channels/beta"
for id in alpha beta; do printf '{"id": "%s", "name": "%s", "platform": "instagram-reels", "format": "problem-solution-reel"}\n' "$id" "$id" > "$T/root/channels/$id/channel.json"; done
cmp_paths() {  # cmp_paths <channel or empty>
  local sh py
  sh="$(env -u REELS_CHANNEL ${1:+REELS_CHANNEL="$1"} REELS_ROOT="$TM/root" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; reels_paths_dump')"
  py="$(env -u REELS_CHANNEL ${1:+REELS_CHANNEL="$1"} REELS_ROOT="$TM/root" python "$REPO_DIR/pipeline/lib/paths.py" dump)"
  [ "$sh" = "$py" ] && [ -n "$sh" ]
}
assert_true "paths.sh and paths.py give the same answers with a channel" cmp_paths alpha
assert_true "paths.sh and paths.py give the same answers without a channel" cmp_paths ""
assert_true "paths.sh puts the channel's files inside channels/alpha" bash -c "env REELS_CHANNEL=alpha REELS_ROOT='$TM/root' bash -c 'source \"$REPO_DIR/pipeline/lib/common.sh\"; [ \"\$REELS_IDEAS\" = \"$TM/root/channels/alpha/ideas.txt\" ] && [ \"\$REELS_LOGS\" = \"$TM/root/channels/alpha/logs\" ] && [ \"\$REELS_LOCKS\" = \"$TM/root/channels/alpha/.locks\" ]'"

# the refusals, in bash and in Python
RM="$(mixed "$REPO_DIR")"
shrun() { env REELS_CHANNEL=alpha REELS_ROOT="$TM/root" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; '"$1" 2>&1; }
pyrun() { env REELS_CHANNEL=alpha REELS_ROOT="$TM/root" python -c "import sys; sys.path.insert(0, '$RM/pipeline/lib'); import paths; $1" 2>&1; echo "rc=$?"; }
grep2() {  # grep2 "pattern" "pattern2" name: both patterns in $T/o.txt
  if grep -q -E -- "$1" "$T/o.txt" && grep -q -E -- "$2" "$T/o.txt"; then pass "$3"; else fail "$3 ($(tr '\n' ' ' < "$T/o.txt" | cut -c1-200))"; fi
}
shrun 'chpath library/hooks.txt' > "$T/o.txt"
assert_eq "$(cat "$T/o.txt")" "$TM/root/channels/alpha/library/hooks.txt" "chpath: a path of the channel's own folder resolves"
shrun 'reels_path_refuse "$REELS_CHANNELS_DIR/beta/library/hooks.txt"; echo "rc=$?"' > "$T/o.txt"
grep2 'ERROR paths' 'rc=3' "bash: a path inside channels/beta is refused for channel alpha (exit 3, an ERROR line)"
shrun 'chpath ../beta/library; echo "rc=$?"' > "$T/o.txt"
grep2 'leaves the channel folder' 'rc=3' "bash: chpath refuses a relative path that leaves the channel folder"
shrun 'reels_path_refuse "$REELS_EXPORTS/beta-3/beta-3.mp4"; echo "rc=$?"' > "$T/o.txt"
grep2 'export folder' 'rc=3' "bash: another channel's export folder is refused"
shrun 'reels_path_refuse "$REELS_EXPORTS/alpha-3/alpha-3.mp4"; echo "rc=$?"' > "$T/o.txt"
grep2 'rc=0' 'rc=0' "bash: the channel's own export folder is allowed"
pyrun 'print(paths.ch("library/hooks.txt"))' > "$T/o.txt"
grep2 'channels/alpha/library/hooks.txt' 'rc=0' "python: paths.ch resolves inside the channel"
pyrun 'paths.check(paths.channels_dir() + "/beta/styles/x")' > "$T/o.txt"
grep2 'ERROR paths' 'rc=3' "python: a path inside channels/beta is refused for alpha (exit 3, an ERROR line)"
pyrun 'paths.ch("../beta/library")' > "$T/o.txt"
grep2 'leaves the channel folder' 'rc=3' "python: a relative path that leaves the channel folder is refused"
pyrun 'paths.check(paths.exports() + "/beta-1/beta-1.mp4")' > "$T/o.txt"
grep2 'export folder' 'rc=3' "python: another channel's export folder is refused"
env -u REELS_CHANNEL REELS_ROOT="$TM/root" python -c "import sys; sys.path.insert(0, '$RM/pipeline/lib'); import paths; paths.require_channel()" > "$T/o.txt" 2>&1; echo "rc=$?" >> "$T/o.txt"
grep2 'rc=2' 'alpha' "python: with two channels and none chosen the module exits 2 and lists them"
grep2 'beta' 'rc=2' "python: the list names the second channel too"
# the trace
env REELS_CHANNEL=alpha REELS_ROOT="$TM/root" REELS_PATH_TRACE=1 REELS_PATH_TRACE_FILE="$TM/trace.txt" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; chpath library/a >/dev/null; chpath runs >/dev/null'
env REELS_CHANNEL=alpha REELS_ROOT="$TM/root" REELS_PATH_TRACE=1 REELS_PATH_TRACE_FILE="$TM/trace.txt" python -c "import sys; sys.path.insert(0, '$RM/pipeline/lib'); import paths; paths.ch('styles')"
assert_eq "$(grep -c "/channels/alpha/" "$T/trace.txt")" "3" "REELS_PATH_TRACE logs every path the module resolves (bash and Python)"
fi

if want 2; then
section "part 2. the canary test: two channels, every prompt recorded"
sandbox_init --with-pipeline
fast_mode
SM="$SANDBOX_M"
RM="$(mixed "$REPO_DIR")"
canary_channel() {  # canary_channel <id> <CANARY>: a channel made from the sandbox's flashfx, every curated file carrying its canary word
  local id="$1" cw="$2" d="$SANDBOX/channels/$1" f
  cp -r "$SANDBOX/channels/flashfx" "$d"
  rm -rf "$d/.cache" "$d/runs" "$d/logs" "$d/.locks"; mkdir -p "$d/logs"
  python - "$SM/channels/$id/channel.json" "$id" "$cw" <<'PYEOF'
import json, sys
p, cid, cw = sys.argv[1:4]
d = json.load(open(p, encoding="utf-8"))
d["id"] = cid; d["name"] = cid.capitalize(); d["brand"] = {"display_name": cid.capitalize() + "Brand", "canary": cw}
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
  printf '%s __ is the canary hook of %s.\n' "$cw" "$id" >> "$d/library/hooks.txt"
  for f in library/profile/account.md library/profile/voice.md library/profile/pronunciations.txt styles/paper-cards/style.md styles/paper-cards/tweaks.md \
           styles/paper-cards/vocabulary.md library/brand/BRAND.md; do
    [ -f "$d/$f" ] && printf '\n%s canary line (%s)\n' "$cw" "$f" >> "$d/$f"
  done
  printf '%s | the canary deliverable of %s | https://example.com/%s\n' "$cw" "$id" "$id" >> "$d/library/profile/deliverables.txt"
  if [ -f "$d/library/brand/brand.json" ]; then
    python - "$SM/channels/$id/library/brand/brand.json" "$cw" <<'PYEOF'
import json, sys
p, cw = sys.argv[1:3]
d = json.load(open(p, encoding="utf-8-sig")); d["canary"] = cw
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
  fi
  : > "$d/ideas.txt"
}
canary_channel alpha CANARYALPHA
canary_channel beta CANARYBETA
IDEA="$(tr -d '\r' < "$FROZEN/idea.txt")"
STAGES="$(python "$STATE_PY" stages | cut -f1)"
seed_before() {  # seed_before <channel> <stage>: a run whose stages before <stage> are done from the frozen outputs; prints the run dir
  local id="$1" target="$2" created rd st
  printf '{%s}\n' "$IDEA" > "$SANDBOX/channels/$id/ideas.txt"
  created="$(printf '%s' "$IDEA" | env REELS_CHANNEL="$id" python "$STATE_PY" new --runs "$SM/channels/$id/runs" --id "iso-$target" 2>/dev/null)"
  rd="$(python -c 'import json, sys; print(json.loads(sys.argv[1])["run_dir"])' "$created")"
  for st in $STAGES; do
    [ "$st" = "$target" ] && break
    if [ -d "$FROZEN/$st" ]; then
      cp -r "$FROZEN/$st/." "$rd/$st/"
      env REELS_CHANNEL="$id" python "$STATE_PY" stage-start "$rd" "$st" >/dev/null 2>&1
      env REELS_CHANNEL="$id" python "$STATE_PY" stage-done "$rd" "$st" --schemas "$SANDBOX_M/pipeline/stages" >/dev/null 2>&1
    fi
  done
  mkdir -p "$rd/13-render"; printf 'dummy\n' > "$rd/13-render/final.mp4"; printf 'dummy\n' > "$rd/13-render/hook2.mp4"
  printf '%s' "$rd"
}
fake_claude_on
export FAKE_CLAUDE_MODE=ok
STAGE_LIST="01-research 02-expansion 03-gate 05-hooks 06-judge 07-script 14-export"
for id in alpha beta; do
  for st in $STAGE_LIST; do
    rd="$(seed_before "$id" "$st")"
    mkdir -p "$T/rec/$id/$st"
    ( cd "$SANDBOX" && env REELS_CHANNEL="$id" REELS_ROOT="$SM" FAKE_CLAUDE_RECORD_DIR="$TM/rec/$id/$st" REELS_SLEEP_SCALE=0 timeout 600 \
        bash "$SANDBOX/pipeline/stages/$st/run.sh" "$rd" ) > "$T/rec/$id/$st/stage.out" 2>&1
    rm -rf "$rd"
  done
done
fake_claude_off
# what was recorded
count_rec() { find "$T/rec/$1" -name '*.prompt.txt' 2>/dev/null | wc -l | tr -d ' '; }
na="$(count_rec alpha)"; nb="$(count_rec beta)"
assert_true "the recorder caught the prompts of channel alpha ($na) and beta ($nb): at least 5 each" test "$na" -ge 5 -a "$nb" -ge 5
assert_eq "$na" "$nb" "both channels' stages reached the same number of model calls"
stages_a="$(cd "$T/rec/alpha" && for s in *; do [ -n "$(find "$s" -name '*.prompt.txt' | head -n 1)" ] && echo "$s"; done | tr '\n' ' ')"
echo "   stages that reached their model call: $stages_a"
missing_st=""; for s in 01-research 02-expansion 03-gate 05-hooks 07-script; do case " $stages_a " in *" $s "*) ;; *) missing_st="$missing_st $s" ;; esac; done
assert_eq "$missing_st" "" "S1, S2, S3, S5 and S7 are among the stages that reached their model call"
cross() {  # cross <recorded channel> <other canary> <other id>: how many recorded files carry the other channel's canary or folder
  grep -r -l -i -E "$2|channels/$3/|$3-[0-9]+" "$T/rec/$1" --include='*.prompt.txt' --include='*.argv.json' 2>/dev/null | wc -l | tr -d ' '
}
assert_eq "$(cross alpha CANARYBETA beta)" "0" "no canary, folder or export name of channel beta in anything recorded for alpha"
assert_eq "$(cross beta CANARYALPHA alpha)" "0" "no canary, folder or export name of channel alpha in anything recorded for beta"
own() { grep -r -l "$2" "$T/rec/$1" --include='*.prompt.txt' 2>/dev/null | wc -l | tr -d ' '; }
assert_true "the canary of alpha does reach alpha's prompts ($(own alpha CANARYALPHA) of $na)" test "$(own alpha CANARYALPHA)" -ge 1
assert_true "the canary of beta does reach beta's prompts ($(own beta CANARYBETA) of $nb)" test "$(own beta CANARYBETA)" -ge 1
assert_eq "$(grep -r -l "CANARYALPHA" "$T/rec/beta" 2>/dev/null | wc -l | tr -d ' ')" "0" "alpha's canary is not in any file recorded for beta (stage output included)"
# the path trace of a dummy run
printf '{An idea for alpha: trace}\n' > "$SANDBOX/channels/alpha/ideas.txt"
printf '{An idea for beta: trace}\n' > "$SANDBOX/channels/beta/ideas.txt"
: > "$T/trace-alpha.txt"
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_DUMMY_SECONDS=0.1 REELS_PATH_TRACE=1 REELS_PATH_TRACE_FILE="$TM/trace-alpha.txt" timeout 1500 bash "$SANDBOX/run.sh" --channel alpha --once ) > "$T/trace-run.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the dummy run of alpha exits 0 with REELS_PATH_TRACE=1"
assert_true "the trace logged paths ($(wc -l < "$T/trace-alpha.txt" | tr -d ' '))" test "$(wc -l < "$T/trace-alpha.txt" | tr -d ' ')" -gt 10
outside="$(grep -v -E "^($SM/channels/alpha/|$SM/exports/alpha-|$RM/|$SM/pipeline/|$SM/exports$|$SM/channels/alpha$)" "$T/trace-alpha.txt" | head -n 5)"
assert_eq "$outside" "" "every logged path is inside the engine, channels/alpha/ or exports/alpha-*/"
assert_eq "$(ls "$SANDBOX/channels/beta/runs" 2>/dev/null | wc -l | tr -d ' ')" "0" "channel beta has no run: alpha's run did not touch its folder"
assert_file "$SANDBOX/exports/alpha-1/alpha-1.mp4" "alpha's export is exports/alpha-1/"
fi

test_summary
