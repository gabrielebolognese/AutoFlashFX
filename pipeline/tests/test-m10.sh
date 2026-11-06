#!/usr/bin/env bash
# test-m10.sh: acceptance test for M10 (Visual stages S9 and S10, BUILD_SPEC.md section 12 and PLAN.md M10). Sections
# 1 and 2 run without a model (the fake claude answers the visual director from fixtures); section 3 calls the real
# visual_director (and the builder when the check needs a repair).
#   bash pipeline/tests/test-m10.sh                       everything (20 to 40 minutes: two builds with renders, the real director)
#   M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh    only those sections (no model; about 15 minutes); "2r" is the repair loop alone
#   M10_FREEZE=1 bash pipeline/tests/test-m10.sh          section 3 also copies the real plans (with the director's answers), events.json,
#                                                         the project files and the drafts into pipeline/tests/fixtures/runs/test-idea/
#                                                         (the inputs of M11; the fake director keeps its hand-made answers)
#
# Sections:
#   1. units, no model: the validator fixtures (good.json passes every rule; each bad-<rule>.json fails and names its rule),
#      the caption chunker's width limit on the frozen words, the pass schemas are current, the preflight's brand check
#      (the repo passes; a sandbox with a broken brand.json stops with the fix)
#   2. S9a, S9b, S9c and S10 through the runner with the fake claude from the frozen M7 outputs: the three plans validate
#      against their schemas and the merged plan passes the validator; `npx hyperframes check --json` passed on the built
#      project; draft.mp4 is 540x960 at 30 fps with no audio stream and a duration within 0.2 s of the voice; the hook 2
#      clip renders at 3.5 s or less; events.json validates and matches what is on screen (every scene change, typing,
#      count, strike and check event verified by a seek one frame before and after; every host starts where the plan
#      says); the contact sheet; the activities and terminal lines; 3 director calls, no builder call. Then the branding
#      with a fixture solution.json for flashfx and one for external: both CTAs carry the FlashFX DM avatar and the lockup;
#      the brand slot shows the bolt only in the flashfx reel and the neutral icon in the other; every logo path is in
#      brand.json with a use_on matching its surface; in the built flashfx project every logo is an image with its aspect
#      ratio locked (measured in the harness). Then the builder's repair loop with a planted broken component: the check
#      fails, the (fake) builder is asked visual.build_fix_rounds times, the stage fails as a code error
#   3. the real visual director and the build on the frozen inputs (3 model calls, 10 to 20 minutes)
#   4. no em dash in the files M10 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
export REELS_ENERGY_RULES=off   # M16: this test validates the frozen low-energy plans of M10 (the energy rules of E9 are off for them)
SECTIONS="${M10_SECTIONS:-1 2 3 4}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
VALIDATE="$REPO_DIR/pipeline/bin/validate-json"
VISUAL="$REPO_DIR/pipeline/lib/visual"
FROZEN="$FIXTURES/runs/test-idea"
PLANS="$FIXTURES/plans"
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
LATER_DUMMIES="$(dummy_after 10-build)"
WORDS="$FROZEN/08-voiceover/words.json"
VOICE_MS="$(python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig"))["duration_ms"])' "$WORDS")"

