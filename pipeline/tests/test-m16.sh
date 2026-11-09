#!/usr/bin/env bash
# test-m16.sh: acceptance test for M16 (Director, components and the energy loop; BUILD_SPEC.md section 12 and section 5, Motion and
# energy rules E8 and E9; PLAN.md M16).
#   bash pipeline/tests/test-m16.sh                       sections 1 to 5 and 7 (about 40 minutes, no model call), then section 6 (the
#                                                         whole pipeline on the test idea with the real models and the real engine,
#                                                         2 to 4 hours; M16_SECTIONS="6" runs it alone)
#   M16_SECTIONS="1 2 3 5" bash pipeline/tests/test-m16.sh    the fast sections
#
# Sections:
#   1. the components: the nine new ones (screenshot-zoom, video-card, card-fan, card-grid, timeline-scrubber, cursor, mock-site-card,
#      swatch-row, swatch-card) are in the catalog with their beats, sound events and stills; each does what its entry promises in the
#      browser harness (the camera travels, the clip plays and loops, the fan opens, the wave builds, the playhead runs, the cursor
#      presses, the swatches fill on their seconds); frame-match passes all nine; no tween outside pc-motion.js; lint and check pass
#   2. S1's page recordings: a long page gives NN-name.png and NN-name.mp4 side by side (H.264, 1080 wide, 5 to 8 s, no sound, the page
#      scrolls), a page that does not scroll gives the screenshot alone, --no-record, assets.json lists the recording
#   3. the plan rules of E9: the golden plan passes every rule; one planted plan per new rule fails its own (a scene whose hero is small,
#      a narrow hero, a scene with one element, no camera move, a late hook, empty paper for 2 s, three cards one after another in the same
#      spot, one transition type everywhere); the levels warn and off; the director's repairs (the hook moves from frame 0, the transitions
#      vary); the 9a, 9b and 9c prompts carry the rules; the digest lists the recordings
#   4. the golden reel: golden/test-idea is rebuilt from the new plan and meets every energy target of tokens.json, and every scene reaches
#      80 percent of each; the plan uses the new components; the numbers are written to golden/test-idea/energy.json
#   5. S12: the energy check first (the golden passes, a frozen scene fails alone with its numbers and goes to 9a, a still video fails
#      everywhere), the liveness checks (no element static, the edge layer present: clean on the golden, caught on planted copies), the
#      energy score of the edit review, the early stop (the same scores and issues twice in a row, through the CLI too)
#   6. the test idea from scratch with the real models (as test-m12 section 4): the reel meets the energy targets or exports after the loop
#      with its numbers in NEEDS REVIEW, the edit review's scores on stopping the scroll, motion variety and nothing generic are above
#      the M13 reel's 3, the time per reel grows by at most 20 percent over the M13 reel's 141 minutes
#   7. no em dash in the files M16 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M16_SECTIONS:-1 2 3 4 5 7}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
VISUAL="$REPO_DIR/pipeline/lib/visual"
REVIEW="$REPO_DIR/pipeline/lib/review"
MOTION="$REPO_DIR/pipeline/lib/motion"
LIB="$REPO_DIR/channels/flashfx/motion-lib"
HF="npx --prefix $REPO_DIR hyperframes"
FROZEN="$REPO_DIR/pipeline/tests/fixtures/runs/test-idea"
GOLDEN="$REPO_DIR/channels/flashfx/golden/test-idea"
W="$REPO_DIR/build/M16/tmp/test"
mkdir -p "$W"
export PYTHONUTF8=1
NINE="screenshot-zoom,video-card,card-fan,card-grid,timeline-scrubber,cursor,mock-site-card,swatch-row,swatch-card"

