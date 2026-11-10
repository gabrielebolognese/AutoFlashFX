#!/usr/bin/env bash
# test-m20.sh: acceptance test for M20 (Formats and the timeline; BUILD_SPEC.md 14.7, 14.8, the format keys of 14.4, 14.12; PLAN.md M20).
#   bash pipeline/tests/test-m20.sh                      every section (about 25 minutes; no model call)
#   M20_SECTIONS="1 2" bash pipeline/tests/test-m20.sh   some sections
#   M20_RECORD=1 bash pipeline/tests/test-m20.sh         section 6 also records build/M20/fingerprint/
# Sections:
#   1. formats: format.json and its schema (planted faults), the stage table and the order of today's stages plus the timeline, session
#      groups and reopen routes (state.py enforces them), the resolved config equals the config before the keys moved, preflight rows
#   2. the timeline of the frozen test-idea run: timeline.json validates, lasts as long as final.mp4 within 1 frame, check.py finds every
#      word, cue and composition layer, planted faults are found; the timeline stage through the runner; a finished real run folder
#   3. the footage-dummy channel end to end with its 3 clips: the export lasts as long as its timeline within 1 frame and its captions
#      appear where the timeline says (sampled frames); new-channel from the format's template
#   4. a format.json with a stage removed or moved changes the runner's order in dummy mode, with no code change
#   5. test-isolation.sh part 1: no FlashFX name in a shared stage (and a planted name is found); the review prompt's rules come from the format
#   6. the dummy fingerprint of flashfx equals build/M19/fingerprint/ plus the timeline/ folder
#   7. the earlier tests that M20 touched (state, config, isolation) still pass
#   8. no em dash in the files M20 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M20_SECTIONS:-1 2 3 4 5 6 7 8}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
T="$(mktemp -d)"
m20_cleanup() { rm -rf "$T" 2>/dev/null || { sleep 2; rm -rf "$T" 2>/dev/null; }; tests_cleanup; }
trap m20_cleanup EXIT
TM="$(mixed "$T")"
PT="$TESTS_DIR"
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
FORMATS_PY="$REPO_DIR/pipeline/lib/formats.py"
TL="$REPO_DIR/pipeline/lib/timeline"
FROZEN="$FIXTURES/runs/test-idea"
export NO_COLOR=1
export PYTHONUTF8=1
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
export REELS_SFX_DIR="$(mixed "$REPO_DIR/channels/flashfx/styles/sfx")" REELS_SFX_NO_BUILD=1
# no section may reach the real model: a stage that fails goes to the error reviewer and its fixer (BUILD_SPEC.md 4.2), which here are the fake claude
fake_claude_on
export FAKE_CLAUDE_REVIEW=no

jf() { python -c 'import json, sys; d = json.loads(sys.argv[1]); v = d.get(sys.argv[2], ""); print(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict, bool)) else v)' "$1" "$2"; }
jget() { python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig"))
for k in sys.argv[2].split("."):
    d = (d[int(k)] if isinstance(d, list) else d.get(k)) if isinstance(d, (dict, list)) else None
print(json.dumps(d) if isinstance(d, (list, dict, bool)) else ("" if d is None else d))' "$1" "$2"; }
run_ch() {  # run_ch <channel> <outfile> [env...]: the real run.sh against $SANDBOX for one channel, --once
  local ch="$1" out="$2"; shift 2
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 1500 bash "$REPO_DIR/run.sh" --channel "$ch" --once --allow-disabled ) > "$out" 2>&1
}
tree() {  # tree <dir>: relative paths, a trailing slash on folders, sorted, the run stamp replaced
  (cd "$1" 2>/dev/null && find . -mindepth 1 | sed 's#^\./##' | while IFS= read -r p; do if [ -d "$p" ]; then echo "$p/"; else echo "$p"; fi; done) \
    | sed -E 's/20[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{4}/<ts>/g' | LC_ALL=C sort
}
TEST_IDEA="$(tr -d '\r' < "$FROZEN/idea.txt")"
OLD_STAGES="01-research,02-expansion,03-gate,04-angle,05-hooks,06-judge,07-script,08-voiceover,09a-animations,09b-text,09c-transitions,10-build,11-sfx,12-review,13-render"

