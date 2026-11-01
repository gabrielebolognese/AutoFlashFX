#!/usr/bin/env python
"""hooks.py: the hooks library (BUILD_SPEC.md 2.2 and S5; PLAN.md M5).

The user's templates live in library/hooks.txt (one hook per line, `__` marks the blank, quotes optional, empty
lines and # lines ignored, never edited by the pipeline). This module parses that file, keeps the index
library/.hooks.index.json (id, family, fits_problem_solution, blanks; family and fit from one batched call to the
indexer model, made by pipeline/bin/index-hooks), writes library/hooks.lint.txt (broken blanks, grammar problems,
duplicates, em dashes), keeps library/.hooks.stats.json (times picked, times won, judge scores, keyed by id), maps
the vendor formulas (pipeline/vendor/ig-agent-skill/hooks.json, 26 shapes) to the same six families, builds the
template shortlist for the hooks stage (weighted by win rate once there is data, uniform at first, fit preferred),
checks the model's filled hooks against the rules of spec S5 and composes 05-hooks/hooks.json, and measures the
brief (tokens = words x 1.3).

  hooks.py parse --file hooks.txt                       JSON list of the parsed lines
  hooks.py index-plan --file F --index I [--force]      what index-hooks must do: {unchanged, to_classify, total}
  hooks.py index-write --file F --index I [--answer A.json]... --lint L --stats S --suggested G [--model NAME]
                                                        merge the model's answers into the index (a later answer
                                                        wins for the same id), write the lint, create the stats
                                                        and suggested files when missing
  hooks.py suggest --file hooks.suggested.txt --shapes '["..."]' --source TEXT   append new hook shapes, deduplicated
  hooks.py vendor --vendor hooks.json                   the 26 vendor formulas with their family and fit
  hooks.py shortlist --index I --stats S --vendor V --n 24 --seed TEXT --out shortlist.json [--fit-weight 0.35]
  hooks.py limits --wpm 150 [--max-words 8] [--max-seconds 3]   {max_words, wpm, seconds_per_word}
  hooks.py check --answer OUT.json --shortlist shortlist.json --index I --vendor V --wpm N --out hooks.json
                 [--min 12 --max 20 --min-families 3 --on-screen-max 6 --max-words 8 --max-seconds 3]
                 [--force] [--keep hooks.json --survivors h01,h02] [--idea-id ID] [--written-by TEXT]
  hooks.py brief --answer OUT.json --out brief.md --header header.md [--min 2000 --max 3000] [--force]
  hooks.py tokens --file brief.md                       {words, tokens}
  hooks.py wpm --voice voice.md --default 150           the measured pace of voice.md, or the default
  hooks.py stats-update --stats S --picked id,id --won id --scores '{"id": 0.8}' [--date D]
  hooks.py templates-text --shortlist shortlist.json    the shortlist as a markdown list for the prompt

Every text that comes from the user's file or from a model is cleaned of em dashes (errors.undash) and CR
characters. Paths may be C:/... or /c/... (both work). Exit 0 ok, 1 usage, 2 file error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errors import undash  # noqa: E402

FAMILIES = ["tools-listicle", "how-to-system", "mistake-warning", "myth-contrarian", "story-confession",
            "transformation"]
UNCLASSIFIED = "unclassified"
INDEX_VERSION = 1
STATS_VERSION = 1
TOKENS_PER_WORD = 1.3
WORD_RE = re.compile(r"[A-Za-z0-9$%'’\u2019-]+")

# The vendor's 26 formulas mapped to the spec's six families, plus whether each one naturally opens a reel that
# presents a viewer's problem and then a solution (DECISIONS.md M5). Judgment calls, recorded once here.
VENDOR_FAMILY = {
    1: ("story-confession", False), 2: ("mistake-warning", True), 3: ("myth-contrarian", True),
    4: ("tools-listicle", True), 5: ("transformation", True), 6: ("transformation", True),
    7: ("mistake-warning", True), 8: ("story-confession", False), 9: ("how-to-system", True),
    10: ("how-to-system", True), 11: ("tools-listicle", True), 12: ("myth-contrarian", True),
    13: ("transformation", True), 14: ("mistake-warning", True), 15: ("story-confession", False),
    16: ("how-to-system", True), 17: ("tools-listicle", True), 18: ("how-to-system", True),
    19: ("mistake-warning", True), 20: ("myth-contrarian", True), 21: ("story-confession", False),
    22: ("myth-contrarian", True), 23: ("myth-contrarian", True), 24: ("tools-listicle", False),
    25: ("transformation", False), 26: ("tools-listicle", True),
}

NUMBER_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "fifteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "million", "billion", "dozen", "half", "twice", "double", "triple", "first", "second", "third",
    "once",
}
TIME_WORDS = {
    "second", "seconds", "sec", "secs", "minute", "minutes", "min", "mins", "hour", "hours", "day", "days",
    "week", "weeks", "month", "months", "year", "years", "today", "tonight", "tomorrow", "overnight", "daily",
    "weekly", "instantly", "now",
}
PREPOSITIONS = ("in", "on", "for", "with", "at", "of", "about", "into", "to", "from", "by", "around", "through",
                "during", "my", "your", "the", "a", "an", "doing", "do")
BROKEN_BLANK_RES = [
    re.compile(r"\b(?:" + "|".join(PREPOSITIONS) + r")\s*(?:[.,!?;:]|$)", re.IGNORECASE),
    re.compile(r"\b(?:in|on|at|of|about|into|to|from|by|around|through|during|with|for)\s+"
               r"(?:actually|really|truly|finally|also|just|even|still|always|never)\s+\w+", re.IGNORECASE),
    re.compile(r"(?<!_)_(?!_)|_{3,}"),
]


# ------------------------------------------------------------------------------------------------ helpers
def winpath(path: str) -> str:
    """/c/Users/... from Git Bash -> C:/Users/... for Windows Python."""
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def clean(value, one_line: bool = True) -> str:
    s = "" if value is None else str(value)
    s = undash(s.replace("\r\n", "\n").replace("\r", "\n"))
    return " ".join(s.split()) if one_line else s


def read_text(path: str) -> str:
    with open(winpath(path), encoding="utf-8-sig", errors="replace") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def load_json(path: str, default=None):
    try:
        with open(winpath(path), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path: str, data) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)


def save_text(path: str, content: str) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def out_json(data) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")


def words_of(text: str) -> list[str]:
    """Spoken words: "$18,000" and "rgba(0,0,0,.1)" count as one word each, like the vendor's hookscore.py."""
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text or ""))


