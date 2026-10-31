#!/usr/bin/env python
"""Build 10-build/events.json from 07-script/script.json: one sound event per beat, spaced by the beat's
estimated duration (words / wpm). Usage: python helper.py <script.json> <events.json>"""
import json
import sys


def main(argv):
    script_path, out_path = argv[0], argv[1]
    with open(script_path, encoding="utf-8-sig") as f:
        script = json.load(f)
    wpm = float(script.get("wpm") or 150)
    events = []
    t_ms = 0
    for n, beat in enumerate(script["beatz"], 1):
        words = len(str(beat.get("spoken", "")).split())
        events.append({"ms": t_ms, "type": "hook_hit" if beat.get("type") == "hook" else "scene_change",
                       "component": "hero-card" if n == 1 else "caption-line", "scene": f"s{n}",
                       "scene_change": n > 1, "transition_ms": 0 if n == 1 else 300})
        t_ms += int(words / wpm * 60000) + 400
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"composition": "project/index.html", "duration_ms": t_ms, "events": events}, f, indent=1)
    print(f"wrote {len(events)} events to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
