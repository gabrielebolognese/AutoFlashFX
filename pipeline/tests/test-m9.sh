#!/usr/bin/env bash
# test-m9.sh: acceptance test for M9 (Motion library, BUILD_SPEC.md section 12 and PLAN.md M9). No model call.
#   bash pipeline/tests/test-m9.sh                      everything (20 to 40 minutes: frame-match and the golden render)
#   M9_SECTIONS="1 2" bash pipeline/tests/test-m9.sh    only those sections
#
# Sections:
#   1. tokens: a sandbox copy of style.md and tweaks.md builds a tokens.json that validates against the schema, every
#      number and color of it appears in the sources, the tracker is off, a rebuild with unchanged sources is a no-op, a
#      touched tweaks.md triggers one, an accepted PROPOSED line changes the caption position; the repo's tokens.json is
#      current and tokens.css exists
#   2. library: `npx hyperframes lint` and `check --json` pass on motion-lib/; catalog.json lists every component of
#      vocabulary.md items 1 to 24 with props, beat types and sound events, plus the DM notification card, and agrees with
#      the files; every logo spot takes an image path and keeps the file's aspect ratio (measured in the harness); every
#      component renders a still (the gallery's stills)
#   3. frame-match: frame-match.md shows a pass for every component in motion-lib/compositions/ and lists the candidates
#      that failed with their numbers; the gallery page exists with one still per component
#   4. golden: golden/test-idea/plan.json validates against pipeline/stages/09-plan/schema.json; render-golden renders
#      golden.mp4 at 1080x1920, 30 fps, with a duration within 0.2 s of vo.wav and an audio stream; the contact sheet
#      and README exist; the CTA carries the FlashFX DM avatar and the lockup and no FlashFX asset sits outside it
#   5. webgl: the WebGL test writes motion-lib/webgl.json with its verdict (the mode frame-match and the gallery use)
#   6. no em dash in the files M9 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M9_SECTIONS:-1 2 3 4 5 6}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
VALIDATE="$REPO_DIR/pipeline/bin/validate-json"
TOK="$REPO_DIR/pipeline/lib/tokens.py"
MOTION="$REPO_DIR/pipeline/lib/motion"
LIB="$REPO_DIR/motion-lib"
HF="npx --prefix $REPO_DIR hyperframes"

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
hf_json() {  # hf_json <command...> -> the JSON envelope on stdout (the CLI prints a telemetry note first)
  $HF "$@" 2>/dev/null | python -c 'import sys, json
raw = sys.stdin.read(); i = raw.find("{")
print(raw[i:] if i >= 0 else "{}")'
}
no_emdash_in() {  # no_emdash_in <name> <file>...
  local name="$1"; shift
  if python -c 'import sys
bad = [p for p in sys.argv[1:] if open(p, "rb").read().find(bytes([0xE2, 0x80, 0x94])) >= 0]
print("\n".join(bad)); sys.exit(1 if bad else 0)' "$@" >/tmp/emdash.txt; then pass "$name"; else fail "$name (em dash in: $(tr '\n' ' ' </tmp/emdash.txt))"; fi
}

# ------------------------------------------------------------------------------------------------ 1. tokens
if want 1; then
  section "1. tokens.json from style.md plus tweaks.md"
  sandbox_init
  mkdir -p "$SANDBOX/styles/paper-cards"
  cp "$REPO_DIR"/styles/paper-cards/style.md "$REPO_DIR"/styles/paper-cards/tweaks.md "$SANDBOX/styles/paper-cards/"
  # the scenario below starts from the six version 2 lines as proposals (the user accepted them on 2026-11-07, M14)
  python - "$SANDBOX/styles/paper-cards/tweaks.md" <<'EOF'
import re, sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
for title in ("Caption position", "Right side, captions", "Hook header", "Length", "Accent-filled cards", "3D"):
    # the proposal is the last bullet with that title (Length and 3D also have an earlier decision bullet)
    hits = list(re.finditer(r"^- \*\*" + re.escape(title) + r":\*\*", s, flags=re.M))
    if hits:
        m = hits[-1]
        s = s[:m.start()] + "- PROPOSED **" + title + ":**" + s[m.end():]
