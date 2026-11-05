#!/usr/bin/env bash
# test-m13.sh: acceptance test for M13 (Hardening; BUILD_SPEC.md section 12 and PLAN.md M13).
#   bash pipeline/tests/test-m13.sh                       every section (section 3 runs three ideas back to back with
#                                                         the real models and engines: several hours)
#   M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh   the fake-only sections (about 20 minutes)
#   M13_REAL_DIR=build/M13/real M13_SECTIONS=3 bash pipeline/tests/test-m13.sh
#                                                         section 3's checks on a real run m13-run.sh already made
#                                                         (bash pipeline/tests/m13-run.sh real build/M13/real)
# Sections:
#   1. units: pipeline/lib/logcheck.py on a good timeline and on every kind of broken one; the log rotation (alone,
#      and inside a live dummy run whose rotated logs still tell one story); the status line written aside and
#      renamed; the fault injection (REELS_FAULT) by itself; build-voice-profile --force on a copy of the profile
#      keeps the hand-written Brand, Content strategy, How I promote, the FlashFX spelling line and a filled field;
#      the doctor
#   2. three ideas unattended with the fake claude (real S1 to S4, dummy stages after): a simulated limit in the second
#      idea, the runner killed in the second idea and restarted, the whole story checked (pipeline/tests/m13-run.sh fake)
#   3. the same with the real models and engines on every stage (pipeline/tests/m13-run.sh real; several hours)
#   4. no em dash in the files M13 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M13_SECTIONS:-1 2 3 4}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
LOGCHECK="$REPO_DIR/pipeline/lib/logcheck.py"
VP="$REPO_DIR/pipeline/lib/voiceprofile.py"
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
export PYTHONUTF8=1

no_emdash_in() {  # no_emdash_in <name> <file>...
  local name="$1"; shift
  local bad
  bad="$(python -c 'import sys
print(" ".join(p for p in sys.argv[1:] if open(p, "rb").read().find(bytes([0xE2, 0x80, 0x94])) >= 0))' "$@" 2>&1)"
  if [ -z "$bad" ]; then pass "$name"; else fail "$name (em dash in: $bad)"; fi
}
jq_py() {  # jq_py <json file> <python expression over d>: prints the value
  python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
v = eval(sys.argv[2])
print(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict, bool)) else v)' "$1" "$2"
}
story_files() {  # story_files <logs dir>: runner.log with its rotated files, oldest first
  local d="$1" f
  for f in $(ls "$d"/runner.log.[0-9]* 2>/dev/null | sed 's/.*\.//' | sort -rn); do printf '%s ' "$d/runner.log.$f"; done
  printf '%s\n' "$d/runner.log"
}

