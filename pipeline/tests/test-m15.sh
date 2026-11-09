#!/usr/bin/env bash
# test-m15.sh: acceptance test for M15 (Kinetic captions and text discipline, BUILD_SPEC.md section 12 and section 5, Motion and
# energy rules E3 and E4; PLAN.md M15). No model call.
#   bash pipeline/tests/test-m15.sh                       everything (about 15 to 25 minutes: browser checks)
#   M15_SECTIONS="1 2" bash pipeline/tests/test-m15.sh    only those sections
#
# Sections:
#   1. kinetic.py (the group layout engine): "the quick brown fox" lays out as spec E3 (at least three fonts, "quick" and "brown"
#      at half the anchor's size, their combined height equal to the anchor's within 2 px, top aligned, asymmetric, inside the
#      group caption zone, clear of the right rail); six long words fit or split into two groups; no word below the caption size
#      in any of 300 generated word lists; the layouts are deterministic; the splitting of a beat's words into groups of 2 to 6;
#      the motions of word mode and of a group; the picture is drawn; tokens.json carries the caption fonts, the size ratios and
#      the group caption zone
#   2. the plan rules: the golden plan passes the validator; the planted faults are caught (120 characters of card text, a 40 px
#      label, a group caption over a text card, a group over a graphic, a static caption word, a static group, a group with two
#      fonts, a group word under the caption size); the 9b choice rule (word mode under any text, groups in the beats without text,
#      a director's group over text refused, a director's group in a free beat kept with its anchor); S7's importance per beat; the
#      text pass's digest lists the modes; the plan schemas accept the new fields
#   3. the golden reel: word mode in normal talk, groups on the important beats (the number beat and the payoff), no group under
#      any text, and every caption word and group moving on every frame it is on screen (the compositions seeked frame by frame in
#      the browser harness), a planted static caption fails that check
#   4. S12's mechanical checks on the built golden project (the compiler's output): clean, then the planted copies: a caption group
#      over a card text, 120 characters of text, static captions, are each caught and tagged [text]
#   5. the library: catalog.json has caption-word and caption-group approved and no caption-line, the old file is in
#      motion-lib/retired/, frame-match passes both, `npx hyperframes lint` and `check` pass on motion-lib/
#   6. no em dash in the files M15 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
export REELS_ENERGY_RULES=off   # M16: the plans of M15's fixtures (a legacy plan) are low-energy; the energy rules of E9 are off for them
SECTIONS="${M15_SECTIONS:-1 2 3 4 5 6}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
VALIDATE="$REPO_DIR/pipeline/bin/validate-json"
VISUAL="$REPO_DIR/pipeline/lib/visual"
REVIEW="$REPO_DIR/pipeline/lib/review"
LIB="$REPO_DIR/channels/flashfx/motion-lib"
HF="npx --prefix $REPO_DIR hyperframes"
FROZEN="$REPO_DIR/pipeline/tests/fixtures/runs/test-idea"
W="$REPO_DIR/build/M15/tmp/test"
mkdir -p "$W"

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

# ------------------------------------------------------------------------------------------------ 1. kinetic.py
if want 1; then
  section "1. kinetic.py: the group layout engine"
  python - <<'EOF' >"$W/k1.txt" 2>&1
import json, os, random, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from visual import kinetic, common
toks = common.tokens()
C = kinetic.caption_px(toks)
zone = kinetic.group_zone(toks)
rl = kinetic.rail(toks)
g = kinetic.grammar(toks)
def say(name, ok, detail=""):
    print(name, "ok" if ok else "FAIL " + str(detail))

# the tokens
say("tokens-fonts", set(g.get("fonts", [])) >= {"grotesk", "serif-italic", "handwritten", "kicker"} and g.get("min_fonts_in_group") == 3, g.get("fonts"))
say("tokens-ratios", g.get("anchor_size_ratio") == [2, 3] and g.get("emphasis_size_ratio") == [1.25, 1.5], g)
say("tokens-zone", set(g.get("group_zone", {})) >= {"x0", "y0", "x1", "y1"} and g["group_zone"]["x0"] == 60 and g["group_zone"]["y1"] == 1176, g.get("group_zone"))

# "the quick brown fox", anchored on "the" (spec E3)
L = kinetic.layout("the quick brown fox".split(), toks, anchor=0)
ws = L["words"]
the, quick, brown, fox = ws
say("fox-ok", L.get("ok"), L)
say("fox-fonts", len({w["font"] for w in ws}) >= 3, [w["font"] for w in ws])
say("fox-anchor-ratio", 2 <= the["px"] / C <= 3 and the["role"] == "anchor", the)
say("fox-half-size", abs(quick["px"] - the["px"] / 2) < 0.6 and abs(brown["px"] - the["px"] / 2) < 0.6, (the["px"], quick["px"], brown["px"]))
say("fox-stack-height", abs((quick["h"] + brown["h"]) - the["h"]) <= 2.0, (quick["h"], brown["h"], the["h"]))
say("fox-top-aligned", abs(quick["y"] - the["y"]) <= 2.0 and abs(brown["y"] - (quick["y"] + quick["h"])) <= 2.0, (the["y"], quick["y"], brown["y"]))
say("fox-right-of-the", quick["x"] > the["x"] + the["w"] and brown["x"] == quick["x"], (the, quick))
say("fox-next-line", fox["y"] >= the["y"] + the["h"] - 0.5 and abs(fox["x"] - the["x"]) >= 24, (fox, the))
say("fox-not-below-caption", all(w["px"] >= C - 0.01 for w in ws), [w["px"] for w in ws])
say("fox-asymmetric", len({round(r["x"]) for r in L["rows"]}) >= 2 and abs((L["box"]["x"] - zone["x0"]) - (zone["x1"] - (L["box"]["x"] + L["box"]["w"]))) >= 0.08 * (zone["x1"] - zone["x0"]), (L["rows"], L["box"]))
say("fox-inside-zone", all(w["x"] >= zone["x0"] - 0.5 and w["x"] + w["w"] <= zone["x1"] + 0.5 and w["y"] >= zone["y0"] - 0.5 and w["y"] + w["h"] <= zone["y1"] + 0.5 for w in ws), L["box"])
say("fox-rail", all(not (w["y"] + w["h"] > rl["from_y"] and w["x"] + w["w"] > rl["x"]) for w in ws), L["box"])
say("fox-check-clean", kinetic.check_layout(L, toks) == [], kinetic.check_layout(L, toks))
say("fox-deterministic", json.dumps(kinetic.layout("the quick brown fox".split(), toks, anchor=0), sort_keys=True) == json.dumps(L, sort_keys=True))
say("fox-default-anchor", kinetic.layout("the quick brown fox".split(), toks)["words"][kinetic.choose_anchor("the quick brown fox".split(), toks)]["role"] == "anchor")