hf_json() {
  $HF "$@" 2>/dev/null | python -c 'import sys, json
raw = sys.stdin.read(); i = raw.find("{")
print(raw[i:] if i >= 0 else "{}")'
}
no_emdash_in() {  # no_emdash_in <name> <file>...
  local name="$1"; shift
  if python -c 'import sys
bad = [p for p in sys.argv[1:] if open(p, "rb").read().find(bytes([0xE2, 0x80, 0x94])) >= 0]
print("\n".join(bad)); sys.exit(1 if bad else 0)' "$@" >"$W/emdash.txt"; then pass "$name"; else fail "$name (em dash in: $(tr '\n' ' ' <"$W/emdash.txt"))"; fi
}
lines_to_asserts() {  # lines_to_asserts <prefix> <file>: every `name ok` line a pass, every `name FAIL why` a fail
  local prefix="$1" file="$2" line name n=0
  while IFS= read -r line; do
    line="${line%$'\r'}"
    case "$line" in
      *" ok") name="${line% ok}"; pass "$prefix$name"; n=$((n + 1)) ;;
      *" FAIL "*) name="${line%% FAIL *}"; fail "$prefix$name (${line#* FAIL })"; n=$((n + 1)) ;;
    esac
  done < "$file"
  [ "$n" -gt 0 ] || fail "$prefix: the driver printed no result line ($(tail -n 3 "$file" | tr '\n' ' '))"
}

