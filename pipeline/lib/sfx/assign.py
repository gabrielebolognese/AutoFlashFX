"""assign.py: cue types for the events of the built visuals (BUILD_SPEC.md S11 step 1, M11).

Deterministic rules over 10-build/events.json, the compiled plan (10-build/plan.json) and 08-voiceover/words.json,
with the randomness (the attention intervals, the pool rotation's start) seeded per reel:

  mandatory     hook_hit on the hook's set piece (the scene with hook_set_piece: its set-piece component's enter or
                pop; else the catalog's hook_hit event), notification on the DM card's landing, stamp on stamps,
                typing on typing segments (trimmed to the segment by place.py), success on checkmarks, negative on
                strike-throughs
  transitions   every scene change: transition_slow when the transition lasts config sfx.slow_transition_ms or more
                or the next beat is calm (config sfx.calm_beats: stake, pain-payoff), else transition_fast
  hero          hero_enter on the scene's hero (the catalog's hero_enter events: cards, window cards, stats, the end
                card), at most one per scene (the hero-role component first, then the earliest that the spacing and
                density rules let through); a hero that enters on the scene change itself pops at its landing instead,
                where the card settles, since the whoosh owns the change; number on a count-up's start
  ui            ui_click on chips and highlights (the catalog's ui_click events)
  attention     when more than config sfx.attention_gap_s (6) seconds pass with no sound: a fast whoosh on a visual
                change in that gap, the next one about U(8, 12) s after the last sound (sfx.attention_interval_s),
                never in the first 2 seconds and never during the ask
  density       at most sfx.max_per_10s (4) hits in any 10 s window, never two sounds within sfx.min_spacing_ms
                (250), nothing on the hook's first word but hook_hit. Candidates are accepted by priority
                (mandatory, then scene changes, then hero and number, then ui, then attention) and by time inside a
                priority, so the trimming keeps the spec's order; every dropped candidate is listed with its reason.
                Two readings of "sounds" are recorded in DECISIONS.md: a typing bed is a continuous sound, not a
                hit, so it respects the spacing but does not count toward the 4 per 10 s; a series of the same
                mandatory cue on one component within sfx.series_gap_ms (a checklist ticking) counts once and plays
                the same file (pick.py).

  assign(events, plan, words, config, seed, feedback=None) -> {"cues": [...], "dropped": [...], "seed": int,
                                                                "settings": {...}, "feedback_applied": [...]}
  Each cue: {"id", "ms", "end_ms" (typing), "cue_type", "group", "priority", "series_of" (the series' first cue),
             "event": {ms, type, component, instance, scene, beat, scene_change, transition_ms, transition_type}, "why"}
"""
from __future__ import annotations

import hashlib
import random
import re

WHOOSH_CUES = {"transition_slow", "transition_fast", "attention", "hook_hit"}   # placed by their peak (place.py)
MANDATORY_BY_TYPE = {"notification": "notification", "stamp": "stamp", "typing": "typing", "check": "success", "strike": "negative"}
VISUAL_CHANGE_TYPES = {"enter", "pop", "card", "check", "strike", "count_start", "typing", "mascot", "lockup", "scene_change", "bar", "row", "fill", "slide", "send", "line", "gauge"}
GROUP_PRIORITY = {"mandatory": 0, "transition": 1, "hero": 2, "ui": 3, "attention": 4}
BED_CUES = {"typing"}   # continuous sounds: spacing applies, the hit count does not
DEFAULT_CALM = ["stake", "pain-payoff"]


def seed_for(text: str, extra: int = 0) -> int:
    return (int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16) + int(extra)) & 0x7FFFFFFF


def cfg(config: dict, key: str, default=None):
    cur = config
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _event_ref(e: dict) -> dict:
    out = {"ms": int(e.get("ms", 0)), "type": e.get("type"), "component": e.get("component"), "instance": e.get("instance"),
           "scene": e.get("scene"), "beat": e.get("beat"), "scene_change": bool(e.get("scene_change"))}
    if e.get("scene_change"):
        out["transition_ms"] = int(e.get("transition_ms", 0) or 0)
        out["transition_type"] = e.get("transition_type")
        out["from_scene"] = e.get("from_scene")
        out["next_beat_type"] = e.get("next_beat_type")
    if e.get("end") is not None:
        out["end"] = int(e["end"])
    if e.get("el"):
        out["el"] = e["el"]
    return out


