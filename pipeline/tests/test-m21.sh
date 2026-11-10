#!/usr/bin/env bash
# test-m21.sh: acceptance test for M21 (Editable project export, S15; BUILD_SPEC.md S15, 14.9, section 8; PLAN.md M21).
#   bash pipeline/tests/test-m21.sh                      every section (about 60 to 90 minutes: renders and captures every frame; no model call)
#   M21_SECTIONS="1 4" bash pipeline/tests/test-m21.sh   some sections
# Sections:
#   1. pure code: the manifest and its capability hash, ease fits and keyframe reduction, the animated WebP frame rule (33, 33, 34 ms: every
#      timeline frame of a 90-frame overlay shows its own frame), the validator's planted faults, the gaps log, CAPABILITIES.md covers every key,
#      cues.json's trim, fade and gain fields, the stage and format entries, the annotations of the motion library
#   2. the frozen test-idea reel with the BASELINE manifest: the project validates, background, voice and every sound are native clips at their
#      times, native text, baked captions plus the hidden native caption track, the layout check passes; duration and mix against the video
#   3. the same reel with manifest-plus.json: cards become native solids, captions native cues (the JSON matches the golden file); the baseline
#      again gives sprites and baked captions
#   4. a forced failure still exports the video with the minimal project and NEEDS REVIEW; the EDITOR section of the captions file; rebuild-project.sh
#   5. the stable editor copy in a scratch repo (accepted batch commits only, a failing build goes back, the server answers)
#   6. the runner's fast mode: a changed manifest between two dummy ideas triggers exactly one capability upgrade, with two runners alive, and a
#      failed upgrade is not retried for the same manifest
#   7. the footage-dummy channel: its project validates, the clips are native video clips and the captions a native caption track
#   8. the time S15 took for the reel (recorded), no em dash in the files M21 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M21_SECTIONS:-1 2 3 4 5 6 7 8}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
T="$(mktemp -d)"
m21_cleanup() { rm -rf "$T" 2>/dev/null || { sleep 2; rm -rf "$T" 2>/dev/null; }; tests_cleanup; }
trap m21_cleanup EXIT
TM="$(mixed "$T")"
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
TL="$REPO_DIR/pipeline/lib/timeline"
S15="$REPO_DIR/pipeline/lib/s15"
HELP="$REPO_DIR/pipeline/tests/m21-helpers.py"
FROZEN="$FIXTURES/runs/test-idea"
export NO_COLOR=1 PYTHONUTF8=1
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
export REELS_SFX_DIR="$(mixed "$REPO_DIR/channels/flashfx/styles/sfx")" REELS_SFX_NO_BUILD=1
export REELS_CHANNEL=flashfx
fake_claude_on
export FAKE_CLAUDE_REVIEW=no
BASE="$REPO_DIR/pipeline/stages/s15-project/baseline-capabilities.json"
PLUS="$REPO_DIR/pipeline/tests/manifest-plus.json"
GOLDEN="$REPO_DIR/pipeline/tests/golden/m21-plus-project.json"

