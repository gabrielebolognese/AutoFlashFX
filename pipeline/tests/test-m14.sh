#!/usr/bin/env bash
# test-m14.sh: acceptance test for M14 (Motion grammar and energy meter, BUILD_SPEC.md section 12 and section 5, Motion and
# energy rules E0, E1, E2, E5, E6, E7; PLAN.md M14). No model call.
#   bash pipeline/tests/test-m14.sh                       everything (30 to 60 minutes: frame-match and the golden render)
#   M14_SECTIONS="1 3" bash pipeline/tests/test-m14.sh    only those sections
#
# Sections:
#   1. energy: the meter (python pipeline/lib/review energy) reproduces the reference numbers of
#      styles/paper-cards/analysis/energy.json within 1 point (the nine reference videos, when they are on this PC) and
#      fails the M13 reel (build/M13/rerun/1.mp4) on every target; the spec's numbers for that reel come out (16, 15, 1.2,
#      29, 2.8); tokens.json carries energy.targets derived from the calibration (41, 46, 3.3, 15, 2 on this PC) and
#      motion.grammar, tokens.css the --m-* variables; an Energy line in a sandbox tweaks.md overrides the targets; the
#      tokens validate and verify
#   2. the library: frame-match passes every component (the main animations still match the style's numbers and the
#      reference strips, no visible element stands still for 0.5 s, the main element's inertia lasts 2 to 4 s), every
#      component has its energy measured alone, catalog.json lists icon-3d approved with the energy fields, every element
#      component declares the hold prop, no composition keeps a tween or a curve of its own (pc-motion.js holds them all),
#      `npx hyperframes lint` and `check` pass on motion-lib/, the gallery shows the energy line
#   3. icon-3d renders with WebGL (data-webgl 1, the canvas draws) and with its CSS-extruded fallback (mode css: data-webgl
#      0, 8 to 16 depth layers, the stage draws and turns); the paper canvas's edge and ambient layers exist for three
#      seeds, stay out of every text zone over 40 s, hold no text, sit 30 to 70 percent outside the frame and move at most
#      20 px per second; the canvas registers a timeline and the project compiler mounts it seeded
#   4. the golden reel rendered again from the same plan (render-golden): it checks, renders and probes clean; its energy
#      measures beat build/M14/golden-energy-before.json on every measure, its moving share at least doubled; the numbers
#      go to golden/test-idea/energy.json
#   5. no em dash in the files M14 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M14_SECTIONS:-1 2 3 4 5}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
VALIDATE="$REPO_DIR/pipeline/bin/validate-json"
TOK="$REPO_DIR/pipeline/lib/tokens.py"
MOTION="$REPO_DIR/pipeline/lib/motion"
REVIEW="$REPO_DIR/pipeline/lib/review"
LIB="$REPO_DIR/motion-lib"
HF="npx --prefix $REPO_DIR hyperframes"
TOKENS="$REPO_DIR/styles/paper-cards/tokens.json"
ENERGY_JSON="$REPO_DIR/styles/paper-cards/analysis/energy.json"
M13_REEL="$REPO_DIR/build/M13/rerun/1.mp4"
BEFORE="$REPO_DIR/build/M14/golden-energy-before.json"

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
print("\n".join(bad)); sys.exit(1 if bad else 0)' "$@" >/tmp/m14-emdash.txt; then pass "$name"; else fail "$name (em dash in: $(tr '\n' ' ' </tmp/m14-emdash.txt))"; fi
}

# ------------------------------------------------------------------------------------------------ 1. energy
if want 1; then
  section "1. the energy meter, the calibration, the tokens"
  sandbox_init
  assert_file "$ENERGY_JSON" "styles/paper-cards/analysis/energy.json exists (the calibration)"
  if [ -d styles/paper-cards/refs/look ] && [ -f "$ENERGY_JSON" ]; then
    python "$REVIEW" energy calibrate --refs styles/paper-cards/refs --out "$SANDBOX_M/energy.json" --index styles/paper-cards/analysis/index.md >/tmp/m14-cal.txt 2>&1; rc=$?
    assert_rc 0 $rc "the meter measures the nine reference videos again"
    python - "$ENERGY_JSON" "$SANDBOX_M/energy.json" <<'EOF' >/tmp/m14-cal2.txt
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8-sig")); b = json.load(open(sys.argv[2], encoding="utf-8-sig"))
keys = ["moving_share_pct", "middle_moving_share_pct", "pixels_changing_pct", "still_share_pct", "longest_still_s"]
worst = 0.0; n = 0
for nick, row in a["videos"].items():
    other = b["videos"].get(nick)
    if not other:
        print("missing", nick); continue
    for k in keys:
        n += 1
        worst = max(worst, abs(float(row[k]) - float(other[k])))