# ----------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. units: the log checker, the rotation, the status line, the fault injection, the voice profile, the doctor"
sandbox_init
L="$SANDBOX/good.log"
cat > "$L" <<'EOF'
[10:00] WARN   preflight: library/voice/engine.txt is missing
[10:00] START  reels autopilot v0.1.0 (abc1234) | queue: 2 ideas | style: paper-cards | voice: kokoro af_bella | sfx map: 93 files
[10:00] INFO   root: /tmp/x | mode: once (stops when the queue is empty)
[10:00] QUEUE  1. first idea
[10:00] START  idea 1/2 "first idea" -> runs/r1
[10:03] STEP   researching facts done (2m51s) -> expanding idea
[10:05] REEL   #idea 1/2 "first idea" | expanding idea | minute 5 | stage 1m10s | issues: 0 fixed, 0 open
[10:06] STEP   expanding idea done (3m00s) -> checking idea (gate)
[10:06] GATE   passed (P3 S2 C3 F ok H ok)
[10:07] LIMIT  session limit hit, resuming at 10:27 (+2 min margin)
[10:10] REEL   #idea 1/2 "first idea" | waiting for usage limit (session) until 10:27 (17m left) | minute 10 | stage 4m00s | issues: 0 fixed, 0 open
[10:15] REEL   #idea 1/2 "first idea" | waiting for usage limit (session) until 10:27 (12m left) | minute 15 | stage 9m00s | issues: 0 fixed, 0 open
[10:20] REEL   #idea 1/2 "first idea" | waiting for usage limit (session) until 10:27 (7m left) | minute 20 | stage 14m00s | issues: 0 fixed, 0 open
[10:25] REEL   #idea 1/2 "first idea" | waiting for usage limit (session) until 10:27 (2m left) | minute 25 | stage 19m00s | issues: 0 fixed, 0 open
[10:27] RESUME limit reset, continuing: checking idea (gate)
[10:28] ERROR  S3 checking idea (gate): boom
[10:29] FIXED  S3: a cause (commit abc1234), restarting stage
[10:30] REEL   #idea 1/2 "first idea" | checking idea (gate) | minute 30 | stage 1m00s | issues: 1 fixed, 0 open
[10:31] STEP   checking idea (gate) done (25m00s) -> exporting #1
[10:31] DONE   exported #1 -> exports/1/ (31 min, 1 issue fixed)
[10:31] NEXT   idea 2/2 "second idea"
[10:31] START  idea 2/2 "second idea" -> runs/r2
[10:32] DROP   idea "second idea" dropped: facts don't hold (P2 S2 C2 F fail H ok): x. Removed from ideas.txt
[10:32] IDLE   queue empty: this session 1 exported, 1 dropped, 0 blocked in 32m00s | today: 1 exported, 1 dropped
EOF
python "$LOGCHECK" story "$L" --json "$SANDBOX/good.json" > "$SANDBOX/good.out"; rc=$?
assert_rc 0 $rc "logcheck story: the good timeline has no problem ($(head -c 300 "$SANDBOX/good.out"))"
assert_eq "$(jq_py "$SANDBOX/good.json" '[i["outcome"] for i in d["ideas"]]')" '["done", "dropped"]' "logcheck: the outcomes done, dropped"
assert_eq "$(jq_py "$SANDBOX/good.json" '[(l["kind"], l["resume_at"], l["resume_text"]) for l in d["limits"]]')" '[["session", "10:27", "limit reset, continuing: checking idea (gate)"]]' "logcheck: the LIMIT line paired with its RESUME"
broken() {  # broken <name> <python replacement code over s> <expected problem regex> [story args]
  local name="$1" code="$2" want="$3"; shift 3
  python -c 'import sys
s = open(sys.argv[1], encoding="utf-8").read()
exec(sys.argv[2])
open(sys.argv[3], "w", encoding="utf-8", newline="\n").write(s)' "$L" "$code" "$SANDBOX/bad.log"
  python "$LOGCHECK" story "$SANDBOX/bad.log" "$@" > "$SANDBOX/bad.out" 2>&1; local rc=$?
  if [ "$rc" = 1 ] && grep -q -E -- "$want" "$SANDBOX/bad.out"; then pass "logcheck catches: $name"
  else fail "logcheck catches: $name (exit $rc, wanted /$want/ in: $(head -c 400 "$SANDBOX/bad.out"))"; fi
}
broken "a LIMIT without its RESUME" 's = s.replace("[10:27] RESUME limit reset, continuing: checking idea (gate)\n", "")' "LIMIT without its RESUME"
broken "an idea silent for 12 minutes (a hang)" 'import re; s = re.sub(r"\[10:(10|15|20)\] REEL[^\n]*\n", "", s)' "silent for 1[0-9] minutes"
broken "a heartbeat with the wrong fixed count" 's = s.replace("issues: 1 fixed, 0 open", "issues: 0 fixed, 0 open")' "heartbeat says 0 fixed"
broken "a heartbeat with the wrong minute" 's = s.replace("minute 20 |", "minute 41 |")' "heartbeat minute 41"
broken "a heartbeat naming another idea" 's = s.replace("[10:30] REEL   #idea 1/2 \"first idea\"", "[10:30] REEL   #idea 1/2 \"other idea\"")' "heartbeat names"
broken "a summary with wrong counts" 's = s.replace("this session 1 exported, 1 dropped", "this session 2 exported, 1 dropped")' "summary says 2 exported"
broken "a missing NEXT line" 's = s.replace("[10:31] NEXT   idea 2/2 \"second idea\"\n", "")' "without a NEXT line"
broken "a broken STEP chain" 's = s.replace("-> expanding idea", "-> picking hooks")' "previous line announced 'picking hooks'"
broken "an em dash in a line" 's = s.replace("x. Removed", "x " + chr(0x2014) + " y. Removed")' "em dash in the line"
broken "a tag not padded to 6" 's = s.replace("[10:03] STEP   researching", "[10:03] STEP researching")' "not in the format|not padded"
broken "an idea that never ends" 's = s[: s.index("[10:31] DONE")]' "ended inside idea 1"
broken "a STOP line" 's = s.replace("[10:32] IDLE", "[10:32] STOP   systemic failure: x. See logs/STOPPED.md\n[10:32] IDLE")' "STOP line"
broken "exports with a gap" 's = s.replace("[10:32] DROP   idea \"second idea\" dropped: facts don\x27t hold (P2 S2 C2 F fail H ok): x. Removed from ideas.txt", "[10:32] GATE   passed (P3 S3 C3 F ok H ok)\n[10:32] DONE   exported #3 -> exports/3/ (1 min, 0 issues fixed)").replace("1 exported, 1 dropped, 0 blocked in", "2 exported, 0 dropped, 0 blocked in")' "without gaps"
broken "a crash that the next session does not resume" 's = s[: s.index("[10:31] DONE")] + "[10:40] START  reels autopilot v0.1.0 (abc1234) | queue: 2 ideas | style: paper-cards | voice: kokoro af_bella | sfx map: 93 files\n[10:40] START  idea 1/2 \"second idea\" -> runs/r2\n[10:41] DROP   idea \"second idea\" dropped: x. Removed from ideas.txt\n[10:41] IDLE   queue empty: this session 0 exported, 1 dropped, 0 blocked in 1m00s | today: 0 exported, 1 dropped\n"' "did not resume r1 first" --allow-crash
python -c 'import sys
s = open(sys.argv[1], encoding="utf-8").read()
s = s[: s.index("[10:31] DONE")] + "[10:40] START  reels autopilot v0.1.0 (abc1234) | queue: 2 ideas | style: paper-cards | voice: kokoro af_bella | sfx map: 93 files\n[10:40] START  idea 1/2 \"first idea\" -> runs/r1 (resumed at checking idea (gate), 2 stages done)\n[10:41] STEP   checking idea (gate) done (1m00s) -> exporting #1\n[10:41] DONE   exported #1 -> exports/1/ (41 min, 1 issue fixed)\n[10:41] IDLE   queue empty: this session 1 exported, 0 dropped, 0 blocked in 1m00s | today: 1 exported, 0 dropped\n"
open(sys.argv[2], "w", encoding="utf-8", newline="\n").write(s)' "$L" "$SANDBOX/crash.log"
assert_rc 0 "$(python "$LOGCHECK" story "$SANDBOX/crash.log" --allow-crash >/dev/null 2>&1; echo $?)" "logcheck --allow-crash: a crash resumed by the next session is a good story"
assert_rc 1 "$(python "$LOGCHECK" story "$SANDBOX/crash.log" >/dev/null 2>&1; echo $?)" "logcheck without --allow-crash: the same crash is a problem"
assert_rc 0 "$(python "$LOGCHECK" line '[10:03] STEP   researching facts done (2m51s) -> expanding idea' >/dev/null; echo $?)" "logcheck line: a valid line"
assert_rc 1 "$(python "$LOGCHECK" line $'\033[36m[10:03] STEP\033[0m   x' >/dev/null; echo $?)" "logcheck line: ANSI codes are refused"
printf '[10:03] QUEUE  1. x\n' > "$SANDBOX/st.txt"
assert_rc 1 "$(python "$LOGCHECK" status "$SANDBOX/st.txt" >/dev/null; echo $?)" "logcheck status: a QUEUE line never belongs in status.txt"
printf '1\t<missing>\n2\t[10:00] START  reels autopilot v1 | queue: 0 ideas | style: s | voice: v | sfx map: m\n3\t\n' > "$SANDBOX/samples.txt"
assert_rc 1 "$(python "$LOGCHECK" samples "$SANDBOX/samples.txt" >/dev/null; echo $?)" "logcheck samples: an empty sample after the first status is a problem"