jf() { python -c 'import json, sys; d = json.loads(sys.argv[1]); v = d.get(sys.argv[2], ""); print(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict, bool)) else v)' "$1" "$2"; }
jget() { python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig"))
for k in sys.argv[2].split("."):
    d = (d[int(k)] if isinstance(d, list) else d.get(k)) if isinstance(d, (dict, list)) else None
print(json.dumps(d) if isinstance(d, (list, dict, bool)) else ("" if d is None else d))' "$1" "$2"; }
helper() {  # helper <label> <args...>: m21-helpers.py, each PASS or FAIL line becomes a test result
  local label="$1" line; shift
  python "$HELP" "$@" > "$T/helper.out" 2>&1
  while IFS= read -r line; do
    case "$line" in
      PASS\ *) pass "$label: ${line#PASS }" ;;
      FAIL\ *) fail "$label: ${line#FAIL }" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done < "$T/helper.out"
}
mkrun() {  # mkrun <dir>: a run folder of the frozen test idea with its project rebuilt from the plans, a final.mp4 (the frozen draft and voice) and a timeline
  local rd="$1"
  rm -rf "$rd"; mkdir -p "$rd/13-render"
  cp -r "$FROZEN/." "$rd/"
  python "$TESTS_DIR/materialize-project.py" "$(mixed "$rd")" > /dev/null 2>&1
  ffmpeg -loglevel error -y -i "$rd/10-build/draft.mp4" -i "$rd/08-voiceover/vo.wav" -map 0:v -map 1:a -c:v copy -c:a aac -ar 48000 "$rd/13-render/final.mp4"
  python "$TL" build --run-dir "$(mixed "$rd")" --format problem-solution-reel --channel flashfx > /dev/null 2>&1
}
s15run() {  # s15run <run dir> <manifest> [extra args]: S15 on a run, prints the seconds it took on the last line of $T/s15.out
  local rd="$1" man="$2"; shift 2
  local t0="$EPOCHSECONDS"
  python "$S15" run --run-dir "$(mixed "$rd")" --manifest "$man" --no-parity "$@" > "$T/s15.out" 2>&1
  local rc=$?
  S15_SECONDS=$(( EPOCHSECONDS - t0 ))
  return $rc
}

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. pure code: manifest, eases, WebP rule, validator, gaps, CAPABILITIES.md, cues.json fields"
helper "unit" unit
out="$(python pipeline/lib/formats.py validate 2>&1)"; rc=$?
assert_rc 0 "$rc" "formats.py validate: s15-project is a valid stage of both formats ($out)"
assert_eq "$(python "$STATE_PY" stages | cut -f1 | tail -n 1)" "s15-project" "s15-project is the last stage of problem-solution-reel (after 14-export)"
assert_eq "$(python "$STATE_PY" stages | awk -F'\t' '$1 == "s15-project" {print $2 "|" $3 "|" $4}')" "S15|building editable project|editor.json" "its label, activity and output"
for f in run.sh dummy.sh schema.json CONTRACT.md baseline-capabilities.json CAPABILITIES.md; do assert_file "pipeline/stages/s15-project/$f" "pipeline/stages/s15-project/$f"; done
assert_eq "$(python -c 'import json; d = json.load(open("pipeline/stages/s15-project/baseline-capabilities.json")); print(d["appVersion"], d["lastBatch"], d["schemaVersion"])')" "1.1.0 53 3" "baseline-capabilities.json is the editor v1.1.0 manifest of the spec"
assert_eq "$(python -c 'import json; d = json.load(open("config.json")); e = d["editor"]; print(e["port"], e["url"], e["project"], e["cap_minutes"], e["parity_ssim"])')" "5310 http://localhost:5310/ True 25 0.97" "config.json has the editor block (port 5310, url, project, cap_minutes 25, parity_ssim 0.97)"
out="$(python pipeline/lib/motion/annotations.py 2>&1)"; rc=$?
assert_rc 0 "$rc" "every component of channels/flashfx/motion-lib carries editor annotations ($(printf '%s' "$out" | tail -n 1))"
assert_true "the builder's prompt asks for data-ed-layer on new candidates" grep -rq "data-ed-layer" pipeline/stages/10-build/prompt.md
sandbox_init
fast_mode
out="$(REELS_DUMMY=all bash "$REPO_DIR/pipeline/stages/s15-project/dummy.sh" "$SANDBOX_CH/runs/x" 2>&1)"; rc=$?
assert_rc 0 "$rc" "the dummy stage runs"
python - "$SANDBOX_CH/runs/x/s15-project/editor.json" "$REPO_DIR/pipeline/stages/s15-project/schema.json" <<'PYEOF'
import json, sys
import jsonschema
jsonschema.validate(json.load(open(sys.argv[1], encoding="utf-8")), json.load(open(sys.argv[2], encoding="utf-8")))
print("dummy editor.json validates")
PYEOF
assert_rc 0 "$?" "the dummy editor.json validates against schema.json"
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. the test-idea reel with the baseline manifest"
RD="$T/run-base"
mkrun "$RD"
assert_file "$RD/timeline/timeline.json" "a run with a timeline (the frozen test idea)"
s15run "$RD" "$BASE"; rc=$?
assert_rc 0 "$rc" "S15 exits 0 ($(tail -n 1 "$T/s15.out" | cut -c1-200))"
echo "S15 took ${S15_SECONDS}s (baseline manifest, $(jget "$RD/timeline/timeline.json" settings.duration_frames) frames)" > "$T/s15-time.txt"
cat "$T/s15-time.txt"
helper "baseline project" project "$(mixed "$RD")" baseline
helper "baseline mix" mixcheck "$(mixed "$RD")"
cp -r "$RD" "$T/run-base-keep" 2>/dev/null
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. manifest-plus.json: native cards and captions; the baseline again gives sprites"
RD2="$T/run-plus"
mkrun "$RD2"
s15run "$RD2" "$PLUS" --reuse-capture; rc=$?
assert_rc 0 "$rc" "S15 exits 0 with manifest-plus.json ($(tail -n 1 "$T/s15.out" | cut -c1-200))"
helper "plus project" project "$(mixed "$RD2")" plus
if [ "${M21_RECORD:-}" = 1 ]; then mkdir -p "$(dirname "$GOLDEN")"; python "$HELP" compare-plus "$(mixed "$RD2")" "$(mixed "$GOLDEN")" --write; fi
if [ -f "$GOLDEN" ]; then helper "plus golden" compare-plus "$(mixed "$RD2")" "$(mixed "$GOLDEN")"; else fail "the golden file $GOLDEN is missing (M21_RECORD=1 writes it)"; fi
s15run "$RD2" "$BASE" --reuse-capture; rc=$?
assert_rc 0 "$rc" "S15 on the same run with the baseline manifest again"
python - "$RD2/s15-project/project/project.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
sprites = [c for c in d["clips"].values() if c["name"].endswith("(sprite)")]
baked = [t for t in d["tracks"] if t["name"] == "Captions (baked)"]
solids_shadow = [c for c in d["clips"].values() if c["kind"] == "solid" and c.get("shadow")]
print("sprites", len(sprites), "baked", len(baked), "solids_shadow", len(solids_shadow), "schema", d["schemaVersion"])
PYEOF
out="$(python - "$RD2/s15-project/project/project.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
sprites = [c for c in d["clips"].values() if c["name"].endswith("(sprite)")]
baked = [t for t in d["tracks"] if t["name"] == "Captions (baked)"]
solids_shadow = [c for c in d["clips"].values() if c["kind"] == "solid" and c.get("shadow")]
print(len(sprites) > 10 and len(baked) == 1 and not solids_shadow and d["schemaVersion"] == 3)
PYEOF
)"
assert_eq "$out" "True" "with the baseline again the cards go back to sprites and the captions are baked (schema 3)"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 4; then
section "4. a forced failure, the export with the project, the EDITOR section, rebuild-project.sh"
sandbox_init
fast_mode
mkdir -p "$SANDBOX_CH/runs"
RD4="$SANDBOX_CH/runs/2026-11-10_0000_m21-test"
mkrun "$RD4"
printf '{%s}\n' "$(tr -d '\r' < "$FROZEN/idea.txt")" > "$SANDBOX_CH/ideas.txt"
# a stand-in 14-export (the real stage needs a model): the manifest the export step reads, the reel and the hook clip
mkdir -p "$RD4/14-export"
cp "$RD4/13-render/final.mp4" "$RD4/14-export/reel.mp4"
ffmpeg -loglevel error -y -i "$RD4/13-render/final.mp4" -t 3 -c copy "$RD4/14-export/hook2.mp4"
python - "$RD4" <<'PYEOF'
import json, sys
rd = sys.argv[1]
json.dump({"caption": "A test caption.", "hashtags": ["#a", "#b", "#c"], "keyword": "TEST", "deliverable": "a file", "deliverable_status": "existing", "link": "", "solution": {"type": "method", "name": "", "url": ""},
           "hooks": {"hook1": "h1", "hook2": "h2"}, "needs_review": [], "facts": [], "files": {"reel": "reel.mp4", "hook2": "hook2.mp4"}}, open(rd + "/14-export/export.json", "w"))