def today() -> str:
    return time.strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------------------ hooks.txt
def normalize_hook(text: str) -> str:
    """The text the id is hashed from: NFC, em dash to comma, straight apostrophes, quotes stripped, whitespace
    collapsed, lower case. A fixed em dash, a case fix or a re-quoted line therefore keeps its stats."""
    s = unicodedata.normalize("NFC", text or "").replace("\r", "")
    s = undash(s).replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1].strip()
    return " ".join(s.split()).lower()


def display_hook(text: str) -> str:
    s = unicodedata.normalize("NFC", text or "").replace("\r", "")
    s = undash(s).strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1].strip()
    elif len(s) >= 2 and s[0] == "\u201c" and s[-1] == "\u201d":
        s = s[1:-1].strip()
    return " ".join(s.split())


def hook_id(text: str) -> str:
    return hashlib.sha1(normalize_hook(text).encode("utf-8")).hexdigest()[:10]


def broken_blank(text: str, blanks: int) -> bool:
    if blanks > 0:
        return bool(re.search(r"(?<!_)_(?!_)|_{3,}", text))
    return any(r.search(text) for r in BROKEN_BLANK_RES)


def parse_file(path: str) -> list[dict]:
    try:
        raw = read_text(path)
    except OSError:
        return []
    entries: list[dict] = []
    seen: dict[str, int] = {}
    for n, line in enumerate(raw.split("\n"), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        text = display_hook(stripped)
        if not text:
            continue
        norm = normalize_hook(stripped)
        hid = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:10]
        blanks = text.count("__")
        entry = {
            "line": n, "id": hid, "text": text, "normalized": norm, "blanks": blanks,
            "em_dash": "\u2014" in stripped, "broken_blank": broken_blank(text, blanks),
            "duplicate_of": seen.get(hid),
        }
        seen.setdefault(hid, n)
        entries.append(entry)
    return entries


def source_hash(path: str) -> str:
    try:
        raw = read_text(path)
    except OSError:
        return ""
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ the index
def index_entries_by_id(index: dict | None) -> dict:
    if not isinstance(index, dict):
        return {}
    return {h.get("id"): h for h in index.get("hooks", []) if isinstance(h, dict) and h.get("id")}


