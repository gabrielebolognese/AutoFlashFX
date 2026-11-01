"""classify.py: tags, categories, whoosh speed and cue type candidates for every measured file (BUILD_SPEC.md
2.6, items 2 and 3).

Rules first (the file name's words; the folder is only a hint): whoosh, click, pop, typing, success, notification,
negative, impact, tick. A whoosh gets a speed class from its measurements (DECISIONS.md, M8):
  fast    effective 0.35 s or shorter, or effective 0.6 s or shorter with an attack of 0.08 s or shorter
  slow    effective 0.8 s or longer with an attack of 0.2 s or longer (a gradual swell), or 1.5 s or longer
  medium  the rest
Every category maps to ranked cue type candidates (category fit 1.0 for the natural use, less for a secondary
use). A file no rule understands, or whose measurements contradict its name (a "pop" 2.7 s long), is unclear: it
goes to the indexer model in one batched call (prompt_lines gives the lines, merge_answers applies the answer:
cue types best first, tags, a confidence; under config sfx.build.min_confidence it waits for the user's pin).

  classify_rules(file, settings) -> dict(tags, category, whoosh_speed, candidates, source, confidence, unclear)
  prompt_lines(files) -> the text lines for the prompt
  merge_answers(files, answers) -> the ids answered
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CUE_TYPES, clean  # noqa: E402

RULES_VERSION = 2  # bump when the rules below change: the settings hash changes and the map rebuilds its pools

DEFAULT_WHOOSH = {
    "fast_max_s": 0.35, "fast_sharp_max_s": 0.60, "sharp_attack_s": 0.08,
    "slow_min_s": 0.80, "swell_attack_s": 0.20, "long_min_s": 1.50,
}

# words that carry no meaning in a sound file's name
STOP_WORDS = {"sound", "sounds", "effect", "effects", "sfx", "fx", "hd", "by", "the", "a", "of", "free", "pack",
              "ashish", "editz", "ese", "fight", "v", "ver", "version", "final", "new", "mp3", "wav"}

RULES: list[tuple[str, set[str]]] = [
    ("whoosh", {"whoosh", "woosh", "swoosh", "swoos", "swish", "whip", "wind", "air", "blow", "swosh", "wosh"}),
    ("click", {"click", "clicks", "mouse"}),
    ("pop", {"pop", "pops"}),
    ("typing", {"typing", "keyboard", "writing", "typewriter", "keys", "keystroke", "keystrokes"}),
    ("success", {"ding", "chime", "bell", "correct", "success", "achievement", "complete", "done", "win"}),
    ("notification", {"notification", "notify", "message", "discord", "ping", "imessage", "whatsapp", "dm"}),
    ("negative", {"error", "erro", "wrong", "fail", "failure", "buzz", "buzzer", "denied", "scratch", "incorrect"}),
    ("impact", {"boom", "thud", "hit", "impact", "slam", "punch", "kick", "stamp", "bass", "thump", "bang"}),
    ("tick", {"tick", "ticks", "counter", "count", "tock"}),
]

# category -> ranked cue type candidates with the category fit (the whoosh entries depend on the speed class)
CATEGORY_CUES: dict[str, dict[str, float]] = {
    "click": {"ui_click": 1.0, "number": 0.7, "hero_enter": 0.5},
    "pop": {"hero_enter": 1.0, "ui_click": 0.5, "number": 0.4},
    "typing": {"typing": 1.0},
    "success": {"success": 1.0, "notification": 0.5},
    "notification": {"notification": 1.0, "success": 0.4},
    "negative": {"negative": 1.0},
    "impact": {"stamp": 1.0, "hook_hit": 0.9},
    "tick": {"number": 1.0, "ui_click": 0.6},
}
WHOOSH_CUES: dict[str, dict[str, float]] = {
    "fast": {"transition_fast": 1.0, "attention": 1.0},
    "medium": {"transition_fast": 0.6, "transition_slow": 0.6, "attention": 0.5},
    "slow": {"transition_slow": 1.0},
}
MODEL_RANK_FIT = (1.0, 0.8, 0.6)


def words_of(text: str) -> list[str]:
    base = os.path.splitext(text)[0]
    base = re.sub(r"([a-z])([A-Z])", r"\1 \2", base)  # PlaneWoosh -> Plane Woosh
    base = re.sub(r"([A-Za-z])(\d)", r"\1 \2", base)   # Swoosh01 -> Swoosh 01
    base = re.sub(r"(\d)([A-Za-z])", r"\1 \2", base)   # 2pop -> 2 pop
    return [w for w in re.split(r"[^a-z0-9]+", base.lower()) if w]


def tags_of(relpath: str) -> list[str]:
    folders = [w for part in relpath.split("/")[:-1] for w in words_of(part)]
    names = words_of(os.path.basename(relpath))
    out: list[str] = []
    for w in folders + names:
        if w in STOP_WORDS or w.isdigit() or len(w) < 2 or w in out:
            continue
        out.append(w)
    return out


def match_category(words: list[str]) -> str | None:
    hits = []
    for cat, keys in RULES:
        if any(w in keys for w in words):
            hits.append(cat)
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]
    # two categories named at once ("Mouse Click Pop"): the first in the words' order wins
    for w in words:
        for cat, keys in RULES:
            if w in keys and cat in hits:
                return cat
    return hits[0]


def whoosh_speed(f: dict, settings: dict | None = None) -> str:
    s = dict(DEFAULT_WHOOSH)
    s.update(settings or {})
    eff = float(f.get("effective_s") or 0.0)
    attack = float(f.get("attack_s") or 0.0)
    if eff <= s["fast_max_s"] or (eff <= s["fast_sharp_max_s"] and attack <= s["sharp_attack_s"]):
        return "fast"
    if eff >= s["long_min_s"] or (eff >= s["slow_min_s"] and attack >= s["swell_attack_s"]):
        return "slow"
    return "medium"


def classify_rules(f: dict, settings: dict | None = None) -> dict:
    """The rule-based classification of one measured file (no model). Sets f's classification fields and returns
    them. A decode error leaves the file unclassified and not unclear (nothing to ask about)."""
    whoosh_cfg = (settings or {}).get("whoosh") if settings else None
    tags = tags_of(f["path"])
    name_words = words_of(os.path.basename(f["path"]))
    folder_words = [w for part in f["path"].split("/")[:-1] for w in words_of(part)]
    out = {"tags": tags, "category": None, "whoosh_speed": None, "candidates": {}, "source": "rules",
           "confidence": 1.0, "unclear": False, "hint": None}
    if f.get("decode_error"):
        f.update(out)
        return out
    cat = match_category(name_words)
    hint = match_category(folder_words)
    out["hint"] = hint
    if cat is None:
        out["unclear"] = True
        out["candidates"] = {}
        out["confidence"] = 0.0
        if hint == "whoosh":
            out["whoosh_speed"] = whoosh_speed(f, whoosh_cfg)
        f.update(out)
        return out
    out["category"] = cat
    if cat == "whoosh":
        speed = whoosh_speed(f, whoosh_cfg)
        out["whoosh_speed"] = speed
        cands = dict(WHOOSH_CUES[speed])
        eff = float(f.get("effective_s") or 0.0)
        attack = float(f.get("attack_s") or 1.0)
        # a whoosh with a quick attack and some length can carry the hook's set piece (a secondary use)
        if eff >= 0.5 and attack <= 0.2:
            cands["hook_hit"] = 0.5
        # a whip crack is also a short hit
        if "whip" in name_words and attack <= 0.08:
            cands["stamp"] = 0.5
        out["candidates"] = cands
    else:
        out["candidates"] = dict(CATEGORY_CUES[cat])
    f.update(out)
    return out


def contradicts_name(f: dict, windows: dict[str, tuple[float, float]], factor: float = 2.0) -> bool:
    """True when the measured effective duration is beyond `factor` times the upper window of every candidate cue
    type: the name says one thing, the sound another (a 2.7 s "pop")."""
    eff = float(f.get("effective_s") or 0.0)
    cands = f.get("candidates") or {}
    if not cands:
        return False
    return all(eff > factor * windows.get(c, (0, 2.5))[1] for c in cands)


def brightness_word(hz) -> str:
    if hz is None:
        return "unknown"
    hz = float(hz)
    if hz < 800:
        return f"{hz:.0f} Hz (dark, bassy)"
    if hz < 3000:
        return f"{hz:.0f} Hz (mid)"
    return f"{hz:.0f} Hz (bright)"


def prompt_lines(files: list[dict]) -> str:
    lines = []
    for f in files:
        folder = f.get("folder") or "(loose file, no folder)"
        guess = f.get("category") or "none"
        if f.get("hint") and not f.get("category"):
            guess = f"none from the name; the folder suggests {f['hint']}"
        if f.get("category") == "whoosh" and f.get("whoosh_speed"):
            guess += f" ({f['whoosh_speed']})"

        def num(key, fmt="{:.2f}", unit=""):
            v = f.get(key)
            return (fmt.format(float(v)) + unit) if isinstance(v, (int, float)) else "?"
        lines.append(
            f"- id {f['id']}: folder \"{clean(folder)}\", file \"{clean(f['name'])}\"; duration {num('duration_s')} s, "
            f"effective {num('effective_s')} s, attack {num('attack_s')} s, tail {num('tail_s')} s, "
            f"peak {num('peak_dbfs', '{:.1f}')} dBFS, loudness {num('lufs', '{:.1f}')} LUFS, "
            f"brightness {brightness_word(f.get('centroid_hz'))}, {f.get('channels') or '?'} ch; "
            f"rule guess: {guess}")
    return "\n".join(lines)


def merge_answers(files: list[dict], answers: list[dict], asked_at: str) -> set[str]:
    """Apply the model's answers (several files: a later one wins for the same id). Returns the ids applied."""
    by_id = {f["id"]: f for f in files}
    applied: set[str] = set()
    for a in answers:
        for item in (a.get("files", []) if isinstance(a, dict) else []):
            if not isinstance(item, dict):
                continue
            fid = str(item.get("id", ""))
            f = by_id.get(fid)
            if f is None:
                continue
            cues = [c for c in (item.get("cue_types") or []) if isinstance(c, str) and c in CUE_TYPES]
            seen: list[str] = []
            for c in cues:
                if c not in seen:
                    seen.append(c)
            cues = seen[:3]
            try:
                conf = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
            except (TypeError, ValueError):
                conf = 0.0
            tags = [clean(t).lower() for t in (item.get("tags") or []) if isinstance(t, str) and clean(t)][:8]
            note = clean(item.get("note", ""))[:200]
            f["model"] = {"cue_types": cues, "tags": tags, "confidence": round(conf, 2), "note": note, "asked_at": asked_at}
            apply_model(f)
            applied.add(fid)
    return applied


def apply_model(f: dict) -> None:
    """Set the classification fields from f['model'] (a cached or fresh answer)."""
    m = f.get("model") or {}
    cues = [c for c in m.get("cue_types", []) if c in CUE_TYPES]
    f["candidates"] = {c: MODEL_RANK_FIT[min(i, 2)] for i, c in enumerate(cues)}
    f["source"] = "model"
    f["confidence"] = float(m.get("confidence", 0.0))
    f["unclear"] = False
    for t in m.get("tags", []):
        if t and t not in f["tags"]:
            f["tags"].append(t)
    if not f.get("category"):
        f["category"] = "other"