state = {"run_id": "2026-11-10_0000_m21-test", "export": {}}
PYEOF
python "$STATE_PY" new --runs "$SANDBOX_M/channels/flashfx/runs" --id m21-forced > /dev/null 2>&1 || true
REELS_S15_FAIL=full python "$S15" run --run-dir "$(mixed "$RD4")" --manifest "$BASE" --no-parity > "$T/s15-forced.out" 2>&1; rc=$?
assert_rc 0 "$rc" "a forced failure still ends with exit 0 ($(tail -n 1 "$T/s15-forced.out" | cut -c1-160))"
assert_eq "$(jget "$RD4/s15-project/editor.json" level)" "minimal" "the project is the minimal one (editor.json level minimal)"
assert_true "the minimal project has a plate, the sounds and the hidden caption track" python - "$RD4/s15-project/project/project.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
kinds = {t["name"]: t for t in d["tracks"]}
plate = [c for c in d["clips"].values() if c["name"].startswith("Visuals")]
aud = [c for c in d["clips"].values() if c["kind"] == "audio"]
cc = [t for t in d["tracks"] if t["kind"] == "caption" and t["hidden"]]
assert len(plate) == 1 and len(aud) >= 10 and len(cc) == 1, (len(plate), len(aud), len(cc))
PYEOF
assert_true "editor.json carries a NEEDS REVIEW reason" python -c 'import json, sys; d = json.load(open(sys.argv[1])); assert d["needs_review"], d' "$RD4/s15-project/editor.json"
# the export step with the project (the runner's own command)
python - "$RD4" <<'PYEOF'
import json, os, sys
import_path = sys.argv[1]
sys.path.insert(0, os.path.join(os.getcwd(), "pipeline", "lib"))
import state as st
rd = import_path
if not os.path.isfile(rd + "/state.json"):
    json.dump({"run_id": os.path.basename(rd), "export": {}, "stages": {}, "flags": [], "stage_order": []}, open(rd + "/state.json", "w"))