seed_run() {  # seed_run: a run in the sandbox with S1 to S12 done from the frozen outputs and S13 done with a final.mp4 made from the frozen draft and voice; prints the run dir
  local id created rd st
  printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/channels/flashfx/ideas.txt"
  id="$(printf '%s' "$TEST_IDEA" | python pipeline/lib/ideas.py id)"
  created="$(printf '%s' "$TEST_IDEA" | python "$STATE_PY" new --runs "$SANDBOX_M/channels/flashfx/runs" --id "$id")"
  rd="$(jf "$created" run_dir)"
  for st in 01-research 02-expansion 03-gate 05-hooks 06-judge 07-script 08-voiceover 09a-animations 09b-text 09c-transitions 10-build 11-sfx 12-review; do
    cp -r "$FROZEN/$st/." "$rd/$st/"
    python "$STATE_PY" stage-start "$rd" "$st" >/dev/null
    python "$STATE_PY" stage-done "$rd" "$st" --schemas "$REPO_DIR/pipeline/stages" >/dev/null || printf 'seed_run: the frozen %s did not validate\n' "$st" >&2
  done
  env REELS_DUMMY_SECONDS=0 bash pipeline/stages/13-render/dummy.sh "$rd" >/dev/null 2>&1
  ffmpeg -loglevel error -y -i "$rd/10-build/draft.mp4" -i "$rd/08-voiceover/vo.wav" -map 0:v -map 1:a -c:v copy -c:a aac -ar 48000 "$rd/13-render/final.mp4"
  python "$STATE_PY" stage-start "$rd" 13-render >/dev/null
  python "$STATE_PY" stage-done "$rd" 13-render --schemas "$REPO_DIR/pipeline/stages" >/dev/null || printf 'seed_run: 13-render did not validate\n' >&2
  printf '%s' "$rd"
}

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. formats: format.json, the stage table, the routes, the resolved config"
out="$(python "$FORMATS_PY" validate 2>&1)"; rc=$?
assert_rc 0 "$rc" "formats.py validate: every format validates ($out)"
assert_eq "$(python "$FORMATS_PY" list | paste -sd,)" "problem-solution-reel,footage-dummy" "the formats found: problem-solution-reel and the test-only footage-dummy"
assert_eq "$(python "$STATE_PY" stages | cut -f1 | paste -sd,)" "$OLD_STAGES,timeline,14-export" "the stage table of problem-solution-reel: today's S1 to S13 in today's order, then timeline, then S14"
assert_eq "$(python "$STATE_PY" stages | awk -F'\t' '$1 == "04-angle" {print $5}')" "skipped" "04-angle starts skipped"
assert_eq "$(python "$STATE_PY" stages | awk -F'\t' '$1 == "timeline" {print $2 "|" $3 "|" $4}')" "TL|building timeline|timeline.json" "the timeline stage: label, activity and output"
missing=""
for st in $(python "$STATE_PY" stages | cut -f1); do d="$(python "$FORMATS_PY" stage-dir "$st")"; for f in run.sh dummy.sh schema.json CONTRACT.md; do [ -f "$d/$f" ] || missing="$missing $st/$f"; done; done
assert_eq "${missing:-none}" "none" "every stage of the format has run.sh, dummy.sh, schema.json and CONTRACT.md"
assert_eq "$(python "$FORMATS_PY" session 01-research)$(python "$FORMATS_PY" session 02-expansion)$(python "$FORMATS_PY" session 04-angle)$(python "$FORMATS_PY" session 05-hooks)" "AAAA" "session A is S1, S2, S4 and S5"
assert_eq "$(python "$FORMATS_PY" session 03-gate)$(python "$FORMATS_PY" session 07-script)" "" "the gate and the script stage are fresh sessions (no group)"
assert_eq "$(python "$FORMATS_PY" routes 03-gate | paste -sd,)|$(python "$FORMATS_PY" routes 04-angle | paste -sd,)" "04-angle|03-gate" "the reopen routes of the gate and the angle loop"
assert_eq "$(python "$FORMATS_PY" routes 12-review | paste -sd,)" "08-voiceover,09a-animations,09b-text,09c-transitions,10-build,11-sfx,12-review" "the reopen routes of the review"
assert_eq "$(python -c 'import sys; sys.path.insert(0, "pipeline/lib"); from review import common as rc; print(",".join(rc.STAGE_ORDER))')" "08-voiceover,09a-animations,09b-text,09c-transitions,10-build,11-sfx,12-review" "the review's stage order is the format's routes, not a list of its own"
assert_eq "$(cmp -s pipeline/stages/timeline/schema.json pipeline/schemas/timeline.schema.json && echo same)" "same" "the timeline stage's schema.json is pipeline/schemas/timeline.schema.json"

# planted faults in a format
FD="$T/formats"; mkdir -p "$FD"
plant() {  # plant <name> <python statement on d>: a copy of problem-solution-reel's format.json changed by the statement
  mkdir -p "$FD/$1"
  python - "$REPO_DIR/pipeline/formats/problem-solution-reel/format.json" "$TM/formats/$1/format.json" "$2" "$1" "$(mixed "$REPO_DIR")" <<'PYEOF'
import json, sys
src, dst, stmt, name = sys.argv[1:5]
d = json.load(open(src, encoding="utf-8"))
d["id"] = name
d["template"] = sys.argv[5] + "/pipeline/formats/problem-solution-reel/template"
exec(stmt)
json.dump(d, open(dst, "w", encoding="utf-8", newline="\n"), indent=2)
PYEOF
}
bad_format() {  # bad_format <name> <statement> <expected message part>
  plant "$1" "$2"
  out="$(REELS_FORMATS_DIR="$TM/formats" python "$FORMATS_PY" validate "$1" 2>&1)"; rc=$?
  if [ "$rc" = 1 ] && printf '%s' "$out" | grep -q -- "$3"; then pass "format.json refused: $1 ($3)"; else fail "format.json not refused: $1 (rc $rc: $out)"; fi
}
plant psrok 'pass'
out="$(REELS_FORMATS_DIR="$TM/formats" python "$FORMATS_PY" validate psrok 2>&1)"; rc=$?
assert_rc 0 "$rc" "a copy of problem-solution-reel under another id validates ($out)"
bad_format dupstage 'd["stages"].append(dict(d["stages"][0]))' "appears twice"
bad_format badroute 'd["stages"][2]["reopen"] = ["nope-stage"]' "which is not a stage of the format"
bad_format nofolder 'd["stages"][0]["folder"] = "no-such-folder"' "has no folder"
bad_format badfamily 'd["family"] = "magic"' "family"
bad_format nosession 'd["stages"][0]["session"] = "Z"' "session group 'Z'"
bad_format nostages 'd["stages"] = []' "stages"
bad_format badinitial 'd["stages"][0]["initial"] = "done"' "initial"

# the keys that moved: the resolved config equals the config before M20, and config.json keeps no format key
python - "$REPO_DIR" <<'PYEOF' > "$T/keys.txt"
import json, os, subprocess, sys, tempfile
repo = sys.argv[1]
os.environ["REELS_CHANNEL"] = "flashfx"
sys.path.insert(0, repo + "/pipeline/lib")
import config
res = config.load()
before = json.load(open(repo + "/build/M20/format-keys-before.json", encoding="utf-8"))
for k, v in before.items():
    got = res.get(k)
    if k == "review":
        got = {kk: vv for kk, vv in (got or {}).items() if kk not in ("branding", "reviewer_tools", "fixer_tools", "fixer_paths", "protected_paths")}
    print(("same" if got == v else "DIFF") + " " + k)