print("videos", len(a["videos"]), "compared", n, "worst", round(worst, 3))
print("within-1", "ok" if worst <= 1.0 else "no")
print("medians", "ok" if all(abs(float(a["medians"]["look"][k]) - float(b["medians"]["look"][k])) <= 1.0 for k in keys) else "no")
print("nine", "ok" if len(a["videos"]) == 9 else str(len(a["videos"])))
EOF
    cat /tmp/m14-cal2.txt
    assert_grep "^within-1 ok" /tmp/m14-cal2.txt "every reference number is reproduced within 1 point"
    assert_grep "^medians ok" /tmp/m14-cal2.txt "the look medians are reproduced within 1 point"
    assert_grep "^nine ok" /tmp/m14-cal2.txt "energy.json holds the nine references"
  else
    printf 'the reference videos are not on this PC (styles/paper-cards/refs/): the calibration check is skipped\n'
  fi
  if [ -f "$M13_REEL" ]; then
    python "$REVIEW" energy "$M13_REEL" --out "$SANDBOX_M/m13.json" >/tmp/m14-m13.txt 2>&1; rc=$?
    assert_rc 1 $rc "the M13 reel fails the energy targets (exit 1)"
    python - "$SANDBOX_M/m13.json" <<'EOF' >/tmp/m14-m13b.txt
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig"))
c = d["check"]["checks"]; w = d["whole"]
print("every-target", "ok" if len(c) == 5 and all(not v["ok"] for v in c.values()) else str({k: v["ok"] for k, v in c.items()}))
spec = {"moving_share_pct": (16, 1.5), "middle_moving_share_pct": (15, 1.5), "pixels_changing_pct": (1.2, 0.3), "still_share_pct": (29, 4), "longest_still_s": (2.8, 0.3)}
print("spec-numbers", "ok" if all(abs(w[k] - v[0]) <= v[1] for k, v in spec.items()) else str({k: w[k] for k in spec}))
print("targets", d["targets"])
EOF
    cat /tmp/m14-m13b.txt
    assert_grep "^every-target ok" /tmp/m14-m13b.txt "the M13 reel misses every one of the five targets"
    assert_grep "^spec-numbers ok" /tmp/m14-m13b.txt "the M13 reel measures what the spec says (16, 15, 1.2, 29, 2.8)"
  else
    printf 'build/M13/rerun/1.mp4 is not on this PC: the M13 reel check is skipped\n'
  fi
  # the tokens
  assert_true "the repo's tokens.json is current" bash pipeline/bin/build-tokens --check
  assert_true "tokens.json validates against the schema" python "$VALIDATE" pipeline/lib/tokens.schema.json "$TOKENS"
  assert_true "tokens.json verifies against the sources" bash pipeline/bin/build-tokens --verify
  assert_eq "$(json_get "$TOKENS" energy.calibration.source)" "analysis/energy.json" "the targets come from the calibration"
  python - "$TOKENS" "$ENERGY_JSON" <<'EOF' >/tmp/m14-tok.txt
import json, math, sys
t = json.load(open(sys.argv[1], encoding="utf-8-sig")); e = json.load(open(sys.argv[2], encoding="utf-8-sig"))
look = e["medians"]["look"]; tg = t["energy"]["targets"]
want = {"moving_share_pct": int(round(look["moving_share_pct"] * 0.7)), "middle_moving_share_pct": int(round(look["middle_moving_share_pct"] * 0.7)),
        "pixels_changing_pct": round(look["pixels_changing_pct"] * 0.7, 1), "still_share_pct": int(math.ceil(look["still_share_pct"] / 5.0 - 1e-9) * 5),
        "longest_still_s": round(math.ceil(look["longest_still_s"] / 0.5 - 1e-9) * 0.5, 1)}
