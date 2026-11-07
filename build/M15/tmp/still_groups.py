import json, os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from motion import common, harness, captions

plan = json.load(open("golden/test-idea/plan.json", encoding="utf-8-sig"))
lib = common.motion_lib_dir()
groups = captions.group_entries(plan["captions"])
words = captions.word_entries(plan["captions"])
os.makedirs("build/M15/tmp/stills", exist_ok=True)
with harness.Harness(lib=lib) as h:
    comp = common.parse_component(os.path.join(lib, "compositions", "caption-group.html"))
    first = min(g["start_ms"] for g in groups)
    clip = max(0, first - 200)
    data = captions.to_component_groups(groups, clip)
    for k, g in enumerate(groups):
        t = (g["start_ms"] - clip) / 1000 + 0.9
        out = h.still(comp, {"groups_json": json.dumps(data)}, t, f"build/M15/tmp/stills/group{k}.png", size=(540, 960))
        print(out, [w["word"] for w in g["words"]])
    comp = common.parse_component(os.path.join(lib, "compositions", "caption-word.html"))
    first = min(g["start_ms"] for g in words)
    clip = max(0, first - 200)
    data = captions.to_component_words(words, clip)
    for k in (2, 3, 7):
        e = words[k]
        t = (e["words"][min(1, len(e["words"]) - 1)]["start_ms"] - clip) / 1000 + 0.12
        out = h.still(comp, {"words_json": json.dumps(data)}, t, f"build/M15/tmp/stills/word{k}.png", size=(540, 960))
        print(out, [w["word"] for w in e["words"]])