open(p, "w", encoding="utf-8", newline="\n").write(s)
EOF
  SD="$SANDBOX_M/styles/paper-cards"; OUT="$SANDBOX_M/tokens.json"; CSS="$SANDBOX_M/tokens.css"
  out="$(bash pipeline/bin/build-tokens --style-dir "$SD" --out "$OUT" --css "$CSS" 2>&1)"; rc=$?
  assert_rc 0 $rc "build-tokens builds in the sandbox"
  assert_grep "tokens rebuilt" <(printf '%s\n' "$out") "the first build reports a rebuild"
  assert_file "$OUT" "tokens.json written"
  assert_file "$CSS" "tokens.css written"
  assert_true "tokens.json validates against pipeline/lib/tokens.schema.json" python "$VALIDATE" pipeline/lib/tokens.schema.json "$OUT"
  assert_true "every number and color of tokens.json appears in style.md or tweaks.md" python "$TOK" verify --style-dir "$SD" --tokens "$OUT"
  assert_eq "$(json_get "$OUT" tracker.enabled)" "false" "the tracker switch is off"
  assert_eq "$(json_get "$OUT" zones.caption.center_y)" "1480" "captions at y 1480 (tweaks.md Caption box in force)"
  assert_eq "$(json_get "$OUT" zones.caption.safe_zone_exception)" "true" "the caption band keeps its safe-zone exception"
  assert_eq "$(json_get "$OUT" zones.kicker_top)" "253" "kicker top 253 (open question 5: v02)"
  assert_eq "$(json_get "$OUT" shapes.dots.spacing_px)" "43.5" "dot spacing 43.5 (open question 7: v02)"
  assert_eq "$(json_get "$OUT" colors.accent)" "#DC6532" "the accent color"
  assert_eq "$(json_get "$OUT" motion.enter.position_frames)" "8" "the enter move's 8 frames"
  assert_eq "$(json_get "$OUT" transitions.scene_change)" "exit-then-enter" "scene change B (open question 3)"
  assert_eq "$(json_get "$OUT" limits.accent_share_max_pct)" "5" "the accent cap from tweaks.md"
  assert_grep "c-paper: #F5EEE3" "$CSS" "tokens.css carries the paper color"
  out="$(bash pipeline/bin/build-tokens --style-dir "$SD" --out "$OUT" --css "$CSS" 2>&1)"
  assert_grep "up to date" <(printf '%s\n' "$out") "a rebuild with unchanged sources is a no-op"
  printf '\n<!-- touched by test-m9 -->\n' >> "$SANDBOX/styles/paper-cards/tweaks.md"
  assert_false "the check sees the touched tweaks.md" bash pipeline/bin/build-tokens --check --style-dir "$SD" --out "$OUT"
  out="$(bash pipeline/bin/build-tokens --style-dir "$SD" --out "$OUT" --css "$CSS" 2>&1)"
  assert_grep "tokens rebuilt \(tweaks.md changed\)" <(printf '%s\n' "$out") "a touched tweaks.md triggers a rebuild"
  # accepting the PROPOSED caption position (removing the word) moves the captions and drops the exception
  python - "$SANDBOX/styles/paper-cards/tweaks.md" <<'EOF'
import sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
s = s.replace("- PROPOSED **Caption position:**", "- **Caption position:**")
open(p, "w", encoding="utf-8", newline="\n").write(s)
EOF
  bash pipeline/bin/build-tokens --style-dir "$SD" --out "$OUT" --css "$CSS" >/dev/null 2>&1
  assert_eq "$(json_get "$OUT" in_force.caption_position)" "true" "the accepted proposal is in force"
  assert_eq "$(json_get "$OUT" zones.caption.center_y)" "1332" "captions move to y 1332"
  assert_eq "$(json_get "$OUT" zones.caption.safe_zone_exception)" "false" "the safe-zone exception is dropped"
  assert_true "the accepted-proposal tokens still verify against the sources" python "$TOK" verify --style-dir "$SD" --tokens "$OUT"
  # the repo's own tokens
  assert_true "the repo's tokens.json is current" bash pipeline/bin/build-tokens --check
  assert_true "the repo's tokens.json validates" python "$VALIDATE" pipeline/lib/tokens.schema.json styles/paper-cards/tokens.json
  assert_true "the repo's tokens.json verifies against the sources" bash pipeline/bin/build-tokens --verify
  assert_file "$LIB/assets/tokens.css" "motion-lib/assets/tokens.css exists"
  sandbox_cleanup
fi