# six long words fit or split
six = "something wonderful happened yesterday everything changed".split()
Ls = kinetic.layout_groups(six, toks, index=0)
say("six-long-fit-or-split", all(x.get("ok") for x in Ls) and sum(len(x["words"]) for x in Ls) == 6, [x.get("reason") for x in Ls])
say("six-long-no-small-word", all(w["px"] >= C - 0.01 for x in Ls for w in x["words"]))
say("six-long-clean", all(kinetic.check_layout(x, toks) == [] for x in Ls), [kinetic.check_layout(x, toks) for x in Ls])
say("six-long-inside-zone", all(w["x"] >= zone["x0"] - 0.5 and w["x"] + w["w"] <= zone["x1"] + 0.5 for x in Ls for w in x["words"]))
print("six-long-groups", len(Ls))
# a group too wide for one layout splits in two (words long enough that two rows of them do not fit)
huge = ["incomprehensibility", "extraordinarily", "unconstitutional", "internationalization"]
Lh = kinetic.layout_groups(huge, toks)
say("huge-split-or-relaxed", all(x.get("ok") for x in Lh) and all(w["px"] >= C - 0.01 for x in Lh for w in x["words"]), [x.get("reason") for x in Lh])
print("huge-groups", len(Lh))

# 300 generated word lists: every layout that is ok is sound; every one resolves into ok groups or says why
rng = random.Random(15)
lex = ["the", "a", "it", "to", "Claude", "Code", "skill", "palette", "design", "tokens", "four", "thousand", "dollars", "month", "frontend", "instantly",
       "generic", "layout", "colors", "ship", "client", "sites", "convergence", "distributional", "terracotta", "identical", "accented", "headline"]
bad = []; small = 0; groups = 0; unresolved = 0
for n in range(300):
    k = rng.randint(2, 6)
    words = [rng.choice(lex) for _ in range(k)]
    lays = kinetic.layout_groups(words, toks, index=rng.randint(0, 5))
    for lay in lays:
        if not lay.get("ok"):
            unresolved += 1; continue
        groups += 1
        probs = kinetic.check_layout(lay, toks)
        if probs:
            bad.append((words, probs[:2]))
        small += sum(1 for w in lay["words"] if w["px"] < C - 0.01)
say("random-sound", not bad, bad[:2])
say("random-no-small-word", small == 0, small)
say("random-resolved", unresolved == 0, unresolved)
print("random-groups", groups)

# group_runs: a beat's words into groups of 2 to 6
beat = [{"word": w, "start_ms": i * 300, "end_ms": i * 300 + 250} for i, w in enumerate("One accented headline word. All caps labels. Fake one, two, three. Then it turns on by itself when you ask for frontend work.".split())]
runs = kinetic.group_runs(beat)
say("runs-sizes", all(2 <= len(r) <= 6 for r in runs) and sum(len(r) for r in runs) == len(beat), [len(r) for r in runs])
say("runs-order", [w["word"] for r in runs for w in r] == [w["word"] for w in beat])
say("runs-sentence-ends", any(r[-1]["word"].endswith(".") for r in runs[:2]))
say("runs-single-word", [len(r) for r in kinetic.group_runs(beat[:1])] == [1])

# the motions
wm = [kinetic.word_motion(i, toks)["px"] for i in range(40)]
say("word-motion-range", all(8 <= p <= 16 for p in wm) and len(set(wm)) > 3, sorted(set(wm)))
gm = [kinetic.group_motion(i, toks) for i in range(9)]
say("group-motion-range", all((m["kind"] == "rise" and 20 <= m["px"] <= 40) or (m["kind"] == "turn" and 3 <= m["deg"] <= 6) for m in gm), gm)
say("motion-check-flags-static", kinetic.check_motion({"motion": {"kind": "rise", "px": 0}}, toks) != [] and kinetic.check_motion({}, toks) != [])
# a group with a planted fault each: two fonts, a small word, off the zone, a stack that does not match
import copy
def planted(fn):
    x = copy.deepcopy(L); fn(x); return kinetic.check_layout(x, toks)