def describe(e: dict) -> str:
    """The visual event in words, for sound-map.txt."""
    if e.get("scene_change"):
        return f"scene change {e.get('from_scene')} -> {e.get('scene')} ({e.get('transition_type')} {int(e.get('transition_ms', 0) or 0)} ms, into {e.get('next_beat_type')})"
    t = e.get("type")
    comp = e.get("component")
    inst = e.get("instance") or ""
    verbs = {"enter": "enters", "pop": "pops in", "typing": "types", "check": "ticks", "strike": "strikes through", "count_start": "starts counting",
             "notification": "lands (the DM notification)", "stamp": "stamps", "card": "card appears", "lockup": "lockup fades in", "mascot": "mascot hops in"}
    return f"{comp} {verbs.get(t, t)} ({inst}, scene {e.get('scene')})"


class Density:
    """The spacing and density rules over the accepted sounds: every sound keeps min_spacing_ms from every other,
    and the hits (a series counted once, beds not at all) stay at or under max_per_10s in any 10 s window."""

    def __init__(self, max_per_10s: int, min_spacing_ms: int):
        self.max_per_10s = max(1, int(max_per_10s))
        self.min_spacing_ms = max(0, int(min_spacing_ms))
        self.times: list[int] = []
        self.hits: list[int] = []

    def reason_against(self, ms: int, counts_as_hit: bool = True) -> str:
        for t in self.times:
            if abs(t - ms) < self.min_spacing_ms:
                return f"within {self.min_spacing_ms} ms of the sound at {t} ms"
        if not counts_as_hit:
            return ""
        window = 10000
        near = sorted(t for t in self.hits if abs(t - ms) <= window) + [ms]
        for s in near:
            if s > ms:
                break
            count = sum(1 for t in near if s <= t <= s + window)
            if count > self.max_per_10s:
                return f"more than {self.max_per_10s} sounds in the 10 s from {s} ms"
        return ""

    def add(self, ms: int, counts_as_hit: bool = True) -> None:
        self.times.append(ms)
        self.times.sort()
        if counts_as_hit:
            self.hits.append(ms)
            self.hits.sort()


def hook_set_piece_event(events: list[dict], plan: dict) -> dict | None:
    hook = next((s for s in plan.get("scenes", []) if s.get("hook_set_piece")), None)
    if hook:
        piece = next((c for c in hook.get("components", []) if c.get("role") == "set-piece" or c.get("at") == "breath"), None)
        if piece:
            for e in events:
                if e.get("instance") == piece["id"] and e.get("type") in ("enter", "pop") and not e.get("scene_change"):
                    return e
    for e in events:
        if e.get("cue") == "hook_hit" and not e.get("scene_change"):
            return e
    return None


def apply_feedback(settings: dict, feedback: list[dict] | None) -> list[str]:
    """The edit review's [sfx] issues (12-review/feedback.json) change the next round: fewer and softer sounds when it
    found them cluttering or loud, louder when too soft, another seed always (so the rotation changes), the files of
    a named cue avoided (pick.py reads settings['avoid_last'])."""
    applied: list[str] = []
    if not feedback:
        return applied
    texts = " ".join(str(i.get("text", "")) for i in feedback if str(i.get("tag", "")).strip("[]") == "sfx").lower()
    if not texts.strip():
        return applied
    settings["reseed"] = True
    applied.append("the rotation starts from a new seed")
    if re.search(r"clutter|busy|too many|too much|noisy|crowded|dense|constant|every", texts):
        settings["max_per_10s"] = max(2, int(settings["max_per_10s"]) - 1)
        settings["no_attention"] = True
        settings["gain_offset_db"] = float(settings.get("gain_offset_db", 0)) - 3
        applied.append(f"fewer sounds: at most {settings['max_per_10s']} per 10 s, no attention whooshes, every sound 3 dB softer")
    if re.search(r"loud|cover|mask|over the voice|drown|harsh|distract", texts):
        settings["gain_offset_db"] = float(settings.get("gain_offset_db", 0)) - 4
        applied.append("every sound 4 dB softer")
    elif re.search(r"quiet|too soft|barely|can't hear|cannot hear|inaudible", texts):
        settings["gain_offset_db"] = float(settings.get("gain_offset_db", 0)) + 3
        applied.append("every sound 3 dB louder (the voice rule still caps it)")
    named = []
    for word, cues in (("whoosh", ["transition_slow", "transition_fast", "attention", "hook_hit"]), ("swoosh", ["transition_slow", "transition_fast", "attention"]),
                       ("click", ["ui_click", "number"]), ("ding", ["success", "notification"]), ("pop", ["hero_enter"]), ("typing", ["typing"]),
                       ("keyboard", ["typing"]), ("notification", ["notification"]), ("impact", ["hook_hit", "stamp"]), ("hit", ["hook_hit", "stamp"]),
                       ("tick", ["number"]), ("error", ["negative"]), ("buzz", ["negative"])):
        if re.search(r"\b" + word + r"\w*", texts):
            named += cues
    if named:
        settings["avoid_last"] = sorted(set(named))
        applied.append("other files for " + ", ".join(sorted(set(named))))
    if re.search(r"slow whoosh.*(fast|quick)|too slow", texts):
        settings["prefer_fast"] = True
        applied.append("fast whooshes on every scene change")
    return applied