# ------------------------------------------------------------------------------------------------ 2. library
if want 2; then
  section "2. the library: lint, check, catalog, logo spots, stills"
  lint="$(hf_json lint --json "$LIB")"
  assert_eq "$(printf '%s' "$lint" | python -c 'import json, sys; print(json.load(sys.stdin).get("errorCount"))')" "0" "npx hyperframes lint: no errors on motion-lib/"
  check="$(cd "$LIB" && hf_json check --json --timeout 90000 --samples 12)"
  assert_eq "$(printf '%s' "$check" | python -c 'import json, sys; d = json.load(sys.stdin); print("true" if d.get("ok") else "false")')" "true" "npx hyperframes check --json passes on motion-lib/"
  assert_eq "$(printf '%s' "$check" | python -c 'import json, sys; d = json.load(sys.stdin); print("true" if d.get("browserSkipped") else "false")')" "false" "the browser audits ran"
  assert_true "the catalog agrees with the component files" python "$MOTION" catalog
  CAT="$LIB/catalog.json"
  python - "$CAT" "$LIB" <<'EOF' >/tmp/m9-catalog.txt
import json, os, sys
cat = json.load(open(sys.argv[1], encoding="utf-8-sig")); lib = sys.argv[2]
comps = cat["components"]
ids = {c["id"] for c in comps}
items = {c.get("item") for c in comps}
print("items", "ok" if all(i in items for i in range(1, 25)) else "missing " + str([i for i in range(1, 25) if i not in items]))
print("dm", "ok" if "dm-card" in ids else "missing")
print("props", "ok" if all(c["props"] for c in comps) else "empty for " + str([c["id"] for c in comps if not c["props"]]))
print("beats", "ok" if all(c["beat_types"] for c in comps) else "none for " + str([c["id"] for c in comps if not c["beat_types"]]))
print("events", "ok" if all(c["sound_events"] for c in comps if c["id"] != "paper-canvas") else "none for " + str([c["id"] for c in comps if not c["sound_events"] and c["id"] != "paper-canvas"]))
cues = set(cat["cue_types"])
bad = [(c["id"], e.get("cue")) for c in comps for e in c["sound_events"] if e.get("cue") and e["cue"] not in cues and not str(e["cue"]).startswith("transition")]
print("cues", "ok" if not bad else str(bad))
logo = {"logo-tile": "image", "end-card": "lockup", "dm-card": "avatar", "headline": "kicker_mark", "table-card": "logos_json"}
missing = [k for k, p in logo.items() if not any(x["id"] == p and x.get("image") for c in comps if c["id"] == k for x in c["props"])]
print("logo-spots", "ok" if not missing else str(missing))
print("count", len(comps))
EOF
  assert_grep "^items ok" /tmp/m9-catalog.txt "vocabulary.md items 1 to 24 all have a component"
  assert_grep "^dm ok" /tmp/m9-catalog.txt "the DM notification card is in the catalog"
  assert_grep "^props ok" /tmp/m9-catalog.txt "every component lists its props"
  assert_grep "^beats ok" /tmp/m9-catalog.txt "every component has beat types"
  assert_grep "^events ok" /tmp/m9-catalog.txt "every component declares sound events"
  assert_grep "^cues ok" /tmp/m9-catalog.txt "every sound event cue is a known cue type"
  assert_grep "^logo-spots ok" /tmp/m9-catalog.txt "every logo spot (tile, end card, DM avatar, kicker mark, table logos) takes an image path"
  # the logos keep their aspect ratio: measured in the harness with the brand files
  python - "$REPO_DIR" <<'EOF' >/tmp/m9-aspect.txt
import os, sys
repo = sys.argv[1]
sys.path.insert(0, os.path.join(repo, "pipeline", "lib"))
from motion import common, harness
from PIL import Image
lib = common.motion_lib_dir()
def ratio(path):
    im = Image.open(path); return im.size[0] / im.size[1]