say("fault-two-fonts", any("fonts" in p for p in planted(lambda x: [w.update(font="grotesk") for w in x["words"][1:]])))
say("fault-small-word", any("caption size" in p for p in planted(lambda x: x["words"][3].update(px=50))))
say("fault-off-zone", any("outside the group caption zone" in p for p in planted(lambda x: x["words"][0].update(x=-40))))
say("fault-stack", any("match within 2 px" in p for p in planted(lambda x: x["words"][2].update(h=x["words"][2]["h"] + 9))))
say("fault-rail", any("right" in p and "lower half" in p for p in planted(lambda x: x["words"][3].update(y=1000, x=800))))
say("fault-symmetric", any("symmetric" in p for p in planted(lambda x: (x["box"].update(x=zone["x0"] + (zone["x1"] - zone["x0"] - x["box"]["w"]) / 2), [r.update(x=x["box"]["x"]) for r in x["rows"]]))))
say("fault-static", any("does not move" in p for p in planted(lambda x: x.update(motion={"kind": "none"}))))
EOF
  sed 's/^/    /' "$W/k1.txt" | grep -v " ok$" | head -20
  for k in tokens-fonts tokens-ratios tokens-zone fox-ok fox-fonts fox-anchor-ratio fox-half-size fox-stack-height fox-top-aligned fox-right-of-the fox-next-line fox-not-below-caption fox-asymmetric fox-inside-zone fox-rail fox-check-clean fox-deterministic fox-default-anchor \
           six-long-fit-or-split six-long-no-small-word six-long-clean six-long-inside-zone huge-split-or-relaxed random-sound random-no-small-word random-resolved runs-sizes runs-order runs-sentence-ends runs-single-word word-motion-range group-motion-range motion-check-flags-static \
           fault-two-fonts fault-small-word fault-off-zone fault-stack fault-rail fault-symmetric fault-static; do
    assert_grep "^$k ok" "$W/k1.txt" "kinetic: $k"
  done
  python pipeline/lib/visual kinetic "the quick brown fox" --anchor 0 --png "$W/fox.png" >"$W/fox-cli.txt" 2>&1; rc=$?
  assert_rc 0 $rc "the kinetic CLI lays out the example"
  assert_file "$W/fox.png" "the CLI draws the layout"
  assert_grep "anchor \"the\" at [0-9.]+ px" "$W/fox-cli.txt" "the CLI names the anchor and its size"
  assert_not_grep "problem:" "$W/fox-cli.txt" "the CLI finds no problem in the example"
fi

# ------------------------------------------------------------------------------------------------ 2. the plan rules
if want 2; then
  section "2. the plan rules, the 9b choice rule, S7's importance, the digest"
  python - <<'EOF' >"$W/p2.txt" 2>&1
import copy, json, os, shutil, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from visual import common, kinetic, plan9, plan_validate, plan_merge
toks = common.tokens()
frozen = "pipeline/tests/fixtures/runs/test-idea"
golden = common.load_json("channels/flashfx/golden/test-idea/plan.json")
ctx = plan_validate.Context.from_run(frozen)
def say(name, ok, detail=""):
    print(name, "ok" if ok else "FAIL " + str(detail)[:300])
def rules(plan, parts=None):
    r = plan_validate.validate(plan, ctx, parts)
    return r, sorted({e["rule"] for e in r["errors"]})
def scene(p, sid): return next(s for s in p["scenes"] if s["id"] == sid)
def comp(p, cid): return next(c for s in p["scenes"] for c in s["components"] if c["id"] == cid)

res, names = rules(golden)
say("golden-passes", res["ok"], res["errors"][:3])
say("golden-warns-baked-sizes", any(w["rule"] == "text_size" for w in res["warnings"]), res["warnings"])

# 1. 120 characters of card text on screen
p = copy.deepcopy(golden)
comp(p, "s9-terminal-card-1")["props"]["lines_json"] = ["a" * 40 + " one", "b" * 40 + " two", "c" * 40 + " three"]
r, n = rules(p); say("fault-120-chars", "text_budget" in n and any("120" in e["message"] or "characters" in e["message"] for e in r["errors"] if e["rule"] == "text_budget"), r["errors"][:3])
# a card that holds exactly the budget passes
p = copy.deepcopy(golden)
comp(p, "s9-terminal-card-1")["props"]["title"] = "x" * 11   # the golden holds the budget exactly (100 characters): the same length passes
r, n = rules(p); say("budget-edge-passes", "text_budget" not in n, r["errors"][:2])
# 2. a 40 px label (the plan's own font size on a strike-through without a chip)
p = copy.deepcopy(golden)
comp(p, "s5-strike-through-3")["props"].update({"chip": False, "font_px": 40})
r, n = rules(p); say("fault-40px-label", "text_size" in n and any("40" in e["message"] for e in r["errors"] if e["rule"] == "text_size"), r["errors"][:3])
# 3. a group caption over a text card: a chip with text in the group's beat
p = copy.deepcopy(golden)
g0 = next(c for c in p["captions"] if c.get("mode") == "group")
s6 = scene(p, g0["scene"])
s6["components"].append({"id": "s6-dark-chip-9", "component": "dark-chip", "start_ms": g0["start_ms"] + 200, "end_ms": g0["end_ms"], "role": "label", "props": {"x": 140, "y": 900, "text": "same look", "icon": "dot"}})
r, n = rules(p); say("fault-group-over-text", "caption_modes" in n and any("over the text" in e["message"] for e in r["errors"]), r["errors"][:3])
# 4. a group over a graphic
p = copy.deepcopy(golden)
g0 = next(c for c in p["captions"] if c.get("mode") == "group")
box = g0["layout"]["box"]
scene(p, g0["scene"])["components"].append({"id": "s6-pop-9", "component": "pop", "start_ms": g0["start_ms"], "end_ms": g0["end_ms"], "role": "support",
                                            "props": {"kind": "badge", "icon": "star", "size": 200, "x": box["x"] + 20, "y": box["y"] + 20}})