json_get() {  # json_get <file> <dotted key> [default]
  python -c 'import json, sys
try:
    cur = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    for part in sys.argv[2].split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
except (OSError, ValueError, KeyError, IndexError, TypeError):
    print(sys.argv[3] if len(sys.argv) > 3 else ""); sys.exit(0)
if isinstance(cur, bool): print("true" if cur else "false")
elif isinstance(cur, (dict, list)): print(json.dumps(cur, ensure_ascii=False))
else: print(cur)' "$@"
}
jf() { python -c 'import json, sys; d = json.loads(sys.argv[1]); v = d.get(sys.argv[2], ""); print(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict, bool)) else v)' "$1" "$2"; }
seed_run() {  # a run in the sandbox with S1 to S8 done from the frozen outputs (04-angle stays skipped); prints the run dir
  local raw id created rd st
  raw="$(tr -d '\r' < "$FROZEN/idea.txt")"
  printf '{%s}\n' "$raw" > "$SANDBOX/channels/flashfx/ideas.txt"
  id="$(printf '%s' "$raw" | python pipeline/lib/ideas.py id)"
  created="$(printf '%s' "$raw" | python "$STATE_PY" new --runs "$SANDBOX_M/channels/flashfx/runs" --id "$id")"
  rd="$(jf "$created" run_dir)"
  for st in 01-research 02-expansion 03-gate 05-hooks 06-judge 07-script 08-voiceover; do
    cp -r "$FROZEN/$st/." "$rd/$st/"
    python "$STATE_PY" stage-start "$rd" "$st" >/dev/null
    python "$STATE_PY" stage-done "$rd" "$st" --schemas "$REPO_DIR/pipeline/stages" >/dev/null \
      || printf 'seed_run: the frozen %s did not validate\n' "$st" >&2
  done
  printf '%s' "$rd"
}
run_once() {  # run_once <outfile> [env...]: the sandbox's own run.sh (REELS_REPO is the sandbox copy of the repo)
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 5400 bash "$SANDBOX/run.sh" --once ) > "$out" 2>&1
}
run_stage() {  # run_stage <stage> <run_dir> <outfile> [env...]: one stage script alone, in the sandbox's copy of the pipeline
  local st="$1" rd="$2" out="$3"; shift 3
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 3600 bash "$SANDBOX/pipeline/stages/$st/run.sh" "$rd" ) > "$out" 2>&1
}
fake_calls() { python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG" 2>/dev/null || echo 0; }
no_emdash_in() {  # no_emdash_in <name> <file>...
  local name="$1"; shift
  if python -c 'import sys
bad = [p for p in sys.argv[1:] if open(p, "rb").read().find(bytes([0xE2, 0x80, 0x94])) >= 0]
print("\n".join(bad)); sys.exit(1 if bad else 0)' "$@" >/tmp/m10-emdash.txt; then pass "$name"; else fail "$name (em dash in: $(tr '\n' ' ' </tmp/m10-emdash.txt))"; fi
}
probe_draft() {  # probe_draft <mp4> <want ms> -> lines size/fps/silent/duration ok|...
  python - "$1" "$2" <<'EOF'
import json, subprocess, sys
mp4, want = sys.argv[1], int(sys.argv[2]) / 1000
d = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt:format=duration", "-of", "json", mp4], capture_output=True, text=True).stdout or "{}")
v = next((s for s in d.get("streams", []) if s["codec_type"] == "video"), None)
if not v:
    print("size no video stream"); sys.exit(0)
num, den = v["r_frame_rate"].split("/")
print("size", "ok" if (v["width"], v["height"]) == (540, 960) else "%sx%s" % (v["width"], v["height"]))
print("fps", "ok" if abs(float(num) / float(den) - 30) < 0.01 else v["r_frame_rate"])
print("codec", "ok" if v.get("codec_name") == "h264" and v.get("pix_fmt") == "yuv420p" else "%s %s" % (v.get("codec_name"), v.get("pix_fmt")))
print("silent", "ok" if not any(s["codec_type"] == "audio" for s in d.get("streams", [])) else "has audio")
dur = float(d["format"]["duration"])
print("duration", "ok" if abs(dur - want) <= 0.2 else "%.2f vs %.2f" % (dur, want))
print("seconds %.2f" % dur)
EOF
}
check_plans() {  # check_plans <run_dir> <label>: the three plans against their schemas and the merged plan against the validator
  local rd="$1" lbl="$2" st rc
  for st in 09a-animations 09b-text 09c-transitions; do
    assert_true "$lbl: $st/plan.json validates against its schema" python "$VALIDATE" "$REPO_DIR/pipeline/stages/$st/schema.json" "$rd/$st/plan.json"
  done
  assert_file "$rd/09c-transitions/merged.json" "$lbl: the merged plan was written by 9c"
  assert_true "$lbl: merged.json validates against pipeline/stages/09-plan/schema.json" python "$VALIDATE" "$REPO_DIR/pipeline/stages/09-plan/schema.json" "$rd/09c-transitions/merged.json"
  python "$VISUAL" validate "$rd/09c-transitions/merged.json" --run-dir "$rd" >/tmp/m10-validate.txt 2>&1; rc=$?
  assert_rc 0 $rc "$lbl: the merged plan passes every rule of the validator ($(tail -n 1 /tmp/m10-validate.txt))"
  assert_true "$lbl: 10-build/plan.json (the plan as compiled) passes the validator too" python "$VISUAL" validate "$rd/10-build/plan.json" --run-dir "$rd"
}
check_build() {  # check_build <run_dir> <label>: the build's outputs
  local rd="$1" lbl="$2"
  local B="$rd/10-build"   # its own line: the words of one local statement are expanded before any is assigned
  assert_true "$lbl: events.json validates against 10-build/schema.json" python "$VALIDATE" "$REPO_DIR/pipeline/stages/10-build/schema.json" "$B/events.json"
  assert_eq "$(json_get "$B/check.json" ok)" "true" "$lbl: npx hyperframes check --json passed on the built project"
  assert_eq "$(json_get "$B/build.json" check_ok)" "true" "$lbl: build.json records the check as ok"
  assert_file "$B/project/index.html" "$lbl: the project exists"
  assert_file "$B/project/instances.json" "$lbl: instances.json exists"
  assert_file "$B/draft.mp4" "$lbl: draft.mp4 rendered"
  probe_draft "$B/draft.mp4" "$VOICE_MS" >/tmp/m10-probe.txt
  assert_grep "^size ok" /tmp/m10-probe.txt "$lbl: draft.mp4 is 540x960"
  assert_grep "^fps ok" /tmp/m10-probe.txt "$lbl: draft.mp4 is 30 fps"
  assert_grep "^codec ok" /tmp/m10-probe.txt "$lbl: draft.mp4 is H.264 yuv420p"
  assert_grep "^silent ok" /tmp/m10-probe.txt "$lbl: draft.mp4 has no audio stream"
  assert_grep "^duration ok" /tmp/m10-probe.txt "$lbl: draft.mp4 lasts as long as the voice (within 0.2 s: $(grep '^seconds' /tmp/m10-probe.txt | cut -d' ' -f2) s against $VOICE_MS ms)"
  assert_file "$B/hook2.mp4" "$lbl: hook2.mp4 rendered"
  local h2dur; h2dur="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$B/hook2.mp4" 2>/dev/null)"
  assert_true "$lbl: hook2.mp4 lasts 3.5 s or less (${h2dur:-?} s)" python -c 'import sys; sys.exit(0 if 0 < float(sys.argv[1]) <= 3.5 + 0.05 else 1)' "${h2dur:-0}"
  assert_file "$B/contact-sheet.png" "$lbl: the contact sheet exists"
  python - "$B/events.json" "$rd/09c-transitions/merged.json" <<'EOF' >/tmp/m10-events.txt
import json, sys
ev = json.load(open(sys.argv[1], encoding="utf-8-sig")); plan = json.load(open(sys.argv[2], encoding="utf-8-sig"))
events = ev["events"]
v = ev.get("verified") or {}
print("verified", "ok" if v.get("checked", 0) >= 30 and not v.get("failed") else "checked %s failed %s" % (v.get("checked"), v.get("failed")))
sc = [e for e in events if e["scene_change"]]
print("scene-changes", "ok" if len(sc) == len(plan["scenes"]) - 1 and all(e.get("verified") for e in sc) and all(e["transition_ms"] == t["duration_ms"] for e, t in zip(sc, plan["transitions"])) else "%d changes, verified %s" % (len(sc), [e.get("verified") for e in sc]))
key = [e for e in events if e["type"] in ("typing", "count_start", "strike", "check")]
print("key-events", "ok" if key and all(e.get("verified") for e in key) else str([(e["type"], e.get("verified")) for e in key]))
print("key-count", len(key))
print("timeline", "ok" if (ev.get("timeline_check") or {}).get("ok") else str(ev.get("timeline_check")))
print("monotonic", "ok" if all(a["ms"] <= b["ms"] for a, b in zip(events, events[1:])) else "not sorted")
print("inside", "ok" if all(0 <= e["ms"] <= ev["duration_ms"] for e in events) else "outside the reel")
print("cues", "ok" if any(e.get("cue") == "notification" for e in events) and any(e.get("cue") == "hook_hit" for e in events) else "no notification or hook_hit cue")
print("harness", "ok" if not ev.get("harness_errors") else str(ev["harness_errors"][:2]))
EOF
  cat /tmp/m10-events.txt | sed 's/^/    /'
  assert_grep "^verified ok" /tmp/m10-events.txt "$lbl: every element event that starts a change was verified on screen (a seek one frame before and after)"
  assert_grep "^scene-changes ok" /tmp/m10-events.txt "$lbl: one verified scene change per scene pair, with the transition's duration"
  assert_grep "^key-events ok" /tmp/m10-events.txt "$lbl: every typing, count, strike and check event verified ($(grep '^key-count' /tmp/m10-events.txt | cut -d' ' -f2) events)"
  assert_grep "^timeline ok" /tmp/m10-events.txt "$lbl: every host starts where the plan says (npx hyperframes timeline)"
  assert_grep "^monotonic ok" /tmp/m10-events.txt "$lbl: events.json is sorted by time"
  assert_grep "^inside ok" /tmp/m10-events.txt "$lbl: every event lies inside the reel"
  assert_grep "^cues ok" /tmp/m10-events.txt "$lbl: the catalog's cues reached events.json (hook_hit, notification)"
  assert_grep "^harness ok" /tmp/m10-events.txt "$lbl: the harness logged no page error"
}
check_branding_plan() {  # check_branding_plan <plan.json> <flashfx|external|none> <label>
  python - "$1" "$2" <<'EOF' >/tmp/m10-brand.txt
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8-sig")); sol = sys.argv[2]
br = p["branding"]
cta = next(s for s in p["scenes"] if s["id"] == br["cta_scene"])
kinds = {c["component"]: c for c in cta["components"]}
print("cta-ask", "ok" if cta["beat_type"] == "ask" else cta["beat_type"])
print("dm", "ok" if "dm-card" in kinds and kinds["dm-card"]["props"].get("avatar") == "brand/mark/avatar-dark.png" and kinds["dm-card"]["props"].get("sender") == "FlashFX" else "missing")
print("lockup", "ok" if "end-card" in kinds and kinds["end-card"]["props"].get("lockup", "").startswith("brand/lockup/") and float(kinds["end-card"]["props"].get("lockup_w", 0)) >= 300 else "missing")
outside = [(c["id"], v) for s in p["scenes"] if s["id"] != cta["id"] for c in s["components"] for v in c["props"].values() if isinstance(v, str) and v.startswith("brand/")]
hook = next(s for s in p["scenes"] if s["beat_type"] == "hook")
mark = next((c["props"].get("kicker_mark") for c in hook["components"] if c["component"] == "headline"), None)
if sol == "flashfx":
    print("slot", "ok" if br.get("brand_slot") == "brand/mark/mark-gradient.png" and mark == "brand/mark/mark-gradient.png" and br.get("flashfx_allowed_outside_cta") else "slot %s mark %s" % (br.get("brand_slot"), mark))
    print("outside", "ok" if outside else "no FlashFX asset in the body although the solution is FlashFX")
else:
    print("slot", "ok" if br.get("brand_slot") is None and mark == "" and not br.get("flashfx_allowed_outside_cta") else "slot %s mark %s" % (br.get("brand_slot"), mark))
    print("outside", "ok" if not outside else str(outside))
print("solution", p.get("solution", {}).get("type"))
EOF
  cat /tmp/m10-brand.txt | sed 's/^/    /'
  assert_grep "^cta-ask ok" /tmp/m10-brand.txt "$3: the CTA scene is the ask"
  assert_grep "^dm ok" /tmp/m10-brand.txt "$3: the CTA has the FlashFX DM card with avatar-dark.png and sender FlashFX"
  assert_grep "^lockup ok" /tmp/m10-brand.txt "$3: the CTA's end card carries a FlashFX lockup of 300 px or more"
  assert_grep "^slot ok" /tmp/m10-brand.txt "$3: the brand slot follows the solution ($2)"
  assert_grep "^outside ok" /tmp/m10-brand.txt "$3: FlashFX assets outside the CTA only when the solution is FlashFX ($2)"
  assert_eq "$(grep '^solution' /tmp/m10-brand.txt | cut -d' ' -f2)" "$2" "$3: the plan records the solution type $2"
}