def cmd_index_plan(args) -> int:
    entries = parse_file(args.file)
    index = load_json(args.index)
    known = index_entries_by_id(index)
    sha = source_hash(args.file)
    to_classify = []
    seen = set()
    for e in entries:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        old = known.get(e["id"])
        if old and old.get("family") in FAMILIES and not args.force:
            continue
        to_classify.append({"id": e["id"], "text": e["text"]})
    unchanged = (bool(index) and index.get("source_sha1") == sha and index.get("version") == INDEX_VERSION
                 and not to_classify and not args.force)
    out_json({"unchanged": unchanged, "to_classify": to_classify, "total": len(seen), "source_sha1": sha,
              "index_exists": bool(index)})
    return 0


def cmd_index_write(args) -> int:
    entries = parse_file(args.file)
    old_index = load_json(args.index)
    known = index_entries_by_id(old_index)
    answers: dict = {}
    for path in (args.answer or []):  # several answers: a later one wins for the same id
        a = load_json(path, {})
        for item in (a.get("hooks", []) if isinstance(a, dict) else []):
            if isinstance(item, dict) and item.get("id") and item.get("family") in FAMILIES:
                answers[str(item["id"])] = item
    hooks = []
    seen = set()
    by_family: dict[str, int] = {}
    for e in entries:
        if e["id"] in seen:
            continue  # a duplicate line: indexed once, listed in the lint
        seen.add(e["id"])
        src = answers.get(e["id"]) or known.get(e["id"]) or {}
        family = src.get("family") if src.get("family") in FAMILIES else UNCLASSIFIED
        fit = bool(src.get("fits_problem_solution", False)) if family != UNCLASSIFIED else False
        issue = clean(src.get("issue", ""))
        hooks.append({
            "id": e["id"], "line": e["line"], "text": e["text"], "family": family,
            "fits_problem_solution": fit, "blanks": e["blanks"], "issue": issue,
            "broken_blank": e["broken_blank"], "em_dash": e["em_dash"],
        })
        by_family[family] = by_family.get(family, 0) + 1
    index = {
        "version": INDEX_VERSION, "source": "library/hooks.txt", "source_sha1": source_hash(args.file),
        "built": time.strftime("%Y-%m-%d %H:%M"), "model": args.model or (old_index or {}).get("model", ""),
        "families": FAMILIES, "counts": {"total": len(hooks), "by_family": by_family,
                                          "unclassified": by_family.get(UNCLASSIFIED, 0)},
        "hooks": hooks,
    }
    save_json(args.index, index)
    # the lint: broken blanks, grammar problems (the model's notes), duplicates, em dashes
    lint_lines = []
    for e in entries:
        text = e["text"]
        if e["duplicate_of"]:
            lint_lines.append(f"line {e['line']}: duplicate of line {e['duplicate_of']}: {text}")
        if e["broken_blank"]:
            lint_lines.append(f"line {e['line']}: broken blank (the __ placeholder was probably lost): {text}")
        if e["em_dash"]:
            lint_lines.append(f"line {e['line']}: em dash (the pipeline reads it as a comma; replace it with a comma, a colon or a period): {text}")
        issue = next((h["issue"] for h in hooks if h["id"] == e["id"]), "")
        if issue and not e["duplicate_of"]:
            lint_lines.append(f"line {e['line']}: grammar: {issue}: {text}")
    lint = ["# hooks.lint.txt: problems found in library/hooks.txt by pipeline/bin/index-hooks (rebuilt whenever the",
            "# file changes; never edited by hand, never read by the runner). Fix the lines in hooks.txt yourself.",
            f"# {time.strftime('%Y-%m-%d %H:%M')}: {len(hooks)} hooks indexed, {len(lint_lines)} problem(s).", ""]
    lint += lint_lines or ["(no problems)"]
    save_text(args.lint, "\n".join(lint) + "\n")
    if args.stats and not os.path.isfile(winpath(args.stats)):
        save_json(args.stats, {"version": STATS_VERSION, "updated": "", "hooks": {}})
    if args.suggested and not os.path.isfile(winpath(args.suggested)):
        save_text(args.suggested, "# hooks.suggested.txt: new hook shapes the pipeline noticed (BUILD_SPEC.md 2.2).\n"
                  "# One per line, like hooks.txt. Move the ones you like into hooks.txt yourself; the runner never reads this file.\n")
    out_json({"total": len(hooks), "classified": len(hooks) - by_family.get(UNCLASSIFIED, 0),
              "unclassified": by_family.get(UNCLASSIFIED, 0), "lint": len(lint_lines), "by_family": by_family,
              "answered": len(answers)})
    return 0