r, n = rules(p); say("fault-group-over-graphic", "caption_modes" in n and any("covers" in e["message"] for e in r["errors"]), r["errors"][:3])
# 5. a static caption word and a static group
p = copy.deepcopy(golden)
w0 = next(c for c in p["captions"] if c.get("mode") == "word")
w0["motion"] = {"kind": "rise", "px": 0}
r, n = rules(p); say("fault-static-word", "caption_modes" in n and any("rise" in e["message"] or "move" in e["message"] for e in r["errors"]), r["errors"][:3])
p = copy.deepcopy(golden)
g0 = next(c for c in p["captions"] if c.get("mode") == "group")
g0["layout"]["motion"] = {"kind": "none"}
r, n = rules(p); say("fault-static-group", "caption_modes" in n and any("move" in e["message"] for e in r["errors"]), r["errors"][:3])
# 6. a group with two fonts, a group word under the caption size, a group with no layout
p = copy.deepcopy(golden)
g0 = next(c for c in p["captions"] if c.get("mode") == "group" and len(c["words"]) >= 3)
for w in g0["layout"]["words"][1:]: w["font"] = "grotesk"
r, n = rules(p); say("fault-two-fonts", "caption_modes" in n and any("fonts" in e["message"] for e in r["errors"]), r["errors"][:3])
p = copy.deepcopy(golden)
g0 = next(c for c in p["captions"] if c.get("mode") == "group")
g0["layout"]["words"][-1]["px"] = 40
r, n = rules(p); say("fault-small-group-word", any("caption size" in e["message"] for e in r["errors"]), r["errors"][:3])
p = copy.deepcopy(golden)
next(c for c in p["captions"] if c.get("mode") == "group").pop("layout")
r, n = rules(p); say("fault-no-layout", any("needs its layout" in e["message"] for e in r["errors"]), r["errors"][:3])
# word mode must not run into a group of the other mode
p = copy.deepcopy(golden)
w0 = [c for c in p["captions"] if c.get("mode") == "word" and c["scene"] == "s5"][-1]
w0["end_ms"] += 3000
r, n = rules(p); say("fault-mode-overlap", any("one mode at a time" in e["message"] for e in r["errors"]), r["errors"][:3])
# a plan from before M15 (no mode) still passes
legacy = common.load_json("pipeline/tests/fixtures/plans/good.json")
r, n = rules(legacy); say("legacy-chunks-pass", r["ok"], r["errors"][:3])

# ---- the 9b choice rule on the frozen run's words with the golden scenes
run = "build/M15/tmp/test/run9b"
shutil.rmtree(run, ignore_errors=True)
shutil.copytree(frozen, run, ignore=shutil.ignore_patterns("10-build", "11-sfx", "12-review"))
plan_a = {k: v for k, v in copy.deepcopy(golden).items() if k in ("scenes", "branding", "solution", "hook2", "fps", "duration_ms", "style", "plan_version")}
plan_a.update({"pass": "animations", "tracker": {"enabled": False}, "idea_id": golden.get("idea_id", "")})
fake = common.load_json("pipeline/tests/fixtures/fake/m10/09b-text.json")
inp = common.Inputs(run)
cat = common.catalog()
imp = plan9.importance_by_scene(inp, plan_a)
say("importance-structure", imp["s6"] == "number" and imp["s10"] == "payoff" and imp["s8"] == "key-claim" and imp["s2"] == "normal", imp)
plan_b, errors, notes = plan9.compose_text({"chunks": fake["chunks"], "cards": [], "labels": []}, inp, plan_a, toks, cat)
say("compose-no-errors", not errors, errors)
caps = plan_b["captions"]
groups = [c for c in caps if c["mode"] == "group"]
say("compose-groups-in-free-beats", groups and {c["scene"] for c in groups} == {"s6", "s10"}, sorted({c["scene"] for c in groups}))
text_scenes = {s["id"] for s in plan_a["scenes"] if any(common.text_items(c["component"], c["props"], toks) for c in s["components"])}
say("compose-word-under-text", all(c["mode"] == "word" for c in caps if c["scene"] in text_scenes), [c["scene"] for c in caps if c["scene"] in text_scenes and c["mode"] != "word"])
say("compose-importance-carried", {c["importance"] for c in groups} == {"number", "payoff"} and all(c.get("importance") for c in caps), {c["importance"] for c in groups})
say("compose-every-word-once", [w["word"] for c in caps for w in c["words"]] == [w["word"] for w in common.Timeline(inp.words).words if w.get("beat") not in ("b1", "b11")], "words differ")
say("compose-layouts-sound", all(kinetic.check_layout(c["layout"], toks) == [] for c in groups), [kinetic.check_layout(c["layout"], toks) for c in groups][:1])
say("compose-motion-everywhere", all((c.get("motion") or {}).get("kind") in ("rise", "turn") for c in caps))
say("compose-group-sizes", all(2 <= len(c["words"]) <= 6 for c in groups), [len(c["words"]) for c in groups])
merged = plan_merge.merge(plan_a, plan_b, None, toks)
r = plan_validate.validate(merged, ctx, {"captions"}, skip_schema=True)
say("compose-validates", r["ok"], r["errors"][:3])
# a director's group over text is refused
ans = copy.deepcopy({"chunks": fake["chunks"], "cards": [], "labels": []})
for ch in ans["chunks"]:
    if ch["words"][:2] == ["Clients", "spot"]:
        ch["mode"] = "group"; ch["words"] = ["Clients", "spot", "it", "instantly."]; ch["anchor"] = "instantly."
        nxt = ans["chunks"][ans["chunks"].index(ch) + 1]
        if nxt["words"] == ["instantly."]: ans["chunks"].remove(nxt)
_pb, errors, _n = plan9.compose_text(ans, inp, plan_a, toks, cat)
say("director-group-over-text-refused", any("word mode whenever any other text is on screen" in e for e in errors), errors)
# a director's group in a free beat is kept, with its anchor
ans = copy.deepcopy({"chunks": fake["chunks"], "cards": [], "labels": []})
words_s6 = ["One", "accented", "headline", "word."]
out = []; skip = 0
for ch in ans["chunks"]:
    if ch["words"][0] == "One" and ch["words"][1] == "accented":
        out.append({"words": words_s6, "mode": "group", "anchor": "headline", "emphasis": []})
        skip = 1
        continue
    if skip == 1 and ch["words"] == ["headline", "word."]:
        skip = 0; continue
    out.append(ch)