jobs = [
    ("logo-tile", {"image": "assets/brand/mark/mark-gradient.png", "size": 200, "image_pad": 20}, "#lt-main img", ratio(os.path.join(repo, "library/brand/mark/mark-gradient.png"))),
    ("end-card", {"lockup": "assets/brand/lockup/lockup-gradient-on-light.png", "lockup_w": 360}, "#ec-lockup img", ratio(os.path.join(repo, "library/brand/lockup/lockup-gradient-on-light.png"))),
    ("dm-card", {"avatar": "assets/brand/mark/avatar-dark.png", "avatar_size": 120}, "#dm-avatar img", 1.0),
    ("headline", {"kicker_mark": "assets/brand/mark/mark-gradient.png"}, "#hl-mark img", None),
]
with harness.Harness(lib=lib) as h:
    for cid, props, sel, want in jobs:
        comp = common.parse_component(os.path.join(lib, "compositions", cid + ".html"))
        res = h.measure(comp, props, [2.5], [sel])
        m = res["rows"][0][sel]
        if m is None or m["h"] == 0:
            print(cid, "MISSING"); continue
        # the image is drawn with object-fit contain inside its box, so the drawn picture keeps the file's ratio whatever
        # the box is (a square tile, the avatar circle); the natural size must be the file's and the fit must be contain
        natural = (m.get("nw") or 0) / (m.get("nh") or 1)
        fit_ok = m.get("fit") == "contain"
        size_ok = (abs(natural - want) / want <= 0.02) if want else natural > 0
        bw, bh = m["w"], m["h"]
        drawn_w, drawn_h = (bw, bw / natural) if bw / bh > natural else (bh * natural, bh)
        print(cid, "ok" if (fit_ok and size_ok) else "fit=%s natural=%.3f want=%.3f" % (m.get("fit"), natural, want or 0),
              "box=%.0fx%.0f drawn=%.0fx%.0f" % (bw, bh, drawn_w, drawn_h))
EOF
  cat /tmp/m9-aspect.txt
  assert_grep "^logo-tile ok" /tmp/m9-aspect.txt "the logo tile keeps the bolt's aspect ratio"
  assert_grep "^end-card ok" /tmp/m9-aspect.txt "the end card keeps the lockup's aspect ratio"
  assert_grep "^dm-card ok" /tmp/m9-aspect.txt "the DM avatar is a round image"
  assert_grep "^headline ok" /tmp/m9-aspect.txt "the kicker mark is an image"
  assert_grep 'object-fit: contain' "$LIB/assets/paper-cards.css" "logos are placed with object-fit contain (never stretched)"
  # stills: one per component (the gallery builds them)
  python "$MOTION" stills >/tmp/m9-stills.txt 2>&1; rc=$?
  assert_rc 0 $rc "the stills build"
  n_comp="$(json_get "$CAT" components | python -c 'import json, sys; print(len(json.load(sys.stdin)))')"
  n_still="$(python - "$CAT" "$LIB" <<'EOF'
import json, os, sys
from PIL import Image
cat = json.load(open(sys.argv[1], encoding="utf-8-sig")); lib = sys.argv[2]
n = 0
for c in cat["components"]:
    p = os.path.join(lib, c["still"])
    if os.path.isfile(p) and Image.open(p).size == (540, 960):
        n += 1
print(n)
EOF
)"
  assert_eq "$n_still" "$n_comp" "every component renders a 540x960 still ($n_comp)"
fi

# ------------------------------------------------------------------------------------------------ 3. frame-match
if want 3; then
  section "3. frame-match against the style's numbers and the reference strips"
  bash pipeline/bin/frame-match >/tmp/m9-fm.txt 2>&1; rc=$?
  tail -3 /tmp/m9-fm.txt
  assert_rc 0 $rc "frame-match passes every component"
  FM="$LIB/gallery/frame-match.md"; FMJ="$LIB/gallery/frame-match.json"
  assert_file "$FM" "frame-match.md written"
  assert_file "$FMJ" "frame-match.json written"
  python - "$FMJ" "$LIB" <<'EOF' >/tmp/m9-fm2.txt