print("derived", "ok" if all(abs(float(tg[k]) - float(v)) < 1e-6 for k, v in want.items()) else str((tg, want)))
print("same-as-energy-json", "ok" if all(abs(float(tg[k]) - float(e["targets"][k])) < 1e-6 for k in want) else str(e["targets"]))
g = t["motion"]["grammar"]
print("grammar", "ok" if g["inertia"]["range_s"] == [2, 4] and g["hold"]["calm"]["drift_px_s"] == 2 and g["hold"]["lively"]["drift_px_s"] == 8 and g["main"]["perspective_px"] == 1400 and g["edges"]["max_speed_px_s"] == 20 else "no")
print("zones", "ok" if set(g["text_zones"]) == {"caption", "hook", "endcard"} else str(g["text_zones"]))
EOF
  cat /tmp/m14-tok.txt
  assert_grep "^derived ok" /tmp/m14-tok.txt "energy.targets follow the 70 percent rule on the look medians"
  assert_grep "^same-as-energy-json ok" /tmp/m14-tok.txt "energy.json's targets agree with tokens.json"
  assert_grep "^grammar ok" /tmp/m14-tok.txt "motion.grammar carries the spec's values (inertia 2 to 4 s, holds 2 to 8 px/s, perspective 1400, edges 20 px/s)"
  assert_grep "^zones ok" /tmp/m14-tok.txt "motion.grammar.text_zones has the caption band, the hook header and the end card"
  CSS="$LIB/assets/tokens.css"
  assert_grep "m-perspective: 1400;" "$CSS" "tokens.css exposes the perspective"
  assert_grep "m-hold-normal-drift: 4;" "$CSS" "tokens.css exposes the hold speeds"
  assert_grep "m-zone-caption: [0-9]" "$CSS" "tokens.css exposes the text zones"
  assert_grep "m-safe-bottom: 1440;" "$CSS" "tokens.css exposes the safe edges for the hold's room"
  # the Energy override line
  mkdir -p "$SANDBOX/styles/paper-cards"
  cp styles/paper-cards/style.md styles/paper-cards/tweaks.md "$SANDBOX/styles/paper-cards/"
  printf '\n- **Energy:** moving 45, middle 50, pixels 3.5, still 12, longest 1.5\n' >> "$SANDBOX/styles/paper-cards/tweaks.md"
  bash pipeline/bin/build-tokens --style-dir "$SANDBOX_M/styles/paper-cards" --out "$SANDBOX_M/tokens.json" --css "$SANDBOX_M/tokens.css" >/dev/null 2>&1; rc=$?
  assert_rc 0 $rc "a sandbox build with an Energy line in tweaks.md"
  assert_eq "$(json_get "$SANDBOX_M/tokens.json" energy.targets.moving_share_pct)" "45" "the Energy line overrides the moving share target"
  assert_eq "$(json_get "$SANDBOX_M/tokens.json" energy.targets.longest_still_s)" "1.5" "the Energy line overrides the longest still target"
  assert_eq "$(json_get "$SANDBOX_M/tokens.json" energy.calibration.source)" "spec" "without a calibration file the targets start from the spec's numbers"
  assert_true "the sandbox tokens validate" python "$VALIDATE" pipeline/lib/tokens.schema.json "$SANDBOX_M/tokens.json"
  assert_true "the sandbox tokens verify against the sources" python "$TOK" verify --style-dir "$SANDBOX_M/styles/paper-cards" --tokens "$SANDBOX_M/tokens.json"
  sandbox_cleanup
fi

# ------------------------------------------------------------------------------------------------ 2. the library
if want 2; then
  section "2. the library on pc-motion.js: frame-match, the life checks, the energy of each component"
  bash pipeline/bin/frame-match >/tmp/m14-fm.txt 2>&1; rc=$?
  tail -3 /tmp/m14-fm.txt
  assert_rc 0 $rc "frame-match passes every component (the style's numbers, the strips, the life checks)"
  FMJ="$LIB/gallery/frame-match.json"
  python - "$FMJ" "$LIB" <<'EOF' >/tmp/m14-fm2.txt