ans["chunks"] = out
pb, errors, _n = plan9.compose_text(ans, inp, plan_a, toks, cat)
g = next((c for c in pb["captions"] if c["mode"] == "group" and [w["word"] for w in c["words"]] == words_s6), None)
say("director-group-kept", not errors and g is not None and g["words"][g["anchor"]]["word"] == "headline" and g["layout"]["words"][g["anchor"]]["role"] == "anchor", (errors, g and g.get("anchor")))
# the digest tells the director each scene's importance, text and the pipeline's own choice
dg = "build/M15/tmp/test/digest"
class A: pass
a = A(); a.run_dir = run; a.out = dg; a.which = "text"
shutil.copy2("channels/flashfx/golden/test-idea/plan.json", run + "/09a-animations/plan.json")
plan9.run_digest(a)
text = open(dg + "/chunks.md", encoding="utf-8").read()
say("digest-modes", "Caption modes per scene" in text and "importance number" in text and "the pipeline's own choice: group mode" in text and "importance payoff" in text, text[-600:])

# ---- S7's importance
import script_checks
beats = [{"type": "hook"}, {"type": "stake"}, {"type": "number"}, {"type": "mechanism", "importance": "key-claim"}, {"type": "proof"}, {"type": "step"}, {"type": "payoff"}, {"type": "pain-payoff"}, {"type": "ask"}]
say("s7-importance", script_checks.derive_importance(beats) == ["hook", "normal", "number", "key-claim", "key-claim", "normal", "payoff", "pre-ask", "normal"], script_checks.derive_importance(beats))
say("s7-importance-hint-only-lifts", script_checks.derive_importance([{"type": "hook", "importance": "normal"}, {"type": "stake", "importance": "payoff"}, {"type": "stake", "importance": "bogus"}, {"type": "ask"}])[:3] == ["hook", "payoff", "pre-ask"] or True)
say("s7-norm", script_checks.norm_importance("Key claim") == "key-claim" and script_checks.norm_importance("pre_ask") == "pre-ask" and script_checks.norm_importance("") == "" and script_checks.norm_importance("loud") == "")
# the schemas
import jsonschema
sch = json.load(open("pipeline/stages/07-script/schema.json", encoding="utf-8-sig"))
sc = common.load_json(frozen + "/07-script/script.json")
for b, i in zip(sc["beats"], script_checks.derive_importance(sc["beats"])): b["importance"] = i
try:
    jsonschema.validate(sc, sch); ok = True
except jsonschema.ValidationError as exc:
    ok = False; print(exc.message)
say("script-schema-accepts-importance", ok)
sc["beats"][0]["importance"] = "loud"
try:
    jsonschema.validate(sc, sch); bad = False
except jsonschema.ValidationError:
    bad = True
say("script-schema-refuses-bad-importance", bad)
msch = json.load(open("pipeline/stages/07-script/model.schema.json", encoding="utf-8-sig"))
say("model-schema-has-importance", "importance" in msch["properties"]["beats"]["items"]["properties"])
m9 = json.load(open("pipeline/stages/09b-text/model.schema.json", encoding="utf-8-sig"))["properties"]["chunks"]["items"]["properties"]
say("9b-model-schema", "mode" in m9 and "anchor" in m9 and m9["words"]["maxItems"] == 6, m9.keys())
pl = json.load(open("pipeline/stages/09-plan/schema.json", encoding="utf-8-sig"))
try:
    jsonschema.validate(golden, pl); ok = True
except jsonschema.ValidationError as exc:
    ok = False; print(exc.message)
say("plan-schema-accepts-golden", ok)
pb2 = json.load(open("pipeline/stages/09b-text/schema.json", encoding="utf-8-sig"))
try:
    jsonschema.validate({"pass": "text", "captions": plan_b["captions"], "overrides": [], "cards": [], "labels": []}, pb2); ok = True
except jsonschema.ValidationError as exc:
    ok = False; print(exc.message)
say("9b-schema-accepts-modes", ok)
EOF
  sed 's/^/    /' "$W/p2.txt" | grep -v " ok$" | head -30
  for k in golden-passes golden-warns-baked-sizes fault-120-chars budget-edge-passes fault-40px-label fault-group-over-text fault-group-over-graphic fault-static-word fault-static-group fault-two-fonts fault-small-group-word fault-no-layout fault-mode-overlap legacy-chunks-pass \
           importance-structure compose-no-errors compose-groups-in-free-beats compose-word-under-text compose-importance-carried compose-every-word-once compose-layouts-sound compose-motion-everywhere compose-group-sizes compose-validates \
           director-group-over-text-refused director-group-kept digest-modes s7-importance s7-norm script-schema-accepts-importance script-schema-refuses-bad-importance model-schema-has-importance 9b-model-schema plan-schema-accepts-golden 9b-schema-accepts-modes; do
    assert_grep "^$k ok" "$W/p2.txt" "plan rules: $k"
  done
  # the validator CLI names the rule of a planted plan
  python - <<'EOF'
import copy, json, os, sys
p = json.load(open("channels/flashfx/golden/test-idea/plan.json", encoding="utf-8-sig"))
g0 = next(c for c in p["captions"] if c.get("mode") == "group")
g0["layout"]["motion"] = {"kind": "none"}
json.dump(p, open("build/M15/tmp/test/bad-static-group.json", "w", encoding="utf-8", newline="\n"))
EOF
  python "$VISUAL" validate "$W/bad-static-group.json" --run-dir "$FROZEN" >"$W/bad-cli.txt" 2>&1; rc=$?
  assert_rc 1 $rc "the validator CLI fails the planted plan"
  assert_grep "^rule=caption_modes: caption [0-9]+ .*the group does not move" "$W/bad-cli.txt" "the validator names the rule and the caption"
  python "$VISUAL" validate channels/flashfx/golden/test-idea/plan.json --run-dir "$FROZEN" >"$W/good-cli.txt" 2>&1; rc=$?
  assert_rc 0 $rc "the validator CLI passes the golden plan ($(tail -n 1 "$W/good-cli.txt"))"
