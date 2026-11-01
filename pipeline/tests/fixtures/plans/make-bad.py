#!/usr/bin/env python
"""make-bad.py: the validator fixtures (PLAN.md M10: one failing plan per rule, one good plan). From good.json (the
merged plan of the test idea, a copy of golden/test-idea/plan.json) it writes bad-<rule>.json, each breaking exactly
one rule of pipeline/lib/visual/plan_validate.py, so test-m10.sh can assert that the rule fires and names itself.
    python pipeline/tests/fixtures/plans/make-bad.py            (writes beside itself)
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def dump(name, data):
    with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")


def scene(plan, sid):
    return next(s for s in plan["scenes"] if s["id"] == sid)


def comp(plan, iid):
    return next(c for s in plan["scenes"] for c in s["components"] if c["id"] == iid)


def main():
    good = load(os.path.join(HERE, "good.json"))
    bad = {}

    p = copy.deepcopy(good); p["scenes"][0]["components"][0]["start_ms"] = 400; bad["first_change"] = p          # the first change after 4 frames
    p = copy.deepcopy(good); s1 = scene(p, "s1"); s1["components"] = [c for c in s1["components"] if c["component"] != "hero-3d"]; s1["hook_set_piece"] = False; s1["set_piece"] = False
    scene(p, "s2")["set_piece"] = True; bad["breath"] = p                                                             # nothing lands in the breath (a set piece elsewhere keeps the count)
    p = copy.deepcopy(good)  # s3 to s5 merged into one 12 s scene with one still card: nothing moves for over 6.5 s (times fires too)
    s3 = scene(p, "s3"); s3["end_ms"] = scene(p, "s5")["end_ms"]; s3["components"] = [s3["components"][0]]; s3["components"][0]["end_ms"] = s3["end_ms"]
    s3["components"][0]["props"].pop("mascot", None); s3["emphasis_hits"] = []
    p["scenes"] = [s for s in p["scenes"] if s["id"] not in ("s4", "s5")]
    p["transitions"] = [t for t in p["transitions"] if t["from"] not in ("s3", "s4", "s5")] + [{"from": "s3", "to": "s6", "type": "fade-blur", "duration_ms": 133}]
    p["captions"] = [c for c in p["captions"] if c["scene"] not in ("s4", "s5")]
    p["labels"] = [l for l in p["labels"] if l["scene"] not in ("s4", "s5")]
    bad["max_gap"] = p
    p = copy.deepcopy(good)
    for s in p["scenes"][:-1]:  # every body component a plain card, the hook's set piece too: 4 distinct components (repeat fires too)
        for c in s["components"]:
            if c["component"] not in ("card", "headline"):
                c["component"] = "card"; c["props"] = {"x": 90, "y": 560, "w": 900, "title": "Card", "enter": "rise"}; c["honesty_label"] = None; c["assets"] = []
        s["honesty_label"] = None
    p["labels"] = [l for l in p["labels"] if l["kind"] != "honesty"]
    bad["distinct"] = p
    p = copy.deepcopy(good)
    for sid in ("s3", "s5"):  # s2, s3, s4 (and s5) all hero cards in a row
        sc = scene(p, sid); hero = sc["components"][0]
        hero["component"] = "card"; hero["props"] = {"x": 90, "y": 560, "w": 900, "title": "Card", "enter": "rise"}; hero["role"] = "hero"; hero["honesty_label"] = None; hero["assets"] = []
        sc["honesty_label"] = None
        for c in sc["components"][1:]:
            c["role"] = "label"
    p["labels"] = [l for l in p["labels"] if not (l["kind"] == "honesty" and l["scene"] == "s3")]
    bad["repeat"] = p
    p = copy.deepcopy(good); comp(p, "s9-terminal-card-1")["component"] = "chat-card"; comp(p, "s9-terminal-card-1")["props"] = {"x": 90, "y": 640, "w": 900, "prompt": "Design it", "honesty": "mock"}
    scene(p, "s9")["beat_type"] = "payoff"; bad["beat_map"] = p                                                   # a chat card in a payoff beat (and the beat type differs from the script: times fires too)
    p = copy.deepcopy(good); c = comp(p, "s4-handwritten-callout-2"); c["component"] = "hero-3d"; c["props"] = {"x": 240, "y": 700, "w": 500, "h": 500, "object": "box"}; bad["three_d"] = p  # 3D in a mechanism beat
    p = copy.deepcopy(good)
    for sid in ("s2", "s3", "s4"):
        scene(p, sid)["set_piece"] = True
    bad["set_pieces"] = p                                                                                           # 4 set pieces
    p = copy.deepcopy(good); comp(p, "s2-card-1")["props"]["x"] = 10; bad["zones"] = p                                 # a card into the side margin
    p = copy.deepcopy(good); p["captions"][0]["words"] = p["captions"][0]["words"] + p["captions"][1]["words"] + p["captions"][2]["words"]; bad["captions"] = p  # a chunk of too many words
    p = copy.deepcopy(good); comp(p, "s2-card-1")["props"]["title"] = "Clients spot the identical cards every single time"; bad["cards"] = p  # 8 words on a card
    p = copy.deepcopy(good); comp(p, "s8-stat-number-2")["props"]["value"] = 987654; bad["assets"] = p                # an invented number
    p = copy.deepcopy(good); p["labels"] = [l for l in p["labels"] if not (l["kind"] == "honesty" and l["scene"] == "s3")]; bad["honesty"] = p  # a sourced screenshot without its label
    p = copy.deepcopy(good); comp(p, "s2-card-1")["props"]["image"] = "brand/mark/mark-gradient.png"; comp(p, "s2-card-1")["assets"] = ["brand/mark/mark-gradient.png"]; bad["branding"] = p  # a FlashFX asset in the body of a non-FlashFX reel
    p = copy.deepcopy(good); p["transitions"][0]["type"] = "zoom"; bad["transitions"] = p                              # a type the style does not allow
    p = copy.deepcopy(good); p["scenes"][2]["start_ms"] += 500; p["scenes"][1]["end_ms"] += 500; bad["times"] = p    # a scene boundary off the words
    p = copy.deepcopy(good); comp(p, "s2-card-1")["component"] = "stone-card"; bad["components"] = p                 # an unknown component
    p = copy.deepcopy(good); p["hook2"] = {"kicker": "X", "lines": ["Something", "*else entirely*"], "set_piece": True}; bad["hook2"] = p  # hook 2's words differ from its display line

    for rule, plan in bad.items():
        plan["source"] = f"fixture bad-{rule}"
        dump(f"bad-{rule}.json", plan)
    print("fixtures written: good.json plus " + ", ".join(f"bad-{r}.json" for r in bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