# ------------------------------------------------------------------------------------------------ the vendor
def vendor_formulas(path: str) -> list[dict]:
    data = load_json(path, {})
    out = []
    for h in (data.get("hooks", []) if isinstance(data, dict) else []):
        try:
            n = int(h.get("id"))
        except (TypeError, ValueError):
            continue
        family, fit = VENDOR_FAMILY.get(n, (UNCLASSIFIED, False))
        template = clean(h.get("template", ""))
        out.append({
            "id": f"v{n:02d}", "source": "vendor", "name": clean(h.get("name", "")), "text": template,
            "example": clean(h.get("example", "")), "on_screen": clean(h.get("on_screen", "")),
            "best_for": clean(h.get("best_for", "")), "trap": clean(h.get("trap", "")),
            "family": family, "fits_problem_solution": fit, "blanks": len(re.findall(r"\{[^{}]*\}", template)),
        })
    return out


def cmd_vendor(args) -> int:
    out_json(vendor_formulas(args.vendor))
    return 0


# ------------------------------------------------------------------------------------------------ the stats
def load_stats(path: str) -> dict:
    s = load_json(path, None)
    if not isinstance(s, dict) or not isinstance(s.get("hooks"), dict):
        s = {"version": STATS_VERSION, "updated": "", "hooks": {}}
    return s


def win_rate(rec: dict | None) -> float:
    picked = int((rec or {}).get("picked", 0) or 0)
    won = int((rec or {}).get("won", 0) or 0)
    return (won + 1.0) / (picked + 2.0)  # Laplace: 0.5 with no data


def cmd_stats_update(args) -> int:
    stats = load_stats(args.stats)
    hooks = stats["hooks"]
    date = args.date or today()
    picked = [p for p in (args.picked or "").split(",") if p]
    try:
        scores = json.loads(args.scores or "{}")
    except ValueError:
        scores = {}
    texts = {}
    if args.texts:
        try:
            texts = json.loads(args.texts)
        except ValueError:
            texts = {}
    for tid in picked:
        rec = hooks.setdefault(tid, {"picked": 0, "won": 0, "scores": [], "last_picked": "", "text": ""})
        rec["picked"] = int(rec.get("picked", 0)) + 1
        rec["last_picked"] = date
        if tid in texts and texts[tid]:
            rec["text"] = clean(texts[tid])
        if tid in scores:
            try:
                rec.setdefault("scores", []).append(round(float(scores[tid]), 3))
            except (TypeError, ValueError):
                pass
            rec["scores"] = rec["scores"][-20:]
    if args.won:
        rec = hooks.setdefault(args.won, {"picked": 0, "won": 0, "scores": [], "last_picked": date, "text": ""})
        rec["won"] = int(rec.get("won", 0)) + 1
        rec["last_won"] = date
    stats["updated"] = time.strftime("%Y-%m-%d %H:%M")
    save_json(args.stats, stats)
    out_json({"picked": len(picked), "won": args.won or "", "hooks": len(hooks)})
    return 0


# ------------------------------------------------------------------------------------------------ the shortlist
def weighted_sample(rng: random.Random, items: list[dict], k: int) -> list[dict]:
    pool = list(items)
    out = []
    while pool and len(out) < k:
        weights = [max(i["weight"], 1e-6) for i in pool]
        pick = rng.choices(range(len(pool)), weights=weights, k=1)[0]
        out.append(pool.pop(pick))
    return out