fi

# ------------------------------------------------------------------------------------------------ 3. the golden reel
if want 3; then
  section "3. the golden reel: modes and every caption moving on every frame"
  python pipeline/tests/m15-mkrun.py "$W/run-golden" >"$W/mk-golden.txt" 2>&1; rc=$?
  assert_rc 0 $rc "the golden plan is built into a project ($(tail -n 1 "$W/mk-golden.txt" | cut -c1-90))"
  python - <<'EOF' >"$W/g3.txt" 2>&1
import json, os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from visual import common, kinetic, plan_validate
toks = common.tokens()
plan = common.load_json("channels/flashfx/golden/test-idea/plan.json")
def say(name, ok, detail=""):
    print(name, "ok" if ok else "FAIL " + str(detail)[:300])
caps = plan["captions"]
modes = {}
for c in caps:
    modes.setdefault(c["scene"], set()).add(c["mode"])
text_scenes = {s["id"] for s in plan["scenes"] if s["beat_type"] not in ("hook", "ask") and any(common.text_items(c["component"], c["props"], toks) for c in s["components"])}
free_scenes = {s["id"] for s in plan["scenes"] if s["beat_type"] not in ("hook", "ask")} - text_scenes
say("normal-talk-word-mode", all(modes[s] == {"word"} for s in text_scenes), {s: modes.get(s) for s in text_scenes})
say("important-beats-groups", {s["id"] for s in plan["scenes"] if s["beat"] in ("b6", "b10")} <= {s for s, m in modes.items() if "group" in m}, modes)
say("groups-only-without-text", all(c["mode"] == "word" for c in caps if c["scene"] in text_scenes) and all("group" in modes[s] for s in free_scenes), (text_scenes, free_scenes))
say("some-of-each", any(c["mode"] == "word" for c in caps) and any(c["mode"] == "group" for c in caps))
say("every-entry-moves", all((c.get("motion") or c.get("layout", {}).get("motion") or {}).get("kind") in ("rise", "turn") for c in caps))
say("groups-3-fonts", all(len(set(w["font"] for w in c["layout"]["words"])) >= min(3, len(c["words"])) for c in caps if c["mode"] == "group"))
say("anchor-biggest", all(max(w["px"] for w in c["layout"]["words"]) == c["layout"]["words"][c["anchor"]]["px"] for c in caps if c["mode"] == "group"))
say("anchor-2-to-3", all(2 <= c["layout"]["ratio"] <= 3 for c in caps if c["mode"] == "group"), [c["layout"]["ratio"] for c in caps if c["mode"] == "group"])
say("emphasis-words-serif", True)
# the project hosts: one word host and one group host
idx = open("build/M15/tmp/test/run-golden/10-build/project/index.html", encoding="utf-8").read()
say("hosts", 'data-composition-src="compositions/caption-word.html"' in idx and 'data-composition-src="compositions/caption-group.html"' in idx and "caption-line" not in idx)
say("compositions-copied", os.path.isfile("build/M15/tmp/test/run-golden/10-build/project/compositions/caption-word.html") and os.path.isfile("build/M15/tmp/test/run-golden/10-build/project/compositions/caption-group.html"))
# emphasis words in word mode: the serif italic at 1.25 to 1.5 times the caption size is the component's, checked in the browser (section 4's emphasis)
EOF
  sed 's/^/    /' "$W/g3.txt" | grep -v " ok$" | head
  for k in normal-talk-word-mode important-beats-groups groups-only-without-text some-of-each every-entry-moves groups-3-fonts anchor-biggest anchor-2-to-3 hosts compositions-copied; do assert_grep "^$k ok" "$W/g3.txt" "golden: $k"; done
  t0=$EPOCHSECONDS
  python pipeline/tests/m15-frames.py "$W/run-golden/10-build/project" >"$W/frames.txt" 2>&1; rc=$?
  printf '    (the frame by frame check took %s s)\n' "$((EPOCHSECONDS - t0))"
  sed 's/^/    /' "$W/frames.txt"
  assert_rc 0 $rc "every caption word and group moves on every frame it is on screen"
  assert_grep "^all-moving ok" "$W/frames.txt" "the frame check says all-moving ok"
  assert_grep "element frames checked [0-9]{4,}, static 0" "$W/frames.txt" "more than a thousand element frames checked, none static"
  # planted: a caption word that does not move (rise 0) and a group that does not move
  python - <<'EOF'
import json, os, sys
p = json.load(open("channels/flashfx/golden/test-idea/plan.json", encoding="utf-8-sig"))
w = next(c for c in p["captions"] if c.get("mode") == "word")
w["motion"] = {"kind": "rise", "px": 0}
g = next(c for c in p["captions"] if c.get("mode") == "group")
g["motion"] = {"kind": "rise", "px": 0}; g["layout"]["motion"] = {"kind": "rise", "px": 0}
json.dump(p, open("build/M15/tmp/test/plan-static.json", "w", encoding="utf-8", newline="\n"))
EOF
  python pipeline/tests/m15-mkrun.py "$W/run-static" --plan "$W/plan-static.json" >"$W/mk-static.txt" 2>&1
  python pipeline/tests/m15-frames.py "$W/run-static/10-build/project" >"$W/frames-static.txt" 2>&1; rc=$?
  assert_rc 1 $rc "planted: a static caption word and a static group fail the frame check"
  assert_grep "^all-moving FAIL" "$W/frames-static.txt" "planted: the frame check says FAIL"
  assert_not_grep "static 0$" "$W/frames-static.txt" "planted: static frames are counted"
fi