import json, os, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig")); lib = sys.argv[2]
res = {r["id"]: r for r in d["results"]}
comps = sorted(f[:-5] for f in os.listdir(os.path.join(lib, "compositions")) if f.endswith(".html"))
print("covered", "ok" if all(c in res for c in comps) else str([c for c in comps if c not in res]))
print("pass", "ok" if all(res[c]["pass"] for c in comps if c in res) else str([c for c in comps if c in res and not res[c]["pass"]]))
static = [c for c in comps if c in res and any(x["check"].startswith("life: never static") and not x["ok"] for x in res[c]["checks"])]
print("never-static", "ok" if not static else str(static))
with_life = [c for c in comps if c in res and any(x["check"].startswith("life:") for x in res[c]["checks"])]
print("life-checked", len(with_life), "of", len(comps))
inertia = [(c, x["measured"]) for c in comps if c in res for x in res[c]["checks"] if x["check"].startswith("life: inertia")]
bad = [(c, m) for c, m in inertia if m is None or not (1.65 <= float(m) <= 4.35)]
print("inertia", "ok" if inertia and not bad else str(bad), "measured on", len(inertia), "components")
energy = [c for c in comps if c in res and (res[c].get("energy") or {}).get("moving_share_pct") is not None]
print("energy", "ok" if len(energy) == len(comps) else str([c for c in comps if c not in energy]))
frames = min(r.get("frames_measured", 0) for r in res.values())
print("four-seconds", "ok" if frames >= 121 else str(frames))
main_ok = [c for c in comps if c in res and all(x["ok"] for x in res[c]["checks"] if not x["check"].startswith("life:"))]
print("main-animations", "ok" if len(main_ok) == len(comps) else str([c for c in comps if c not in main_ok]))
print("icon-3d", "ok" if "icon-3d" in res and res["icon-3d"]["pass"] else "no")
EOF
  cat /tmp/m14-fm2.txt
  assert_grep "^covered ok" /tmp/m14-fm2.txt "every component in compositions/ was measured"
  assert_grep "^pass ok" /tmp/m14-fm2.txt "every component passes"
  assert_grep "^main-animations ok" /tmp/m14-fm2.txt "every main animation still frame-matches its reference numbers"
  assert_grep "^never-static ok" /tmp/m14-fm2.txt "no visible element stands still for 0.5 s in any component rendered alone for 4 s"
  assert_grep "^inertia ok" /tmp/m14-fm2.txt "the inertia after the landing lasts 2 to 4 s on every main element"
  assert_grep "^energy ok" /tmp/m14-fm2.txt "every component has its energy measured alone"
  assert_grep "^four-seconds ok" /tmp/m14-fm2.txt "every component was measured for at least 4 s"
  assert_grep "^icon-3d ok" /tmp/m14-fm2.txt "icon-3d passes frame-match"
  CAT="$LIB/catalog.json"
  assert_true "the catalog agrees with the component files" python "$MOTION" catalog
  python - "$CAT" <<'EOF' >/tmp/m14-cat.txt