eng = json.load(open(repo + "/config.json", encoding="utf-8"))
left = [k for k in ("research", "hooks", "judge", "script", "visual", "caption") if k in eng]
print("engine-left " + (",".join(left) or "none"))
print("engine-review " + ",".join(sorted(eng["review"].keys())))
print("engine-preflight-files " + ",".join(sorted((c.get("path") or c["check"]) for c in eng["preflight"]["require"] if c["check"] in ("file", "brand", "fill_in", "voice"))))
PYEOF
assert_eq "$(grep -c '^same ' "$T/keys.txt")" "7" "the resolved config's research, hooks, judge, script, visual, caption and review equal the config before the keys moved"
assert_eq "$(grep -c '^DIFF' "$T/keys.txt")" "0" "no format key differs"
assert_eq "$(grep '^engine-left' "$T/keys.txt")" "engine-left none" "config.json holds no research, hooks, judge, script, visual or caption key any more"
assert_eq "$(grep '^engine-review' "$T/keys.txt")" "engine-review fixer_paths,fixer_tools,protected_paths,reviewer_tools" "config.json's review block keeps only the four safety keys"
assert_eq "$(grep '^engine-preflight-files' "$T/keys.txt")" "engine-preflight-files node_modules/hyperframes/package.json" "config.json's preflight keeps no channel file check (they are the format's required_files)"
assert_eq "$(python "$FORMATS_PY" get required_files | python -c 'import json, sys; print(len(json.load(sys.stdin)))')" "10" "the format lists 10 required checks (the voice, the sound map, the style files, the catalog, the brand kit, hooks, fill_in)"
rm -rf "$SANDBOX_M"/channels/flashfx/.cache 2>/dev/null
assert_true "preflight --channel flashfx reads the required files from the format and passes" bash -c "bash '$REPO_DIR/pipeline/bin/preflight' --channel flashfx 2>&1 | grep -q 'READY  preflight ok: 8 tools, 2 python packages, 9 files'"

# the safety keys cannot move into a format, and a channel keeps its overrides
sandbox_init
python - "$SANDBOX_CH_M/channel.json" <<'PYEOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8"))
d.setdefault("config", {}).setdefault("visual", {})["max_same_in_a_row"] = 7
json.dump(d, open(p, "w", encoding="utf-8", newline="\n"), indent=2)
PYEOF
assert_eq "$(python -c 'import json, sys; print(json.load(open(sys.argv[1]))["visual"]["max_same_in_a_row"])' "$(resolved_config)")" "7" "the channel's config block is merged after the format's"
# state.py enforces the reopen routes of the format
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/channels/flashfx/ideas.txt"
id="$(printf '%s' "$TEST_IDEA" | python pipeline/lib/ideas.py id)"
created="$(printf '%s' "$TEST_IDEA" | python "$STATE_PY" new --runs "$SANDBOX_M/channels/flashfx/runs" --id "$id")"; rd="$(jf "$created" run_dir)"
assert_eq "$(jget "$rd/state.json" format)" "problem-solution-reel" "a new run records its format in state.json"
assert_eq "$(python -c 'import json, sys; print(",".join(json.load(open(sys.argv[1]))["stage_order"]))' "$rd/state.json")" "$OLD_STAGES,timeline,14-export" "a new run's stage_order is the format's"
for st in 01-research 02-expansion 03-gate; do cp -r "$FROZEN/$st/." "$rd/$st/"; python "$STATE_PY" stage-start "$rd" "$st" >/dev/null; python "$STATE_PY" stage-done "$rd" "$st" --schemas "$REPO_DIR/pipeline/stages" >/dev/null; done
python "$STATE_PY" stage-start "$rd" 03-gate >/dev/null; printf '04-angle\n' > "$rd/03-gate/reopen.txt"
res="$(python "$STATE_PY" stage-done "$rd" 03-gate --schemas "$REPO_DIR/pipeline/stages" 2>"$T/route1.err")"
assert_eq "$(jf "$res" reopened)" '["04-angle"]' "the gate may reopen 04-angle (a route of the format)"
python "$STATE_PY" stage-start "$rd" 03-gate >/dev/null; printf '09a-animations\n' > "$rd/03-gate/reopen.txt"
res="$(python "$STATE_PY" stage-done "$rd" 03-gate --schemas "$REPO_DIR/pipeline/stages" 2>"$T/route2.err")"
assert_eq "$(jf "$res" reopened)" '[]' "the gate may not reopen 09a-animations (not a route of the gate in the format)"
assert_grep "not one of the reopen routes of 03-gate" "$T/route2.err" "state.py says so"
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. the timeline of the frozen test-idea run"
sandbox_init
fast_mode
RD="$(seed_run)"
assert_file "$RD/13-render/final.mp4" "a run with S1 to S13 done and a final.mp4"
out="$(python "$TL" build --run-dir "$RD" --format problem-solution-reel --channel flashfx 2>&1)"; rc=$?
assert_rc 0 "$rc" "timeline build exits 0 ($(printf '%s' "$out" | tail -n 1))"
assert_file "$RD/timeline/timeline.json" "timeline/timeline.json"
out="$(python "$TL" validate "$RD/timeline/timeline.json" 2>&1)"; rc=$?
assert_rc 0 "$rc" "timeline.json validates against pipeline/schemas/timeline.schema.json ($out)"
out="$(python "$TL" check --run-dir "$RD" 2>&1)"; rc=$?
assert_rc 0 "$rc" "check.py: no failure ($(printf '%s' "$out" | tail -n 1))"
for c in schema sources duration layers composition plan_components words captions cues markers; do assert_grep "^ok   $c:" <(printf '%s\n' "$out") "check.py reports $c ok"; done
python - "$RD" > "$T/tl-facts.txt" <<'PYEOF'
import json, re, subprocess, sys
rd = sys.argv[1]
t = json.load(open(rd + "/timeline/timeline.json", encoding="utf-8"))
words = json.load(open(rd + "/08-voiceover/words.json", encoding="utf-8"))
cues = json.load(open(rd + "/11-sfx/cues.json", encoding="utf-8"))
html = open(rd + "/10-build/project/index.html", encoding="utf-8").read()
probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", rd + "/13-render/final.mp4"], capture_output=True, text=True).stdout.strip()
fps = t["settings"]["fps"]["num"] / t["settings"]["fps"]["den"]
print("frames-diff", round(abs(float(probe) * fps - t["settings"]["duration_frames"]), 3))
print("words", len(t["audio"]["voice"]["words"]), len(words["words"]))
print("cues", len(t["audio"]["sfx"]), len(cues["cues"]))
print("hosts", sum(1 for l in t["layers"] if l.get("selector")), len(re.findall(r'<div id="[^"]+" class="clip"', html)))
print("kinds", ",".join(sorted({l["kind"] for l in t["layers"]})))
print("settings", t["settings"]["width"], t["settings"]["height"], t["settings"]["fps"]["num"], t["settings"]["sample_rate"])
print("markers", ",".join(sorted({m["kind"] for m in t["markers"]})))
print("caption-style", t["captions"]["style"], len(t["captions"]["chunks"]))
print("provenance", all(l.get("provenance") for l in t["layers"]))
print("components", all(l.get("component") and l.get("selector") for l in t["layers"]))
PYEOF
assert_true "the timeline lasts as long as final.mp4 within 1 frame ($(grep '^frames-diff' "$T/tl-facts.txt"))" python -c 'import sys; sys.exit(0 if float(sys.argv[1]) <= 1.0 else 1)' "$(grep '^frames-diff' "$T/tl-facts.txt" | cut -d' ' -f2)"
assert_eq "$(grep '^words' "$T/tl-facts.txt" | cut -d' ' -f2)" "$(grep '^words' "$T/tl-facts.txt" | cut -d' ' -f3)" "every word of words.json is in the timeline ($(grep '^words' "$T/tl-facts.txt" | cut -d' ' -f3) words)"
assert_eq "$(grep '^cues' "$T/tl-facts.txt" | cut -d' ' -f2)" "$(grep '^cues' "$T/tl-facts.txt" | cut -d' ' -f3)" "every sound of cues.json is in the timeline ($(grep '^cues' "$T/tl-facts.txt" | cut -d' ' -f3) sounds)"
assert_eq "$(grep '^hosts' "$T/tl-facts.txt" | cut -d' ' -f2)" "$(grep '^hosts' "$T/tl-facts.txt" | cut -d' ' -f3)" "one composition layer per host of the composition ($(grep '^hosts' "$T/tl-facts.txt" | cut -d' ' -f3))"
assert_eq "$(grep '^kinds' "$T/tl-facts.txt")" "kinds caption-burn,composition-scene" "the layers are composition-scene layers and the caption-burn layer"
assert_eq "$(grep '^settings' "$T/tl-facts.txt")" "settings 540 960 30 48000" "settings: the size and rate of the rendered video"
assert_eq "$(grep '^markers' "$T/tl-facts.txt")" "markers beat,end-card,hook-end,keyword,scene" "markers: scenes, beats, the hook end, the end card and the keyword moment"
assert_eq "$(grep '^provenance' "$T/tl-facts.txt")" "provenance True" "every layer names the stage that produced it"
assert_eq "$(grep '^components' "$T/tl-facts.txt")" "components True" "every layer has its selector and its component id in the motion library"