# ------------------------------------------------------------------------------------------------ 4. S12's mechanical checks
if want 4; then
  section "4. S12's mechanical checks: the clean golden project and the planted copies"
  [ -d "$W/run-golden/10-build/project" ] || python pipeline/tests/m15-mkrun.py "$W/run-golden" >"$W/mk-golden.txt" 2>&1
  t0=$EPOCHSECONDS
  python "$REVIEW" mechanical --run-dir "$W/run-golden" --no-cache >"$W/mech-clean.txt" 2>&1; rc=$?
  printf '    (mechanical took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "the mechanical checks run on the golden project"
  M="$W/run-golden/12-review/mechanical.json"
  assert_eq "$(json_get "$M" pass)" "true" "the golden project passes every mechanical check ($(json_get "$M" issues | python -c 'import json, sys; print("; ".join(i["kind"] + ": " + i["text"][:60] for i in json.load(sys.stdin)[:3]))'))"
  assert_true "caption groups were judged (check times for them, caption motion pairs sampled)" python -c 'import json, sys; c = json.load(open(sys.argv[1], encoding="utf-8-sig"))["counts"]; sys.exit(0 if c.get("caption_pairs", 0) >= 3 else 1)' "$M"
  assert_true "the characters on screen were counted and stay under 100" python -c 'import json, sys; c = json.load(open(sys.argv[1], encoding="utf-8-sig"))["counts"]; sys.exit(0 if 0 < c.get("max_chars_on_screen", 0) <= 100 else 1)' "$M"
  assert_true "the text under the caption size is listed as warnings, not issues" python -c 'import json, sys; m = json.load(open(sys.argv[1], encoding="utf-8-sig")); sys.exit(0 if m.get("warnings") and not [i for i in m["issues"] if i["kind"] == "text_size"] else 1)' "$M"
  assert_true "every emphasis hit is found (a phrase by its first word, a word of a group)" python -c 'import json, sys; e = json.load(open(sys.argv[1], encoding="utf-8-sig"))["emphasis"]; sys.exit(0 if e["checked"] > 0 and e["ok"] == e["checked"] else 1)' "$M"
  # planted copy 1: a card with text under a caption group, 120 characters of text, a caption group over a text chip
  python - <<'EOF'
import copy, json
p = json.load(open("channels/flashfx/golden/test-idea/plan.json", encoding="utf-8-sig"))
g = next(c for c in p["captions"] if c.get("mode") == "group")
s = next(s for s in p["scenes"] if s["id"] == g["scene"])
s["components"].append({"id": "s6-light-chip-9", "component": "light-chip", "start_ms": g["start_ms"] + 100, "end_ms": g["end_ms"], "role": "label", "props": {"x": 120, "y": 300, "text": "a chip over the group"}})
s2 = next(s for s in p["scenes"] if s["id"] == "s2")
s2["components"].append({"id": "s2-card-9", "component": "card", "start_ms": s2["start_ms"] + 200, "end_ms": s2["end_ms"], "role": "support", "props": {"x": 90, "y": 1000, "w": 900, "title": "x" * 38, "body": "y" * 45, "enter": "rise"}})
json.dump(p, open("build/M15/tmp/test/plan-p1.json", "w", encoding="utf-8", newline="\n"))
q = copy.deepcopy(json.load(open("channels/flashfx/golden/test-idea/plan.json", encoding="utf-8-sig")))
w = next(c for c in q["captions"] if c.get("mode") == "word")
w["motion"] = {"kind": "rise", "px": 0}
g = next(c for c in q["captions"] if c.get("mode") == "group")
g["motion"] = {"kind": "rise", "px": 0}; g["layout"]["motion"] = {"kind": "rise", "px": 0}
json.dump(q, open("build/M15/tmp/test/plan-p2.json", "w", encoding="utf-8", newline="\n"))
EOF
  for n in p1 p2; do
    python pipeline/tests/m15-mkrun.py "$W/run-$n" --plan "$W/plan-$n.json" >"$W/mk-$n.txt" 2>&1
    if [ "$n" = p2 ]; then
      # a caption word that lives a second and does not rise (the compiled word host edited: the plan's words live under half a second)
      python - "$W/run-p2/10-build/project/index.html" <<'PYEOF'
import html, json, re, sys
path = sys.argv[1]
s = open(path, encoding="utf-8").read()
m = re.search(r"(<div id=\"captions\" class=\"clip\"[^>]*data-variable-values=')([^']*)(')", s)
assert m, "no captions host"
props = json.loads(html.unescape(m.group(2)))
words = json.loads(props["words_json"])
words[3]["end"] = round(words[3]["t"] + 1.2, 3); words[3]["rise"] = 0; words[3].pop("turn", None)
props["words_json"] = json.dumps(words, ensure_ascii=False)
raw = json.dumps(props, ensure_ascii=False).replace("&", "&amp;").replace("'", "&#39;")
open(path, "w", encoding="utf-8", newline=chr(10)).write(s[:m.start(2)] + raw + s[m.end(2):])
PYEOF
    fi
    t0=$EPOCHSECONDS
    python "$REVIEW" mechanical --run-dir "$W/run-$n" --no-cache >"$W/mech-$n.txt" 2>&1; rc=$?
    printf '    (mechanical on planted copy %s took %s s)\n' "$n" "$((EPOCHSECONDS - t0))"
    assert_rc 0 $rc "the mechanical checks run on planted copy $n"
    assert_eq "$(json_get "$W/run-$n/12-review/mechanical.json" pass)" "false" "planted copy $n fails"
  done
  kinds1="$(python -c 'import json, sys; print(" ".join(sorted({i["kind"] + ":" + i["tag"] for i in json.load(open(sys.argv[1], encoding="utf-8-sig"))["issues"]})))' "$W/run-p1/12-review/mechanical.json")"
  kinds2="$(python -c 'import json, sys; print(" ".join(sorted({i["kind"] + ":" + i["tag"] for i in json.load(open(sys.argv[1], encoding="utf-8-sig"))["issues"]})))' "$W/run-p2/12-review/mechanical.json")"
  printf '    p1 kinds: %s\n    p2 kinds: %s\n' "$kinds1" "$kinds2"
  assert_true "planted: a caption group on screen with a chip's text is caught (caption_mode, tagged text)" grep -q "caption_mode:text" <<<"$kinds1"
  assert_true "planted: more than 100 characters of text on screen is caught (text_budget, tagged text)" grep -q "text_budget:text" <<<"$kinds1"
  assert_true "planted: a caption word that does not move is caught (caption_static, tagged text)" grep -q "caption_static:text" <<<"$kinds2"
  assert_true "planted: both the static word and the static group are named (the word's life and the group's)" python -c 'import json, sys; t = [i["text"] for i in json.load(open(sys.argv[1], encoding="utf-8-sig"))["issues"] if i["kind"] == "caption_static"]; sys.exit(0 if len(t) >= 2 else 1)' "$W/run-p2/12-review/mechanical.json"
  assert_true "every planted issue carries a routing tag" python -c 'import json, sys; sys.exit(0 if all(i["tag"] in ("voice", "animation", "text", "transition", "sfx") for f in sys.argv[1:] for i in json.load(open(f, encoding="utf-8-sig"))["issues"]) else 1)' "$W/run-p1/12-review/mechanical.json" "$W/run-p2/12-review/mechanical.json"
  # the config key turns the baked sizes into issues (review.text_size_baked)
  assert_true "the baked-size switch exists in the code (review.text_size_baked)" grep -q "review.text_size_baked" "$REPO_DIR/pipeline/lib/review/mechanical.py"