import json, os, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig")); lib = sys.argv[2]
res = {r["id"]: r for r in d["results"]}
comps = sorted(f[:-5] for f in os.listdir(os.path.join(lib, "compositions")) if f.endswith(".html"))
cands = sorted(f[:-5] for f in os.listdir(os.path.join(lib, "candidates")) if f.endswith(".html")) if os.path.isdir(os.path.join(lib, "candidates")) else []
missing = [c for c in comps if c not in res]
failing = [c for c in comps if c in res and not res[c]["pass"]]
print("covered", "ok" if not missing else str(missing))
print("approved-pass", "ok" if not failing else str(failing))
md = open(os.path.join(lib, "gallery", "frame-match.md"), encoding="utf-8").read()
print("md-rows", "ok" if all(("| %s |" % c) in md for c in comps) else "missing rows")
print("candidates-listed", "ok" if all(c in md for c in cands) else str(cands))
with_strip = sum(1 for r in d["results"] if (r["correlation"].get("best") or {}).get("r") is not None)
print("strips", with_strip)
EOF
  cat /tmp/m9-fm2.txt
  assert_grep "^covered ok" /tmp/m9-fm2.txt "every component in compositions/ was measured"
  assert_grep "^approved-pass ok" /tmp/m9-fm2.txt "every component in compositions/ passes"
  assert_grep "^md-rows ok" /tmp/m9-fm2.txt "frame-match.md has a row per component"
  assert_grep "^candidates-listed ok" /tmp/m9-fm2.txt "the candidates (if any) are listed with their numbers"
  if [ -d styles/paper-cards/analysis ]; then
    assert_true "the reference strips were correlated (analysis/ exists on this PC)" test "$(grep '^strips' /tmp/m9-fm2.txt | cut -d' ' -f2)" -ge 15
  fi
  # the gallery page with one still per component
  bash pipeline/bin/gallery --no-stills >/dev/null 2>&1; rc=$?
  assert_rc 0 $rc "the gallery page builds"
  G="$LIB/gallery/index.html"
  assert_file "$G" "motion-lib/gallery/index.html exists"
  python - "$LIB/catalog.json" "$G" "$LIB" <<'EOF' >/tmp/m9-gal.txt
import json, os, sys
cat = json.load(open(sys.argv[1], encoding="utf-8-sig")); g = open(sys.argv[2], encoding="utf-8").read(); lib = sys.argv[3]
missing = [c["id"] for c in cat["components"] if ("stills/%s.png" % c["id"]) not in g or not os.path.isfile(os.path.join(lib, "gallery", "stills", c["id"] + ".png"))]
players = [c["id"] for c in cat["components"] if not os.path.isfile(os.path.join(lib, "gallery", "play", c["id"] + ".html"))]
print("stills", "ok" if not missing else str(missing))
print("players", "ok" if not players else str(players))
EOF
  assert_grep "^stills ok" /tmp/m9-gal.txt "the gallery shows one still per component"
  assert_grep "^players ok" /tmp/m9-gal.txt "the gallery has a player per component"
fi

# ------------------------------------------------------------------------------------------------ 4. golden
if want 4; then
  section "4. the golden reel"
  PLAN="golden/test-idea/plan.json"; VO="pipeline/tests/fixtures/runs/test-idea/08-voiceover/vo.wav"
  if [ ! -f "$VO" ]; then
    fail "the frozen voice $VO is missing: run M7_SECTIONS=3 bash pipeline/tests/test-m7.sh once"
  else
    bash pipeline/bin/render-golden --make-plan >/tmp/m9-golden.txt 2>&1; rc=$?
    tail -5 /tmp/m9-golden.txt
    assert_rc 0 $rc "render-golden builds, checks, renders and probes clean"
    assert_file "$PLAN" "golden/test-idea/plan.json exists"
    assert_true "plan.json validates against pipeline/stages/09-plan/schema.json" python "$VALIDATE" pipeline/stages/09-plan/schema.json "$PLAN"
    assert_file golden/test-idea/golden.mp4 "golden.mp4 rendered"
    assert_file golden/test-idea/contact-sheet.png "the contact sheet exists"
    assert_file golden/test-idea/README.md "README.md exists"
    assert_file golden/test-idea/project/index.html "the project exists"
    assert_eq "$(json_get golden/test-idea/check.json ok)" "true" "npx hyperframes check passed on the golden project"
    probe="$(ffprobe -v error -show_entries stream=codec_type,width,height,r_frame_rate:format=duration -of json golden/test-idea/golden.mp4)"
    want="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$VO")"
    python - "$probe" "$want" <<'EOF' >/tmp/m9-probe.txt