# ------------------------------------------------------------------------------------------------ 1. the components
if want 1; then
  section "1. the nine new components: catalog, behavior in the browser, frame-match, lint and check"
  python pipeline/tests/m16-lib.py >"$W/lib.txt" 2>&1
  lines_to_asserts "components: " "$W/lib.txt"
  env -u REELS_ROOT python "$MOTION" catalog >"$W/catalog.txt" 2>&1; rc=$?
  assert_rc 0 $rc "catalog.json matches the component files ($(tail -n 1 "$W/catalog.txt"))"
  env -u REELS_ROOT python "$MOTION" frame-match --only "$NINE" >"$W/fm.txt" 2>&1; rc=$?
  assert_rc 0 $rc "frame-match: the nine pass ($(tail -n 1 "$W/fm.txt"))"
  for c in ${NINE//,/ }; do assert_grep "^$c: pass" "$W/fm.txt" "frame-match: $c passes (its main animation, the life checks, the strips)"; done
  python - <<'EOF' >"$W/fm2.txt" 2>&1
import json
r = json.load(open("channels/flashfx/motion-lib/gallery/frame-match.json", encoding="utf-8"))["results"]
nine = "screenshot-zoom,video-card,card-fan,card-grid,timeline-scrubber,cursor,mock-site-card,swatch-row,swatch-card".split(",")
by = {x["id"]: x for x in r}
print("report-has-all-components", "ok" if len(by) >= 38 and all(i in by for i in nine) else "FAIL " + str(len(by)))
print("report-energy-measured", "ok" if all((by[i].get("energy") or {}).get("moving_share_pct") is not None for i in nine) else "FAIL")
bad = [i for i in nine if not any(c["check"].startswith("life: never static") for c in by[i]["checks"])]
print("report-life-checks-run", "ok" if not bad else "FAIL " + str(bad))
cat = {c["id"]: c for c in json.load(open("channels/flashfx/motion-lib/catalog.json", encoding="utf-8"))["components"]}
print("catalog-has-energy", "ok" if all(cat[i].get("energy") for i in nine) else "FAIL " + str([i for i in nine if not cat[i].get("energy")]))
print("catalog-beat-map", "ok" if all(cat[i]["beat_types"] for i in nine) else "FAIL")
vid = cat["video-card"]
print("video-card-needs-clip-start", "ok" if any(p["id"] == "clip_start" for p in vid["props"]) and any(p.get("image") for p in vid["props"] if p["id"] == "video") else "FAIL")
EOF
  lines_to_asserts "library: " "$W/fm2.txt"
  if grep -l -E 'tl\.(to|fromTo|from)\(|gsap\.(to|fromTo|from)\(|onUpdate' "$LIB"/compositions/*.html >"$W/tweens.txt" 2>/dev/null; then
    fail "no composition keeps a tween of its own (found in: $(tr '\n' ' ' <"$W/tweens.txt"))"
  else
    pass "no composition keeps a tween or an onUpdate of its own (the new ones too: pc-motion.js's move helpers)"
  fi
  lint="$(hf_json lint --json "$LIB")"
  assert_eq "$(printf '%s' "$lint" | python -c 'import json, sys; print(json.load(sys.stdin).get("errorCount"))')" "0" "npx hyperframes lint: no errors on channels/flashfx/motion-lib/"
  check="$(cd "$LIB" && hf_json check --json --timeout 120000 --samples 12)"
  assert_eq "$(printf '%s' "$check" | python -c 'import json, sys; d = json.load(sys.stdin); print("true" if d.get("ok") else "false")')" "true" "npx hyperframes check --json passes on channels/flashfx/motion-lib/"
  env -u REELS_ROOT bash pipeline/bin/gallery --no-stills >/dev/null 2>&1; rc=$?
  assert_rc 0 $rc "the gallery page builds"
  for c in ${NINE//,/ }; do assert_grep "stills/$c.png" "$LIB/gallery/index.html" "the gallery shows $c"; assert_file "$LIB/gallery/stills/$c.png" "still of $c"; done
fi

# ------------------------------------------------------------------------------------------------ 2. S1's recordings
if want 2; then
  section "2. S1's page recordings: a scroll video next to the screenshot"
  rm -rf "$W/rec"; mkdir -p "$W/rec"
  python pipeline/tests/m16-recording.py "$W/rec" >"$W/rec.txt" 2>&1
  lines_to_asserts "recordings: " "$W/rec.txt"
  assert_grep "scroll video" pipeline/stages/01-research/prompt.md "the research prompt tells the model about the recordings"
  assert_grep "recording" pipeline/stages/01-research/schema.json "assets.json's schema has the recording fields"
  assert_grep "recording" pipeline/stages/01-research/CONTRACT.md "the research contract describes the recordings"
fi

# ------------------------------------------------------------------------------------------------ 3. the plan rules
if want 3; then
  section "3. the plan rules of E9: the golden plan passes, one planted plan per rule fails, the levels, the repairs, the prompts"
  python pipeline/tests/m16-plans.py check --plan "$GOLDEN/plan.json" --out "$W/planted" >"$W/plans.txt" 2>&1
  lines_to_asserts "rules: " "$W/plans.txt"
  python - <<'EOF' >"$W/plans2.txt" 2>&1
import copy, json, os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from visual import common, plan9, plan_validate as pv
toks = common.tokens()
def say(n, ok, d=""): print(n, "ok" if ok else "FAIL " + str(d))
g = ((toks.get("motion") or {}).get("grammar") or {}).get("composition") or {}
say("tokens-composition", g.get("hero_width_share") == [0.7, 0.85] and g.get("camera_every_scenes") == 3 and g.get("transition_type_max") == 3 and g.get("hook_moving_by_frame") == 4 and g.get("hero_band_y") == [640, 1280], g)
say("rules-listed", all(r in pv.RULES for r in pv.ENERGY_RULES) and all(r in pv.SCENE_RULES or r in pv.TRANSITION_RULES for r in pv.ENERGY_RULES))
# the director's repairs
comps = [{"id": "s1-headline-1", "component": "headline", "start_ms": 800, "end_ms": 3000, "props": {"enter_at": 0.8}, "role": "hero"},
         {"id": "s1-hero-3d-2", "component": "hero-3d", "start_ms": 2400, "end_ms": 3400, "props": {}, "role": "set-piece"}]
note = plan9.hook_moves_from_frame0(comps, 0, toks)
say("repair-hook-moves-from-frame-0", comps[0]["start_ms"] == 0 and "enter_at" not in comps[0]["props"] and comps[1]["start_ms"] == 2400 and "frame 0" in note, (comps, note))
comps2 = [{"id": "a", "component": "headline", "start_ms": 0, "end_ms": 3000, "props": {}, "role": "hero"}]
say("repair-leaves-an-early-hook-alone", plan9.hook_moves_from_frame0(comps2, 0, toks) == "")
tr = [{"from": f"s{i}", "to": f"s{i + 1}", "type": "fade-blur", "duration_ms": 133} for i in range(1, 11)]
notes = []
plan9.vary_transitions(tr, ["fade-blur", "fall", "push", "cut"], {"fade-blur": 133, "fall": 333, "push": 267, "cut": 0}, 3, notes)
cnt = {}
for t in tr: cnt[t["type"]] = cnt.get(t["type"], 0) + 1
say("repair-transitions-vary", max(cnt.values()) <= 3 and len(notes) >= 6, cnt)
say("repair-durations-follow-the-type", all(t["duration_ms"] == {"fade-blur": 133, "fall": 333, "push": 267, "cut": 0}[t["type"]] for t in tr), tr)
say("repair-cuts-stay-at-a-third", cnt.get("cut", 0) * 3 <= 10 and not any(a["type"] == "cut" and b["type"] == "cut" for a, b in zip(tr, tr[1:])), cnt)
# the prompts
def has(path, *needles):
    s = open(path, encoding="utf-8").read()
    return all(n in s for n in needles)
say("prompt-9a-energy", has("pipeline/stages/09a-animations/prompt.md", "Motion and energy", "hero zone", "70 to 85 percent", "video-card", "screenshot-zoom", "1 of every 3 scenes", "hold", "frame 0", "card-fan"))
say("prompt-9c-variety", has("pipeline/stages/09c-transitions/prompt.md", "more than 3 times"))
say("prompt-9b-text-last", has("pipeline/stages/09b-text/prompt.md", "last resort", "100 characters"))
say("prompt-12-energy", has("pipeline/stages/12-review/prompt.md", "- energy:", "energy\": 4"))
sch = json.load(open("pipeline/stages/12-review/model.schema.json", encoding="utf-8"))
say("schema-12-energy", "energy" in sch["properties"]["scores"]["required"])
# the digest of the research assets lists the recordings
class Inp:
    pass
run = os.path.join("pipeline", "tests", "fixtures", "runs", "test-idea")
inp = common.Inputs(run, None)
md = plan9.assets_md(inp)
say("digest-lists-the-recordings", "Page recordings (5)" in md and "research/05-install-docs.mp4" in md and "its scroll recording is research/03-skill-md.mp4" in md, md[:400])
cat = plan9.catalog_md(common.catalog())
say("digest-lists-the-new-components", all(f"### {c}" in cat for c in "screenshot-zoom,video-card,card-fan,card-grid,timeline-scrubber,cursor,mock-site-card,swatch-row,swatch-card".split(",")))
# a research video and a plan that never plays one: the warning of the real_motion rule
plan = json.load(open(os.path.join("channels", "flashfx", "golden", "test-idea", "plan.json"), encoding="utf-8"))
for s in plan["scenes"]:
    for c in s["components"]:
        if c["component"] == "video-card":
            c["component"] = "window-card"; c["props"] = {k: v for k, v in c["props"].items() if k in ("x", "y", "w", "h", "honesty")}
            c["props"]["image"] = "research/02-plugin-page.png"; c["props"]["honesty"] = "sourced"
ctx = pv.Context(words=common.load_json(os.path.join(run, "08-voiceover", "words.json")), script=common.load_json(os.path.join(run, "07-script", "script.json")),
                 assets={f: {} for f in os.listdir(os.path.join(run, "01-research", "assets")) if f.endswith((".png", ".mp4"))})
rep = pv.Report(); pv.rule_real_motion(plan, ctx, rep)
say("real-motion-warns-when-no-recording-plays", any(w["rule"] == "real_motion" for w in rep.warnings) and not rep.errors, rep.warnings)
# the new components' footprints and the text they carry count for the budget
fp = common.footprint("mock-site-card", {"x": 90, "y": 420, "w": 900, "title": "a.com", "headline": "Same look", "cta": "Go"}, toks)
say("footprint-mock-site", fp["w"] == 900 and fp["h"] == 820 and len(fp["text_boxes"]) == 3, fp)
say("text-items-new-components", sum(i["chars"] for i in common.text_items("mock-site-card", {"title": "a.com", "headline": "Same look", "cta": "Go"}, toks)) == len("a.com") + len("Same look") + 2
    and sum(i["chars"] for i in common.text_items("card-fan", {"items_json": [{"label": "Plan"}, {"label": "Post"}]}, toks)) == 8
    and common.text_items("cursor", {"points_json": []}, toks) == [] and common.text_items("screenshot-zoom", {"image": "research/x.png"}, toks) == [])
EOF
  lines_to_asserts "plans: " "$W/plans2.txt"
fi

# ------------------------------------------------------------------------------------------------ 4. the golden reel
if want 4; then
  section "4. the golden reel: rebuilt from the new plan, every energy target met, every scene at 80 percent"
  fresh=1
  if [ -f "$GOLDEN/golden.mp4" ] && [ "${M16_RERENDER:-0}" != 1 ] && [ "$GOLDEN/golden.mp4" -nt "$GOLDEN/plan.json" ] && [ "$GOLDEN/golden.mp4" -nt "$REPO_DIR/channels/flashfx/motion-lib/assets/pc-motion.js" ] \
     && [ "$GOLDEN/golden.mp4" -nt "$LIB/compositions/video-card.html" ]; then fresh=0; fi
  if [ "$fresh" = 1 ]; then
    t0=$EPOCHSECONDS
    env -u REELS_ROOT bash pipeline/bin/render-golden --make-plan >"$W/golden.txt" 2>&1; rc=$?
    printf '   (the golden render took %s s)\n' "$((EPOCHSECONDS - t0))"
    assert_rc 0 $rc "render-golden rebuilds the golden reel from the plan ($(tail -n 1 "$W/golden.txt" | cut -c1-100))"
  else
    echo "   (golden.mp4 is newer than the plan and the library: not rendered again; M16_RERENDER=1 forces it)"
  fi
  assert_file "$GOLDEN/golden.mp4" "golden.mp4 exists"
  python - <<'EOF' >"$W/golden2.txt" 2>&1
import json, os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from review import energy, energy_check
from visual import common
def say(n, ok, d=""): print(n, "ok" if ok else "FAIL " + str(d))
toks = common.tokens()
plan = json.load(open("channels/flashfx/golden/test-idea/plan.json", encoding="utf-8"))
rep = energy.measure_video("channels/flashfx/golden/test-idea/golden.mp4", plan=plan, tokens=toks)
w = rep["whole"]
print("   the reel: " + energy.summary_line(w, rep["check"]))
for name, c in rep["check"]["checks"].items():
    say(f"golden-meets-{name}", c["ok"], c)
share = 0.8
bounds = energy_check.scene_targets(rep["targets"], share)
bad = []
for s in rep["scenes"]:
    if s["beat_type"] in energy_check.EXEMPT_BEATS:
        print(f"   {s['id']} {s['beat_type']:<11} (the CTA's content is fixed by the branding rules: it counts in the reel's numbers only)")
        continue
    chk = energy.check_targets(s["measures"], bounds)
    line = f"   {s['id']} {s['beat_type']:<11} " + ", ".join(f"{k.split('_')[0]} {v['got']}" for k, v in chk["checks"].items())
    print(line)
    for name, c in chk["checks"].items():
        if not c["ok"]:
            bad.append((s["id"], name, c["got"], c["want"]))
say("every-scene-at-80-percent-of-every-target", not bad, bad)
say("energy-check-agrees", not energy_check.scene_issues(json.loads(json.dumps(rep)), share))
json.dump({"written_by": "pipeline/tests/test-m16.sh", "video": "channels/flashfx/golden/test-idea/golden.mp4", "targets": rep["targets"], "scene_bounds": bounds, "whole": w, "check": rep["check"],
           "scenes": [{"id": s["id"], "beat_type": s["beat_type"], "measures": s["measures"]} for s in rep["scenes"]]}, open("channels/flashfx/golden/test-idea/energy.json", "w", encoding="utf-8", newline="\n"), indent=1)
# the plan uses the new components where the energy comes from
kinds = {c["component"] for s in plan["scenes"] for c in s["components"]}
new = kinds & set("screenshot-zoom,video-card,card-fan,card-grid,timeline-scrubber,cursor,mock-site-card,swatch-row,swatch-card".split(","))
say("golden-uses-the-new-components", len(new) >= 5, sorted(new))
say("golden-has-the-energy-grammar", plan["scenes"][0]["components"][0]["props"].get("hold") == "lively")
EOF
  grep -E "^   " "$W/golden2.txt" | sed 's/^/ /'
  lines_to_asserts "golden: " "$W/golden2.txt"
  assert_grep "video-card" "$GOLDEN/README.md" "the README lists the new golden's components"
fi

# ------------------------------------------------------------------------------------------------ 5. S12
if want 5; then
  section "5. S12: the energy check, the liveness checks, the energy score, the early stop"
  rm -rf "$W/review"; mkdir -p "$W/review"
  python pipeline/tests/m16-review.py "$W/review" >"$W/review.txt" 2>&1
  lines_to_asserts "review: " "$W/review.txt"
fi

# ------------------------------------------------------------------------------------------------ 6. the whole pipeline
if want 6; then
  section "6. the test idea end to end with the real models: research to export, energy loop included (2 to 4 hours)"
  export SANDBOX_ENERGY=on
  FAKES="$REPO_DIR/pipeline/tests/fakes"
  SFX_DIR_REAL="$(mixed "$REPO_DIR/channels/flashfx/styles/sfx")"
  export REELS_SFX_DIR="$SFX_DIR_REAL" REELS_SFX_NO_BUILD=1
  ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
  TEST_IDEA="$(tr -d '\r' < "$FROZEN/idea.txt")"
  sandbox_init --with-review
  fake_claude_off
  printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/channels/flashfx/ideas.txt"
  started="$EPOCHSECONDS"
  ( cd "$SANDBOX" && env NO_COLOR=1 timeout "${M16_TIMEOUT:-18000}" bash "$SANDBOX/run.sh" --once ) > "$SANDBOX/real.out" 2>&1; rc=$?
  OUT="$SANDBOX/real.out"
  RD="$(ls -d "$SANDBOX"/channels/flashfx/runs/*/ 2>/dev/null | sed 's|/$||' | head -n 1)"
  mins=$(( (EPOCHSECONDS - started) / 60 ))
  printf 'the real run took %s min, kept at %s\n' "$mins" "$RD"
  mkdir -p build/M16/real && cp -r "$RD/12-review" build/M16/real/12-review 2>/dev/null; cp "$OUT" build/M16/real/real.out; cp -r "$RD/09a-animations" build/M16/real/ 2>/dev/null
  grep -E "$ts_regex(STEP|GATE|DROP|DONE|ERROR|FIXED|ESCAL|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /' | tail -n 80
  assert_rc 0 $rc "the runner exits 0"
  assert_grep "${ts_regex}DONE   exported flashfx-1 -> exports/flashfx-1/" "$OUT" "DONE: exported flashfx-1"
  assert_not_grep "${ts_regex}(BLOCK|DROP|STOP)" "$OUT" "no BLOCK, DROP or STOP line"
  assert_file "$SANDBOX/exports/flashfx-1/flashfx-1.mp4" "exports/flashfx-1/flashfx-1.mp4"
  assert_file "$RD/12-review/energy.json" "12-review/energy.json: the energy check ran"
  python - "$RD" "$mins" <<'EOF' >"$W/real2.txt" 2>&1