# planted faults: each is found by the check it belongs to, on a copy
fault() {  # fault <name> <expected failing check> <python statement on t (the timeline) and rd>
  local c="$T/fault-$1"; rm -rf "$c"; mkdir -p "$c"; cp -r "$RD/." "$c/"
  python - "$c" "$3" <<'PYEOF'
import json, sys
rd, stmt = sys.argv[1:3]
p = rd + "/timeline/timeline.json"
t = json.load(open(p, encoding="utf-8"))
exec(stmt)
json.dump(t, open(p, "w", encoding="utf-8", newline="\n"), indent=2)
PYEOF
  out="$(python "$TL" check --run-dir "$c" 2>&1)"; rc=$?
  if [ "$rc" = 1 ] && printf '%s' "$out" | grep -q "^FAIL $2:"; then pass "a planted fault is found: $1 (check $2)"; else fail "planted fault not found: $1 (rc $rc, wanted FAIL $2: $(printf '%s' "$out" | grep -E '^(FAIL|timeline check)' | head -n 3 | tr '\n' ' '))"; fi
}
fault word-moved words 't["audio"]["voice"]["words"][5]["start_ms"] += 400'
fault word-lost words 'del t["audio"]["voice"]["words"][7]'
fault cue-moved cues 't["audio"]["sfx"][2]["start_ms"] += 250'
fault cue-lost cues 'del t["audio"]["sfx"][0]'
fault layer-lost composition 'del t["layers"][4]'
fault layer-selector composition 't["layers"][3]["selector"] = "#not-a-host"'
fault duration duration 't["settings"]["duration_frames"] += 9'
fault caption-off captions 't["captions"]["chunks"][3]["words"][0]["start_ms"] += 333'
fault source-changed sources 't["sources"][0]["sha256"] = "0" * 64'
fault schema-version schema 't["version"] = 2'
c="$T/fault-final"; rm -rf "$c"; mkdir -p "$c"; cp -r "$RD/." "$c/"
ffmpeg -loglevel error -y -i "$c/13-render/final.mp4" -t 30 -c copy "$c/13-render/short.mp4" && mv "$c/13-render/short.mp4" "$c/13-render/final.mp4"
out="$(python "$TL" check --run-dir "$c" --no-hash 2>&1)"; rc=$?
if [ "$rc" = 1 ] && printf '%s' "$out" | grep -q "^FAIL duration:"; then pass "a planted fault is found: a final.mp4 11 s shorter than its timeline (check duration)"; else fail "a shorter final.mp4 is not found (rc $rc: $out)"; fi