# the rotation, alone
(
  export REELS_ROOT="$SANDBOX_M"; unset REELS_COMMON_LOADED
  source "$REPO_DIR/pipeline/lib/common.sh"; source "$REPO_DIR/pipeline/lib/log.sh"; source "$REPO_DIR/pipeline/lib/config.sh"
  export REELS_LOG_ROTATE_BYTES=1000
  rm -f "$REELS_LOGS"/runner.log*
  printf '[10:00] STEP   %0900d\n' 0 > "$REELS_LOGS/runner.log"
  reels_log_rotate >/dev/null; echo "small:$?"
  for n in 1 2 3 4 5; do
    for k in 1 2; do printf '[10:00] STEP   %0900d\n' "$n" >> "$REELS_LOGS/runner.log"; done
    reels_log_rotate >/dev/null; echo "rotate$n:$?"
  done
  echo status:"$(cat "$REELS_LOGS/status.txt" 2>/dev/null)"
) > "$SANDBOX/rot.out" 2>&1
assert_eq "$(grep -c '^rotate[1-5]:0$' "$SANDBOX/rot.out")/$(grep -c '^small:1$' "$SANDBOX/rot.out")" "5/1" "rotation: a log under the size stays, one over it rotates every time"
assert_eq "$(ls "$SANDBOX"/logs/runner.log* | sed 's|.*/||' | paste -sd' ')" "runner.log runner.log.1 runner.log.2 runner.log.3" "rotation: runner.log plus 3 old files (logs.rotate_keep), the oldest deleted"
assert_grep "^\[[0-9:]+\] INFO   logs/runner.log reached [0-9]+ bytes: the earlier lines are in logs/runner.log.1 \(up to 3 old files are kept\)$" "$SANDBOX/logs/runner.log" "rotation: the new log starts with the INFO line naming the old one"
assert_grep "0{895}5$" "$SANDBOX/logs/runner.log.1" "rotation: runner.log.1 holds the latest lines before the rotation"
assert_eq "$(grep '^status:' "$SANDBOX/rot.out")" "status:" "rotation: the INFO line does not replace status.txt"