import json, sys
d = json.loads(sys.argv[1]); want = float(sys.argv[2])
v = next(s for s in d["streams"] if s["codec_type"] == "video")
num, den = v["r_frame_rate"].split("/")
print("size", "ok" if (v["width"], v["height"]) == (1080, 1920) else "%sx%s" % (v["width"], v["height"]))
print("fps", "ok" if abs(float(num) / float(den) - 30) < 0.01 else v["r_frame_rate"])
dur = float(d["format"]["duration"])
print("duration", "ok" if abs(dur - want) <= 0.2 else "%.2f vs %.2f" % (dur, want))
print("audio", "ok" if any(s["codec_type"] == "audio" for s in d["streams"]) else "none")
EOF
    cat /tmp/m9-probe.txt
    assert_grep "^size ok" /tmp/m9-probe.txt "golden.mp4 is 1080x1920"
    assert_grep "^fps ok" /tmp/m9-probe.txt "golden.mp4 is 30 fps"
    assert_grep "^duration ok" /tmp/m9-probe.txt "golden.mp4 lasts as long as vo.wav (within 0.2 s)"
    assert_grep "^audio ok" /tmp/m9-probe.txt "golden.mp4 has an audio stream"
    python - "$PLAN" <<'EOF' >/tmp/m9-plan.txt
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8-sig"))
cta = next(s for s in p["scenes"] if s["id"] == p["branding"]["cta_scene"])
kinds = {c["component"]: c for c in cta["components"]}
print("dm", "ok" if "dm-card" in kinds and kinds["dm-card"]["props"].get("avatar") == "brand/mark/avatar-dark.png" else "missing")
print("lockup", "ok" if "end-card" in kinds and kinds["end-card"]["props"].get("lockup", "").startswith("brand/lockup/") else "missing")
outside = [c["id"] for s in p["scenes"] if s["id"] != cta["id"] for c in s["components"] for v in c["props"].values() if isinstance(v, str) and v.startswith("brand/")]
print("outside", "ok" if not outside else str(outside))
hook = next(s for s in p["scenes"] if s["beat_type"] == "hook")
print("hook-set-piece", "ok" if hook.get("hook_set_piece") and any(c["start_ms"] >= 2000 for c in hook["components"]) else "none")
print("captions", "ok" if p["captions"] and all(1 <= len(c["words"]) <= 4 for c in p["captions"]) else "bad")
EOF
    cat /tmp/m9-plan.txt
    assert_grep "^dm ok" /tmp/m9-plan.txt "the CTA scene has the FlashFX DM card with avatar-dark.png"
    assert_grep "^lockup ok" /tmp/m9-plan.txt "the CTA scene's end card carries a FlashFX lockup"
    assert_grep "^outside ok" /tmp/m9-plan.txt "no FlashFX asset outside the CTA (the solution is not FlashFX)"
    assert_grep "^hook-set-piece ok" /tmp/m9-plan.txt "the hook has a set piece landing in the breath"
    assert_grep "^captions ok" /tmp/m9-plan.txt "caption chunks of 1 to 4 words"
  fi
fi

# ------------------------------------------------------------------------------------------------ 5. webgl
if want 5; then
  section "5. the WebGL test"
  bash pipeline/bin/webgl-test --out "$LIB/webgl.json" >/tmp/m9-webgl.txt 2>&1; rc=$?
  tail -3 /tmp/m9-webgl.txt
  assert_rc 0 $rc "webgl-test runs"
  assert_file "$LIB/webgl.json" "motion-lib/webgl.json written"
  assert_true "webgl.json has a verdict" test -n "$(json_get "$LIB/webgl.json" webgl)"
  assert_true "webgl.json names the harness mode" test -n "$(json_get "$LIB/webgl.json" harness_gpu)"
  assert_grep "summary" "$LIB/webgl.json" "webgl.json has a summary line"
fi

# ------------------------------------------------------------------------------------------------ 6. em dashes
if want 6; then
  section "6. no em dash in the files M9 wrote"
  files=(pipeline/lib/tokens.py pipeline/lib/tokens.schema.json pipeline/bin/build-tokens pipeline/bin/frame-match pipeline/bin/gallery pipeline/bin/render-golden
         pipeline/bin/webgl-test pipeline/bin/setup-node pipeline/stages/09-plan/schema.json styles/paper-cards/tokens.json motion-lib/catalog.json
         motion-lib/index.html motion-lib/assets/paper-cards.css motion-lib/assets/paper-cards.js motion-lib/gallery/index.html motion-lib/gallery/frame-match.md)
  for f in pipeline/lib/motion/*.py motion-lib/compositions/*.html; do files+=("$f"); done
  [ -f golden/test-idea/plan.json ] && files+=(golden/test-idea/plan.json golden/test-idea/README.md)
  existing=(); for f in "${files[@]}"; do [ -f "$f" ] && existing+=("$f"); done
  no_emdash_in "no em dash in the M9 files" "${existing[@]}"
fi

test_summary