def mark_series(cands: list[dict], gap_ms: int) -> None:
    """The same mandatory cue on one component within gap_ms (a checklist ticking): a series, counted once."""
    last: dict = {}
    for c in sorted(cands, key=lambda c: c["ms"]):
        if c["group"] != "mandatory" or c["cue_type"] in BED_CUES:
            continue
        key = (c["event"].get("instance"), c["cue_type"])
        prev = last.get(key)
        if prev is not None and c["ms"] - prev["ms"] <= gap_ms:
            c["series_of"] = prev.get("series_of") or prev["id"]
        last[key] = c


def assign(events: list[dict], plan: dict, words: dict, config: dict, seed: int, feedback: list[dict] | None = None,
           last_files: dict | None = None) -> dict:
    settings = {
        "max_per_10s": int(cfg(config, "sfx.max_per_10s", 4)),
        "min_spacing_ms": int(cfg(config, "sfx.min_spacing_ms", 250)),
        "slow_transition_ms": int(cfg(config, "sfx.slow_transition_ms", 400)),
        "calm_beats": list(cfg(config, "sfx.calm_beats", DEFAULT_CALM) or DEFAULT_CALM),
        "attention_gap_s": float(cfg(config, "sfx.attention_gap_s", 6)),
        "attention_interval_s": list(cfg(config, "sfx.attention_interval_s", [8, 12]) or [8, 12]),
        "attention_min_start_ms": int(cfg(config, "sfx.attention_min_start_ms", 2000)),
        "series_gap_ms": int(cfg(config, "sfx.series_gap_ms", 2000)),
        "gain_offset_db": 0.0,
        "no_attention": False,
        "reseed": False,
        "avoid_last": [],
        "prefer_fast": False,
    }
    applied = apply_feedback(settings, feedback)
    rng = random.Random(seed)
    duration_ms = int(plan.get("duration_ms") or events_duration(events))
    first_word = (words.get("words") or [{}])[0] if words else {}
    first_window = (int(first_word.get("start_ms", 0)), int(first_word.get("end_ms", 0))) if first_word else (0, 0)
    ask = next((b for b in (words.get("beats") or []) if b.get("type") == "ask"), None) if words else None
    ask_window = (int(ask["start_ms"]), duration_ms) if ask else None
    hero_roles = {c["id"]: c.get("role") for s in plan.get("scenes", []) for c in s.get("components", [])}

    cands: list[dict] = []
    n = 0

    def add(e: dict, cue: str, group: str, why: str, end_ms=None):
        nonlocal n
        n += 1
        c = {"id": f"c{n:02d}", "ms": int(e["ms"]), "cue_type": cue, "group": group, "priority": GROUP_PRIORITY[group], "event": _event_ref(e), "why": why}
        if end_ms is not None:
            c["end_ms"] = int(end_ms)
        cands.append(c)

    piece = hook_set_piece_event(events, plan)
    if piece is not None:
        add(piece, "hook_hit", "mandatory", "the hook's set piece")
    change_ms = sorted(int(e["ms"]) for e in events if e.get("scene_change"))
    land_of: dict = {}
    for e in events:
        if e.get("type") == "land" and e.get("instance") and e.get("instance") not in land_of:
            land_of[e["instance"]] = int(e["ms"])
    for e in events:
        if e.get("scene_change"):
            tr = int(e.get("transition_ms", 0) or 0)
            calm = str(e.get("next_beat_type", "")) in settings["calm_beats"]
            if settings["prefer_fast"]:
                cue, why = "transition_fast", "scene change (fast whooshes asked by the review)"
            elif tr >= settings["slow_transition_ms"]:
                cue, why = "transition_slow", f"scene change with a {tr} ms transition"
            elif calm:
                cue, why = "transition_slow", f"scene change into a calm beat ({e.get('next_beat_type')})"
            else:
                cue, why = "transition_fast", f"scene change ({e.get('transition_type')} {tr} ms)"
            add(e, cue, "transition", why)
            continue
        t = e.get("type")
        if e is piece:
            continue
        if t in MANDATORY_BY_TYPE:
            add(e, MANDATORY_BY_TYPE[t], "mandatory", {"notification": "the DM card lands", "stamp": "a stamp", "typing": "a typing segment", "check": "a checkmark", "strike": "a strike-through"}[t],
                end_ms=e.get("end") if t == "typing" else None)
            continue
        if t == "count_start":
            add(e, "number", "hero", "a number counts up")
            continue
        if e.get("cue") == "hero_enter" and t in ("enter", "pop"):
            # a hero that enters on the scene change itself would always lose to the whoosh (the spacing rule): its
            # pop moves to its landing, where the card settles (DECISIONS.md M11)
            hero_e = e
            why = "the scene's hero enters" if hero_roles.get(e.get("instance")) in ("hero", "cta", "set-piece") else "a card enters"
            if any(abs(int(e["ms"]) - m) < settings["min_spacing_ms"] for m in change_ms):
                land = land_of.get(e.get("instance"))
                if land and land > int(e["ms"]):
                    hero_e = dict(e, ms=land, type="land")
                    why = "the scene's hero lands (its enter is on the scene change)"
            add(hero_e, "hero_enter", "hero", why)
            continue
        if e.get("cue") == "ui_click" and t in ("enter", "pop"):
            add(e, "ui_click", "ui", "a chip or highlight changes state")
            continue
    mark_series(cands, settings["series_gap_ms"])

    def hero_rank(c: dict) -> int:
        return 0 if hero_roles.get(c["event"].get("instance")) in ("hero", "cta", "set-piece") else 1

    density = Density(settings["max_per_10s"], settings["min_spacing_ms"])
    accepted: list[dict] = []
    dropped: list[dict] = []
    hero_scenes: set = set()
    order = sorted(cands, key=lambda c: (c["priority"], hero_rank(c) if c["cue_type"] == "hero_enter" else 0, c["ms"]))
    for c in order:
        if c["cue_type"] != "hook_hit" and first_window[1] > first_window[0] and first_window[0] - settings["min_spacing_ms"] <= c["ms"] <= first_window[1]:
            dropped.append({**c, "reason": "on the hook's first word (only hook_hit may sound there)"})
            continue
        if c["cue_type"] == "hero_enter" and c["event"]["scene"] in hero_scenes:
            dropped.append({**c, "reason": "a second hero sound in the scene"})
            continue
        counts = c["cue_type"] not in BED_CUES and not c.get("series_of")
        why_not = density.reason_against(c["ms"], counts)
        if why_not:
            dropped.append({**c, "reason": why_not})
            continue
        density.add(c["ms"], counts)
        accepted.append(c)
        if c["cue_type"] == "hero_enter":
            hero_scenes.add(c["event"]["scene"])
    # attention: fast whooshes in the silent gaps
    if not settings["no_attention"]:
        change_events: dict = {}
        for e in events:
            if e.get("type") in VISUAL_CHANGE_TYPES or e.get("scene_change"):
                change_events.setdefault(int(e["ms"]), e)
        changes = sorted(change_events)
        gap_ms = int(settings["attention_gap_s"] * 1000)
        lo_s, hi_s = float(settings["attention_interval_s"][0]), float(settings["attention_interval_s"][-1])
        intervals = sorted((c["ms"], int(c.get("end_ms") or c["ms"])) for c in accepted)
        cursor = 0
        guard = 0
        while guard < 200:
            guard += 1
            nxt = next((iv for iv in intervals if iv[0] > cursor), None)
            nxt_start = nxt[0] if nxt else duration_ms
            if nxt_start - cursor <= gap_ms:
                if nxt is None:
                    break
                cursor = max(cursor, nxt[1])
                continue
            target = cursor + int(rng.uniform(lo_s, hi_s) * 1000)
            if target >= nxt_start - settings["min_spacing_ms"]:
                target = cursor + (nxt_start - cursor) // 2
            lo = max(cursor + settings["min_spacing_ms"], settings["attention_min_start_ms"])
            hi = nxt_start - settings["min_spacing_ms"]
            options = [t for t in changes if lo <= t <= hi and not (ask_window and ask_window[0] <= t <= ask_window[1])]
            placed = False
            for best in sorted(options, key=lambda t: abs(t - target)):
                e = change_events[best]
                n += 1
                c = {"id": f"c{n:02d}", "ms": best, "cue_type": "attention", "group": "attention", "priority": GROUP_PRIORITY["attention"], "event": _event_ref(e),
                     "why": f"{(best - cursor) / 1000:.1f} s without a sound; a whoosh on a visual change"}
                why_not = density.reason_against(best)
                if why_not:
                    dropped.append({**c, "reason": why_not})
                    continue
                density.add(best)
                accepted.append(c)
                intervals = sorted(intervals + [(best, best)])
                cursor = best
                placed = True
                break
            if not placed:
                if nxt is None:
                    break
                cursor = max(cursor, nxt[1])
    accepted.sort(key=lambda c: (c["ms"], c["priority"]))
    return {"seed": seed, "cues": accepted, "dropped": dropped, "settings": settings, "feedback_applied": applied,
            "counts": {g: sum(1 for c in accepted if c["group"] == g) for g in GROUP_PRIORITY}, "candidates": len(cands)}


def events_duration(events: list[dict]) -> int:
    return max([int(e.get("ms", 0)) for e in events] + [0])