import glob, json, os, sys
rd, mins = sys.argv[1], int(sys.argv[2])
def say(n, ok, d=""): print(n, "ok" if ok else "FAIL " + str(d))
e = json.load(open(os.path.join(rd, "12-review", "energy.json"), encoding="utf-8"))
rev = json.load(open(os.path.join(rd, "12-review", "review.json"), encoding="utf-8"))
w = e["whole"]
print("   energy of the last round:", {k: w.get(k) for k in ("moving_share_pct", "middle_moving_share_pct", "pixels_changing_pct", "still_share_pct", "longest_still_s")}, "targets", e["targets"])
print("   review rounds:", sorted(os.path.basename(p) for p in glob.glob(os.path.join(rd, "12-review", "review-r*.json"))), "verdict", rev["verdict"], "scores", rev["edit_review"]["scores"])
cap = open(glob.glob(os.path.join(os.path.dirname(os.path.dirname(rd)), "exports", "1", "1captions.txt"))[0], encoding="utf-8").read() if glob.glob(os.path.join(os.path.dirname(os.path.dirname(rd)), "exports", "1", "1captions.txt")) else ""
meets = e["check"]["pass"] and not e["failing_scenes"]
needs_review = "NEEDS REVIEW" in cap
say("reel-meets-the-targets-or-exports-with-its-numbers-in-needs-review", meets or (needs_review and "moving share" in cap.lower() or needs_review and "energy" in cap.lower()), (meets, needs_review))
sc = rev["edit_review"]["scores"]
for k in ("stop", "variety", "generic"):
    say(f"edit-review-{k}-above-the-M13-reels-3", sc.get(k, 0) > 3, sc)