def build_shortlist(index: dict | None, stats: dict, vendor: list[dict], n: int, seed: str,
                    fit_weight: float, per_family: int) -> list[dict]:
    candidates = []
    for h in (index or {}).get("hooks", []) if isinstance(index, dict) else []:
        if h.get("broken_blank") or not h.get("text"):
            continue
        candidates.append({"template_id": h["id"], "source": "library", "family": h.get("family", UNCLASSIFIED),
                           "fits_problem_solution": bool(h.get("fits_problem_solution")), "text": h["text"],
                           "blanks": h.get("blanks", 0), "example": "", "on_screen": "", "name": ""})
    for v in vendor:
        candidates.append({"template_id": v["id"], "source": "vendor", "family": v["family"],
                           "fits_problem_solution": v["fits_problem_solution"], "text": v["text"],
                           "blanks": v["blanks"], "example": v["example"], "on_screen": v["on_screen"],
                           "name": v["name"]})
    hooks_stats = stats.get("hooks", {})
    for c in candidates:
        rec = hooks_stats.get(c["template_id"])
        c["win_rate"] = round(win_rate(rec), 3)
        c["picked"] = int((rec or {}).get("picked", 0) or 0)
        c["won"] = int((rec or {}).get("won", 0) or 0)
        c["weight"] = c["win_rate"] * (1.0 if c["fits_problem_solution"] else fit_weight)
    rng = random.Random(f"shortlist:{seed}")
    chosen: list[dict] = []
    taken = set()
    for fam in FAMILIES:  # every family present in the pool is represented
        fam_pool = [c for c in candidates if c["family"] == fam]
        for c in weighted_sample(rng, fam_pool, per_family):
            chosen.append(c)
            taken.add(c["template_id"])
    rest = [c for c in candidates if c["template_id"] not in taken]
    chosen += weighted_sample(rng, rest, max(0, n - len(chosen)))
    rng.shuffle(chosen)
    for c in chosen:
        c.pop("weight", None)
    return chosen[:max(n, len(chosen))] if n <= 0 else chosen


def cmd_shortlist(args) -> int:
    index = load_json(args.index)
    stats = load_stats(args.stats) if args.stats else {"hooks": {}}
    vendor = vendor_formulas(args.vendor) if args.vendor else []
    chosen = build_shortlist(index, stats, vendor, args.n, args.seed, args.fit_weight, args.per_family)
    save_json(args.out, chosen)
    fams = sorted({c["family"] for c in chosen})
    out_json({"n": len(chosen), "families": fams, "library": sum(1 for c in chosen if c["source"] == "library"),
              "vendor": sum(1 for c in chosen if c["source"] == "vendor"),
              "with_data": sum(1 for c in chosen if c["picked"] > 0)})
    return 0


def cmd_templates_text(args) -> int:
    chosen = load_json(args.shortlist, [])
    lines = []
    for c in chosen:
        fit = "yes" if c.get("fits_problem_solution") else "no"
        extra = ""
        if c.get("source") == "vendor":
            extra = f' (vendor formula "{c.get("name", "")}"; example: "{c.get("example", "")}"; on screen: "{c.get("on_screen", "")}")'
        lines.append(f"- template_id `{c['template_id']}` | family {c.get('family')} | fits problem to solution: {fit} | "
                     f"win rate so far {c.get('win_rate', 0.5)} ({c.get('won', 0)}/{c.get('picked', 0)}) | \"{c.get('text', '')}\"{extra}")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


# ------------------------------------------------------------------------------------------------ limits
def max_spoken_words(wpm: float, max_words: int, max_seconds: float) -> int:
    """8 words or fewer and under max_seconds at the user's pace: words x 60 / wpm < max_seconds."""
    import math
    by_time = math.ceil(wpm * max_seconds / 60.0) - 1  # the largest count strictly under the limit
    return max(3, min(int(max_words), by_time))


def cmd_limits(args) -> int:
    mw = max_spoken_words(args.wpm, args.max_words, args.max_seconds)
    out_json({"wpm": args.wpm, "max_words": mw, "seconds_per_word": round(60.0 / args.wpm, 3),
              "max_seconds": args.max_seconds})
    return 0


# ------------------------------------------------------------------------------------------------ the check
def has_concrete_marker(spoken: str, marker: str, kind: str) -> tuple[bool, str]:
    sp = spoken.lower()
    mk = (marker or "").strip()
    if not mk:
        return False, "no marker given"
    if mk.lower() not in sp:
        return False, f'the marker "{mk}" is not in the spoken line'
    low = [w.lower().strip("'’") for w in words_of(mk)]
    has_digit = bool(re.search(r"\d", mk))
    number_word = any(w in NUMBER_WORDS for w in low)
    time_word = any(w in TIME_WORDS for w in low)
    looks_name = bool(re.search(r"[A-Z]", mk)) or bool(re.search(r"[./\\_@#-]", mk)) or any(
        w.endswith((".md", ".py", ".js", ".json")) for w in low)
    if has_digit or number_word or time_word or looks_name:
        return True, ""
    return False, f'the marker "{mk}" ({kind}) is neither a named tool, a number nor a time'