import json, sys
cat = json.load(open(sys.argv[1], encoding="utf-8-sig"))
by = {c["id"]: c for c in cat["components"]}
i3 = by.get("icon-3d")
print("icon3d", "ok" if i3 and i3["status"] == "approved" and i3.get("fallback") == "css" and i3["kind"] == "3d" and "hook" in i3["beat_types"] else "no")
no_hold = [c["id"] for c in cat["components"] if c["id"] not in ("paper-canvas",) and not any(p["id"] == "hold" for p in c["props"])]
print("hold-prop", "ok" if not no_hold else str(no_hold))
canvas = by.get("paper-canvas")
print("canvas-props", "ok" if canvas and {p["id"] for p in canvas["props"]} >= {"seed", "duration", "layers", "edges", "ambient"} else "no")
noe = [c["id"] for c in cat["components"] if not isinstance(c.get("energy"), dict) or c["energy"].get("moving_share_pct") is None]
print("energy-in-catalog", "ok" if not noe else str(noe))
print("count", len(cat["components"]))
EOF
  cat /tmp/m14-cat.txt
  assert_grep "^icon3d ok" /tmp/m14-cat.txt "catalog.json lists icon-3d approved, kind 3d with a css fallback, allowed in the hook"
  assert_grep "^hold-prop ok" /tmp/m14-cat.txt "every element component declares the hold prop"
  assert_grep "^canvas-props ok" /tmp/m14-cat.txt "the canvas declares seed, duration, layers, edges and ambient"
  assert_grep "^energy-in-catalog ok" /tmp/m14-cat.txt "catalog.json carries every component's energy measures"
  # no component keeps a tween or a curve of its own: the phases and curves are pc-motion.js's
  if grep -l -E 'tl\.(to|fromTo|from)\(|gsap\.(to|fromTo|from)\(|onUpdate' "$LIB"/compositions/*.html >/tmp/m14-tweens.txt 2>/dev/null; then
    fail "no composition keeps a tween of its own (found in: $(tr '\n' ' ' </tmp/m14-tweens.txt))"
  else
    pass "no composition keeps a tween or an onUpdate of its own (pc-motion.js holds the phases and the curves)"
  fi
  n_pcm="$(grep -l 'assets/pc-motion.js' "$LIB"/compositions/*.html | wc -l | tr -d ' ')"
  n_all="$(ls "$LIB"/compositions/*.html | wc -l | tr -d ' ')"
  assert_eq "$n_pcm" "$n_all" "every component loads pc-motion.js ($n_all)"
  for fn in "PCM.life" "PCM.glide" "PCM.canvas" "PCM.idle" "PCM.depth" "PCM.exit" "PCM.countUp" "PCM.typeInto"; do
    assert_grep "$fn = function" "$LIB/assets/pc-motion.js" "pc-motion.js defines $fn"
  done
  # lint and check, the gallery
  lint="$(hf_json lint --json "$LIB")"
  assert_eq "$(printf '%s' "$lint" | python -c 'import json, sys; print(json.load(sys.stdin).get("errorCount"))')" "0" "npx hyperframes lint: no errors on motion-lib/"
  bash pipeline/bin/gallery --no-stills >/dev/null 2>&1; rc=$?
  assert_rc 0 $rc "the gallery page builds"
  assert_grep "Energy \(alone, 4 s\):" "$LIB/gallery/index.html" "the gallery shows each component's energy measures"
  assert_not_grep "data-no-timeline" "$LIB/index.html" "the showreel's canvas host is driven by the runtime (no data-no-timeline)"
  check="$(cd "$LIB" && hf_json check --json --timeout 120000 --samples 12)"
  assert_eq "$(printf '%s' "$check" | python -c 'import json, sys; d = json.load(sys.stdin); print("true" if d.get("ok") else "false")')" "true" "npx hyperframes check --json passes on motion-lib/"
fi

# ------------------------------------------------------------------------------------------------ 3. icon-3d, the canvas layers
if want 3; then
  section "3. icon-3d with WebGL and with its fallback; the edge and ambient layers out of every text zone"
  python - "$REPO_DIR" <<'EOF' >/tmp/m14-i3.txt
import json, os, sys
repo = sys.argv[1]
sys.path.insert(0, os.path.join(repo, "pipeline", "lib"))
from motion import common, harness
from PIL import Image
lib = common.motion_lib_dir()
toks = common.tokens()
zones = toks["motion"]["grammar"]["text_zones"]
comp = common.parse_component(os.path.join(lib, "compositions", "icon-3d.html"))
canvas = common.parse_component(os.path.join(lib, "compositions", "paper-canvas.html"))
gpu = "auto"
wg = os.path.join(lib, "webgl.json")
if os.path.isfile(wg):
    gpu = common.load_json(wg).get("harness_gpu", "auto")

def drew(h, box):
    tmp = os.path.join(lib, ".harness", "m14-shot.png")
    h.page.screenshot(path=tmp)
    im = Image.open(tmp).convert("RGB")
    region = im.crop((box[0], box[1], box[0] + box[2], box[1] + box[3]))
    paper = im.crop((60, 200, 260, 400))
    ref = list(paper.getdata()); px = list(region.getdata())
    mean = tuple(sum(c[i] for c in ref) / len(ref) for i in range(3))
    far = sum(1 for c in px if sum(abs(c[i] - mean[i]) for i in range(3)) > 60)
    return far / max(1, len(px))

with harness.Harness(lib=lib, gpu=gpu, tag="-m14") as h:
    # WebGL
    h.open(comp, {"icon": "bolt", "enter_at": 0.0})
    h.page.evaluate(harness.SEEK_JS, {"id": "icon-3d", "t": 1.5}); h.page.wait_for_timeout(80)
    attr = h.page.evaluate("() => document.getElementById('root').getAttribute('data-webgl')")
    share = drew(h, (290, 560, 500, 500))
    print("webgl-attr", attr, "drawn", round(share, 4))
    print("webgl", "ok" if attr == "1" and share > 0.03 else "no")
    # the fallback
    h.open(comp, {"icon": "bolt", "enter_at": 0.0, "mode": "css"})
    h.page.evaluate(harness.SEEK_JS, {"id": "icon-3d", "t": 1.5}); h.page.wait_for_timeout(80)
    attr2 = h.page.evaluate("() => document.getElementById('root').getAttribute('data-webgl')")
    layers = h.page.evaluate("() => document.querySelectorAll('#i3-css .i3-layer').length")
    share2 = drew(h, (290, 560, 500, 500))
    res = h.page.evaluate(harness.MEASURE_JS, {"id": "icon-3d", "times": [i / 30 for i in range(0, 121)], "selectors": ["#i3-css"]})
    rows = res["rows"]
    runs = 0; worst = 0
    for a, b in zip(rows, rows[1:]):
        ma, mb = a.get("#i3-css"), b.get("#i3-css")
        same = ma and mb and ma["ry"] == mb["ry"] and ma["cy"] == mb["cy"] and ma["scale"] == mb["scale"]
        runs = runs + 1 if same else 0
        worst = max(worst, runs)
    print("css-attr", attr2, "layers", layers, "drawn", round(share2, 4), "longest unchanged run", worst)
    print("fallback", "ok" if attr2 == "0" and 8 <= layers <= 16 and share2 > 0.03 and worst < 15 else "no")
    # the canvas layers
    bad_zone = []; with_text = []; outside_bad = []; speed_bad = []; counts = []
    for seed in (7, 1234, 98765):
        h.open(canvas, {"seed": seed, "duration": 60})
        info = h.page.evaluate("""(args) => {
          const tl = window.__timelines["paper-canvas"];
          const out = { registered: !!tl, duration: tl ? tl.duration() : 0, samples: [] };
          const sels = Array.from(document.querySelectorAll('#paper-edges .pc-edge, #paper-ambient .pc-ambient'));
          for (const t of args.times) {
            if (tl) tl.seek(t, false);
            const rows = sels.map(el => { const r = el.getBoundingClientRect(); return { id: el.id, edge: el.classList.contains('pc-edge'), x: r.left, y: r.top, w: r.width, h: r.height, text: (el.textContent || '').trim() }; });
            out.samples.push({ t: t, rows: rows });
          }
          return out;
        }""", {"times": [0, 2, 5, 10, 20, 40] + [i / 30 for i in range(0, 61)]})
        counts.append((seed, sum(1 for r in info["samples"][0]["rows"] if r["edge"]), sum(1 for r in info["samples"][0]["rows"] if not r["edge"])))
        if not info["registered"]:
            bad_zone.append((seed, "no timeline"))
        for s in info["samples"][:6]:
            for r in s["rows"]:
                if r["text"]:
                    with_text.append((seed, r["id"]))
                for name, z in zones.items():
                    if r["x"] < z["x"] + z["w"] and r["x"] + r["w"] > z["x"] and r["y"] < z["y"] + z["h"] and r["y"] + r["h"] > z["y"]:
                        bad_zone.append((seed, s["t"], r["id"], name))
                if r["edge"]:
                    inside = max(0, min(1080, r["x"] + r["w"]) - max(0, r["x"]))
                    outside = 1 - inside / max(1, r["w"])
                    if not (0.22 <= outside <= 0.78):
                        outside_bad.append((seed, s["t"], r["id"], round(outside, 2)))
        # speeds over the first 2 s, frame by frame
        seq = info["samples"][6:]
        ids = [r["id"] for r in seq[0]["rows"]]
        for k, rid in enumerate(ids):
            for a, b in zip(seq, seq[1:]):
                ra, rb = a["rows"][k], b["rows"][k]
                v = ((rb["x"] + rb["w"] / 2 - ra["x"] - ra["w"] / 2) ** 2 + (rb["y"] + rb["h"] / 2 - ra["y"] - ra["h"] / 2) ** 2) ** 0.5 * 30
                limit = 20 if ra["edge"] else 12
                if v > limit:
                    speed_bad.append((seed, rid, round(v, 1)))
    # the review and the transients: the DM card's texts while it arrives, once landed, while it leaves
    from review import mechanical
    dm = common.parse_component(os.path.join(lib, "compositions", "dm-card.html"))
    h.open(dm, {"enter_at": 0.0, "exit": "fall", "exit_at": 2.5})
    rv = h.page.evaluate(mechanical.REVIEW_JS, {"id": "dm-card", "times": [0.1, 0.5, 1.0, 2.0, 2.6]})
    by_t = {}
    for row in rv["rows"]:
        by_t[row["t"]] = [t for t in row["texts"] if t["opacity"] >= 0.5]
    arriving = by_t.get(0.1, []) and by_t.get(0.5, []) and all(t["transient"] == "main" for t in by_t[0.1] + by_t[0.5])
    first_scale = min((t["scale"] for t in by_t.get(0.1, [])), default=0)
    settled = by_t.get(1.0, []) and by_t.get(2.0, []) and all(t["transient"] == "" and t["scale"] >= 0.999 for t in by_t[1.0] + by_t[2.0])
    small = [t for t in by_t.get(1.0, []) if t["size"] <= 28.5]
    leaving = by_t.get(2.6, []) and all(t["transient"] == "exit" for t in by_t[2.6])
    print("review-rows", {k: [(t["text"][:9], round(t["scale"], 3), t["transient"]) for t in v] for k, v in by_t.items()})
    print("review-arriving", "ok" if arriving and 0.8 <= first_scale <= 0.87 else "no")
    print("review-settled", "ok" if settled and small and all(t["size"] * t["scale"] >= 27.9 for t in small) else "no")
    print("review-leaving", "ok" if leaving else "no")
    # the room rule: the DM card dropped in at the CTA's y (its bottom 2 px above the safe bottom) keeps its message
    # above the safe bottom for 8 s (the drift fits the room), while the same card at y 700 drifts on
    h.open(dm, {"enter_at": 0.0, "y": 1266, "enter": "drop", "hold": "normal"})  # the CTA's card: a drop, so the inertia and the drift point down
    rv2 = h.page.evaluate(mechanical.REVIEW_JS, {"id": "dm-card", "times": [1.0, 4.0, 8.0]})
    bottoms = [max([t["y"] + t["h"] for t in row["texts"] if t["opacity"] >= 0.5] or [0]) for row in rv2["rows"]]
    h.open(dm, {"enter_at": 0.0, "y": 700, "enter": "drop", "hold": "normal"})
    mv = h.page.evaluate(harness.MEASURE_JS, {"id": "dm-card", "times": [1.0, 8.0], "selectors": ["#dm"]})
    ty = [r["#dm"]["ty"] for r in mv["rows"] if r.get("#dm")]
    print("room-rows", [round(b, 1) for b in bottoms], [round(v, 1) for v in ty])
    print("room-hold", "ok" if bottoms and 1380 <= max(bottoms) <= 1444 else "no")
    print("room-free", "ok" if len(ty) == 2 and ty[1] - ty[0] >= 20 else "no")  # downward: 16 px of inertia plus 4 px per second
    print("counts", counts)
    print("layers-present", "ok" if all(e >= 4 and a >= 8 for _, e, a in counts) else "no")
    print("zones-clear", "ok" if not bad_zone else str(bad_zone[:6]))
    print("no-text", "ok" if not with_text else str(with_text[:4]))
    print("edges-outside", "ok" if not outside_bad else str(outside_bad[:6]))
    print("speeds", "ok" if not speed_bad else str(speed_bad[:6]))
EOF
  cat /tmp/m14-i3.txt
  assert_grep "^webgl ok" /tmp/m14-i3.txt "icon-3d renders with WebGL (data-webgl 1, the canvas draws)"
  assert_grep "^fallback ok" /tmp/m14-i3.txt "icon-3d renders with its CSS-extruded fallback (8 to 16 layers, drawn, turning)"
  assert_grep "^layers-present ok" /tmp/m14-i3.txt "the canvas builds its edge and ambient layers for three seeds"
  assert_grep "^zones-clear ok" /tmp/m14-i3.txt "the edge and ambient layers stay out of every text zone over 40 s"
  assert_grep "^no-text ok" /tmp/m14-i3.txt "the layers hold no text"
  assert_grep "^edges-outside ok" /tmp/m14-i3.txt "every edge element sits 30 to 70 percent outside the frame (a few px of sway allowed)"
  assert_grep "^speeds ok" /tmp/m14-i3.txt "the edge layer moves at most 20 px per second, the ambient layer slower"
  assert_grep "^review-arriving ok" /tmp/m14-i3.txt "the review sees the DM card's texts arriving for the combined animation (data-pcm-main), the scale read in 3D (0.85 at the first frame)"
  assert_grep "^review-settled ok" /tmp/m14-i3.txt "once landed the texts are judged, their scale at least 1 (the inertia grows): the 28 px labels read 28 px or more"
  assert_grep "^review-leaving ok" /tmp/m14-i3.txt "the review sees the texts leaving during the exit (data-pcm-exit)"
  assert_grep "^room-hold ok" /tmp/m14-i3.txt "the hold fits the room: the DM card at the CTA's y keeps its message above the safe bottom for 8 s"
  assert_grep "^room-free ok" /tmp/m14-i3.txt "the same card with room below drifts on (20 px or more between 1 and 8 s)"
fi

# ------------------------------------------------------------------------------------------------ 4. the golden reel
if want 4; then
  section "4. the golden reel rendered again with the new library (same plan)"
  VO="pipeline/tests/fixtures/runs/test-idea/08-voiceover/vo.wav"
  if [ ! -f "$VO" ]; then
    fail "the frozen voice $VO is missing: run M7_SECTIONS=3 bash pipeline/tests/test-m7.sh once"
  elif [ ! -f "$BEFORE" ]; then
    fail "build/M14/golden-energy-before.json is missing (the old golden's numbers)"
  else
    plan_before="$(python -c 'import hashlib, sys; print(hashlib.sha1(open(sys.argv[1], "rb").read()).hexdigest())' golden/test-idea/plan.json)"
    bash pipeline/bin/render-golden >/tmp/m14-golden.txt 2>&1; rc=$?
    tail -4 /tmp/m14-golden.txt
    assert_rc 0 $rc "render-golden builds, checks, renders and probes clean with the new library"
    plan_after="$(python -c 'import hashlib, sys; print(hashlib.sha1(open(sys.argv[1], "rb").read()).hexdigest())' golden/test-idea/plan.json)"
    assert_eq "$plan_after" "$plan_before" "the plan did not change (the same plan, the new library)"
    assert_eq "$(json_get golden/test-idea/check.json ok)" "true" "npx hyperframes check passed on the golden project"
    python "$REVIEW" energy golden/test-idea/golden.mp4 --plan golden/test-idea/plan.json --out golden/test-idea/energy.json >/tmp/m14-genergy.txt 2>&1
    head -1 /tmp/m14-genergy.txt
    python - "$BEFORE" golden/test-idea/energy.json <<'EOF' >/tmp/m14-gcmp.txt
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8-sig"))["whole"]; b = json.load(open(sys.argv[2], encoding="utf-8-sig"))["whole"]
better = {"moving_share_pct": b["moving_share_pct"] > a["moving_share_pct"], "middle_moving_share_pct": b["middle_moving_share_pct"] > a["middle_moving_share_pct"],
          "pixels_changing_pct": b["pixels_changing_pct"] > a["pixels_changing_pct"], "still_share_pct": b["still_share_pct"] < a["still_share_pct"],
          "longest_still_s": b["longest_still_s"] < a["longest_still_s"]}
print("before", {k: a[k] for k in better}); print("after", {k: b[k] for k in better})
print("every-measure", "ok" if all(better.values()) else str([k for k, v in better.items() if not v]))
print("doubled", "ok" if b["moving_share_pct"] >= 2 * a["moving_share_pct"] else f"{b['moving_share_pct']} vs 2 x {a['moving_share_pct']}")
EOF
    cat /tmp/m14-gcmp.txt
    assert_grep "^every-measure ok" /tmp/m14-gcmp.txt "the re-rendered golden measures higher than before on every energy measure"
    assert_grep "^doubled ok" /tmp/m14-gcmp.txt "its moving share at least doubled"
    assert_file golden/test-idea/energy.json "golden/test-idea/energy.json written"
    assert_file golden/test-idea/contact-sheet.png "the contact sheet exists"
    # the compiler mounts the canvas seeded and driven, and pc-motion.js travels with the project
    python - "$REPO_DIR" <<'EOF' >/tmp/m14-host.txt
import os, sys, re
repo = sys.argv[1]
idx = open(os.path.join(repo, "golden", "test-idea", "project", "index.html"), encoding="utf-8").read()
m = re.search(r'<div id="paper-canvas"[^>]*>', idx)
host = m.group(0) if m else ""
print("host", "ok" if host and "data-no-timeline" not in host and '"seed"' in host and '"duration"' in host else host[:200] or "no canvas host")
print("pcm", "ok" if os.path.isfile(os.path.join(repo, "golden", "test-idea", "project", "assets", "pc-motion.js")) else "missing")
EOF
    cat /tmp/m14-host.txt
    assert_grep "^host ok" /tmp/m14-host.txt "the golden project's canvas host is seeded, runs the reel's length and has a timeline"
    assert_grep "^pcm ok" /tmp/m14-host.txt "the golden project carries pc-motion.js"
  fi
fi

# ------------------------------------------------------------------------------------------------ 5. em dashes
if want 5; then
  section "5. no em dash in the files M14 wrote"
  files=(pipeline/lib/review/energy.py pipeline/lib/review/__main__.py pipeline/lib/tokens.py pipeline/lib/tokens.schema.json pipeline/lib/motion/framematch.py
         pipeline/lib/motion/expectations.py pipeline/lib/motion/harness.py pipeline/lib/motion/catalog.py pipeline/lib/motion/gallery.py pipeline/lib/motion/golden.py
         pipeline/tests/test-m14.sh styles/paper-cards/tokens.json motion-lib/catalog.json motion-lib/assets/pc-motion.js motion-lib/assets/paper-cards.js
         motion-lib/assets/paper-cards.css motion-lib/assets/tokens.css motion-lib/gallery/frame-match.md motion-lib/index.html)
  for f in motion-lib/compositions/*.html; do files+=("$f"); done
  [ -f golden/test-idea/energy.json ] && files+=(golden/test-idea/energy.json)
  [ -f build/M14/report.md ] && files+=(build/M14/report.md)
  existing=(); for f in "${files[@]}"; do [ -f "$f" ] && existing+=("$f"); done
  no_emdash_in "no em dash in the M14 files" "${existing[@]}"
fi

test_summary