# the status line is written aside and renamed (never seen empty or half written), nothing left behind
(
  export REELS_ROOT="$SANDBOX_M"; unset REELS_COMMON_LOADED
  source "$REPO_DIR/pipeline/lib/common.sh"; source "$REPO_DIR/pipeline/lib/log.sh"
  for n in $(seq 1 30); do say STEP "step $n done (1s) -> next"; done
) > /dev/null 2>&1
assert_eq "$(sed 's/^\[[0-9:]*\] //' "$SANDBOX/logs/status.txt")" "STEP   step 30 done (1s) -> next" "status.txt holds the latest line"
assert_eq "$(ls -a "$SANDBOX/logs" | grep -c '^\.status\.')" "0" "no .status.* file is left behind"

# the fault injection by itself (ai.sh): the stage and the run ordinal, the once-only marker, the limit result
sandbox_init
RD1="$(printf 'idea one' | python pipeline/lib/state.py new --runs "$SANDBOX_M/runs" --id one 2>/dev/null | python -c 'import json, sys; print(json.load(sys.stdin)["run_dir"])')"
mkdir -p "$RD1/02-expansion/calls"
(
  export REELS_ROOT="$SANDBOX_M"; unset REELS_COMMON_LOADED
  source "$REPO_DIR/pipeline/lib/common.sh"; source "$REPO_DIR/pipeline/lib/log.sh"; source "$REPO_DIR/pipeline/lib/config.sh"
  source "$REPO_DIR/pipeline/lib/state.sh"; source "$REPO_DIR/pipeline/lib/status.sh"; source "$REPO_DIR/pipeline/lib/ai.sh"
  b="$RD1/02-expansion/calls/001-x"
  REELS_FAULT="limit:03-gate" ai_fault "$RD1/02-expansion" "$b" sid-1 >/dev/null 2>&1; echo "other-stage:$?"
  REELS_FAULT="limit:02-expansion@2" ai_fault "$RD1/02-expansion" "$b" sid-1 >/dev/null 2>&1; echo "other-idea:$?"
  REELS_FAULT="bogus:02-expansion" ai_fault "$RD1/02-expansion" "$b" sid-1 >/dev/null 2>&1; echo "bogus:$?"
  REELS_FAULT="limit:02-expansion@1" REELS_FAULT_MINUTES=5 ai_fault "$RD1/02-expansion" "$b" sid-1 >/dev/null 2>&1; echo "fires:$?"
  REELS_FAULT="limit:02-expansion@1" ai_fault "$RD1/02-expansion" "$b.2" sid-1 >/dev/null 2>&1; echo "again:$?"
) > "$SANDBOX/fault.out" 2>&1
assert_eq "$(paste -sd' ' "$SANDBOX/fault.out")" "other-stage:1 other-idea:1 bogus:1 fires:0 again:1" "REELS_FAULT: only its stage and its idea, an unknown kind ignored, once only"
assert_file "$SANDBOX/logs/.faults/limit-02-expansion@1" "the fault's once-only marker in logs/.faults/"
F="$RD1/02-expansion/calls/001-x.json"
assert_eq "$(jq_py "$F" 'd["is_error"]')/$(jq_py "$F" 'd["session_id"]')" "true/sid-1" "the injected result: an error in the same session"
cls="$(python pipeline/lib/errors.py classify --rc 1 --stdout "$F" --stderr "$RD1/02-expansion/calls/001-x.err" --tz Europe/Rome 2>/dev/null || true)"
assert_true "the injected result is classified as a usage limit with its reset time ($cls)" python -c 'import json, sys; d = json.loads(sys.argv[1]); assert d["class"] == "limit" and d["limit"]["reset"]' "$cls"