def known_templates(shortlist: list[dict], index: dict | None, vendor: list[dict]) -> dict:
    known = {}
    for v in vendor:
        known[v["id"]] = {"family": v["family"], "source": "vendor", "text": v["text"]}
    for h in ((index or {}).get("hooks", []) if isinstance(index, dict) else []):
        known[h["id"]] = {"family": h.get("family", UNCLASSIFIED), "source": "library", "text": h.get("text", "")}
    for c in shortlist:
        known[c["template_id"]] = {"family": c.get("family", UNCLASSIFIED), "source": c.get("source", ""),
                                   "text": c.get("text", "")}
    return known


def cmd_check(args) -> int:
    answer = load_json(args.answer, {})
    shortlist = load_json(args.shortlist, []) if args.shortlist else []
    index = load_json(args.index) if args.index else None
    vendor = vendor_formulas(args.vendor) if args.vendor else []
    known = known_templates(shortlist, index, vendor)
    max_words = max_spoken_words(args.wpm, args.max_words, args.max_seconds)
    kept: list[dict] = []
    errors: list[str] = []
    dropped: list[dict] = []
    seen_norm: set[str] = set()
    # regenerate mode: the survivors of the previous hooks.json are kept as they are
    if args.keep:
        previous = load_json(args.keep, {}).get("hooks", [])
        survivors = {s for s in (args.survivors or "").split(",") if s}
        for h in previous:
            if h.get("id") in survivors:
                kept.append(dict(h))
                seen_norm.add(normalize_hook(h.get("spoken", "")))
    raw_hooks = answer.get("hooks", []) if isinstance(answer, dict) else []
    if not isinstance(raw_hooks, list):
        raw_hooks = []
    for i, h in enumerate(raw_hooks, 1):
        if not isinstance(h, dict):
            errors.append(f"hook {i}: not an object")
            continue
        spoken = clean(h.get("spoken", ""))
        on_screen = clean(h.get("on_screen", ""))
        marker = clean(h.get("marker", ""))
        kind = clean(h.get("marker_kind", "")).lower()
        family = clean(h.get("family", "")).lower()
        tid = clean(h.get("template_id", ""))
        problems = []
        n_sp = len(words_of(spoken))
        n_os = len([w for w in words_of(on_screen) if re.search(r"[A-Za-z0-9]", w)])
        if not spoken:
            problems.append("no spoken line")
        elif n_sp > max_words:
            problems.append(f"spoken line has {n_sp} words, the cap is {max_words} (8 words or fewer and under "
                            f"{args.max_seconds:g} s at {args.wpm:g} words per minute)")
        if not on_screen:
            problems.append("no on-screen line")
        elif n_os > args.on_screen_max:
            problems.append(f"on-screen line has {n_os} words, the cap is {args.on_screen_max}")
        ok_marker, why = has_concrete_marker(spoken, marker, kind)
        if not ok_marker:
            problems.append(why)
        if family not in FAMILIES:
            problems.append(f'family "{family}" is not one of {", ".join(FAMILIES)}')
        if tid not in known:
            problems.append(f'template_id "{tid}" is not in the list you were given')
        norm = normalize_hook(spoken)
        if norm and norm in seen_norm:
            problems.append("the same spoken line appears twice")
        if problems:
            errors.append(f'hook {i} "{spoken[:60]}": ' + "; ".join(problems))
            dropped.append({"spoken": spoken, "problems": problems})
            continue
        seen_norm.add(norm)
        kept.append({
            "id": "", "template_id": tid, "template": known[tid]["text"], "template_source": known[tid]["source"],
            "family": family, "spoken": spoken, "on_screen": on_screen, "marker": marker,
            "marker_kind": kind if kind in ("tool", "number", "time") else "",
            "spoken_words": n_sp, "spoken_seconds": round(n_sp * 60.0 / args.wpm, 2), "on_screen_words": n_os,
        })
    if len(kept) > args.max:
        kept = kept[:args.max]
    for n, h in enumerate(kept, 1):
        h["id"] = f"h{n:02d}"
    families = sorted({h["family"] for h in kept})
    rule_errors = list(errors)
    if len(kept) < args.min:
        rule_errors.append(f"only {len(kept)} valid hooks, at least {args.min} are needed (write more, one per template)")
    if len(families) < args.min_families:
        rule_errors.append(f"the valid hooks come from {len(families)} famil{'y' if len(families) == 1 else 'ies'} "
                           f"({', '.join(families) or 'none'}), at least {args.min_families} are needed")
    ok = not rule_errors
    written = False
    if ok or args.force:
        if len(kept) >= args.min_for_judge:
            data = {
                "idea_id": args.idea_id or "", "written_by": args.written_by or "05-hooks", "checked": today(),
                "wpm": args.wpm, "max_spoken_words": max_words, "templates_considered": len(shortlist),
                "families": families, "hooks": kept, "rule_errors": [] if ok else rule_errors,
                "dropped": dropped, "notes": clean(answer.get("notes", "")) if isinstance(answer, dict) else "",
            }
            if args.keep:
                data["regenerated"] = True
            save_json(args.out, data)
            written = True
    out_json({"ok": ok, "errors": rule_errors, "kept": len(kept), "families": families, "written": written,
              "max_words": max_words, "dropped": len(dropped)})
    return 0