# ------------------------------------------------------------------------------------------------ 1. units
if want 1; then
  section "1. units: the validator fixtures, the caption width, the pass schemas, the preflight's brand check"
  ctx=(--words "$WORDS" --script "$FROZEN/07-script/script.json" --assets-json "$FROZEN/01-research/assets.json" --numbers "$FROZEN/01-research/numbers.json")
  python "$VISUAL" validate "$PLANS/good.json" "${ctx[@]}" >/tmp/m10-good.txt 2>&1; rc=$?
  assert_rc 0 $rc "good.json passes every rule ($(tail -n 1 /tmp/m10-good.txt))"
  n_bad=0
  for f in "$PLANS"/bad-*.json; do
    rule="$(basename "$f" .json)"; rule="${rule#bad-}"
    out="$(python "$VISUAL" validate "$f" "${ctx[@]}" 2>&1)"; rc=$?
    if [ "$rc" = 1 ] && printf '%s\n' "$out" | grep -q "^rule=$rule:"; then pass "bad-$rule.json fails and names its rule: $(printf '%s\n' "$out" | grep "^rule=$rule:" | head -n 1 | cut -c1-120)"; else fail "bad-$rule.json: exit $rc, rules: $(printf '%s\n' "$out" | grep -o '^rule=[a-z_0-9]*' | sort -u | tr '\n' ' ')"; fi
    n_bad=$((n_bad + 1))
  done
  assert_true "one failing fixture per rule of the spec's list and more (18 or more)" test "$n_bad" -ge 18
  python - "$WORDS" "$FROZEN/07-script/script.json" <<'EOF' >/tmp/m10-chunks.txt