# build-voice-profile --force on a copy of the profile keeps the hand-written parts. The copy is the drafts as they
# were when this block was written (pipeline/tests/fixtures/profile/, placeholders and all): the user's filled profile
# stays out of the tests (DECISIONS.md 305)
sandbox_init
P="$SANDBOX/library/profile"
cp "$REPO_DIR/pipeline/tests/fixtures/profile/voice.md" "$P/voice.md"
cp "$REPO_DIR/pipeline/tests/fixtures/profile/account.md" "$P/account.md"
python - "$P" <<'EOF'
import sys
p = sys.argv[1]
acc = open(p + "/account.md", encoding="utf-8").read()
acc += "\n## Content strategy\n\n- About 1 in 3 reels FlashFX, the rest external tools and methods.\n- Problem first, always.\n"
open(p + "/account.md", "w", encoding="utf-8", newline="\n").write(acc)
v = open(p + "/voice.md", encoding="utf-8").read()
v = v.replace("## Proof I can use", "## How I promote\n\nI mention FlashFX once, at the end, never as a hard sell.\n\n## Proof I can use")
v = v.replace("- **Name:** [FILL IN]", "- **Name:** Gabriele")
open(p + "/voice.md", "w", encoding="utf-8", newline="\n").write(v)
EOF
cp "$P/account.md" "$SANDBOX/account.before.md"; cp "$P/voice.md" "$SANDBOX/voice.before.md"
REELS_ROOT="$SANDBOX_M" bash pipeline/bin/build-voice-profile --force --no-model > "$SANDBOX/vp.out" 2>&1; rc=$?
assert_rc 0 $rc "build-voice-profile --force exits 0"
section_of() {  # section_of <file> <heading>: the section's body
  python -c 'import sys
sys.path.insert(0, sys.argv[3])
from voiceprofile import split_sections, read_text
_, secs = split_sections(read_text(sys.argv[1]))
print(next((b.strip() for h, b in secs if h == sys.argv[2]), "<missing>"))' "$1" "$2" "$REPO_DIR/pipeline/lib"
}
assert_eq "$(section_of "$P/account.md" Brand)" "$(section_of "$SANDBOX/account.before.md" Brand)" "account.md: the hand-written Brand section is kept word for word"
assert_eq "$(section_of "$P/account.md" "Content strategy")" "$(section_of "$SANDBOX/account.before.md" "Content strategy")" "account.md: the Content strategy section is kept"
assert_eq "$(section_of "$P/voice.md" "How I promote")" "I mention FlashFX once, at the end, never as a hard sell." "voice.md: How I promote is kept"
assert_grep '^  - The brand name is always written "FlashFX"\.$' "$P/voice.md" "voice.md: the FlashFX spelling line is kept"
assert_eq "$(grep -n 'The brand name is always written' "$P/voice.md" | cut -d: -f1)" "$(( $(grep -n 'Words I actually use' "$P/voice.md" | cut -d: -f1) + 1 ))" "voice.md: the spelling line stays under 'Words I actually use'"
assert_grep '^- \*\*Name:\*\* Gabriele$' "$P/voice.md" "voice.md: a field filled by hand survives the template's placeholder"
assert_grep '^- \*\*Pace:\*\* 195 words per minute, measured' "$P/voice.md" "voice.md: the measured pace survives a rebuild that measured nothing"
assert_eq "$(section_of "$P/voice.md" "Verbatim excerpts of my real speech" | grep -c '^[0-9]\. "')" "5" "voice.md: the 5 verbatim excerpts survive"
assert_grep "kept your hand-written parts of account.md: Brand; Content strategy" "$SANDBOX/vp.out" "the script names what it kept"
assert_file "$SANDBOX/logs/voice-profile/account.md.before-$(date +%Y-%m-%d).md" "the previous account.md is copied into logs/voice-profile/"
cp "$P/voice.md" "$SANDBOX/voice.first.md"; cp "$P/account.md" "$SANDBOX/account.first.md"
REELS_ROOT="$SANDBOX_M" bash pipeline/bin/build-voice-profile --force --no-model --quiet >/dev/null 2>&1
assert_true "a second --force rebuild changes nothing (idempotent)" bash -c "cmp -s '$P/voice.md' '$SANDBOX/voice.first.md' && cmp -s '$P/account.md' '$SANDBOX/account.first.md'"
# the spelling line in another section stays in that section; a memo draft wins for the fields it filled
python - "$P/voice.md" <<'EOF'
import sys
p = sys.argv[1]; v = open(p, encoding="utf-8").read()
v = v.replace('  - The brand name is always written "FlashFX".\n', "")
v = v.replace("## The ask\n", '## The ask\n\n- Spell it FlashFX, never Flash FX.\n')
v = v.replace("- **Handle:** [FILL IN]", "- **Handle:** @gab")
open(p, "w", encoding="utf-8", newline="\n").write(v)
EOF
printf '%s\n' '{"voice_md": "## Who I am\n\n- **Name:** Gabriele B\n- **Handle:** [FILL IN]\n- **What I do, in one sentence:** I show AI tools that save an afternoon.\n\n## The ask\n\n- **My keyword CTA, if I use one:** FLASH\n"}' > "$SANDBOX/answer.json"
python "$VP" compose --out "$P/voice.md" --answer "$SANDBOX/answer.json" --memo-name library/voice/memo.wav --keep "$P/voice.md" > "$SANDBOX/compose.out"
assert_grep '^- \*\*Name:\*\* Gabriele B$' "$P/voice.md" "memo draft: the field the memo filled wins"
assert_grep '^- \*\*Handle:\*\* @gab$' "$P/voice.md" "memo draft: a field only the old file had is kept"
assert_eq "$(section_of "$P/voice.md" "The ask" | grep -c 'Spell it FlashFX, never Flash FX\.')" "1" "memo draft: the spelling line stays in its section (The ask)"
assert_eq "$(section_of "$P/voice.md" "How I promote")" "I mention FlashFX once, at the end, never as a hard sell." "memo draft: How I promote is kept"
# from nothing: account.md's template now has the Brand section of the brand kit (2.7)
rm -f "$P/account.md" "$P/voice.md"
REELS_ROOT="$SANDBOX_M" bash pipeline/bin/build-voice-profile --no-model --quiet >/dev/null 2>&1
assert_grep '^- Brand kit: library/brand/' "$P/account.md" "a fresh account.md has the Brand section pointing at library/brand/"