# ------------------------------------------------------------------------------------------------ the brief
def token_estimate(text: str) -> tuple[int, int]:
    n_words = len(text.split())
    return n_words, int(round(n_words * TOKENS_PER_WORD))


def cmd_brief(args) -> int:
    answer = load_json(args.answer, {})
    body = clean(answer.get("brief_markdown", "") if isinstance(answer, dict) else "", one_line=False).strip()
    header = ""
    if args.header:
        try:
            header = read_text(args.header).strip()
        except OSError:
            header = ""
    content = (header + "\n\n" if header else "") + body + "\n"
    n_words, tokens = token_estimate(content)
    errors = []
    if not body:
        errors.append("the brief is empty")
    if tokens < args.min:
        errors.append(f"the brief is about {tokens} tokens ({n_words} words); it must be between {args.min} and {args.max} "
                      f"tokens, so add about {int((args.min - tokens) / TOKENS_PER_WORD) + 40} words of useful detail")
    elif tokens > args.max:
        errors.append(f"the brief is about {tokens} tokens ({n_words} words); it must be between {args.min} and {args.max} "
                      f"tokens, so cut about {int((tokens - args.max) / TOKENS_PER_WORD) + 40} words")
    ok = not errors
    if ok or args.force:
        save_text(args.out, content)
    out_json({"ok": ok, "errors": errors, "tokens": tokens, "words": n_words,
              "video_type": clean(answer.get("video_type", "")) if isinstance(answer, dict) else "",
              "tones": answer.get("suggested_tones", []) if isinstance(answer, dict) else []})
    return 0


def cmd_tokens(args) -> int:
    try:
        text = read_text(args.file)
    except OSError:
        out_json({"words": 0, "tokens": 0})
        return 2
    n_words, tokens = token_estimate(text)
    out_json({"words": n_words, "tokens": tokens})
    return 0


# ------------------------------------------------------------------------------------------------ suggestions
def cmd_suggest(args) -> int:
    """Append new hook shapes to library/hooks.suggested.txt (spec 2.2), deduplicated, with a dated comment."""
    try:
        shapes = json.loads(args.shapes or "[]")
    except ValueError:
        shapes = []
    shapes = [clean(s) for s in shapes if isinstance(s, str) and clean(s)]
    shapes = [s for s in shapes if 12 <= len(s) <= 200][:5]
    existing = set()
    try:
        for line in read_text(args.file).split("\n"):
            if line.strip() and not line.startswith("#"):
                existing.add(normalize_hook(line))
    except OSError:
        pass
    new = []
    for s in shapes:
        n = normalize_hook(s)
        if n and n not in existing:
            existing.add(n)
            new.append(s)
    if new:
        path = winpath(args.file)
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        header = not os.path.isfile(path)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            if header:
                f.write("# hooks.suggested.txt: new hook shapes the pipeline noticed (BUILD_SPEC.md 2.2).\n"
                        "# One per line, like hooks.txt. Move the ones you like into hooks.txt yourself; the runner never reads this file.\n")
            f.write(f"# {time.strftime('%Y-%m-%d %H:%M')} from {clean(args.source) or 'the pipeline'}\n")
            for s in new:
                f.write(s + "\n")
    out_json({"added": len(new), "given": len(shapes)})
    return 0


# ------------------------------------------------------------------------------------------------ voice.md
WPM_RES = [
    re.compile(r"\*\*Pace:?\*\*:?\s*(\d{2,3})\s*(?:words per minute|wpm)", re.IGNORECASE),
    re.compile(r"\bPace:?\s*(\d{2,3})\s*(?:words per minute|wpm)", re.IGNORECASE),
    re.compile(r"\bwpm\s*[=:]\s*(\d{2,3})\b", re.IGNORECASE),
    re.compile(r"\b(\d{2,3})\s*words per minute", re.IGNORECASE),
]