import json, os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from motion import captions
from visual import common
toks = common.tokens()
words = json.load(open(sys.argv[1], encoding="utf-8-sig"))["words"]
script = json.load(open(sys.argv[2], encoding="utf-8-sig"))
terms = {b["id"]: b.get("emphasis", []) for b in script["beats"]}
body = [w for w in words if w["beat"] not in ("b1", "b11")]
max_w = float(toks["zones"]["caption"]["max_width"])
plain = captions.chunk_words(body, terms)
limited = captions.chunk_words(body, terms, max_width=max_w, width_fn=lambda ws: common.caption_chunk_width(ws, toks))
wide_plain = sum(1 for c in plain if common.caption_chunk_width(c["words"], toks) > max_w)
wide_limited = sum(1 for c in limited if common.caption_chunk_width(c["words"], toks) > max_w)
print("plain", len(plain), wide_plain)
print("limited", len(limited), wide_limited)
print("words", "ok" if [w["word"] for c in limited for w in c["words"]] == [w["word"] for w in body] else "lost words")
print("sizes", "ok" if all(1 <= len(c["words"]) <= 4 for c in limited) else "bad")
EOF
  cat /tmp/m10-chunks.txt | sed 's/^/    /'
  assert_true "the plain chunker leaves chunks wider than the caption line (the M9 gap)" test "$(grep '^plain' /tmp/m10-chunks.txt | cut -d' ' -f3)" -gt 0
  assert_eq "$(grep '^limited' /tmp/m10-chunks.txt | cut -d' ' -f3)" "0" "with the width limit no chunk is wider than $(json_get channels/flashfx/styles/paper-cards/tokens.json zones.caption.max_width) px"
  assert_grep "^words ok" /tmp/m10-chunks.txt "the width-limited chunks keep every spoken word in order"
  assert_grep "^sizes ok" /tmp/m10-chunks.txt "the width-limited chunks hold 1 to 4 words"
  tmp="$(mktemp -d)"; python pipeline/stages/09-plan/pass-schemas.py "$(mixed "$tmp")" >/dev/null
  same=1; for st in 09a-animations 09b-text 09c-transitions; do cmp -s "$tmp/$st/schema.json" "pipeline/stages/$st/schema.json" || same=0; done; rm -rf "$tmp"
  assert_eq "$same" "1" "the three pass schemas are the ones pass-schemas.py generates from 09-plan/schema.json"
  assert_true "the merged plan schema accepts the golden plan" python "$VALIDATE" pipeline/stages/09-plan/schema.json channels/flashfx/golden/test-idea/plan.json
  # the preflight's brand check: the repo passes; a sandbox with a broken brand.json stops with the fix
  assert_true "bash pipeline/bin/preflight passes in the repo (brand.json and every logo file present)" bash pipeline/bin/preflight
  sandbox_init --with-pipeline
  printf '{"assets": [{"path": "library/brand/mark/missing.png", "use_on": "light", "width": 1, "height": 1}]}\n' > "$SANDBOX/channels/flashfx/library/brand/brand.json"
  ( cd "$SANDBOX" && NO_COLOR=1 bash "$SANDBOX/pipeline/bin/preflight" ) >/tmp/m10-preflight.txt 2>&1; rc=$?
  assert_rc 3 $rc "a brand.json that lists a missing file stops the preflight (exit 3)"
  assert_grep "brand.json lists files that do not exist" "$SANDBOX/channels/flashfx/logs/STOPPED.md" "STOPPED.md names the missing logo file"
  assert_grep "git checkout -- channels/flashfx/library/brand" "$SANDBOX/channels/flashfx/logs/STOPPED.md" "STOPPED.md gives the exact fix"
  sandbox_cleanup