# the M13 reel took 141 minutes (build/M13/report.md): at most 20 percent more
say("time-per-reel-grows-by-at-most-20-percent", mins <= round(141 * 1.2), f"{mins} min against {round(141 * 1.2)}")
EOF
  lines_to_asserts "real run: " "$W/real2.txt"
  grep -E "^   " "$W/real2.txt"
  echo "   the captions file:"; sed 's/^/      /' "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt" 2>/dev/null | head -n 40
  sandbox_cleanup
fi

# ------------------------------------------------------------------------------------------------ 7. no em dash
if want 7; then
  section "7. no em dash in the files M16 wrote"
  no_emdash_in "no em dash in the M16 components, helpers and sources" \
    channels/flashfx/motion-lib/assets/pc-motion.js channels/flashfx/motion-lib/compositions/screenshot-zoom.html channels/flashfx/motion-lib/compositions/video-card.html channels/flashfx/motion-lib/compositions/card-fan.html \
    channels/flashfx/motion-lib/compositions/card-grid.html channels/flashfx/motion-lib/compositions/timeline-scrubber.html channels/flashfx/motion-lib/compositions/cursor.html channels/flashfx/motion-lib/compositions/mock-site-card.html \
    channels/flashfx/motion-lib/compositions/swatch-row.html channels/flashfx/motion-lib/compositions/swatch-card.html pipeline/lib/motion/demo_assets.py pipeline/lib/motion/catalog.py pipeline/lib/motion/expectations.py \
    pipeline/lib/motion/goldenplan.py pipeline/lib/screenshot.py pipeline/lib/research.py pipeline/lib/visual/plan_validate.py pipeline/lib/visual/plan9.py pipeline/lib/visual/common.py \
    pipeline/lib/review/energy_check.py pipeline/lib/review/liveness.py pipeline/lib/review/route.py pipeline/lib/review/edit.py pipeline/lib/review/mechanical.py pipeline/lib/review/__main__.py
  no_emdash_in "no em dash in the M16 prompts, schemas, contracts and tests" \
    pipeline/stages/01-research/prompt.md pipeline/stages/01-research/CONTRACT.md pipeline/stages/01-research/schema.json pipeline/stages/09a-animations/prompt.md \
    pipeline/stages/09c-transitions/prompt.md pipeline/stages/12-review/prompt.md pipeline/stages/12-review/model.schema.json pipeline/stages/12-review/run.sh \
    pipeline/tests/test-m16.sh pipeline/tests/m16-lib.py pipeline/tests/m16-plans.py pipeline/tests/m16-recording.py pipeline/tests/m16-review.py pipeline/tests/sandbox-config.py \
    channels/flashfx/golden/test-idea/plan.json channels/flashfx/golden/test-idea/README.md channels/flashfx/golden/test-idea/energy.json config.json
fi

test_summary