# the timeline stage through the runner: S1 to S13 done, the timeline stage real, S14 dummy
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=14-export timeout 900 bash "$REPO_DIR/run.sh" --channel flashfx --once ) > "$T/stage.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the runner runs the real timeline stage after S13 and exits 0"
assert_grep "${ts_regex}STEP   building timeline done \([0-9]+s\) -> " "$T/stage.out" "the STEP line of the timeline stage"
assert_grep "${ts_regex}DONE   exported flashfx-1 -> exports/flashfx-1/" "$T/stage.out" "the run is exported after the timeline"
assert_file "$(ls -d "$SANDBOX"/channels/flashfx/runs/*/ | head -n 1)timeline/timeline.json" "the run folder keeps timeline/timeline.json after the export"
assert_file "$(ls -d "$SANDBOX"/channels/flashfx/runs/*/ | head -n 1)timeline/check.json" "and timeline/check.json"
sandbox_cleanup

# a finished real run folder of the channel, when one exists (the M12 and M13 runs were made in temporary roots, so usually none)
n=0; bad=""
for r in "$REPO_DIR"/channels/*/runs/*/; do
  [ -f "$r/13-render/final.mp4" ] && [ -f "$r/09c-transitions/merged.json" ] || continue
  n=$((n + 1)); c="$T/real-$n"; mkdir -p "$c"; cp -r "$r/." "$c/"
  python "$TL" build --run-dir "$c" --channel "$(basename "$(dirname "$(dirname "$r")")")" >/dev/null 2>&1 && python "$TL" check --run-dir "$c" >/dev/null 2>&1 || bad="$bad $(basename "$r")"
done
assert_eq "${bad:-none}" "none" "a copy of every finished real run folder of the channels gets a timeline with no check failure ($n found)"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. the footage-dummy channel end to end"
sandbox_init
fast_mode
mkdir -p "$T/clips"
mkclip() {  # mkclip <name> <color> <size> <fps> <seconds> <tone Hz>
  ffmpeg -loglevel error -y -f lavfi -i "color=c=$2:s=$3:r=$4:d=$5" -f lavfi -i "sine=frequency=$6:duration=$5:sample_rate=44100" -c:v libx264 -pix_fmt yuv420p -preset ultrafast -c:a aac -shortest "$T/clips/$1.mp4"
}
mkclip clip1 0x1a2a6c 1280x720 25 3 330
mkclip clip2 0x14532d 720x1280 30 3 440
mkclip clip3 0x7f1d1d 1920x1080 24 4 550
assert_eq "$(ls "$T/clips" | paste -sd,)" "clip1.mp4,clip2.mp4,clip3.mp4" "the 3 fixture clips (other sizes and rates than the timeline's 1080x1920 at 30 fps)"
out="$(bash pipeline/bin/new-channel footageone --format footage-dummy --platform instagram-reels --name "Footageone" 2>&1)"; rc=$?
assert_rc 0 "$rc" "new-channel --format footage-dummy creates the channel from the format's template ($(printf '%s' "$out" | head -n 1))"
assert_file "$SANDBOX/channels/footageone/channel.json" "channels/footageone/channel.json"
assert_eq "$(jget "$SANDBOX/channels/footageone/channel.json" enabled)" "false" "the new channel starts disabled"
assert_eq "$(jget "$SANDBOX/channels/footageone/channel.json" format)" "footage-dummy" "its format is footage-dummy"
out="$(bash pipeline/bin/preflight --channel footageone 2>&1)"; rc=$?
assert_true "preflight --channel footageone names the missing clip (the format's required file) and stops that channel only" bash -c "! bash '$REPO_DIR/pipeline/bin/preflight' --channel footageone >/dev/null 2>&1 && grep -q 'footage/clip1.mp4' '$SANDBOX/channels/footageone/logs/STOPPED.md'"
cp "$T"/clips/*.mp4 "$SANDBOX/channels/footageone/footage/"
printf '{A test cut of three fixture clips}\n' > "$SANDBOX/channels/footageone/ideas.txt"
run_ch footageone "$T/foot.out"; rc=$?
assert_rc 0 "$rc" "the footage-dummy runner exits 0 ($(tail -n 2 "$T/foot.out" | tr '\n' ' ' | cut -c1-220))"
assert_grep "${ts_regex}DONE   exported footageone-1 -> exports/footageone-1/" "$T/foot.out" "DONE: exported footageone-1"
for s in "ingesting clips" "cutting clips" "rendering timeline" "writing caption"; do assert_grep "${ts_regex}STEP   $s done" "$T/foot.out" "STEP: $s"; done
EX="$SANDBOX/exports/footageone-1"
assert_file "$EX/footageone-1.mp4" "exports/footageone-1/footageone-1.mp4"
assert_file "$EX/footageone-1captions.txt" "footageone-1captions.txt"
assert_file "$EX/footageone-1hook2.mp4" "footageone-1hook2.mp4 (the platform has a hook 2 clip)"
RUN="$(ls -d "$SANDBOX"/channels/footageone/runs/*/ 2>/dev/null | head -n 1)"; RUN="${RUN%/}"
assert_file "$RUN/timeline/timeline.json" "the run keeps timeline/timeline.json (written by the cut stage)"
assert_file "$RUN/timeline-render/final.mp4" "and timeline-render/final.mp4"
python "$TL" validate "$RUN/timeline/timeline.json" > "$T/foot-valid.txt" 2>&1; rc=$?
assert_rc 0 "$rc" "the footage timeline validates against the schema ($(tail -n 1 "$T/foot-valid.txt"))"
python "$TL" check --run-dir "$RUN" > "$T/foot-check.txt" 2>&1; rc=$?
assert_rc 0 "$rc" "check.py passes on the footage timeline ($(tail -n 1 "$T/foot-check.txt"))"
assert_grep "^ok   footage: 3 footage layers, 3 footage audio entries agree" "$T/foot-check.txt" "check.py: 3 footage layers with their audio"
python - "$RUN" "$EX/footageone-1.mp4" > "$T/foot-facts.txt" <<'PYEOF'
import json, subprocess, sys
run, mp4 = sys.argv[1:3]
t = json.load(open(run + "/timeline/timeline.json", encoding="utf-8"))
fps = t["settings"]["fps"]["num"] / t["settings"]["fps"]["den"]
total = t["settings"]["duration_frames"]
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", mp4], capture_output=True, text=True).stdout)
dur = float(pr["format"]["duration"])
v = next(s for s in pr["streams"] if s["codec_type"] == "video")
a = [s for s in pr["streams"] if s["codec_type"] == "audio"]
print("frames-diff", round(abs(dur * fps - total), 3))
print("size", v["width"], v["height"], v["avg_frame_rate"], v["codec_name"], v["pix_fmt"], len(a), a[0]["sample_rate"] if a else "-")
print("layers", len(t["layers"]), total)