# the doctor
sandbox_init
printf '[10:00] STEP   researching facts done (1s) -> expanding idea\n' > "$SANDBOX/logs/status.txt"
REELS_ROOT="$SANDBOX_M" bash pipeline/bin/doctor --quick > "$SANDBOX/doc.out" 2>&1; rc=$?
assert_rc 0 $rc "doctor --quick exits 0 on a healthy sandbox ($(grep -c '^FAIL' "$SANDBOX/doc.out") FAIL lines)"
for s in versions disk freshness runner "queue and logs"; do assert_grep "^== $s$" "$SANDBOX/doc.out" "doctor: the $s section"; done
assert_grep '^OK    node packages as pinned in package.json: gsap [0-9.]+, hyperframes [0-9.]+, three [0-9.]+$' "$SANDBOX/doc.out" "doctor: the node packages against the pins"
assert_grep '^OK    status \([0-9]+ min ago\): \[10:00\] STEP' "$SANDBOX/doc.out" "doctor: the last status, checked"
printf 'not a status line\n' > "$SANDBOX/logs/status.txt"
printf '# STOPPED\n\nsystemic failure: x\n' > "$SANDBOX/logs/STOPPED.md"
REELS_ROOT="$SANDBOX_M" bash pipeline/bin/doctor --quick > "$SANDBOX/doc2.out" 2>&1; rc=$?
assert_rc 1 $rc "doctor exits 1 on a broken status line and a STOPPED.md"
assert_grep '^FAIL  logs/status.txt is not a valid status line' "$SANDBOX/doc2.out" "doctor: names the broken status line"
assert_grep '^FAIL  logs/STOPPED.md' "$SANDBOX/doc2.out" "doctor: names STOPPED.md"

# the rotation inside a live run: rotated files still tell one story
sandbox_init --with-pipeline
fast_mode
export REELS_STATUS_EVERY=1
python - "$SANDBOX_M/config.json" <<'EOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8")); d.setdefault("logs", {})["rotate_keep"] = 50
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
EOF
grep -v '^#' "$FIXTURES/ideas/three-ideas.txt" > "$SANDBOX/ideas.txt"
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_LOG_ROTATE_BYTES=6000 REELS_LOG_ROTATE_EVERY=2 timeout 900 bash "$SANDBOX/run.sh" --once ) > "$SANDBOX/rotrun.out" 2>&1; rc=$?
assert_rc 0 $rc "the dummy run with a 6 KB rotation exits 0"
nrot="$(ls "$SANDBOX"/logs/runner.log.[0-9]* 2>/dev/null | wc -l | tr -d ' ')"
assert_true "the live run rotated logs/runner.log at least twice ($nrot rotated files)" test "$nrot" -ge 2
python "$LOGCHECK" story $(story_files "$SANDBOX/logs") --heartbeat 1 --no-gate-line > "$SANDBOX/rotstory.out" 2>&1; rc=$?
assert_rc 0 $rc "the rotated logs, read oldest first, tell one complete story ($(head -c 300 "$SANDBOX/rotstory.out"))"
assert_grep '"exports": \[1, 2, 3\]' "$SANDBOX/rotstory.out" "the story across the rotated files has the exports 1, 2, 3"
unset REELS_STATUS_EVERY
fi