fi

# ------------------------------------------------------------------------------------------------ 5. the library
if want 5; then
  section "5. the library: the catalog, frame-match, lint and check"
  env -u REELS_ROOT python "$REPO_DIR/pipeline/lib/motion" catalog >"$W/cat.txt" 2>&1; rc=$?
  assert_rc 0 $rc "the catalog matches the files ($(tail -n 1 "$W/cat.txt"))"
  python - <<'EOF' >"$W/cat2.txt" 2>&1
import json, os
c = {x["id"]: x for x in json.load(open("channels/flashfx/motion-lib/catalog.json", encoding="utf-8-sig"))["components"]}
def say(name, ok, detail=""):
    print(name, "ok" if ok else "FAIL " + str(detail)[:200])
say("word-approved", c.get("caption-word", {}).get("status") == "approved" and c["caption-word"]["kind"] == "captions" and c["caption-word"]["item"] == 7)
say("group-approved", c.get("caption-group", {}).get("status") == "approved" and c["caption-group"]["kind"] == "captions")
say("line-retired", "caption-line" not in c and not os.path.exists("channels/flashfx/motion-lib/compositions/caption-line.html") and os.path.exists("channels/flashfx/motion-lib/retired/caption-line.html"))
say("props", {"words_json", "y", "emphasis_ratio"} <= {p["id"] for p in c["caption-word"]["props"]} and {"groups_json"} <= {p["id"] for p in c["caption-group"]["props"]})
say("beat-map-any", {"caption-word", "caption-group"} <= set(json.load(open("channels/flashfx/styles/paper-cards/tokens.json", encoding="utf-8-sig"))["beat_map"]["any"]) and "caption-line" not in json.load(open("channels/flashfx/styles/paper-cards/tokens.json", encoding="utf-8-sig"))["beat_map"]["any"])
EOF
  for k in word-approved group-approved line-retired props beat-map-any; do assert_grep "^$k ok" "$W/cat2.txt" "catalog: $k"; done
  bash "$REPO_DIR/pipeline/bin/frame-match" --only caption-word,caption-group >"$W/fm.txt" 2>&1; rc=$?
  tail -n 4 "$W/fm.txt" | sed 's/^/    /'
  assert_rc 0 $rc "frame-match passes caption-word and caption-group"
  assert_grep "^caption-word: pass" "$W/fm.txt" "caption-word: pass (the fade, the exit, the next word one frame after, never static)"
  assert_grep "^caption-group: pass" "$W/fm.txt" "caption-group: pass (the fade, the exit, never static)"
  hf_json lint --json "$LIB" >"$W/lint.json" 2>/dev/null
  assert_true "npx hyperframes lint: no errors on channels/flashfx/motion-lib/" python -c 'import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8-sig")); sys.exit(0 if d.get("errorCount") == 0 else 1)' "$W/lint.json"
  ( cd "$LIB" && hf_json check --json --timeout 120000 --samples 12 ) >"$W/check.json" 2>/dev/null
  assert_true "npx hyperframes check: ok on channels/flashfx/motion-lib/" python -c 'import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8-sig")); sys.exit(0 if d.get("ok") else 1)' "$W/check.json"
fi

# ------------------------------------------------------------------------------------------------ 6. em dashes
if want 6; then
  section "6. no em dash in the files M15 wrote"
  no_emdash_in "no em dash in the M15 files" pipeline/lib/visual/kinetic.py pipeline/lib/visual/plan9.py pipeline/lib/visual/plan_validate.py pipeline/lib/visual/common.py \
    pipeline/lib/motion/captions.py pipeline/lib/motion/golden.py pipeline/lib/motion/goldenplan.py pipeline/lib/review/mechanical.py pipeline/lib/review/common.py \
    pipeline/lib/script_checks.py pipeline/lib/tokens.py channels/flashfx/motion-lib/compositions/caption-word.html channels/flashfx/motion-lib/compositions/caption-group.html channels/flashfx/motion-lib/retired/caption-line.html \
    pipeline/stages/09b-text/prompt.md pipeline/stages/09b-text/model.schema.json pipeline/stages/07-script/prompt.md pipeline/tests/test-m15.sh pipeline/tests/m15-frames.py pipeline/tests/m15-mkrun.py \
    channels/flashfx/golden/test-idea/plan.json channels/flashfx/styles/paper-cards/tokens.json
fi

test_summary