def voice_wpm(path: str) -> int | None:
    try:
        text = read_text(path)
    except OSError:
        return None
    for r in WPM_RES:
        m = r.search(text)
        if m:
            n = int(m.group(1))
            if 80 <= n <= 260:
                return n
    return None


def cmd_wpm(args) -> int:
    n = voice_wpm(args.voice) if args.voice else None
    sys.stdout.write(f"{n if n else int(args.default)}\n")
    return 0


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("parse"); sp.add_argument("--file", required=True)
    sp.set_defaults(func=lambda a: (out_json(parse_file(a.file)), 0)[1])

    sp = sub.add_parser("index-plan"); sp.add_argument("--file", required=True); sp.add_argument("--index", required=True)
    sp.add_argument("--force", action="store_true"); sp.set_defaults(func=cmd_index_plan)

    sp = sub.add_parser("index-write"); sp.add_argument("--file", required=True); sp.add_argument("--index", required=True)
    sp.add_argument("--answer", action="append"); sp.add_argument("--lint", required=True); sp.add_argument("--stats")
    sp.add_argument("--suggested"); sp.add_argument("--model", default=""); sp.set_defaults(func=cmd_index_write)

    sp = sub.add_parser("vendor"); sp.add_argument("--vendor", required=True); sp.set_defaults(func=cmd_vendor)

    sp = sub.add_parser("shortlist"); sp.add_argument("--index", required=True); sp.add_argument("--stats")
    sp.add_argument("--vendor"); sp.add_argument("--n", type=int, default=24); sp.add_argument("--seed", default="")
    sp.add_argument("--out", required=True); sp.add_argument("--fit-weight", type=float, default=0.35)
    sp.add_argument("--per-family", type=int, default=2); sp.set_defaults(func=cmd_shortlist)

    sp = sub.add_parser("templates-text"); sp.add_argument("--shortlist", required=True); sp.set_defaults(func=cmd_templates_text)

    sp = sub.add_parser("limits"); sp.add_argument("--wpm", type=float, default=150); sp.add_argument("--max-words", type=int, default=8)
    sp.add_argument("--max-seconds", type=float, default=3.0); sp.set_defaults(func=cmd_limits)

    sp = sub.add_parser("check"); sp.add_argument("--answer", required=True); sp.add_argument("--shortlist")
    sp.add_argument("--index"); sp.add_argument("--vendor"); sp.add_argument("--wpm", type=float, default=150)
    sp.add_argument("--out", required=True); sp.add_argument("--min", type=int, default=12); sp.add_argument("--max", type=int, default=20)
    sp.add_argument("--min-families", type=int, default=3); sp.add_argument("--on-screen-max", type=int, default=6)
    sp.add_argument("--max-words", type=int, default=8); sp.add_argument("--max-seconds", type=float, default=3.0)
    sp.add_argument("--min-for-judge", type=int, default=4); sp.add_argument("--force", action="store_true")
    sp.add_argument("--keep"); sp.add_argument("--survivors", default=""); sp.add_argument("--idea-id", default="")
    sp.add_argument("--written-by", default="05-hooks"); sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("brief"); sp.add_argument("--answer", required=True); sp.add_argument("--out", required=True)
    sp.add_argument("--header"); sp.add_argument("--min", type=int, default=2000); sp.add_argument("--max", type=int, default=3000)
    sp.add_argument("--force", action="store_true"); sp.set_defaults(func=cmd_brief)

    sp = sub.add_parser("tokens"); sp.add_argument("--file", required=True); sp.set_defaults(func=cmd_tokens)

    sp = sub.add_parser("wpm"); sp.add_argument("--voice"); sp.add_argument("--default", type=int, default=150)
    sp.set_defaults(func=cmd_wpm)

    sp = sub.add_parser("suggest"); sp.add_argument("--file", required=True); sp.add_argument("--shapes", default="[]")
    sp.add_argument("--source", default=""); sp.set_defaults(func=cmd_suggest)

    sp = sub.add_parser("stats-update"); sp.add_argument("--stats", required=True); sp.add_argument("--picked", default="")
    sp.add_argument("--won", default=""); sp.add_argument("--scores", default="{}"); sp.add_argument("--texts", default="")
    sp.add_argument("--date", default=""); sp.set_defaults(func=cmd_stats_update)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except OSError as exc:
        print(f"hooks.py {args.cmd}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