# ----------------------------------------------------------------------------------------------------------------
check_multi() {  # check_multi <driver out dir> <fake|real>: the acceptance checks on an m13-run.sh run
  local D="$1" mode="$2" S RD2 hb
  if [ ! -f "$D/result.env" ]; then fail "$mode run: $D/result.env is missing (the driver did not finish)"; return; fi
  local MODE SANDBOX_M RC1 RC2 RC3 LIMIT_FIRED KILL_FIRED LOCK_LEFT PID_LEFT T0 T1 T2
  source "$D/result.env"
  S="$(cygpath -u "$SANDBOX_M" 2>/dev/null || printf '%s' "$SANDBOX_M")"
  printf '   sandbox %s; run 1 %s s, run 2 %s s\n' "$SANDBOX_M" "$((T1 - T0))" "$((T2 - T1))"
  grep -E "$ts_regex(START|STEP|GATE|ANGLE|LIMIT|RESUME|DONE|DROP|BLOCK|NEXT|IDLE|ERROR|FIXED|ESCAL|STOP)|fault injected|interrupted" "$S/logs/runner.log" | grep -v 'STEP   ' | sed 's/^/    /' | head -60
  assert_eq "$LIMIT_FIRED/$KILL_FIRED" "1/1" "$mode: the simulated limit and the kill both fired in the second idea"
  assert_eq "$RC1" "137" "$mode: run 1 ended killed (exit 137) during the second idea"
  assert_eq "$LOCK_LEFT/$PID_LEFT" "1/1" "$mode: the killed runner left its lock and the stage's pid file, as a real crash does"
  assert_eq "$RC2" "0" "$mode: the restarted runner (run 2) finishes the queue and exits 0"
  assert_eq "$RC3" "130" "$mode: run 3 (forever mode) stops on SIGTERM with exit 130"
  # the story
  python "$LOGCHECK" story $(story_files "$S/logs") --allow-crash $([ "$mode" = fake ] && echo "--heartbeat 1") --json "$D/story.json" > "$D/story.out" 2>&1; local rc=$?
  assert_rc 0 $rc "$mode: runner.log tells the full story with no problem ($(python -c 'import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); print("; ".join(d["problems"][:6]))' "$D/story.json" 2>/dev/null))"
  assert_eq "$(jq_py "$D/story.json" 'len(d["sessions"])')" "3" "$mode: three runner sessions (run 1, the restart, the forever mode)"
  assert_eq "$(jq_py "$D/story.json" 'sorted(set(i["run"] for i in d["ideas"] if i["outcome"] in ("done", "dropped", "blocked")))' | python -c 'import json, sys; print(len(json.load(sys.stdin)))')" "3" "$mode: every idea ended exported, dropped or blocked"
  assert_eq "$(jq_py "$D/story.json" '[(i["session"], i["k"], i["outcome"]) for i in d["ideas"] if i["outcome"] == "interrupted"]')" '[[1, 2, "interrupted"]]' "$mode: only the second idea of session 1 was interrupted (the kill)"
  assert_eq "$(jq_py "$D/story.json" '[(i["resumed"], i["resumed_at"], i.get("resumed_after_crash", False)) for i in d["sessions"][1]["ideas"][:1]]')" '[[true, "checking idea (gate)", true]]' "$mode: the restart resumed the same idea at the same stage (S3)"
  assert_grep "${ts_regex}INFO   S3 checking idea \(gate\): attempt 2 \(the previous one was interrupted\)$" "$S/logs/runner.log" "$mode: S3 runs again as attempt 2 after the interruption"
  assert_eq "$(jq_py "$D/story.json" '[(l["idea"], l["session"], l["kind"], l["resume_text"]) for l in d["limits"]]')" '[[2, 1, "session", "limit reset, continuing: expanding idea"]]' "$mode: one LIMIT (session limit) in the second idea, followed by its RESUME line"
  assert_grep "${ts_regex}LIMIT  session limit hit, resuming at [0-9]{2}:[0-9]{2} \(\+2 min margin\)$" "$S/logs/runner.log" "$mode: the LIMIT line names the time it resumes at (reset plus the margin)"
  assert_grep "\| session limit \| reset 20[0-9-]+ [0-9:]+ \| waiting until 20[0-9-]+ [0-9:]+ \(reset \+ 120 s\) \|" "$S/logs/limits.log" "$mode: limits.log has the target time"
  assert_grep "resumed after the session limit" "$S/logs/limits.log" "$mode: limits.log has the resume"
  RD2="$(jq_py "$D/story.json" 'd["sessions"][0]["ideas"][1]["run"]')"; RD2="$S/runs/$RD2"
  local fj next sid1 sid2
  fj="$(grep -l '"fault": "REELS_FAULT limit"' "$RD2"/02-expansion/calls/*.json 2>/dev/null | head -n 1)"
  assert_true "$mode: the faulted S2 call is in the call log ($(basename "${fj:-none}"))" test -n "$fj"
  if [ -n "$fj" ]; then
    next="$(ls "$RD2"/02-expansion/calls/*.meta | grep -A1 -F "${fj%.json}.meta" | tail -n 1)"
    sid1="$(sed -n 's/^resume: //p' "${fj%.json}.meta")"; sid2="$(sed -n 's/^resume: //p' "$next")"
    assert_true "$mode: the retry after the limit resumes the same session ($sid1)" test -n "$sid1" -a "$sid1" = "$sid2" -a "$next" != "${fj%.json}.meta"
    assert_grep '^class: ok$' "$next" "$mode: the retried call in that session succeeds"
  fi
  # heartbeats with counters on every idea
  hb="$(jq_py "$D/story.json" '[i["heartbeats"] for i in d["ideas"]]')"
  if [ "$mode" = fake ]; then
    assert_true "$mode: every idea has heartbeat lines ($hb)" python -c 'import json, sys; assert all(n > 0 for n in json.loads(sys.argv[1]))' "$hb"
  else
    assert_true "$mode: every idea that ran past 5 minutes has heartbeat lines ($hb)" python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for i in d["ideas"]:
    long = any(s["seconds"] >= 330 for s in i["steps"]) or i["outcome"] == "done"
    assert not long or i["heartbeats"] > 0, i["run"]' "$D/story.json"
  fi
  assert_true "$mode: every idea that passed the gate has its GATE line and its stage STEPs" python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for i in d["ideas"]:
    acts = [s["activity"] for s in i["steps"]]
    if i["outcome"] == "done":
        assert i["gate"] and i["gate"].startswith("passed"), i["run"]
        assert "writing caption" in acts, (i["run"], acts)
        if not i["resumed"]:
            assert acts[:3] == ["researching facts", "expanding idea", "checking idea (gate)"], acts[:3]' "$D/story.json"
  # the outcomes on disk
  local nexp
  nexp="$(jq_py "$D/story.json" 'len(d["exports"])')"
  assert_eq "$(ls "$S/exports" 2>/dev/null | sort -n | paste -sd' ')" "$(seq 1 "$nexp" 2>/dev/null | paste -sd' ')" "$mode: exports/ numbered 1 to $nexp without gaps"
  local n ok_files=1
  for n in $(seq 1 "$nexp"); do
    [ -s "$S/exports/$n/$n.mp4" ] && [ -s "$S/exports/$n/${n}captions.txt" ] || ok_files=0
    [ "$mode" = real ] && { [ -s "$S/exports/$n/${n}hook2.mp4" ] || ok_files=0; }
  done
  assert_eq "$ok_files" "1" "$mode: every export has its N.mp4 and Ncaptions.txt$([ "$mode" = real ] && echo " and Nhook2.mp4")"
  assert_eq "$(grep -c . "$S/logs/history.txt")" "3" "$mode: history.txt has one line per idea"
  assert_eq "$(grep -c -E '\| (exported [0-9]+|dropped: .+|blocked: .+)$' "$S/logs/history.txt")" "3" "$mode: each history line says exported N, dropped or blocked with a reason"
  assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "$mode: ideas.txt is empty"
  assert_no_file "$S/logs/STOPPED.md" "$mode: no logs/STOPPED.md"
  # status.txt at every sampled moment, and at the end
  python "$LOGCHECK" samples "$D/samples.txt" > "$D/samples.out" 2>&1; rc=$?
  assert_rc 0 $rc "$mode: status.txt was a valid status line at every sampled moment ($(cat "$D/samples.out"))"
  assert_rc 0 "$(python "$LOGCHECK" status "$S/logs/status.txt" >/dev/null 2>&1; echo $?)" "$mode: the final status.txt is valid"
  assert_eq "$(ls -a "$S/logs" | grep -c '^\.status\.')" "0" "$mode: no .status.* file left behind"
  assert_grep "${ts_regex}IDLE   no ideas in ideas.txt, checking every 2 s \(idle 0 min\) \| today: [0-9]+ exported, [0-9]+ dropped" "$D/run3.out" "$mode: the forever mode's IDLE line"
  assert_grep "${ts_regex}INFO   stopped by the user \(TERM\)$" "$D/run3.out" "$mode: the forever mode's stop line"
  assert_grep "${ts_regex}IDLE   queue empty: this session 0 exported, 0 dropped, 0 blocked in " "$D/run3.out" "$mode: the summary line on the empty queue"
  no_emdash_in "$mode: no em dash in the exports and the logs" "$S/logs/runner.log" "$S/logs/history.txt" "$S/logs/limits.log" "$S/logs/status.txt" \
    $(ls "$S"/exports/*/*captions.txt 2>/dev/null) $(ls "$S/logs/blocked.txt" 2>/dev/null) "$D/run1.out" "$D/run2.out" "$D/run3.out"
}

if want 2; then
section "2. three ideas unattended with the fake claude: a simulated limit and a kill in the second idea, the restart, the story"
D2="$(mixed "$(mktemp -d)")"
bash "$TESTS_DIR/m13-run.sh" fake "$D2" > "$D2/driver.out" 2>&1
check_multi "$D2" fake
[ -z "${KEEP_SANDBOX:-}" ] && rm -rf "$(cygpath -u "$(sed -n 's/^SANDBOX_M=//p' "$D2/result.env")" 2>/dev/null)" "$D2" 2>/dev/null
fi

if want 3; then
section "3. three ideas unattended with the real models and engines (several hours)"
D3="${M13_REAL_DIR:-}"
if [ -z "$D3" ]; then
  D3="$REPO_DIR/build/M13/real"
  bash "$TESTS_DIR/m13-run.sh" real "$D3" > "$D3.driver.out" 2>&1
fi
check_multi "$D3" real
fi

# ----------------------------------------------------------------------------------------------------------------
if want 4; then
section "4. no em dash in the files M13 wrote"
no_emdash_in "no em dash in the M13 sources, tests and fixtures" pipeline/lib/logcheck.py pipeline/bin/doctor pipeline/lib/ai.sh \
  pipeline/lib/log.sh pipeline/lib/status.sh pipeline/lib/runner.sh pipeline/lib/voiceprofile.py pipeline/bin/build-voice-profile \
  pipeline/bin/runner-status pipeline/tests/test-m13.sh pipeline/tests/m13-run.sh pipeline/tests/fixtures/ideas/three-ideas.txt config.json
fi

test_summary