PYEOF
out="$(python pipeline/lib/export.py run --run-dir "$(mixed "$RD4")" --exports "$SANDBOX_M/exports" --root "$SANDBOX_CH_M" --channel flashfx --locks-dir "$SANDBOX_M/.locks" 2>&1)"; rc=$?
assert_rc 0 "$rc" "export.py run exports the reel with its project ($(printf '%s' "$out" | tail -n 1 | cut -c1-160))"
EX="$SANDBOX/exports/flashfx-1"
assert_file "$EX/flashfx-1.mp4" "exports/flashfx-1/flashfx-1.mp4 exists although S15 failed"
assert_file "$EX/project/project.json" "exports/flashfx-1/project/project.json (the minimal project went with the export)"
assert_grep "^EDITOR$" "$EX/flashfx-1captions.txt" "the captions file has the EDITOR section"
assert_grep "^Project: exports/flashfx-1/project \(open http://localhost:5310/\?open=exports/flashfx-1/project, or Open project and pick that folder\)" "$EX/flashfx-1captions.txt" "its Project line names the folder and the open link"
assert_grep "^Layers: minimal project, [0-9]+ baked \(see project/FALLBACKS.md\)" "$EX/flashfx-1captions.txt" "its Layers line says the project is minimal"
assert_true "NEEDS REVIEW lists S15's reason" bash -c "sed -n '/^NEEDS REVIEW/,/^$/p' '$EX/flashfx-1captions.txt' | grep -q 'minimal'"
assert_eq "$(python -c 'import json, sys; print(json.load(open(sys.argv[1]))["name"])' "$EX/project/project.json")" "flashfx-1 2026-11-10_0000_m21-test" "project.json's name is the export's name and the run"
assert_true "OPEN.txt has the export's link" grep -q "exports/flashfx-1/project" "$EX/project/OPEN.txt"
# rebuild: the full project (baseline manifest) replaces the minimal one; an edited project is kept aside
out="$(REELS_ROOT="$SANDBOX_M" bash pipeline/bin/rebuild-project.sh flashfx-1 --manifest "$BASE" 2>&1)"; rc=$?
assert_rc 0 "$rc" "rebuild-project.sh flashfx-1 ($(printf '%s' "$out" | tail -n 1 | cut -c1-160))"
assert_eq "$(jget "$RD4/s15-project/editor.json" level)" "full" "the rebuild made the full project"
assert_true "exports/flashfx-1/project now has the full project (a sprite or native text)" python -c 'import json, sys; d = json.load(open(sys.argv[1])); assert any(c["kind"] == "text" for c in d["clips"].values())' "$EX/project/project.json"
assert_no_file "$EX/project.edited-*" "no edited copy was kept (the editor had not changed the project)" 2>/dev/null
sleep 2; touch "$EX/project/project.json"
out="$(REELS_ROOT="$SANDBOX_M" bash pipeline/bin/rebuild-project.sh flashfx-1 --manifest "$BASE" --no-capture 2>&1)"; rc=$?
assert_rc 0 "$rc" "a second rebuild after the project was changed ($(printf '%s' "$out" | tail -n 1 | cut -c1-120))"
assert_true "the changed project is kept aside as project.edited-<date>/" bash -c "ls -d '$EX'/project.edited-*/ >/dev/null 2>&1"
assert_file "$EX/flashfx-1.mp4" "the video is untouched by the rebuild"
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 5; then
section "5. the stable editor copy in a scratch repo"
out="$(bash pipeline/tests/m21-editor-scratch.sh 2>&1)"; rc=$?
printf '%s\n' "$out" | tail -n 3
assert_rc 0 "$rc" "m21-editor-scratch.sh: advance only to accepted batch reviews, a failing build goes back, the server answers ($(printf '%s' "$out" | tail -n 1))"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 6; then
section "6. the runner's fast mode: one capability upgrade for a changed manifest, two runners alive, no retry of a failed one"
sandbox_init
fast_mode
STABLE6="$T/stable6"; mkdir -p "$STABLE6"
cp "$BASE" "$STABLE6/capabilities.json"
python "$S15" caps --manifest "$STABLE6/capabilities.json" > /dev/null
cp "$BASE" "$SANDBOX/logs-caps.tmp"
mkdir -p "$SANDBOX/logs"
cp "$BASE" "$SANDBOX/logs/editor-capabilities.json"      # the manifest S15 last accepted
export EDITOR_STABLE_DIR="$(mixed "$STABLE6")" REELS_EDITOR_MAINT=on EDITOR_SKIP_ADVANCE=1 EDITOR_SKIP_SERVE=1
run6() { ( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all timeout 600 bash "$REPO_DIR/run.sh" --channel flashfx --once --allow-disabled ) > "$1" 2>&1; }
printf '{First idea for the editor test}\n{Second idea for the editor test}\n' > "$SANDBOX_CH/ideas.txt"
run6 "$T/up1.out"; rc=$?
assert_rc 0 "$rc" "two dummy ideas with an unchanged manifest run ($(tail -n 1 "$T/up1.out" | cut -c1-120))"
assert_eq "$(grep -c 'capability upgrade' "$T/up1.out")" "0" "no upgrade while the manifest is the accepted one"
python - "$STABLE6/capabilities.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
d["solid"]["stroke"] = True
d["lastBatch"] = 60
json.dump(d, open(sys.argv[1], "w"), indent=2)
PYEOF
printf '{Third idea for the editor test}\n{Fourth idea for the editor test}\n' > "$SANDBOX_CH/ideas.txt"
run6 "$T/up2.out"; rc=$?
assert_rc 0 "$rc" "two more ideas with a changed manifest run ($(tail -n 1 "$T/up2.out" | cut -c1-120))"
assert_eq "$(grep -c 'EDITOR capability upgrade: ' "$T/up2.out")" "1" "exactly one capability upgrade starts for the changed manifest"
assert_grep "${ts_regex}EDITOR capability upgrade: solid.stroke" "$T/up2.out" "its status line names the added key"
assert_eq "$(grep -c 'capability upgrade accepted' "$T/up2.out")" "1" "and it is accepted (dummy sessions)"
assert_eq "$(python -c 'import json, sys; print(json.load(open(sys.argv[1]))["solid"]["stroke"])' "$SANDBOX/logs/editor-capabilities.json")" "True" "logs/editor-capabilities.json now holds the new manifest"
python - "$STABLE6/capabilities.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
d["solid"]["shadow"] = True
json.dump(d, open(sys.argv[1], "w"), indent=2)
PYEOF
printf '{Fifth idea}\n{Sixth idea}\n' > "$SANDBOX_CH/ideas.txt"
REELS_DUMMY_UPGRADE=fail run6 "$T/up3.out"
assert_eq "$(grep -c 'capability upgrade not accepted' "$T/up3.out")" "1" "a refused upgrade is reverted and reported once"
assert_file "$SANDBOX/logs/editor-upgrade.json" "logs/editor-upgrade.json records the hash and the reasons"
printf '{Seventh idea}\n{Eighth idea}\n' > "$SANDBOX_CH/ideas.txt"
run6 "$T/up4.out"
assert_eq "$(grep -c 'EDITOR capability upgrade: ' "$T/up4.out")" "0" "the failed manifest is not tried again (the same hash, less than 24 hours)"
# two channels' runners alive: both run the upgrade check, one upgrade only (the second finds the accepted manifest)
python - "$STABLE6/capabilities.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
d["text"]["counter"] = True
json.dump(d, open(sys.argv[1], "w"), indent=2)
PYEOF
python - "$SANDBOX/channels" <<'PYEOF'
import json, os, shutil, sys
src = os.path.join(sys.argv[1], "flashfx")
dst = os.path.join(sys.argv[1], "second")
shutil.copytree(src, dst, dirs_exist_ok=True)
d = json.load(open(os.path.join(dst, "channel.json"), encoding="utf-8"))
d["id"] = "second"
json.dump(d, open(os.path.join(dst, "channel.json"), "w", encoding="utf-8"), indent=2)
PYEOF
printf '{Ninth idea}\n' > "$SANDBOX_CH/ideas.txt"
printf '{Tenth idea}\n' > "$SANDBOX/channels/second/ideas.txt"
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_DUMMY_SECONDS=1 timeout 600 bash "$REPO_DIR/run.sh" --channel flashfx --once --allow-disabled ) > "$T/up5a.out" 2>&1 &
PA=$!
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_DUMMY_SECONDS=1 timeout 600 bash "$REPO_DIR/run.sh" --channel second --once --allow-disabled ) > "$T/up5b.out" 2>&1 &
PB=$!
wait "$PA"; wait "$PB"
assert_eq "$(cat "$T/up5a.out" "$T/up5b.out" | grep -c 'capability upgrade accepted')" "1" "with two runners alive the capability upgrade runs once, not twice"
unset EDITOR_STABLE_DIR REELS_EDITOR_MAINT EDITOR_SKIP_ADVANCE EDITOR_SKIP_SERVE
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 7; then
section "7. the footage-dummy channel: native clips and a native caption track"
sandbox_init
fast_mode
mkdir -p "$T/clips"
mkclip() { ffmpeg -loglevel error -y -f lavfi -i "color=c=$2:s=$3:r=$4:d=$5" -f lavfi -i "sine=frequency=$6:duration=$5:sample_rate=44100" -c:v libx264 -pix_fmt yuv420p -preset ultrafast -c:a aac -shortest "$T/clips/$1.mp4"; }
mkclip clip1 0x1a2a6c 1280x720 25 3 330
mkclip clip2 0x14532d 720x1280 30 3 440
mkclip clip3 0x7f1d1d 1920x1080 24 4 550
bash pipeline/bin/new-channel footageone --format footage-dummy --platform instagram-reels --name "Footageone" > /dev/null 2>&1
cp "$T"/clips/*.mp4 "$SANDBOX/channels/footageone/footage/"
printf '{A test cut of three fixture clips}\n' > "$SANDBOX/channels/footageone/ideas.txt"
( cd "$SANDBOX" && env NO_COLOR=1 REELS_EDITOR_MAINT=off timeout 1500 bash "$REPO_DIR/run.sh" --channel footageone --once --allow-disabled ) > "$T/foot.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the footage-dummy runner exits 0 ($(tail -n 2 "$T/foot.out" | tr '\n' ' ' | cut -c1-200))"
assert_grep "${ts_regex}STEP   building editable project done" "$T/foot.out" "STEP: building editable project done (S15 runs as the last stage)"
EX="$SANDBOX/exports/footageone-1"
assert_file "$EX/project/project.json" "exports/footageone-1/project/project.json"
python - "$EX/project" > "$T/foot-project.txt" 2>&1 <<'PYEOF'
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "pipeline", "lib"))
from s15 import manifest as sm, validate
folder = sys.argv[1]
d = json.load(open(folder + "/project.json", encoding="utf-8"))
res = validate.validate(d, folder, sm.load(None, None))
videos = [c for c in d["clips"].values() if c["kind"] == "video"]
cc = [t for t in d["tracks"] if t["kind"] == "caption"]
cues = [c for c in d["clips"].values() if c["kind"] == "caption"]
print("valid", res["ok"], res["errors"][:2])
print("videos", len(videos), "caption tracks", len(cc), "hidden", cc[0]["hidden"] if cc else None, "cues", len(cues))
print("ok", res["ok"] and len(videos) == 3 and len(cc) == 1 and cc[0]["hidden"] is False and len(cues) >= 3)
PYEOF
assert_grep "^ok True" "$T/foot-project.txt" "the footage project validates, its 3 clips are native video clips and its captions a visible native caption track ($(tr '\n' ' ' < "$T/foot-project.txt" | cut -c1-200))"
assert_grep "^Layers: 3 native, 0 baked" "$EX/footageone-1captions.txt" "the EDITOR section counts 3 native layers"
sandbox_cleanup
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 8; then
section "8. the time S15 took, no em dash"
if [ -f "$T/s15-time.txt" ]; then cat "$T/s15-time.txt"; fi
python - <<'PYEOF' > "$T/emdash-files.txt"
import os
root = "."
files = ["pipeline/bin/editor-stable.sh", "pipeline/bin/rebuild-project.sh", "pipeline/lib/editor.sh", "pipeline/lib/export.py", "pipeline/tests/test-m21.sh", "pipeline/tests/m21-helpers.py",
         "pipeline/tests/m21-editor-scratch.sh", "pipeline/tests/manifest-plus.json", "config.json", "build/M21/report.md"]
for base in ("pipeline/lib/s15", "pipeline/stages/s15-project", "pipeline/lib/motion/annotations.py", "channels/flashfx/motion-lib/compositions", "pipeline/tests/golden"):
    if os.path.isfile(base):
        files.append(base)
        continue
    for dp, dn, fn in os.walk(os.path.join(root, base)):
        files += [os.path.relpath(os.path.join(dp, f), root).replace(chr(92), "/") for f in fn if not f.endswith((".pyc", ".png", ".mp4", ".wav"))]
bad = [f for f in files if os.path.isfile(os.path.join(root, f)) and b"\xe2\x80\x94" in open(os.path.join(root, f), "rb").read()]
print("\n".join(bad))
PYEOF
assert_eq "$(grep -c . "$T/emdash-files.txt")" "0" "no em dash in the files M21 added or changed ($(head -n 3 "$T/emdash-files.txt" | tr '\n' ' '))"
fi

test_summary