def band_white(sec):
    """White-ish pixels in the caption band (y 1280 to 1440) of the frame at sec."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{sec:.3f}", "-i", mp4, "-frames:v", "1", "-vf", "crop=1080:160:0:1280,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    return sum(1 for b in raw if b > 200)

on, off = [], []
for ch in t["captions"]["chunks"]:
    mid = (ch["start_ms"] + ch["end_ms"]) / 2000.0
    on.append(band_white(mid))
    layer = next(l for l in t["layers"] if l["id"] == ch["scene"])
    gap = ch["end_ms"] / 1000.0 + 0.2
    if gap < layer["end"] / fps - 0.05:
        off.append(band_white(gap))
print("on", ",".join(str(x) for x in on))
print("off", ",".join(str(x) for x in off))
PYEOF
assert_true "the export lasts as long as its timeline within 1 frame ($(grep '^frames-diff' "$T/foot-facts.txt"))" python -c 'import sys; sys.exit(0 if float(sys.argv[1]) <= 1.0 else 1)' "$(grep '^frames-diff' "$T/foot-facts.txt" | cut -d' ' -f2)"
assert_eq "$(grep '^size' "$T/foot-facts.txt")" "size 1080 1920 30/1 h264 yuv420p 1 48000" "the export is 1080x1920 at 30 fps, H.264, yuv420p, one audio stream at 48 kHz"
assert_eq "$(grep '^layers' "$T/foot-facts.txt" | cut -d' ' -f2)" "3" "the timeline has the 3 clips as footage layers"
assert_true "the captions appear where the timeline says: every chunk's middle frame shows text ($(grep '^on' "$T/foot-facts.txt"))" python -c 'import sys; v = [int(x) for x in sys.argv[1].split(",") if x]; sys.exit(0 if len(v) == 3 and min(v) > 400 else 1)' "$(grep '^on' "$T/foot-facts.txt" | cut -d' ' -f2)"
assert_true "and where it says there is none: the frames after each chunk show no text ($(grep '^off' "$T/foot-facts.txt"))" python -c 'import sys; v = [int(x) for x in sys.argv[1].split(",") if x]; sys.exit(0 if len(v) == 3 and max(v) < 20 else 1)' "$(grep '^off' "$T/foot-facts.txt" | cut -d' ' -f2)"
assert_grep "^CAPTION$" "$EX/footageone-1captions.txt" "the captions file has its sections (the platform's exporter ran for the footage format)"
assert_eq "$(find "$SANDBOX/.locks" "$SANDBOX/channels/footageone/.locks" -mindepth 1 2>/dev/null | wc -l | tr -d ' ')" "0" "no lock is left behind"
# a clip that disappears after the cut: the timeline check refuses to render it
mv "$SANDBOX/channels/footageone/footage/clip2.mp4" "$SANDBOX/channels/footageone/footage/clip2.gone"
python "$TL" check --run-dir "$RUN" > "$T/foot-gone.txt" 2>&1; rc=$?
assert_true "check.py names a missing clip (sources) and fails" bash -c "[ $rc = 1 ] && grep -q '^FAIL sources:' '$T/foot-gone.txt'"
mv "$SANDBOX/channels/footageone/footage/clip2.gone" "$SANDBOX/channels/footageone/footage/clip2.mp4"
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 4; then
section "4. a format.json with a stage removed or moved changes the runner's order"
sandbox_init
fast_mode
FD="$T/formats4"; mkdir -p "$FD"
plant_into() {  # plant_into <dir> <name> <statement>
  mkdir -p "$1/$2"
  python - "$REPO_DIR/pipeline/formats/problem-solution-reel/format.json" "$(mixed "$1")/$2/format.json" "$3" "$2" "$(mixed "$REPO_DIR")" <<'PYEOF'
import json, sys
src, dst, stmt, name, repo = sys.argv[1:6]
d = json.load(open(src, encoding="utf-8"))
d["id"] = name
d["template"] = repo + "/pipeline/formats/problem-solution-reel/template"
exec(stmt)
json.dump(d, open(dst, "w", encoding="utf-8", newline="\n"), indent=2)
PYEOF
}
# psrvar: 06-judge removed, 11-sfx moved before 10-build, the timeline moved before 13-render
plant_into "$FD" psrvar 'st = {s["id"]: s for s in d["stages"]}; order = [s["id"] for s in d["stages"] if s["id"] not in ("06-judge", "11-sfx", "timeline")]; i = order.index("10-build"); order[i:i] = ["11-sfx"]; j = order.index("13-render"); order[j:j] = ["timeline"]; d["stages"] = [st[k] for k in order]; d["stages"][d["stages"].index(st["12-review"])]["reopen"] = [k for k in st["12-review"]["reopen"] if k in order]'
export REELS_FORMATS_DIR="$(mixed "$FD")"
out="$(python "$FORMATS_PY" validate psrvar 2>&1)"; rc=$?
assert_rc 0 "$rc" "the variant format validates ($out)"
WANT="$(python "$FORMATS_PY" stages --format psrvar | cut -f1 | paste -sd,)"
assert_eq "$WANT" "01-research,02-expansion,03-gate,04-angle,05-hooks,07-script,08-voiceover,09a-animations,09b-text,09c-transitions,11-sfx,10-build,12-review,timeline,13-render,14-export" "the variant's stage table: no judge, the sound before the build, the timeline before the render"
cp -r "$SANDBOX/channels/flashfx" "$SANDBOX/channels/variant"
rm -rf "$SANDBOX/channels/variant/.cache" "$SANDBOX/channels/variant/runs" "$SANDBOX/channels/variant/logs" "$SANDBOX/channels/variant/.locks"; mkdir -p "$SANDBOX/channels/variant/logs"
python - "$SANDBOX_M/channels/variant/channel.json" <<'PYEOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8"))
d.update(id="variant", name="Variant", format="psrvar", enabled=True); d["brand"] = {"display_name": "Variant"}
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
printf '{Idea for the variant format: the order comes from format.json}\n' > "$SANDBOX/channels/variant/ideas.txt"
printf '{Idea for the plain format: the order comes from format.json}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
run_ch variant "$T/var.out" REELS_DUMMY=all REELS_DUMMY_SECONDS=0.1; rc=$?
assert_rc 0 "$rc" "the variant channel's dummy run exits 0 ($(tail -n 1 "$T/var.out" | cut -c1-160))"
VR="$(ls -d "$SANDBOX"/channels/variant/runs/*/ | head -n 1)"; VR="${VR%/}"
assert_eq "$(python -c 'import json, sys; print(",".join(json.load(open(sys.argv[1]))["stage_order"]))' "$VR/state.json")" "$WANT" "the run's stage_order is the variant's"
assert_eq "$(jget "$VR/state.json" format)" "psrvar" "the run records the variant format"
assert_no_file "$VR/06-judge" "no folder for the removed stage"
GOT="$(grep -E "${ts_regex}STEP   " "$T/var.out" | sed -E 's/^\[[0-9:]+\] STEP   //; s/ done \(.*$//' | paste -sd'|')"
EXPECT="$(python - "$WANT" <<'PYEOF'
import json, subprocess, sys
want = sys.argv[1].split(",")
act = {}
for line in subprocess.run([sys.executable, "pipeline/lib/formats.py", "stages", "--format", "psrvar"], capture_output=True, text=True).stdout.splitlines():
    k, label, activity, output, initial, folder = line.split("\t")
    act[k] = (activity, initial)
print("|".join(act[k][0] for k in want if act[k][1] != "skipped"))
PYEOF
)"
assert_eq "$(printf '%s' "$GOT" | sed -E 's/\|(exporting #[0-9]+|finishing)//g')" "$EXPECT" "the STEP lines come in the variant's order (the activities of its stages)"
assert_true "the first STEP is 01-research's and the last stage run is the export" bash -c "printf '%s' '$GOT' | grep -q '^researching facts' && grep -q 'DONE   exported variant-1' '$T/var.out'"
# the same machine with the plain format: today's order
run_ch flashfx "$T/plain.out" REELS_DUMMY=all REELS_DUMMY_SECONDS=0.1; rc=$?
assert_rc 0 "$rc" "the plain format's dummy run exits 0"
PR="$(ls -d "$SANDBOX"/channels/flashfx/runs/*/ | head -n 1)"; PR="${PR%/}"
assert_eq "$(python -c 'import json, sys; print(",".join(json.load(open(sys.argv[1]))["stage_order"]))' "$PR/state.json")" "$OLD_STAGES,timeline,14-export" "with the same code, problem-solution-reel keeps its own order"
# the group of a removed stage cannot be reopened: a review round naming it is ignored by state.py
unset REELS_FORMATS_DIR
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 5; then
section "5. no FlashFX name in a shared stage; the format's own rules"
out="$(python "$PT/isolation_scan.py" 2>&1)"; rc=$?
assert_rc 0 "$rc" "isolation_scan.py: no literal path and no channel, brand or style name in a shared stage ($(printf '%s' "$out" | tail -n 1))"
ISOLATION_PARTS=1 bash "$PT/test-isolation.sh" > "$T/iso1.out" 2>&1; rc=$?
assert_rc 0 "$rc" "test-isolation.sh part 1 passes ($(tail -n 1 "$T/iso1.out"))"
assert_eq "$(grep -c "FlashFX\|flashfx\|paper-cards" pipeline/stages/12-review/prompt.md pipeline/stages/12-review/model.schema.json pipeline/stages/12-review/run.sh | grep -v ':0' | wc -l | tr -d ' ')" "0" "12-review's prompt, schema and script name no FlashFX"
assert_grep "^\{\{BRAND\}\}|\{\{BRAND\}\}" pipeline/formats/problem-solution-reel/prompts/12-review-rules.md "the format's review rules use {{BRAND}} (the channel's display name), not a name of their own"
assert_eq "$(python pipeline/lib/formats.py prompt 12-review rules | sed 's#.*/pipeline/#pipeline/#')" "pipeline/formats/problem-solution-reel/prompts/12-review-rules.md" "format.json names the review's rules file as a prompt override of 12-review"
sandbox_init
RULES="$T/rules.md"
python pipeline/lib/prompt.py render pipeline/formats/problem-solution-reel/prompts/12-review-rules.md --out "$RULES" --set "BRAND=$(python pipeline/lib/config.py brand)" >/dev/null
assert_grep "^Branding: the CTA always carries the FlashFX DM notification card and the FlashFX lockup; elsewhere FlashFX shows$" "$RULES" "rendered for the flashfx channel, the rules read as they did before M20"
assert_eq "$(python pipeline/lib/config.py brand)" "FlashFX" "config.py brand reads channel.json's brand.display_name"
python - "$SANDBOX_CH_M/channel.json" <<'PYEOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8")); d["brand"]["display_name"] = "Zorbo"
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
assert_eq "$(python -c 'import sys; sys.path.insert(0, "pipeline/lib"); from review import common as rc; import types; c = rc.Ctx.__new__(rc.Ctx); import config; print(config.brand())')" "Zorbo" "another channel of the format gets its own brand name in the review's text"
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 6; then
section "6. the dummy fingerprint of flashfx equals build/M19/fingerprint/ plus the timeline/ folder"
sandbox_init
fast_mode
printf '{Claude Code'"'"'s frontend-design skill: it makes websites built with AI stop looking AI-generated. Show what it does and how to install it.}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
run_ch flashfx "$T/fp.out" REELS_DUMMY=all; rc=$?
assert_rc 0 "$rc" "REELS_DUMMY=all bash run.sh --channel flashfx --once exits 0"
tree "$SANDBOX/channels/flashfx/runs" > "$T/fp-run.txt"
tree "$SANDBOX/exports" > "$T/fp-exports.txt"
FP="$REPO_DIR/build/M20/fingerprint"
if [ -n "${M20_RECORD:-}" ]; then
  mkdir -p "$FP"; cp "$T/fp-run.txt" "$FP/fingerprint-run.txt"; cp "$T/fp-exports.txt" "$FP/fingerprint-exports.txt"; pass "the dummy fingerprint is recorded in build/M20/fingerprint/ (M20_RECORD)"
fi
grep -v '/timeline/' "$T/fp-run.txt" | grep -v '_[a-z0-9-]*/timeline/$' > "$T/fp-run-without.txt"
if cmp -s "$T/fp-run-without.txt" "$REPO_DIR/build/M19/fingerprint/fingerprint-run.txt"; then pass "the run folder tree without timeline/ equals build/M19/fingerprint/ ($(grep -c . "$T/fp-run-without.txt") entries)"
else fail "the run folder tree differs from build/M19/fingerprint/: $(diff "$T/fp-run-without.txt" "$REPO_DIR/build/M19/fingerprint/fingerprint-run.txt" | head -n 6 | tr '\n' ' ')"; fi
assert_eq "$(grep '/timeline' "$T/fp-run.txt" | sed -E 's#^<ts>_[a-z0-9-]*/##' | paste -sd,)" "timeline/,timeline/.done,timeline/.log-offset,timeline/stage.log,timeline/timeline.json" "and the one new folder is timeline/ (.done, .log-offset, stage.log, timeline.json)"
if cmp -s "$T/fp-exports.txt" "$REPO_DIR/build/M19/fingerprint/fingerprint-exports.txt"; then pass "the exports tree equals build/M19/fingerprint/"
else fail "the exports tree differs from build/M19/fingerprint/: $(diff "$T/fp-exports.txt" "$REPO_DIR/build/M19/fingerprint/fingerprint-exports.txt" | head -n 6 | tr '\n' ' ')"; fi
assert_true "the dummy timeline.json validates against the timeline schema" python "$TL" validate "$(ls -d "$SANDBOX"/channels/flashfx/runs/*/ | head -n 1)timeline/timeline.json"
python "$REPO_DIR/pipeline/lib/logcheck.py" story "$SANDBOX/channels/flashfx/logs/runner.log" --no-gate-line --heartbeat 1 > "$T/story.txt" 2>&1; rc=$?
assert_rc 0 "$rc" "the whole terminal story is a valid story: the new activities are in the activity table ($(head -c 200 "$T/story.txt" | tr '
' ' '))"
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 7; then
section "7. earlier tests that M20 touched"
ISOLATION_PARTS="1 2" bash "$PT/test-isolation.sh" > "$T/iso12.out" 2>&1; rc=$?
assert_rc 0 "$rc" "test-isolation.sh, both parts, passes ($(tail -n 1 "$T/iso12.out"))"
bash "$PT/test-no-emdash.sh" > "$T/emdash.out" 2>&1; rc=$?
assert_rc 0 "$rc" "test-no-emdash.sh passes ($(tail -n 1 "$T/emdash.out"))"
M19_SECTIONS="1" bash "$PT/test-m19.sh" > "$T/m19.out" 2>&1; rc=$?
assert_rc 0 "$rc" "test-m19.sh section 1 (numbering, two channels side by side) passes ($(tail -n 1 "$T/m19.out"))"
M18_SECTIONS="1 2" bash "$PT/test-m18.sh" > "$T/m18.out" 2>&1; rc=$?
assert_rc 0 "$rc" "test-m18.sh sections 1 and 2 (channel.json, config, paths) pass ($(tail -n 1 "$T/m18.out"))"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 8; then
section "8. no em dash in the files M20 wrote"
python - "$REPO_DIR" > "$T/emdash-files.txt" <<'PYEOF'
import os, sys
root = sys.argv[1]
files = ["pipeline/lib/formats.py", "pipeline/lib/config.py", "pipeline/lib/state.py", "pipeline/lib/runner.sh", "pipeline/lib/newchannel.py",
         "pipeline/schemas/format.schema.json", "pipeline/schemas/timeline.schema.json", "pipeline/tests/test-m20.sh", "pipeline/tests/isolation_scan.py",
         "config.json", "build/M20/report.md"]
for base in ("pipeline/lib/timeline", "pipeline/stages/timeline", "pipeline/stages/timeline-render", "pipeline/formats", "pipeline/tests/formats", "pipeline/stages/12-review"):
    for dp, dn, fn in os.walk(os.path.join(root, base)):
        files += [os.path.relpath(os.path.join(dp, f), root).replace(chr(92), "/") for f in fn if not f.endswith(".pyc")]
bad = [f for f in files if os.path.isfile(os.path.join(root, f)) and b"\xe2\x80\x94" in open(os.path.join(root, f), "rb").read()]
print("\n".join(bad))
PYEOF
assert_eq "$(grep -c . "$T/emdash-files.txt")" "0" "no em dash in the files M20 added or changed ($(head -n 3 "$T/emdash-files.txt" | tr '\n' ' '))"
fi

test_summary