fi

# ------------------------------------------------------------------------------------------------ 2. the stages with the fake director
if want 2; then
  section "2. S9a, S9b, S9c and S10 through the runner with the fake visual director, from the frozen M7 outputs"
  sandbox_init --with-visual
  fake_claude_on
  mkdir -p "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m10/"*.json "$SANDBOX/fixtures/"
  export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
  RD="$(seed_run)"
  rm -f "$RD/02-expansion/solution.json"   # the frozen run has one since M12 (5407b58): this reel is the one without it
  fast_mode
  run_once "$SANDBOX/fake.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_CLAUDE_REVIEW=no; rc=$?
  OUT="$SANDBOX/fake.out"
  grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
  assert_rc 0 $rc "the runner exits 0"
  assert_grep "${ts_regex}START  idea 1/1 .* \(resumed at planning animations, 7 stages done\)$" "$OUT" "START: the run seeded from the frozen outputs resumes at S9a"
  assert_grep "${ts_regex}INFO   S9: animations planned: 11 scenes, [0-9]+ component instances, [0-9]+ distinct \(.*\); brand slot neutral, hook set piece true$" "$OUT" "S9a: the summary line (11 scenes, the neutral brand slot, the hook's set piece)"
  assert_grep "${ts_regex}STEP   planning animations done \([0-9hms]+\) -> planning text$" "$OUT" "S9a done, the runner moves to S9b"
  assert_grep "${ts_regex}INFO   S9: text planned: [0-9]+ caption chunks, [0-9]+ card texts changed, [0-9]+ labels$" "$OUT" "S9b: the summary line"
  assert_grep "${ts_regex}STEP   planning text done \([0-9hms]+\) -> planning transitions$" "$OUT" "S9b done, the runner moves to S9c"
  assert_grep "${ts_regex}INFO   S9: transitions planned: 10 transitions \(.*\); the merged plan passes the validator$" "$OUT" "S9c: the summary line (10 transitions, the merged plan validated)"
  assert_grep "${ts_regex}STEP   planning transitions done \([0-9hms]+\) -> building visuals$" "$OUT" "S9c done, the runner moves to S10"
  assert_grep "${ts_regex}INFO   S10: project built from the plan: [0-9]+ hosts, 11 scenes, assets .*; builder role builder \(1 3D objects\)$" "$OUT" "S10: the project line (hosts, assets, the builder role, one 3D object)"
  assert_grep "${ts_regex}INFO   S10: hyperframes check ok \([0-9]+ warnings\)$" "$OUT" "S10: the check passed"
  assert_grep "${ts_regex}INFO   S10: events.json: [0-9]+ events \(10 scene changes\); ([0-9]+) of \1 element events verified on screen$" "$OUT" "S10: the events line (10 scene changes, every element event verified)"
  assert_grep "${ts_regex}INFO   S10: draft.mp4 540x960 30.0 fps, [0-9.]+ s \(plan [0-9.]+ s\), silent, rendered in [0-9.]+ s$" "$OUT" "S10: the draft line"
  assert_grep "${ts_regex}INFO   S10: hook2.mp4 [0-9.]+ s \([0-9]+ ms planned\), rendered in [0-9.]+ s$" "$OUT" "S10: the hook 2 line"
  assert_grep "${ts_regex}STEP   building visuals done \([0-9hms]+\) -> adding sound effects$" "$OUT" "S10 done, the runner moves to S11"
  assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the run continued to the (dummy) export"
  assert_not_grep "${ts_regex}(ERROR|BLOCK|FLAG)" "$OUT" "no ERROR, BLOCK or FLAG line"
  assert_eq "$(fake_calls)" "3" "three model calls: one per director pass, none for the builder (the check passed at once)"
  for a in "planning animations" "validating plan"; do assert_grep "^activity: $a$" "$RD/09a-animations/stage.log" "activity \"$a\" was published by S9a"; done
  assert_grep "^activity: planning text$" "$RD/09b-text/stage.log" "activity \"planning text\" was published by S9b"
  assert_grep "^activity: planning transitions$" "$RD/09c-transitions/stage.log" "activity \"planning transitions\" was published by S9c"
  for a in "building visuals" "rendering draft"; do assert_grep "^activity: $a$" "$RD/10-build/stage.log" "activity \"$a\" was published by S10"; done
  check_plans "$RD" "fake"
  check_branding_plan "$RD/09a-animations/plan.json" none "fake (no solution.json)"
  check_build "$RD" "fake"
  assert_eq "$(json_get "$RD/10-build/build.json" builder_role)" "builder" "the builder role is the Opus builder (one 3D object, no review rounds)"
  assert_eq "$(json_get "$RD/09a-animations/plan.json" hook2.lines | python -c 'import json, sys; print(len(json.load(sys.stdin)))')" "2" "hook 2's headline has its two lines"
  assert_grep '"breath"' "$RD/09a-animations/plan.json" "the hook's set piece is placed at the breath"
  no_emdash_in "no em dash in the stage files" "$RD/09a-animations/plan.json" "$RD/09b-text/plan.json" "$RD/09c-transitions/plan.json" "$RD/09c-transitions/merged.json" \
    "$RD/10-build/events.json" "$RD/10-build/project/index.html" "$RD/09a-animations/prompt.md" "$RD/09b-text/prompt.md" "$RD/09c-transitions/prompt.md" "$SANDBOX/channels/flashfx/logs/runner.log"
  FAKE_RD="$RD"

  # ---- the branding: a flashfx solution and an external one (the 9a stage alone), then the flashfx build
  for sol in flashfx external; do
    fake_claude_reset
    RD="$(seed_run)"
    cp "$FIXTURES/solutions/$sol.json" "$RD/02-expansion/solution.json"
    run_stage 09a-animations "$RD" "$SANDBOX/9a-$sol.out"; rc=$?
    assert_rc 0 $rc "branding ($sol): the animations pass runs"
    assert_true "branding ($sol): plan.json validates" python "$VALIDATE" pipeline/stages/09a-animations/schema.json "$RD/09a-animations/plan.json"
    assert_true "branding ($sol): the plan passes the validator (branding rule included)" python "$VISUAL" validate "$RD/09a-animations/plan.json" --run-dir "$RD" --parts scenes
    check_branding_plan "$RD/09a-animations/plan.json" "$sol" "branding ($sol)"
    assert_grep "Solution of this reel: $sol" "$RD/09a-animations/digest/solution.md" "branding ($sol): the director was told the solution and its branding"
    if [ "$sol" = flashfx ]; then
      # a FlashFX asset in a body card must pass for a flashfx reel and be rejected for the external one: the validator rule
      python - "$RD/09a-animations/plan.json" "$SANDBOX_M/plan-flashfx-body.json" <<'EOF'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8-sig"))
c = next(c for s in p["scenes"] for c in s["components"] if c["id"] == "s2-card-1")
c["props"]["image"] = "brand/mark/mark-gradient.png"
json.dump(p, open(sys.argv[2], "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
EOF
      assert_true "branding (flashfx): a FlashFX bolt on a body card passes the validator" python "$VISUAL" validate "$SANDBOX_M/plan-flashfx-body.json" --run-dir "$RD" --parts scenes
      python - "$SANDBOX_M/plan-flashfx-body.json" "$SANDBOX_M/plan-flashfx-wrong.json" <<'EOF'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8-sig"))
c = next(c for s in p["scenes"] for c in s["components"] if c["id"] == "s2-card-1")
c["props"]["image"] = "brand/mark/mark-white.png"  # a dark-surface variant on a light card
json.dump(p, open(sys.argv[2], "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
EOF
      out="$(python "$VISUAL" validate "$SANDBOX_M/plan-flashfx-wrong.json" --run-dir "$RD" --parts scenes 2>&1)"; rc=$?
      assert_true "branding (flashfx): a white (dark-surface) bolt on a light card is rejected (use_on must match the surface)" test "$rc" = 1
      assert_grep "use_on must match" <(printf '%s\n' "$out") "branding (flashfx): the rejection names the use_on rule"
      run_stage 09b-text "$RD" "$SANDBOX/9b-$sol.out" && run_stage 09c-transitions "$RD" "$SANDBOX/9c-$sol.out" && run_stage 10-build "$RD" "$SANDBOX/10-$sol.out"; rc=$?
      assert_rc 0 $rc "branding (flashfx): the text, transitions and build stages run"
      assert_true "branding (flashfx): the merged plan passes the validator" python "$VISUAL" validate "$RD/09c-transitions/merged.json" --run-dir "$RD"
      assert_eq "$(json_get "$RD/10-build/check.json" ok)" "true" "branding (flashfx): the check passed on the built project"
      python - "$RD/10-build/project" "$REPO_DIR" <<'EOF' >/tmp/m10-logos.txt
import json, os, sys
project, repo = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(repo, "pipeline", "lib"))
from motion import common as mc, harness
from PIL import Image
brand = json.load(open(os.path.join(repo, "channels", "flashfx", "library", "brand", "brand.json"), encoding="utf-8-sig"))
assets = {a["path"].replace("library/brand/", ""): a for a in brand["assets"]}
inst = json.load(open(os.path.join(project, "instances.json"), encoding="utf-8-sig"))["instances"]
spots = {"headline": ("kicker_mark", "#hl-mark img"), "end-card": ("lockup", "#ec-lockup img"), "dm-card": ("avatar", "#dm-avatar img"), "logo-tile": ("image", "#lt-main img")}
n = 0
with harness.Harness(lib=project) as h:
    for i in inst:
        if i["component"] not in spots:
            continue
        prop, sel = spots[i["component"]]
        path = i["props"].get(prop, "")
        if not path or not path.startswith("assets/brand/"):
            continue
        rel = path[len("assets/brand/"):]
        if rel not in assets:
            print(i["instance"], "NOT-IN-BRAND-JSON", rel); continue
        comp = mc.parse_component(os.path.join(project, "compositions", i["component"] + ".html"))
        props = dict(i["props"]); props.pop("clip_start", None)
        m = h.measure(comp, props, [2.5], [sel])["rows"][0][sel]
        if not m or not m.get("h"):
            print(i["instance"], "NO-IMG", rel); continue
        im = Image.open(os.path.join(repo, "channels", "flashfx", "library", "brand", rel)); want = im.size[0] / im.size[1]
        natural = (m.get("nw") or 0) / (m.get("nh") or 1)
        ok = m.get("fit") == "contain" and abs(natural - want) / want <= 0.02
        n += 1
        print(i["instance"], "ok" if ok else "fit=%s natural=%.3f want=%.3f" % (m.get("fit"), natural, want), rel, "use_on", assets[rel]["use_on"])
print("count", n)
EOF
      cat /tmp/m10-logos.txt | sed 's/^/    /'
      assert_true "branding (flashfx): the built project places 3 or more logos (kicker mark, lockup, avatar)" test "$(grep '^count' /tmp/m10-logos.txt | cut -d' ' -f2)" -ge 3
      assert_eq "$(grep -v '^count' /tmp/m10-logos.txt | grep -v -c ' ok ')" "0" "branding (flashfx): every logo is an image from brand.json drawn with object-fit contain at the file's aspect ratio"
      assert_grep "^s1-headline-1 ok mark/mark-gradient.png" /tmp/m10-logos.txt "branding (flashfx): the hook's kicker mark is the FlashFX bolt image"
      probe_draft "$RD/10-build/draft.mp4" "$VOICE_MS" >/tmp/m10-probe2.txt
      assert_grep "^size ok" /tmp/m10-probe2.txt "branding (flashfx): the draft rendered at 540x960"
    fi
  done
  sandbox_cleanup
  fake_claude_off
fi

# ------------------------------------------------------------------------------------------------ 2r. the builder's repair loop
if want 2 || want 2r; then
  section "2r. the builder's repair loop: a planted broken component, the (fake) builder asked twice, then a code error"
  # a component that throws at mount makes the check fail; the (fake) builder cannot fix it, so the stage asks it
  # config visual.build_fix_rounds times and then fails as a code error
  sandbox_init --with-visual
  fake_claude_on
  mkdir -p "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m10/"*.json "$SANDBOX/fixtures/"
  export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
  RD="$(seed_run)"
  run_stage 09a-animations "$RD" "$SANDBOX/9a-repair.out" && run_stage 09b-text "$RD" "$SANDBOX/9b-repair.out" && run_stage 09c-transitions "$RD" "$SANDBOX/9c-repair.out"; rc=$?
  assert_rc 0 $rc "repair loop: the three plan passes run"
  python - "$SANDBOX/channels/flashfx/motion-lib/compositions/dark-chip.html" <<'EOF2'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
marker = "(function () {\n      var v = PC.vars("
planted = "(function () {\n      throw new Error(\"planted by the test: a broken component\");\n      var v = PC.vars("
s = s.replace(marker, planted, 1)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("planted" if "planted by the test" in s else "NOT planted")
EOF2
  n_before="$(fake_calls)"
  run_stage 10-build "$RD" "$SANDBOX/10-repair.out"; rc=$?
  assert_rc 1 $rc "repair loop: the build stage fails as a code error when the check still fails after the repairs"
  # a stage run directly prints its terminal lines to stdout (the runner would route them through fd 3): they are in the captured output
  assert_grep "S10: hyperframes check found [0-9]+ errors \(runtime: console_error: .*planted by the test" "$SANDBOX/10-repair.out" "repair loop: the check named the planted error"
  assert_grep "asking the builder model to repair the project \(round 1/2\)" "$SANDBOX/10-repair.out" "repair loop: the builder was asked a first time (round 1/2)"
  assert_grep "asking the builder model to repair the project \(round 2/2\)" "$SANDBOX/10-repair.out" "repair loop: the builder was asked a second time (round 2/2)"
  assert_grep "hyperframes check still reports errors after 2 builder repairs" "$SANDBOX/10-repair.out" "repair loop: the stage's last line names the cap"
  assert_eq "$(( $(fake_calls) - n_before ))" "2" "repair loop: exactly two builder calls (config visual.build_fix_rounds)"
  assert_file "$RD/10-build/prompt-repair-r1.md" "repair loop: the repair prompt was written"
  assert_grep "planted by the test" "$RD/10-build/prompt-repair-r1.md" "repair loop: the repair prompt quotes the check's errors"
  assert_grep "^# Role: builder" "$RD/10-build/prompt-repair-r1.md" "repair loop: the prompt is the builder's"
  assert_eq "$(python "$STATE_PY" get "$RD" rounds.build 0)" "2" "repair loop: state.json counts the two build rounds"
  assert_no_file "$RD/10-build/draft.mp4" "repair loop: no draft was rendered from a failing project"
  sandbox_cleanup
  fake_claude_off
fi

# ------------------------------------------------------------------------------------------------ 3. the real director
if want 3; then
  section "3. the real visual director and the build on the frozen inputs (real model calls)"
  sandbox_init --with-visual
  RD="$(seed_run)"
  rm -f "$RD/02-expansion/solution.json"   # the frozen run has one since M12 (5407b58): this reel is the one without it
  fast_mode
  t0=$EPOCHSECONDS
  run_once "$SANDBOX/real.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
  OUT="$SANDBOX/real.out"
  grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
  printf '    (section 3 took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "real: the runner exits 0"
  assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "real: the run continued to the (dummy) export"
  assert_not_grep "${ts_regex}(ERROR|BLOCK)" "$OUT" "real: no ERROR or BLOCK line"
  assert_grep "${ts_regex}INFO   S9: animations planned: 11 scenes" "$OUT" "real: S9a planned 11 scenes"
  assert_grep "${ts_regex}INFO   S9: transitions planned: 10 transitions .*; the merged plan passes the validator" "$OUT" "real: S9c's merged plan passed the validator"
  assert_grep "${ts_regex}INFO   S10: hyperframes check ok" "$OUT" "real: the check passed"
  check_plans "$RD" "real"
  check_branding_plan "$RD/09a-animations/plan.json" none "real (no solution.json)"
  check_build "$RD" "real"
  n_calls="$(ls "$RD"/09a-animations/calls/*.json "$RD"/09b-text/calls/*.json "$RD"/09c-transitions/calls/*.json 2>/dev/null | grep -v -c '\.out\.json$')"
  printf '    director calls: %s (3 without a retry); builder repairs: %s\n' "$n_calls" "$(json_get "$RD/10-build/build.json" fix_rounds 0)"
  assert_true "real: the director answered in 3 to 6 calls (one retry per pass at most)" test "$n_calls" -ge 3 -a "$n_calls" -le 6
  if [ "$FAIL_N" -eq 0 ] && [ -n "${M10_FREEZE:-}" ]; then
    # the real outputs become the frozen inputs of M11; the fake director keeps its hand-made answers (the golden design)
    for st in 09a-animations 09b-text 09c-transitions; do
      mkdir -p "$FROZEN/$st"; cp "$RD/$st/plan.json" "$FROZEN/$st/plan.json"
      last="$(ls "$RD/$st"/calls/*.out.json | tail -n 1)"; cp "$last" "$FROZEN/$st/answer.json"
    done
    cp "$RD/09c-transitions/merged.json" "$FROZEN/09c-transitions/merged.json"
    mkdir -p "$FROZEN/10-build/project" "$FROZEN/10-build/hook2"
    for f in events.json plan.json build.json check.json draft.mp4 hook2.mp4 contact-sheet.png; do cp "$RD/10-build/$f" "$FROZEN/10-build/$f"; done
    cp "$RD/10-build/project/index.html" "$RD/10-build/project/instances.json" "$FROZEN/10-build/project/"
    cp "$RD/10-build/hook2/index.html" "$RD/10-build/hook2/plan.json" "$FROZEN/10-build/hook2/"
    pass "frozen: the real plans (with the director's answers), merged.json, events.json, plan.json, build.json, check.json, the contact sheet, the project's index.html and instances.json, the hook 2 files and the two drafts (ignored by git) copied to pipeline/tests/fixtures/runs/test-idea/ (M10_FREEZE)"
  fi
  sandbox_cleanup
fi

# ------------------------------------------------------------------------------------------------ 4. em dashes
if want 4; then
  section "4. no em dash in the files M10 wrote"
  files=(pipeline/lib/visual.sh pipeline/bin/contact-sheet pipeline/stages/09-plan/schema.json pipeline/stages/09-plan/pass-schemas.py pipeline/tests/test-m10.sh pipeline/tests/fixtures/plans/make-bad.py)
  for f in pipeline/lib/visual/*.py pipeline/stages/09a-animations/* pipeline/stages/09b-text/* pipeline/stages/09c-transitions/* pipeline/stages/10-build/* pipeline/tests/fixtures/fake/m10/*.json pipeline/tests/fixtures/plans/*.json pipeline/tests/fixtures/solutions/*.json; do
    [ -f "$f" ] && files+=("$f")
  done
  no_emdash_in "no em dash in the M10 files" "${files[@]}"
fi

test_summary
