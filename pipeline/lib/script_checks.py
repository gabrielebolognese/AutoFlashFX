#!/usr/bin/env python
"""script_checks.py: the script stage's helpers (S7, BUILD_SPEC.md section 5). The model writes; this file decides.

  setup           read the inputs once and write plan.json: the pace, the length range (tweaks.md wins over
                  config lengths), the video type and the two tones (from the brief's header, else from the hook's
                  family), the word targets, hook 1 and hook 2 from judge.json, the keyword and the identity from
                  expansion.json, the pronunciations, the style's beat map, the voice excerpts
  draft           turn a model answer into a draft file: ids b1..bn, every text cleaned (no em dash, no CR), the hook
                  beat's display and card forced to hook 1's lines, emphasis words filtered, pronunciations and
                  numbers applied to the spoken track, hook 2's tracks
  cut-data        what the cut prompt needs (the listing, the word counts, the tokens that must survive)
  cut-apply       merge the cut model's answer into a draft and judge it (10 to 30 percent fewer words, every number
                  and name kept, every beat kept)
  cut-best        among several cut attempts, keep the best one (or the uncut draft)
  check           humanize.py on every text, then the local checks: beats.py (hook 3 s or less, no beat over 4 s,
                  no 3 abstract beats in a row, the loop), detect.py (PASS: overall 70 or more, no check under 55),
                  zero placeholders, the structure (hook, stake 2 to 7 s with the identity, body, payoff, one ask
                  with the keyword that repeats a hook word), the length against the range, the cards (6 words or
                  fewer); writes the report (hard and soft failures) and, with --write, the humanized draft
  claims-data     the beats listing for the claims prompt
  claims          merge the checks model's answer (every claim mapped to facts.md) into the report
  feedback        the failing checks as a list for the rewrite prompt
  draft-text      a readable rendering of a draft (for the cut and pick prompts)
  pick-data       the two drafts in a seeded order for the pick prompt
  pick            read the pick answer back to a draft label
  compose         script.json from the final draft, its report, the pick and the rounds
  rewrite-line-data / rewrite-line-apply   S8's one-line rewrite (prompt data, then the answer applied to script.json)
  numbers         print the spoken form of a text (numbers written out, pronunciations applied)
  length-rule     print the length ranges read from tweaks.md

The vendored scripts (pipeline/vendor/ig-agent-skill) are imported as modules and called as they are: beats.py's
analyse, words, CONCRETE_RE and STOPWORDS; humanize.py's humanize; detect.py's run. Their behavior is not changed
(BUILD_SPEC.md section 10). Every text that comes from a model is cleaned with errors.undash (no file of this
project may hold an em dash). Paths may be C:/... or /c/... (both work).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from errors import undash  # noqa: E402
import solution as solution_lib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
VENDOR_DEFAULT = os.path.join(REPO, "pipeline", "vendor", "ig-agent-skill")

TONES = ["warning", "insider", "contrarian", "calm expert", "confession"]
TONE_GUIDE = {
    "warning": "a heads-up from someone who got burned: name the risk early, stay factual, no fear-mongering",
    "insider": "someone who read the actual file: exact values, the detail outsiders miss, said plainly",
    "contrarian": "push against what most people assume, then back it with the facts; respectful, never a rant",
    "calm expert": "unhurried and precise, no hype; let the mechanism and the honest caveats do the work",
    "confession": "first person, a mistake admitted and what fixed it; only with real first-person material, never invented",
}
FAMILY_TONE = {
    "mistake-warning": "warning", "myth-contrarian": "contrarian", "story-confession": "confession",
    "tools-listicle": "insider", "how-to-system": "calm expert", "transformation": "insider",
}
TONE_DEFAULT_ORDER = ["insider", "calm expert", "warning", "contrarian", "confession"]
BEAT_TYPES = ["hook", "stake", "number", "tool", "step", "comparison", "proof", "mechanism", "before-after",
              "pain-payoff", "payoff", "ask"]
BODY_TYPES = {"number", "tool", "step", "comparison", "proof", "mechanism", "before-after", "pain-payoff"}
HARD_CHECKS = {"facts", "placeholders", "requirements", "ask", "structure", "length_hard", "solution"}
WORD_RE = re.compile(r"[A-Za-z0-9$%'\u2019-]+")
ALNUM_RE = re.compile(r"[A-Za-z0-9]")
PLACEHOLDER_RES = [
    re.compile(r"\{\{[^}]*\}\}"),
    re.compile(r"\[(?:FILL IN|INSERT|YOUR|NAME|NUMBER|TBD|PLACEHOLDER|LINK|DATE|TOOL)[^\]]*\]", re.I),
    re.compile(r"\bTBD\b|\bTODO\b|\blorem ipsum\b", re.I),
    re.compile(r"\bXX+\b"),
]
CTA_RES = [
    ("comment", re.compile(r"\bcomment(?:s|ed|ing)?\b", re.I)),
    ("follow", re.compile(r"\bfollow (?:me|us|for|along|this|the)\b|\bhit follow\b|\bgive (?:me |us )?a follow\b", re.I)),
    ("link in bio", re.compile(r"\blink in (?:my |the |our )?bio\b|\bbio link\b", re.I)),
    ("save", re.compile(r"\bsave (?:this|it|the (?:video|reel|post))\b", re.I)),
    ("share", re.compile(r"\bshare (?:this|it|the (?:video|reel|post))\b|\bsend (?:this|it) to\b", re.I)),
    ("subscribe", re.compile(r"\bsubscribe\b", re.I)),
    ("like", re.compile(r"\blike (?:this|the) (?:video|reel|post)\b|\bdouble[- ]tap\b|\bhit (?:the )?like\b", re.I)),
    ("notifications", re.compile(r"\bturn on (?:post )?notifications\b", re.I)),
    ("tag", re.compile(r"\btag (?:a|someone|your|the)\b", re.I)),
    ("dm me", re.compile(r"\b(?:dm|message) me\b", re.I)),
]
IDENTITY_STOP = {"if", "you", "your", "the", "a", "an", "and", "or", "who", "that", "with", "for", "of", "to", "in",
                 "on", "are", "is", "be", "people", "anyone", "someone", "those", "them", "they", "it", "this", "by",
                 "every", "any", "all", "from", "at", "as", "i", "my", "me", "we", "our", "still", "now", "just"}


# ---------------------------------------------------------------------------------------------------- utilities
def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def winpath(path: str) -> str:
    """/c/Users/... from Git Bash -> C:/Users/... for Windows Python."""
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def clean(value, one_line: bool = True) -> str:
    s = "" if value is None else str(value)
    s = undash(s.replace("\r\n", "\n").replace("\r", "\n"))
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return " ".join(s.split()) if one_line else s


def read_text(path: str) -> str:
    with open(winpath(path), encoding="utf-8-sig", errors="replace") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def read_text_or(path: str, default: str = "") -> str:
    try:
        return read_text(path) if path else default
    except OSError:
        return default


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


def today() -> str:
    return time.strftime("%Y-%m-%d")


def words_of(text: str) -> list[str]:
    """Spoken words, counted as the vendor's scripts count them ("1,134,112" is one word)."""
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text or ""))


def n_words(text: str) -> int:
    return len(words_of(text))


def card_words(text: str) -> int:
    return len([w for w in (text or "").split() if ALNUM_RE.search(w)])


def norm_line(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9$%'@/#.-]+", " ", clean(text).lower()).split())


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, winpath(path))
    if spec is None or spec.loader is None:
        raise OSError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Vendor:
    """The vendored scripts as modules (behavior untouched)."""

    def __init__(self, folder: str):
        self.folder = winpath(folder)
        self.beats = load_module("vendor_beats", os.path.join(self.folder, "beats.py"))
        self.humanize = load_module("vendor_humanize", os.path.join(self.folder, "humanize.py"))
        self.detect = load_module("vendor_detect", os.path.join(self.folder, "detect.py"))
        with open(os.path.join(self.folder, "slop.json"), encoding="utf-8") as f:
            self.lex = json.load(f)


# ---------------------------------------------------------------------------------------------------- numbers
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
SCALES = [(10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")]
ORDINAL_SPECIAL = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
                   "nine": "ninth", "twelve": "twelfth"}
UNIT_WORDS = {"s": ("second", "seconds"), "sec": ("second", "seconds"), "ms": ("millisecond", "milliseconds"),
              "min": ("minute", "minutes"), "h": ("hour", "hours"), "px": ("pixel", "pixels"), "fps": ("f p s", "f p s"),
              "k": ("thousand", "thousand"), "kb": ("kilobyte", "kilobytes"), "mb": ("megabyte", "megabytes"),
              "gb": ("gigabyte", "gigabytes"), "x": ("x", "x")}


def int_words(n: int) -> str:
    if n < 0:
        return "minus " + int_words(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return TENS[t] + ("-" + ONES[o] if o else "")
    if n < 1000:
        h, rest = divmod(n, 100)
        return ONES[h] + " hundred" + (" " + int_words(rest) if rest else "")
    for value, name in SCALES:
        if n >= value:
            head, rest = divmod(n, value)
            return int_words(head) + " " + name + (" " + int_words(rest) if rest else "")
    return str(n)


def year_words(n: int) -> str:
    if 2000 <= n <= 2009:
        return "two thousand" + (" " + ONES[n - 2000] if n > 2000 else "")
    head, tail = divmod(n, 100)
    return int_words(head) + " " + ("oh-" + ONES[tail] if tail < 10 and tail > 0 else (int_words(tail) if tail else "hundred"))


def digits_words(s: str) -> str:
    return " ".join("oh" if c == "0" else ONES[int(c)] for c in s)


def ordinal_words(n: int) -> str:
    text = int_words(n)
    head, sep, last = text.rpartition("-") if "-" in text else text.rpartition(" ")
    if last in ORDINAL_SPECIAL:
        last = ORDINAL_SPECIAL[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last = last + "th"
    return head + sep + last if sep else last


def number_token_words(token: str) -> str:
    """A plain number with optional thousands commas and decimals: '1,134,112', '9.17', '.1', '1.1.1'."""
    t = token.replace(",", "")
    if re.fullmatch(r"\d+", t):
        if t.startswith("0") and len(t) > 1:
            return digits_words(t)
        n = int(t)
        if len(t) == 4 and 1900 <= n <= 2099 and "," not in token:
            return year_words(n)
        return int_words(n)
    parts = t.split(".")
    out = []
    for i, part in enumerate(parts):
        if i == 0:
            out.append(int_words(int(part)) if part else "")
        else:
            out.append("point " + (" ".join(ONES[int(c)] for c in part) if part else ""))
    return " ".join(p for p in out if p)


def spoken_numbers(text: str) -> tuple[str, list[str]]:
    """Write every number of a spoken line out in words; return the text and the replacements made."""
    changes: list[str] = []

    def note(src: str, dst: str) -> str:
        if src != dst:
            changes.append(f"{src} -> {dst}")
        return dst

    def hexcolor(m):
        body = m.group(1)
        return note(m.group(0), " ".join(c.upper() if c.isalpha() else ONES[int(c)] for c in body))

    def money(m):
        amount = m.group(1).replace(",", "")
        whole, _, cents = amount.partition(".")
        out = int_words(int(whole or "0")) + " dollar" + ("" if whole == "1" else "s")
        if cents:
            out += " " + int_words(int(cents.ljust(2, "0")[:2]))
        return note(m.group(0), out)

    def percent(m):
        return note(m.group(0), number_token_words(m.group(1)) + " percent")

    def ordinal(m):
        return note(m.group(0), ordinal_words(int(m.group(1))))

    def clock(m):
        h, mm, ap = int(m.group(1)), m.group(2), (m.group(3) or "").lower()
        mins = "" if mm == "00" else (" oh " + ONES[int(mm[1])] if mm[0] == "0" else " " + int_words(int(mm)))
        suffix = {"am": " a m", "pm": " p m"}.get(ap.replace(".", ""), "")
        return note(m.group(0), int_words(h) + mins + suffix)

    def unit(m):
        num, u = m.group(1), m.group(2).lower()
        if u not in UNIT_WORDS:
            return m.group(0)
        one, many = UNIT_WORDS[u]
        value = number_token_words(num)
        return note(m.group(0), value + " " + (one if num.replace(",", "") in ("1", "1.0") else many))

    def by(m):
        return note(m.group(0), number_token_words(m.group(1)) + " by " + number_token_words(m.group(2)))

    def dash_range(m):
        return note(m.group(0), number_token_words(m.group(1)) + " to " + number_token_words(m.group(2)))

    def signed(m):
        sign = "minus " if m.group(1) == "-" else "plus "
        return note(m.group(0), sign + number_token_words(m.group(2)))

    def plain(m):
        return note(m.group(0), number_token_words(m.group(0)))

    num = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    text = re.sub(r"#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b", hexcolor, text)
    text = re.sub(r"\$(" + num + r")", money, text)
    text = re.sub(r"(" + num + r")\s?%", percent, text)
    text = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", ordinal, text)
    text = re.sub(r"\b(\d{1,2}):(\d{2})\s?(am|pm|a\.m\.|p\.m\.)?\b", clock, text)
    text = re.sub(r"\b(" + num + r")\s?x\s?(" + num + r")\b", by, text)
    text = re.sub(r"(?<![\w.])(" + num + r")-(" + num + r")(?![\w.])", dash_range, text)
    text = re.sub(r"\b(" + num + r")\s?(ms|fps|px|kb|mb|gb|sec|min|s|h|k)\b", unit, text, flags=re.I)
    text = re.sub(r"(?<![\w$])([+-])(" + num + r")\b", signed, text)
    text = re.sub(r"(?<![\w.])(?:" + num + r"(?:\.\d+)*|\.\d+)(?![\w])", plain, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, changes


def read_pronunciations(path: str) -> list[list[str]]:
    items: list[list[str]] = []
    for line in read_text_or(path).split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        word, _, say = line.partition("=")
        word, say = clean(word), clean(say)
        if word and say:
            items.append([word, say])
    items.sort(key=lambda p: -len(p[0]))
    return items


def apply_pronunciations(text: str, items: list[list[str]]) -> tuple[str, list[str]]:
    applied: list[str] = []
    for word, say in items:
        pattern = re.compile(r"(?<![A-Za-z0-9\[])" + re.escape(word) + r"(?![A-Za-z0-9]|\]\()", re.I)
        if pattern.search(text):
            if say.startswith("/") and say.endswith("/") and len(say) > 2:  # Kokoro's inline phonemes (M7): [word](/phonemes/)
                text = pattern.sub(lambda m, s=say: f"[{m.group(0)}]({s})", text)
            else:
                text = pattern.sub(say, text)
            applied.append(f"{word} -> {say}")
    return text, applied


def spoken_track(text: str, pronunciations: list[list[str]]) -> tuple[str, list[str]]:
    text = clean(text)
    text, applied = apply_pronunciations(text, pronunciations)
    text, changes = spoken_numbers(text)
    return text, applied + changes


# ---------------------------------------------------------------------------------------------------- setup
def tweaks_length(path: str) -> dict | None:
    """The Length line of tweaks.md that is in force (not PROPOSED): {"default": [lo, hi], "list": [lo, hi]}."""
    text = read_text_or(path)
    for line in text.split("\n"):
        if "PROPOSED" in line or "length" not in line.lower():
            continue
        if not re.match(r"^\s*-\s*\*{0,2}\s*length\b", line, re.I):
            continue
        out: dict = {}
        for sentence in re.split(r"(?<=[.;])\s+", line):
            m = re.search(r"(\d+)\s*(?:to|-)\s*(\d+)\s*s\b", sentence)
            if not m:
                continue
            pair = [int(m.group(1)), int(m.group(2))]
            if re.search(r"\blist|explainer", sentence, re.I):
                out["list"] = pair
            elif re.search(r"everything else|default|other", sentence, re.I) or "default" not in out:
                out["default"] = pair
        if out:
            return out
    return None


def brief_header(brief: str) -> dict:
    head = brief.split("\n## ", 1)[0]
    out = {"video_type": "", "tones": []}
    m = re.search(r"Video type:\s*(default|list)", head, re.I)
    if m:
        out["video_type"] = m.group(1).lower()
    m = re.search(r"Suggested tones:\s*([^\n]+)", head, re.I)
    if m:
        raw = re.split(r"[,;/]| and ", m.group(1).strip().rstrip("."))
        out["tones"] = [t.strip().strip(".").lower() for t in raw if t.strip()]
    return out


def choose_tones(suggested: list[str], family: str, allowed: list[str]) -> tuple[list[str], str]:
    tones: list[str] = []
    source = "brief"
    for t in suggested:
        if t in allowed and t not in tones:
            tones.append(t)
        if len(tones) == 2:
            break
    if len(tones) < 2:
        source = "brief and hook family" if tones else "hook family"
        fam = FAMILY_TONE.get(family, "")
        for t in [fam] + TONE_DEFAULT_ORDER:
            if t and t in allowed and t not in tones:
                tones.append(t)
            if len(tones) == 2:
                break
    return tones[:2], source


def voice_excerpts(voice: str) -> str:
    m = re.search(r"^## Verbatim excerpts[^\n]*\n(.*?)(?=^## |\Z)", voice, re.M | re.S)
    if not m:
        return ""
    lines = [ln.strip() for ln in m.group(1).split("\n") if re.match(r"^\s*\d+\.\s", ln)]
    return "\n".join(lines)


def beat_map_text(style: str) -> str:
    m = re.search(r"^## Beat map[^\n]*\n(.*?)(?=^## |\Z)", style, re.M | re.S)
    return m.group(1).strip() if m else "(no beat map in style.md)"


def solution_rules_text(sol: dict) -> str:
    """The solution rules of spec S7 for the writer's prompt, by the solution's type (M12)."""
    stype = sol.get("type", "none")
    name, url = sol.get("name", ""), sol.get("url", "")
    where = f"{name}" + (f" ({url})" if url else "")
    if stype == "flashfx":
        return ("The solution of this reel is FlashFX" + (f" ({url})" if url else "") + ": show it solving the viewer's problem the way "
                "any tool would be shown, what the viewer does with it, step by step, from verified claims of facts.md and the account's proof "
                "lines only. No ad language: no pitch, no hype, no superlatives, no sign-up or trial push, no 'the best', no 'game-changer'. "
                "Never say or imply that this reel itself was made, edited or animated in FlashFX (the reels are rendered by another tool): "
                "say what FlashFX does for the problem, never what made this video. The keyword FLASH sends the viewer access to FlashFX.")
    if stype == "external":
        return (f"The solution of this reel is {where or 'an external tool'}: show it solving the viewer's problem. Never mention FlashFX "
                "anywhere, not in the spoken track, the display track or a card, and pitch nothing: no 'the best tool', no sign-up push. "
                "The keyword LINK sends the viewer its link.")
    if stype == "method":
        return (f"The solution of this reel is a method with no product: {name or 'the steps the reel shows'}. Never mention FlashFX anywhere, "
                "and no product pitch.")
    return ("No solution decision was recorded for this run (it predates the solution choice): the reel counts as not FlashFX. Never mention "
            "FlashFX anywhere.")


def cmd_setup(args) -> int:
    cfg = load_json(args.config, {}) or {}
    script_cfg = cfg.get("script", {}) if isinstance(cfg.get("script"), dict) else {}
    lengths = cfg.get("lengths", {}) if isinstance(cfg.get("lengths"), dict) else {}
    allowed_tones = [t for t in script_cfg.get("tones", TONES) if t in TONES] or TONES
    wpm = float(args.wpm)
    brief = read_text_or(args.brief)
    header = brief_header(brief)
    judge = load_json(args.judge, {}) or {}
    expansion = load_json(args.expansion, {}) or {}
    winner = judge.get("winner", {}) if isinstance(judge.get("winner"), dict) else {}
    runner_up = judge.get("runner_up", {}) if isinstance(judge.get("runner_up"), dict) else {}
    if not winner.get("spoken"):
        print("setup: judge.json has no winner with a spoken line", file=sys.stderr)
        return 2
    video_type = header["video_type"] or "default"
    tw = tweaks_length(args.tweaks) if args.tweaks else None
    source = "config"
    rng = lengths.get("list_s" if video_type == "list" else "default_s")
    if tw and tw.get(video_type):
        rng = tw[video_type]
        source = "tweaks.md"
    if not (isinstance(rng, list) and len(rng) == 2):
        rng = [45, 75] if video_type == "list" else [25, 40]
    lo, hi = float(rng[0]), float(rng[1])
    final_words = [int(math.floor(lo * wpm / 60)), int(math.ceil(hi * wpm / 60))]
    mid_words = (lo + hi) / 2 * wpm / 60
    overshoot = float(script_cfg.get("overshoot_pct", 25)) / 100
    write_target = int(round(mid_words * (1 + overshoot)))
    write_words = [int(round(write_target * 0.92)), int(round(write_target * 1.08))]
    tones, tone_source = choose_tones(header["tones"], winner.get("family", ""), allowed_tones)
    voice = read_text_or(args.voice)
    hook = {"id": winner.get("id", "h01"), "spoken": clean(winner.get("spoken", "")), "on_screen": clean(winner.get("on_screen", "")),
            "family": winner.get("family", ""), "template_id": winner.get("template_id", ""), "template": clean(winner.get("template", "")),
            "marker": clean(winner.get("marker", ""))}
    hook2 = {"id": runner_up.get("id", ""), "spoken": clean(runner_up.get("spoken", "")), "on_screen": clean(runner_up.get("on_screen", "")),
             "family": runner_up.get("family", "")}
    beat_max_s = float(script_cfg.get("beat_max_s", 4))
    stake_max_s = float(script_cfg.get("stake_max_s", 5))
    sol_raw = load_json(args.solution, {}) if getattr(args, "solution", "") else {}
    sol_type = str((sol_raw or {}).get("type", "none")).lower()
    solution_decision = {"type": sol_type if sol_type in solution_lib.SOLUTION_TYPES else "none",
                         "name": clean((sol_raw or {}).get("name", "")), "url": clean((sol_raw or {}).get("url", ""))}
    plan = {
        "written_by": "07-script", "checked": today(), "wpm": wpm,
        "video_type": video_type, "length_s": [lo, hi], "length_source": source, "target_seconds": round((lo + hi) / 2, 1),
        "final_words": final_words, "write_words": write_words, "write_target": write_target,
        "beat_max_words": int(beat_max_s * wpm / 60), "stake_max_words": int(stake_max_s * wpm / 60),
        "hook_max_s": float(script_cfg.get("hook_max_s", 3)), "beat_max_s": beat_max_s, "stake_max_s": stake_max_s,
        "abstract_run": int(script_cfg.get("abstract_run", 3)), "length_tolerance_pct": float(script_cfg.get("length_tolerance_pct", 15)),
        "card_max_words": int(script_cfg.get("card_max_words", 6)), "min_body_beats": int(script_cfg.get("min_body_beats", 2)),
        "detect_min_overall": float(script_cfg.get("detect_min_overall", 70)), "detect_min_check": float(script_cfg.get("detect_min_check", 55)),
        "detect_skip": list(script_cfg.get("detect_skip", ["BURSTINESS"])),
        "cut_pct": float(script_cfg.get("cut_pct", 20)), "cut_range_pct": script_cfg.get("cut_range_pct", [10, 30]),
        "cut_tries": int(script_cfg.get("cut_tries", 2)), "rounds": int(args.rounds),
        "tones": tones, "tone_source": tone_source, "tone_guide": {t: TONE_GUIDE[t] for t in tones},
        "suggested_tones": header["tones"],
        "hook": hook, "hook2": hook2,
        "keyword": clean(expansion.get("keyword", "")).upper(), "deliverable": clean(expansion.get("deliverable", "")),
        "deliverable_status": expansion.get("deliverable_status", "new"), "deliverable_link": clean(expansion.get("deliverable_link", "")),
        "identity": clean(expansion.get("share_identity", "")), "problem": clean(expansion.get("problem", "")),
        "solution": clean(expansion.get("solution", "")), "one_true_thing": clean(expansion.get("one_true_thing", "")),
        "solution_decision": solution_decision, "solution_rules": solution_rules_text(solution_decision),
        "pronunciations": read_pronunciations(args.pronunciations) if args.pronunciations else [],
        "beat_map": beat_map_text(read_text_or(args.style)) if args.style else "(no style file)",
        "voice_excerpts": voice_excerpts(voice), "voice_present": bool(voice.strip()),
        "idea_id": args.idea_id or "", "idea_text": clean(args.idea_text or ""),
    }
    save_json(args.out, plan)
    out_json({"ok": True, "wpm": wpm, "video_type": video_type, "length_s": [lo, hi], "length_source": source,
              "final_words": final_words, "write_words": write_words, "tones": tones, "tone_source": tone_source,
              "keyword": plan["keyword"], "hook_spoken": hook["spoken"], "hook_on_screen": hook["on_screen"],
              "hook_id": hook["id"], "hook2_id": hook2["id"], "pronunciations": len(plan["pronunciations"]),
              "has_excerpts": bool(plan["voice_excerpts"]), "solution_type": solution_decision["type"]})
    return 0


# ---------------------------------------------------------------------------------------------------- drafts
def normalize_facts(value) -> list[str]:
    out: list[str] = []
    items = value if isinstance(value, list) else ([value] if value else [])
    for item in items:
        for m in re.finditer(r"\d+", str(item)):
            ref = f"facts.md#{int(m.group(0))}"
            if ref not in out:
                out.append(ref)
    return out


def filter_emphasis(words: list, display: str) -> list[str]:
    present = {w.lower().strip(".,;:!?\"'()") for w in display.split()}
    out: list[str] = []
    for w in words if isinstance(words, list) else []:
        w = clean(w).strip(".,;:!?\"'()")
        if not w:
            continue
        parts = [p.lower() for p in w.split()]
        if all(p in present for p in parts) and w not in out:
            out.append(w)
    return out[:3]


IMPORTANCE = ("hook", "key-claim", "number", "payoff", "pre-ask", "normal")


def norm_importance(value) -> str:
    """The model's importance word for a beat (hook, key claim, number, payoff, pre-ask, normal), or "" when it gave none."""
    v = re.sub(r"[\s_]+", "-", clean(value).lower()) if value else ""
    return v if v in IMPORTANCE else ""


def derive_importance(beats: list[dict]) -> list[str]:
    """Each beat's importance for the captions (BUILD_SPEC.md S7, Motion and energy rules E3): the hook, a key claim, a number,
    the payoff, the line before the ask, or normal talk. The structure decides what it can (the hook beat, a number beat,
    a payoff beat, the beat before the ask, a proof beat as a key claim); the model's own word only lifts a normal beat."""
    out = []
    n = len(beats)
    for i, b in enumerate(beats):
        t = b.get("type", "")
        hint = norm_importance(b.get("importance"))
        if i == 0 and t == "hook":
            imp = "hook"
        elif t == "ask":
            imp = "normal"
        elif t == "number":
            imp = "number"
        elif t == "payoff":
            imp = "payoff"
        elif i == n - 2 and n >= 2 and beats[-1].get("type") == "ask":
            imp = "pre-ask"
        elif t == "proof":
            imp = "key-claim"
        else:
            imp = hint if hint in ("key-claim", "number", "payoff") else "normal"
        out.append(imp)
    return out


def build_draft(answer: dict, plan: dict, label: str, tone: str, round_n: int, source: str) -> dict:
    pron = plan.get("pronunciations", [])
    hook = plan.get("hook", {})
    hook2 = plan.get("hook2", {})
    beats_in = answer.get("beats", []) if isinstance(answer, dict) else []
    beats: list[dict] = []
    notes: list[str] = []
    for i, b in enumerate(beats_in):
        if not isinstance(b, dict):
            continue
        display = clean(b.get("display", ""))
        spoken_src = clean(b.get("spoken", "")) or display
        btype = clean(b.get("type", "")).lower()
        if btype == "before_after":
            btype = "before-after"
        if btype == "pain_payoff":
            btype = "pain-payoff"
        card = clean(b.get("card", ""))
        if i == 0 and btype == "hook" and hook.get("spoken"):
            if norm_line(display) != norm_line(hook["spoken"]):
                notes.append(f"the hook's display was replaced by hook 1's line (the model wrote: {display[:80]})")
            display = hook["spoken"]
            card = hook.get("on_screen") or card
        spoken, changes = spoken_track(spoken_src, pron)
        beats.append({
            "id": f"b{i + 1}", "model_id": clean(b.get("id", "")), "type": btype, "display": display, "spoken": spoken,
            "emphasis": filter_emphasis(b.get("emphasis", []), display), "card": card,
            "facts": normalize_facts(b.get("facts", [])), "spoken_changes": changes, "importance": norm_importance(b.get("importance")),
        })
    ask_in = answer.get("ask", {}) if isinstance(answer, dict) and isinstance(answer.get("ask"), dict) else {}
    ask_beat = beats[-1] if beats and beats[-1]["type"] == "ask" else None
    ask = {"keyword": clean(ask_in.get("keyword", "")).upper() or plan.get("keyword", ""),
           "line": ask_beat["display"] if ask_beat else clean(ask_in.get("line", ""))}
    h2_in = answer.get("hook2", {}) if isinstance(answer, dict) and isinstance(answer.get("hook2"), dict) else {}
    h2_spoken_src = clean(h2_in.get("spoken", "")) or hook2.get("spoken", "")
    h2_spoken, h2_changes = spoken_track(h2_spoken_src, pron)
    draft = {
        "label": label, "tone": tone or clean(answer.get("tone", "")) if isinstance(answer, dict) else tone,
        "round": round_n, "source": source, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "beats": beats, "ask": ask,
        "hook2": {"id": hook2.get("id", ""), "display": hook2.get("spoken", ""), "spoken": h2_spoken,
                  "card": hook2.get("on_screen", ""), "spoken_changes": h2_changes},
        "notes": clean(answer.get("notes", "")) if isinstance(answer, dict) else "",
        "normalizer_notes": notes,
    }
    draft["words"] = draft_words(draft)
    return draft


def draft_words(draft: dict) -> dict:
    display = sum(n_words(b["display"]) for b in draft["beats"])
    spoken = sum(n_words(b["spoken"]) for b in draft["beats"])
    return {"display": display, "spoken": spoken}


def cmd_draft(args) -> int:
    answer = load_json(args.answer, {})
    plan = load_json(args.plan, {})
    if not isinstance(answer, dict) or not plan:
        print("draft: cannot read the answer or the plan", file=sys.stderr)
        return 2
    draft = build_draft(answer, plan, args.label, args.tone, int(args.round), args.source)
    if args.previous:  # a rewrite keeps the cut statistics of the round-1 draft it descends from
        previous = load_json(args.previous, {}) or {}
        if previous.get("cut"):
            draft["cut"] = dict(previous["cut"], from_round=previous.get("round", 1))
    save_json(args.out, draft)
    out_json({"ok": bool(draft["beats"]), "beats": len(draft["beats"]), "words": draft["words"],
              "notes": draft["normalizer_notes"]})
    return 0


def draft_listing(draft: dict, with_spoken: bool = True, with_card: bool = True) -> str:
    lines = []
    for b in draft["beats"]:
        line = f"{b['id']} [{b['type']}] display: {b['display']}"
        if with_spoken:
            line += f" | spoken: {b['spoken']}"
        if with_card:
            line += f" | card: {b['card']}"
        if b.get("emphasis"):
            line += " | emphasis: " + ", ".join(b["emphasis"])
        if b.get("facts"):
            line += " | " + ", ".join(b["facts"])
        lines.append(line)
    return "\n".join(lines)


def draft_script_text(draft: dict) -> str:
    """The display track as a reader sees it: one beat per line with its type."""
    return "\n".join(f"[{b['type']}] {b['display']}" for b in draft["beats"])


def draft_as_answer(draft: dict) -> dict:
    """The draft in the shape of the model's own answer (what a rewrite prompt shows and asks back)."""
    return {
        "tone": draft.get("tone", ""),
        "beats": [{"id": b["id"], "type": b["type"], "display": b["display"], "spoken": b["spoken"],
                   "emphasis": b.get("emphasis", []), "card": b["card"], "facts": b.get("facts", [])} for b in draft["beats"]],
        "ask": {"keyword": draft.get("ask", {}).get("keyword", ""), "line": draft.get("ask", {}).get("line", "")},
        "hook2": {"spoken": draft.get("hook2", {}).get("spoken", "")},
        "notes": "",
    }


def cmd_draft_text(args) -> int:
    draft = load_json(args.draft, {})
    if not draft:
        return 2
    if args.as_answer:
        sys.stdout.write(json.dumps(draft_as_answer(draft), ensure_ascii=False, indent=1) + "\n")
    elif args.plain:
        sys.stdout.write(draft_script_text(draft) + "\n")
    else:
        sys.stdout.write(draft_listing(draft, with_spoken=not args.no_spoken) + "\n")
    return 0


# ---------------------------------------------------------------------------------------------------- the cut
def must_keep_tokens(draft: dict, plan: dict) -> list[str]:
    keep: list[str] = []
    text = " ".join(b["display"] for b in draft["beats"])
    for tok in text.split():
        t = tok.strip("().,;:!?\"'")
        if not t:
            continue
        if re.search(r"\d", t) or re.search(r"[@/#]", t) or re.search(r"[A-Za-z]\.[A-Za-z]", t):
            if t not in keep:
                keep.append(t)
    kw = plan.get("keyword", "")
    if kw and kw not in keep:
        keep.append(kw)
    return keep


def cmd_cut_data(args) -> int:
    draft = load_json(args.draft, {})
    plan = load_json(args.plan, {})
    if not draft or not plan:
        return 2
    words = draft["words"]["display"]
    pct = float(plan.get("cut_pct", 20)) / 100
    floor = int(plan.get("final_words", [0, 0])[0])
    target = max(int(round(words * (1 - pct))), floor)
    rng = plan.get("cut_range_pct", [10, 30])
    out_json({
        "text": draft_listing(draft, with_spoken=True, with_card=True),
        "words": words, "target": target, "floor": floor,
        "min_after": max(int(math.ceil(words * (1 - rng[1] / 100))), floor), "max_after": int(math.floor(words * (1 - rng[0] / 100))),
        "must_keep": must_keep_tokens(draft, plan), "must_keep_text": ", ".join(must_keep_tokens(draft, plan)),
        "hook_id": draft["beats"][0]["id"] if draft["beats"] else "b1",
        "ask_id": draft["beats"][-1]["id"] if draft["beats"] else "",
    })
    return 0


def judge_cut(before: dict, after: dict, plan: dict) -> dict:
    rng = plan.get("cut_range_pct", [10, 30])
    floor = int(plan.get("final_words", [0, 0])[0])
    b_words = before["words"]["display"]
    a_words = after["words"]["display"]
    removed = round(100 * (1 - a_words / b_words), 1) if b_words else 0.0
    errors: list[str] = []
    if a_words >= b_words:
        errors.append(f"nothing was removed: {b_words} words before, {a_words} after; delete about {int(round(b_words * plan.get('cut_pct', 20) / 100))} words")
    elif removed < rng[0] and not (removed >= rng[0] / 2 and a_words <= floor + 5):
        errors.append(f"only {removed:.0f}% of the words were removed ({b_words} to {a_words}); remove between {rng[0]} and {rng[1]}% (about {int(round(b_words * plan.get('cut_pct', 20) / 100))} words)")
    elif removed > rng[1]:
        errors.append(f"{removed:.0f}% of the words were removed ({b_words} to {a_words}); that is too much: remove between {rng[0]} and {rng[1]}% and keep every idea")
    before_ids = [b["id"] for b in before["beats"]]
    after_ids = [b["id"] for b in after["beats"]]
    if before_ids != after_ids:
        errors.append(f"the beats changed: expected {', '.join(before_ids)}, got {', '.join(after_ids)}; keep every beat with its id and order")
    after_text = " ".join(b["display"] for b in after["beats"]).lower()
    lost = [t for t in must_keep_tokens(before, plan) if t.lower() not in after_text]
    if lost:
        errors.append("the cut lost these numbers, names or commands: " + ", ".join(lost[:12]) + "; put them back")
    empty = [b["id"] for b in after["beats"] if not b["display"].strip() or not b["spoken"].strip()]
    if empty:
        errors.append("these beats came back empty: " + ", ".join(empty))
    return {"ok": not errors, "errors": errors, "before_words": b_words, "after_words": a_words, "removed_pct": removed, "lost": lost}


def cmd_cut_apply(args) -> int:
    draft = load_json(args.draft, {})
    answer = load_json(args.answer, {})
    plan = load_json(args.plan, {})
    if not draft or not isinstance(answer, dict) or not plan:
        print("cut-apply: cannot read the draft, the answer or the plan", file=sys.stderr)
        return 2
    pron = plan.get("pronunciations", [])
    hook = plan.get("hook", {})
    by_id = {}
    for b in answer.get("beats", []) if isinstance(answer.get("beats"), list) else []:
        if isinstance(b, dict) and b.get("id"):
            by_id[clean(b.get("id", ""))] = b
    new_beats: list[dict] = []
    for i, b in enumerate(draft["beats"]):
        nb = dict(b)
        src = by_id.get(b["id"]) or by_id.get(b.get("model_id", ""))
        if src is not None:
            display = clean(src.get("display", "")) or b["display"]
            if i == 0 and b["type"] == "hook" and hook.get("spoken"):
                display = hook["spoken"]
            spoken_src = clean(src.get("spoken", "")) or display
            spoken, changes = spoken_track(spoken_src, pron)
            nb["display"] = display
            nb["spoken"] = spoken
            nb["spoken_changes"] = changes
            if src.get("card"):
                nb["card"] = hook.get("on_screen", "") if (i == 0 and b["type"] == "hook" and hook.get("on_screen")) else clean(src.get("card"))
            nb["emphasis"] = filter_emphasis(src.get("emphasis", b.get("emphasis", [])), display) or filter_emphasis(b.get("emphasis", []), display)
        new_beats.append(nb)
    extra = [clean(b.get("id", "")) for b in by_id.values() if clean(b.get("id", "")) not in {x["id"] for x in draft["beats"]} and clean(b.get("id", "")) not in {x.get("model_id") for x in draft["beats"]}]
    after = dict(draft)
    after["beats"] = new_beats
    after["source"] = "cut"
    if new_beats and new_beats[-1]["type"] == "ask":
        after["ask"] = dict(draft["ask"], line=new_beats[-1]["display"])
    after["words"] = draft_words(after)
    verdict = judge_cut(draft, after, plan)
    if extra:
        verdict["errors"].append("the answer named beats that do not exist: " + ", ".join(extra))
        verdict["ok"] = False
    after["cut"] = {"attempt": int(args.attempt), **verdict, "notes": clean(answer.get("notes", ""))}
    save_json(args.out, after)
    out_json({"ok": verdict["ok"], "errors": verdict["errors"], "before_words": verdict["before_words"],
              "after_words": verdict["after_words"], "removed_pct": verdict["removed_pct"]})
    return 0


def cmd_cut_best(args) -> int:
    draft = load_json(args.draft, {})
    plan = load_json(args.plan, {})
    target = float(plan.get("cut_pct", 20))
    best = None
    best_key = None
    for path in args.attempts:
        cand = load_json(path, None)
        if not cand or "cut" not in cand:
            continue
        c = cand["cut"]
        key = (0 if c.get("ok") else 1, 1 if c.get("lost") else 0, abs(float(c.get("removed_pct", 0)) - target))
        if best_key is None or key < best_key:
            best, best_key = cand, key
    if best is None or best["cut"].get("lost") or best["cut"]["after_words"] >= best["cut"]["before_words"]:
        final = dict(draft)
        final["cut"] = {"ok": False, "errors": ["no cut attempt kept every number and removed words; the uncut draft is used"],
                        "before_words": draft["words"]["display"], "after_words": draft["words"]["display"], "removed_pct": 0.0,
                        "lost": [], "attempt": 0, "chosen": "uncut", "tries": len(args.attempts)}
    else:
        final = best
        final["cut"]["chosen"] = f"attempt {best['cut'].get('attempt', '?')}"
        final["cut"]["tries"] = len(args.attempts)
    save_json(args.out, final)
    out_json({"ok": final["cut"]["ok"], "chosen": final["cut"]["chosen"], "removed_pct": final["cut"]["removed_pct"],
              "before_words": final["cut"]["before_words"], "after_words": final["cut"]["after_words"], "errors": final["cut"]["errors"]})
    return 0


# ---------------------------------------------------------------------------------------------------- the checks
CODE_TOKEN_RE = re.compile(r"\S*(?:\d\S*[,.(][,.(]?\S*|[@/#]\S*)")


def humanize_text(text: str, vendor: Vendor) -> tuple[str, dict]:
    """humanize.py on one text, with code-like tokens (rgba(0,0,0,.1), #D97757, /plugin, name@place) swapped out
    first: the vendor's comma cleanup would turn rgba(0,0,0,.1) into rgba(0,0,0.1), and an exact value must survive."""
    kept: list[str] = []

    def stash(m: re.Match) -> str:
        kept.append(m.group(0))
        return f"\x00K{len(kept) - 1}\x00"

    protected = CODE_TOKEN_RE.sub(stash, text)
    new, report = vendor.humanize.humanize(protected, vendor.lex)
    for i, tok in enumerate(kept):
        new = new.replace(f"\x00K{i}\x00", tok)
    return new, report


def humanize_draft(draft: dict, vendor: Vendor) -> dict:
    """humanize.py on every text (the hook beat's display and card are hook 1's lines and stay as they are)."""
    hits = {"invisible": 0, "typographic": 0, "lexical": 0, "changed": [], "structures": []}

    def fix(text: str, where: str) -> str:
        if not text:
            return text
        new, report = humanize_text(text, vendor)
        new = clean(new)
        for k in ("invisible", "typographic", "lexical"):
            hits[k] += sum(h.get("count", 0) for h in report.get(k, []))
        if new != clean(text):
            hits["changed"].append(f"{where}: {clean(text)[:60]} -> {new[:60]}")
        return new

    for i, b in enumerate(draft["beats"]):
        if not (i == 0 and b["type"] == "hook"):
            b["display"] = fix(b["display"], f"{b['id']} display")
            b["card"] = fix(b["card"], f"{b['id']} card")
        b["spoken"] = fix(b["spoken"], f"{b['id']} spoken")
        b["emphasis"] = filter_emphasis(b.get("emphasis", []), b["display"])
    if draft["beats"] and draft["beats"][-1]["type"] == "ask":
        draft["ask"]["line"] = draft["beats"][-1]["display"]
    h2 = draft.get("hook2", {})
    if h2.get("spoken"):
        h2["spoken"] = fix(h2["spoken"], "hook2 spoken")
    full = "\n".join(b["display"] for b in draft["beats"])
    _, report = vendor.humanize.humanize(full, vendor.lex)
    hits["structures"] = [f"{s['name']} x{s['count']}: {s['fix']}" for s in report.get("structures", [])]
    draft["words"] = draft_words(draft)
    return hits


def rhythm_advice(beats: list[dict]) -> str:
    """Name the beats whose sentences have the middle length (6 to 10 words), the rhythm detect.py's burstiness check
    reads as machine-written, so the rewrite prompt can say which beats to reshape and how."""
    sent_re = re.compile(r"[^.!?\n]+[.!?]*")
    shapes = []
    for i, b in enumerate(beats):
        # detect.py ignores sentences of 2 words or fewer, so they neither help nor hurt
        lens = [n for n in (len(s.split()) for s in sent_re.findall(b["display"]) if s.strip()) if n > 2]
        if not lens or (i == 0 and b["type"] == "hook"):
            continue
        if len(lens) == 1 and lens[0] >= 12:
            shape = "A"
        elif all(n <= 4 for n in lens):
            shape = "B"
        else:
            shape = "mid"
        shapes.append((b["id"], shape, lens))
    mid = [f"{bid} ({', '.join(str(n) for n in lens)} words)" for bid, shape, lens in shapes if shape == "mid"]
    same = [f"{a[0]} and {b[0]}" for a, b in zip(shapes, shapes[1:]) if a[1] == b[1] and a[1] != "mid"]
    parts = []
    if mid:
        parts.append("these beats have sentences of 5 to 11 words, the length the check reads as machine rhythm; rewrite each as either one sentence of 12 or 13 words or two to three sentences of 3 or 4 words, alternating the two shapes along the script: " + "; ".join(mid))
    if same:
        parts.append("beats of the same shape in a row (alternate them): " + ", ".join(same))
    return ". ".join(parts)


def detect_hints(name: str, detail: str) -> str:
    return {
        "BURSTINESS": "rewrite the rhythm: half the beats one sentence of 12 or 13 words, the other half two or three sentences of 3 or 4 words, alternating, and no sentence of 5 to 11 words anywhere but the hook",
        "SPECIFICITY": "put more names and numbers from facts.md in the lines (a tool name, a count, a date, an exact value)",
        "SLOP DENSITY": "replace the stock words named here with plain ones",
        "FINGERPRINT": "straight quotes, no em dash, no ellipsis character, no special spaces",
        "VOICE": "use contractions (don't, it's, you're), talk to 'you' and say 'I', and break any 'X, Y, and Z' triad, 'not just X, it's Y' or 'not only ... but also' shape",
    }.get(name, "")


def failure(check: str, message: str, beat: str = "", hint: str = "", hard: bool | None = None) -> dict:
    severity = "hard" if (check in HARD_CHECKS if hard is None else hard) else "soft"
    return {"check": check, "severity": severity, "beat": beat, "message": message, "hint": hint}


def run_checks(draft: dict, plan: dict, vendor: Vendor) -> dict:
    """Every local check on a (humanized) draft. Returns the report."""
    wpm = float(plan.get("wpm", 150))
    wps = wpm / 60.0
    beats = draft["beats"]
    failures: list[dict] = []
    info: list[str] = []
    checks: dict = {}
    hook_max = float(plan.get("hook_max_s", vendor.beats.HOOK_WINDOW))
    beat_max = float(plan.get("beat_max_s", vendor.beats.MAX_BEAT))
    abstract_run = int(plan.get("abstract_run", vendor.beats.ABSTRACT_RUN))
    kw = plan.get("keyword", "")

    # texts
    for b in beats:
        for field in ("display", "spoken", "card"):
            for r in PLACEHOLDER_RES:
                m = r.search(b.get(field, ""))
                if m:
                    failures.append(failure("placeholders", f"{b['id']} {field} holds the placeholder {m.group(0)!r}: write the real value or drop the line", b["id"]))
    for r in PLACEHOLDER_RES:
        if r.search(draft.get("hook2", {}).get("spoken", "")):
            failures.append(failure("placeholders", f"hook 2's spoken line holds the placeholder {r.search(draft['hook2']['spoken']).group(0)!r}"))
    checks["placeholders"] = {"found": len([f for f in failures if f["check"] == "placeholders"])}

    # per-beat timing (the larger of the two tracks: the voice reads the spoken one)
    rows = []
    clock = 0.0
    for b in beats:
        wd, ws = n_words(b["display"]), n_words(b["spoken"])
        dur = max(wd, ws) / wps if wps else 0
        rows.append({"id": b["id"], "type": b["type"], "start": round(clock, 2), "dur": round(dur, 2), "words": wd, "spoken_words": ws,
                     "concrete": len(vendor.beats.CONCRETE_RE.findall(b["display"]))})
        clock += dur
    total_display = sum(n_words(b["display"]) for b in beats) / wps if wps else 0
    total_spoken = sum(n_words(b["spoken"]) for b in beats) / wps if wps else 0
    total = max(total_display, total_spoken)

    # beats.py itself, on the display track, for the record and its own notes
    vendor_notes: list[str] = []
    try:
        analysis = vendor.beats.analyse("\n".join(b["display"] for b in beats), wpm=wpm, target=plan.get("target_seconds"))
        vendor_notes = analysis.get("notes", []) if analysis else []
    except Exception as exc:  # the vendor script is not ours; never let it crash the stage
        vendor_notes = [f"beats.py failed: {exc}"]
    if rows:
        if rows[0]["dur"] > hook_max:
            failures.append(failure("beats", f"the hook runs {rows[0]['dur']:.1f} s ({rows[0]['words']} words); it must stay under {hook_max:.0f} s", rows[0]["id"], hard=False))
        if rows[0]["concrete"] == 0:
            info.append("the hook has no number and no name in it (beats.py)")
    long_rows = [r for r in rows if r["dur"] > beat_max]
    for r in long_rows:
        failures.append(failure("beats", f"{r['id']} runs {r['dur']:.1f} s ({max(r['words'], r['spoken_words'])} words); no beat may run over {beat_max:.0f} s: split it or cut it to {int(beat_max * wps)} words", r["id"], hard=False))
    run_len, run_start = 0, None
    abstract_runs: list[str] = []
    for r in rows:
        if r["concrete"] == 0:
            run_len += 1
            run_start = run_start if run_start is not None else r["id"]
            if run_len == abstract_run:
                abstract_runs.append(f"{run_start} to {r['id']}")
        else:
            run_len, run_start = 0, None
    for span in abstract_runs:
        failures.append(failure("beats", f"beats {span} have nothing concrete in them ({abstract_run} in a row): put a number, an exact value or a capitalized name that is not the beat's first word (Claude, Anthropic) in one of them", span.split(" ")[0], hard=False))
    loop_word = ""
    if len(rows) >= 2:
        stop = vendor.beats.STOPWORDS
        first = {w.lower() for w in vendor.beats.words(beats[0]["display"]) if w.lower() not in stop}
        last = {w.lower() for w in vendor.beats.words(beats[-1]["display"]) if w.lower() not in stop}
        common = sorted(first & last, key=len, reverse=True)
        loop_word = common[0] if common else ""
    if not loop_word:
        failures.append(failure("beats", "no loop: the last line shares no word with the hook; repeat one word of the hook in the ask line", beats[-1]["id"] if beats else "", hard=False))
    checks["beats"] = {"wpm": wpm, "rows": rows, "hook_seconds": rows[0]["dur"] if rows else 0, "long_beats": [r["id"] for r in long_rows],
                       "abstract_runs": abstract_runs, "loop_word": loop_word, "vendor_notes": vendor_notes,
                       "total_seconds_display": round(total_display, 2), "total_seconds_spoken": round(total_spoken, 2)}

    # the structure: hook, stake, body, payoff, ask
    types = [b["type"] for b in beats]
    unknown = [f"{b['id']} ({b['type']})" for b in beats if b["type"] not in BEAT_TYPES]
    if unknown:
        failures.append(failure("structure", "unknown beat types: " + ", ".join(unknown) + "; use hook, stake, number, tool, step, comparison, proof, mechanism, before-after, pain-payoff, payoff, ask"))
    if not beats or types[0] != "hook":
        failures.append(failure("structure", "the first beat must be the hook (type hook)"))
    if types.count("hook") > 1:
        failures.append(failure("structure", "only one hook beat is allowed"))
    if not beats or types[-1] != "ask":
        failures.append(failure("structure", "the last beat must be the ask (type ask)"))
    if types.count("ask") > 1:
        failures.append(failure("ask", "more than one ask beat: one ask only, as the last beat"))
    stake_idx = [i for i, t in enumerate(types) if t == "stake"]
    if not stake_idx:
        failures.append(failure("requirements", "no stake beat: right after the hook, name the viewer's pain with the specific identity (the share driver)"))
    elif stake_idx[0] != 1:
        failures.append(failure("structure", f"the stake must come right after the hook (it is beat {beats[stake_idx[0]]['id']})"))
    body = [b for b in beats if b["type"] in BODY_TYPES]
    if len(body) < int(plan.get("min_body_beats", 2)):
        failures.append(failure("structure", f"only {len(body)} body beats; write at least {plan.get('min_body_beats', 2)} (one idea per beat: number, tool, step, comparison, proof, mechanism, before-after or pain-payoff)"))
    payoff_idx = [i for i, t in enumerate(types) if t == "payoff"]
    if not payoff_idx:
        failures.append(failure("structure", "no payoff beat: deliver what the hook promised in a beat of type payoff before the ask", hard=False))
    elif stake_idx and payoff_idx[-1] < stake_idx[-1]:
        failures.append(failure("structure", "the payoff comes before the stake; the order is hook, stake, body, payoff, ask", hard=False))
    checks["structure"] = {"types": types, "body_beats": len(body), "stake_beats": len(stake_idx), "payoff": bool(payoff_idx)}

    # the stake: seconds 2 to 7, with the identity
    stake_rows = [rows[i] for i in stake_idx] if rows else []
    stake_dur = sum(r["dur"] for r in stake_rows)
    stake_end = (stake_rows[-1]["start"] + stake_rows[-1]["dur"]) if stake_rows else 0
    stake_max = float(plan.get("stake_max_s", 5))
    if stake_rows and stake_dur > stake_max:
        failures.append(failure("timing", f"the stake runs {stake_dur:.1f} s (it has seconds 2 to 7 of the reel, about {stake_max:.0f} s): cut it to about {int(stake_max * wps)} words", beats[stake_idx[0]]["id"], hard=False))
    if stake_rows and stake_dur < 1.0:
        failures.append(failure("timing", f"the stake runs only {stake_dur:.1f} s: give the viewer's pain a full sentence", beats[stake_idx[0]]["id"], hard=False))
    identity = plan.get("identity", "")
    id_words = [w for w in re.findall(r"[a-z0-9][a-z0-9'-]*", identity.lower()) if w not in IDENTITY_STOP and len(w) > 2]
    # word stems, so "Long recording" names "long recordings" and "Clipping" names "clips" (M13, DECISIONS.md 286: the
    # exact-word match blocked a reel whose stake said "recording" for the identity's "recordings")
    stake_stems = {word_stem(w) for w in re.findall(r"[a-z0-9][a-z0-9'-]*", " ".join(beats[i]["display"] for i in stake_idx).lower())}
    all_stems = {word_stem(w) for w in re.findall(r"[a-z0-9][a-z0-9'-]*", " ".join(b["display"] for b in beats).lower())}
    hit_stake = [w for w in id_words if word_stem(w) in stake_stems]
    hit_all = [w for w in id_words if word_stem(w) in all_stems]
    need = min(2, len(id_words)) if id_words else 0
    identity_ok = len(hit_stake) >= need if need else True
    if id_words and not identity_ok:
        failures.append(failure("requirements", f"the stake does not name the share identity ({identity}): use at least two of its words ({', '.join(id_words[:8])}) in the stake beat" + (f"; found elsewhere: {', '.join(hit_all)}" if hit_all else "")))
    checks["stake"] = {"seconds": round(stake_dur, 2), "ends_at": round(stake_end, 2), "identity_words": id_words, "identity_hits": hit_stake, "identity_ok": identity_ok}

    # the ask: the keyword, one ask only, the loop
    ask_beat = beats[-1] if beats and beats[-1]["type"] == "ask" else None
    ask_text = ask_beat["display"] if ask_beat else draft.get("ask", {}).get("line", "")
    kw_ok = bool(kw) and re.search(r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])", ask_text, re.I) is not None
    if kw and not kw_ok:
        failures.append(failure("requirements", f"the ask line does not contain the comment keyword {kw}: write it as 'Comment {kw} ...'", ask_beat["id"] if ask_beat else ""))
    if kw and draft.get("ask", {}).get("keyword", "").upper() != kw:
        failures.append(failure("requirements", f"ask.keyword must be {kw} (the expansion's keyword), not {draft.get('ask', {}).get('keyword', '')!r}"))
    if ask_text and not re.search(r"\bcomment", ask_text, re.I):
        failures.append(failure("ask", "the ask line must ask for a comment with the keyword ('Comment " + (kw or "KEYWORD") + " ...')", ask_beat["id"] if ask_beat else ""))
    second_asks: list[str] = []
    for b in beats:
        is_ask = ask_beat is not None and b["id"] == ask_beat["id"]
        for name, r in CTA_RES:
            if r.search(b["display"]):
                if is_ask and name == "comment":
                    continue
                second_asks.append(f"{b['id']}: '{name}'")
    if second_asks:
        failures.append(failure("ask", "a second ask: " + ", ".join(second_asks) + "; the only ask is the comment keyword in the last beat (no follow, like, share, save, link in bio or DM)"))
    checks["ask"] = {"keyword": kw, "keyword_in_ask": kw_ok, "second_asks": second_asks, "loop_word": loop_word, "line": ask_text}
    checks["requirements"] = {"problem": bool(stake_idx), "identity": identity_ok, "keyword": kw_ok}

    # the solution rules (M12, spec S7): no FlashFX mention unless the solution is flashfx, nothing implying the reel
    # was made in FlashFX, no explicit sales phrase (the checks model judges the rest of the ad language)
    sol = plan.get("solution_decision") or {"type": "none"}
    sol_texts = {}
    for b in beats:
        for field in ("display", "spoken", "card"):
            sol_texts[f"{b['id']} {field}"] = b.get(field, "")
    sol_texts["ask line"] = draft.get("ask", {}).get("line", "")
    sol_texts["hook 2"] = draft.get("hook2", {}).get("spoken", "")
    sol_res = solution_lib.check_texts(sol, sol_texts)
    for prob in sol_res["problems"]:
        m = re.match(r"^(b\d+) ", prob["text"])
        failures.append(failure("solution", prob["message"], m.group(1) if m else ""))
    checks["solution"] = {"type": sol.get("type", "none"), "ok": sol_res["ok"], "problems": [p["message"] for p in sol_res["problems"]]}

    # the length against the range
    lo, hi = float(plan["length_s"][0]), float(plan["length_s"][1])
    tol = float(plan.get("length_tolerance_pct", 15)) / 100
    length_ok = lo <= total <= hi
    if not length_ok:
        if total < lo:
            delta_w = int(math.ceil((lo - total) * wps))
            msg = f"the script runs about {total:.1f} s ({draft['words']['display']} words); it must run {lo:.0f} to {hi:.0f} s: add about {delta_w + 3} words of substance"
            hard = total < lo * (1 - tol)
        else:
            delta_w = int(math.ceil((total - hi) * wps))
            msg = f"the script runs about {total:.1f} s ({draft['words']['display']} words); it must run {lo:.0f} to {hi:.0f} s: cut about {delta_w + 3} words"
            hard = total > hi * (1 + tol)
        failures.append(failure("length_hard" if hard else "length", msg, hard=hard))
    checks["length"] = {"seconds": round(total, 2), "seconds_display": round(total_display, 2), "seconds_spoken": round(total_spoken, 2),
                        "range": [lo, hi], "ok": length_ok, "words": draft["words"]}

    # the cards and the emphasis words
    cmax = int(plan.get("card_max_words", 6))
    bad_cards = []
    for b in beats:
        n = card_words(b["card"])
        if n > cmax:
            bad_cards.append(f"{b['id']} ({n} words)")
        elif n == 0:
            bad_cards.append(f"{b['id']} (empty)")
    if bad_cards:
        failures.append(failure("cards", f"on-screen card text must be 1 to {cmax} words: " + ", ".join(bad_cards), hard=False))
    checks["cards"] = {"max_words": cmax, "bad": bad_cards}
    hook = plan.get("hook", {})
    if beats and hook.get("spoken") and norm_line(beats[0]["display"]) != norm_line(hook["spoken"]):
        failures.append(failure("requirements", "the hook beat's display must be hook 1's spoken line, word for word: " + hook["spoken"]))
    checks["hook"] = {"verbatim": bool(beats) and norm_line(beats[0]["display"]) == norm_line(hook.get("spoken", "")), "line": hook.get("spoken", "")}
    digits = [b["id"] for b in beats if re.search(r"\d", b["spoken"])]
    if digits:
        info.append("digits left in the spoken track of " + ", ".join(digits) + " (the voice reads them as the engine likes)")
    checks["spoken"] = {"beats_with_digits": digits}

    # detect.py on the display track
    text = "\n".join(b["display"] for b in beats)
    try:
        results, overall, verdict = vendor.detect.run(text, vendor.lex)
        dres = {name: {"score": round(results[name][0], 1), "detail": results[name][1]} for name in vendor.detect.CHECKS}
    except Exception as exc:
        results, overall, verdict, dres = {}, 0.0, "ERROR", {"error": str(exc)}
    min_overall = float(plan.get("detect_min_overall", 70))
    min_check = float(plan.get("detect_min_check", 55))
    # config script.detect_skip (default BURSTINESS, 2026-11-09): measured and reported, left out of the gate. The
    # sentence-length statistic pushed the drafts into strings of fragments nobody could follow on one listen.
    skip = set(plan.get("detect_skip", ["BURSTINESS"]))
    gated = {n: v for n, v in dres.items() if n not in skip and isinstance(v, dict) and "score" in v}
    gate_overall = overall
    if skip and gated:
        sc = [v["score"] for v in gated.values()]
        gate_overall = sum(sc) / len(sc) * 0.6 + min(sc) * 0.4
    low = [n for n, v in gated.items() if v["score"] < min_check]
    detect_ok = gate_overall >= min_overall and not low and verdict != "ERROR"
    if not detect_ok:
        parts = [f"{n} {dres[n]['score']:.0f} ({dres[n]['detail']}): {detect_hints(n, dres[n]['detail'])}" for n in low] or \
                [f"{n} {v['score']:.0f} ({v['detail']})" for n, v in sorted(gated.items(), key=lambda kv: kv[1].get('score', 100))[:2]]
        weak = low or [n for n, v in sorted(gated.items(), key=lambda kv: kv[1].get('score', 100))[:1]]
        if "BURSTINESS" in weak:
            advice = rhythm_advice(beats)
            if advice:
                parts.append(advice)
        failures.append(failure("detect", f"detect.py scores {overall:.0f} (needs {min_overall:.0f} overall and {min_check:.0f} on every check): " + "; ".join(parts), hard=False))
    checks["detect"] = {"overall": round(overall, 1), "verdict": verdict, "ok": detect_ok, "checks": dres, "min_overall": min_overall, "min_check": min_check,
                        "skipped": sorted(skip), "gate_overall": round(gate_overall, 1)}

    hard = [f for f in failures if f["severity"] == "hard"]
    soft = [f for f in failures if f["severity"] == "soft"]
    return {"ok": not failures, "hard": hard, "soft": soft, "info": info, "checks": checks,
            "summary": {"seconds": round(total, 1), "words": draft["words"]["display"], "detect": round(overall, 1),
                        "beats": len(beats), "hard": len(hard), "soft": len(soft)}}


def cmd_check(args) -> int:
    draft = load_json(args.draft, {})
    plan = load_json(args.plan, {})
    if not draft or not plan:
        print("check: cannot read the draft or the plan", file=sys.stderr)
        return 2
    vendor = Vendor(args.vendor or VENDOR_DEFAULT)
    hum = humanize_draft(draft, vendor)
    if args.write:
        draft["humanized"] = True
        save_json(args.draft, draft)
    report = run_checks(draft, plan, vendor)
    report["checks"]["humanize"] = hum
    report["checks"]["claims"] = {"status": "pending"}
    report["draft"] = args.draft
    report["label"] = draft.get("label", "")
    report["round"] = draft.get("round", 0)
    report["checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_json(args.out, report)
    out_json({"ok": report["ok"], "hard": len(report["hard"]), "soft": len(report["soft"]), "summary": report["summary"],
              "first": (report["hard"] + report["soft"])[0]["message"] if (report["hard"] or report["soft"]) else "",
              "humanize_changes": len(hum["changed"])})
    return 0


def cmd_claims_data(args) -> int:
    draft = load_json(args.draft, {})
    if not draft:
        return 2
    lines = []
    for b in draft["beats"]:
        facts = (" (the writer cites " + ", ".join(b["facts"]) + ")") if b.get("facts") else ""
        lines.append(f"- {b['id']} [{b['type']}]{facts}\n  display: {b['display']}\n  spoken: {b['spoken']}")
    out_json({"text": "\n".join(lines), "n": len(draft["beats"])})
    return 0


def cmd_claims(args) -> int:
    report = load_json(args.report, {})
    answer = load_json(args.answer, {})
    draft = load_json(args.draft, {}) if args.draft else {}
    if not report or not isinstance(answer, dict):
        print("claims: cannot read the report or the answer", file=sys.stderr)
        return 2
    valid_ids = {b["id"] for b in draft.get("beats", [])} if draft else set()
    claims = []
    bad: list[dict] = []
    for c in answer.get("claims", []) if isinstance(answer.get("claims"), list) else []:
        if not isinstance(c, dict):
            continue
        item = {"beat": clean(c.get("beat", "")), "claim": clean(c.get("claim", "")), "status": clean(c.get("status", "")).lower(),
                "facts": normalize_facts(c.get("facts", [])), "note": clean(c.get("note", ""))}
        claims.append(item)
        if item["status"] in ("unsupported", "overstated"):
            bad.append(item)
    report["hard"] = [f for f in report.get("hard", []) if f["check"] != "facts" and not (f["check"] == "solution" and f.get("source") == "model")]
    for item in bad:
        beat = item["beat"] if item["beat"] in valid_ids or not valid_ids else ""
        what = "is not backed by facts.md" if item["status"] == "unsupported" else "says more than facts.md backs"
        msg = f"{item['beat'] or 'a beat'}: the claim '{item['claim'][:120]}' {what}" + (f" ({item['note'][:160]})" if item["note"] else "") + \
              "; reword it from a verified claim of facts.md or remove it"
        report["hard"].append(failure("facts", msg, beat))
    # the solution rules the checks model judges (M12, spec S7): ad language, and anything implying the reel itself
    # was made in FlashFX; each one is a hard failure of check "solution" (the scripted part sits in run_checks)
    solution_issues = []
    for c in answer.get("solution_issues", []) if isinstance(answer.get("solution_issues"), list) else []:
        if not isinstance(c, dict) or not clean(c.get("text", "")):
            continue
        kind = clean(c.get("kind", "")).lower() or "ad_language"
        beat = clean(c.get("beat", ""))
        item = {"beat": beat, "kind": kind, "text": clean(c.get("text", "")), "note": clean(c.get("note", ""))}
        solution_issues.append(item)
        what = {"made_in_flashfx": "implies the reel itself was made in FlashFX (the reels are rendered by another tool)",
                "flashfx_mention": "names FlashFX although the reel's solution is not FlashFX",
                "pitch": "reads as ad language"}.get(kind, "reads as ad language (a pitch, hype or a superlative about the solution)")
        msg = f"{beat or 'a beat'}: '{item['text'][:120]}' {what}" + (f" ({item['note'][:160]})" if item["note"] else "") + \
              "; show the solution solving the problem instead, the way any tool would be shown"
        f = failure("solution", msg, beat if (beat in valid_ids or not valid_ids) else "")
        f["source"] = "model"
        report["hard"].append(f)
    report["checks"]["claims"] = {"status": "checked", "n": len(claims), "supported": len([c for c in claims if c["status"] == "supported"]),
                                  "unsupported": len([c for c in claims if c["status"] == "unsupported"]),
                                  "overstated": len([c for c in claims if c["status"] == "overstated"]),
                                  "not_a_claim": len([c for c in claims if c["status"] in ("not a claim", "framing", "not_a_claim")]),
                                  "claims": claims, "summary": clean(answer.get("summary", ""))}
    report["checks"].setdefault("solution", {})["model_issues"] = solution_issues
    report["ok"] = not report["hard"] and not report.get("soft")
    report["summary"]["hard"] = len(report["hard"])
    report["summary"]["claims_unsupported"] = len(bad)
    report["summary"]["solution_issues"] = len(solution_issues)
    save_json(args.out or args.report, report)
    out_json({"ok": report["ok"], "hard": len(report["hard"]), "soft": len(report.get("soft", [])), "claims": len(claims), "bad": len(bad),
              "first": (report["hard"] + report.get("soft", []))[0]["message"] if (report["hard"] or report.get("soft")) else ""})
    return 0


def feedback_text(report: dict, plan: dict | None) -> str:
    lines = []
    for f in report.get("hard", []) + report.get("soft", []):
        tag = "must fix" if f["severity"] == "hard" else "fix"
        lines.append(f"- [{tag}, {f['check']}] {f['message']}" + (f" Hint: {f['hint']}" if f.get("hint") else ""))
    s = report.get("summary", {})
    if plan:
        lo, hi = plan["length_s"]
        lines.append(f"- current length: about {s.get('seconds', '?')} s ({s.get('words', '?')} words at {plan['wpm']:.0f} wpm); the final script must run {lo:.0f} to {hi:.0f} s, "
                     f"which is {plan['final_words'][0]} to {plan['final_words'][1]} words, and no cut pass follows a rewrite")
    return "\n".join(lines) if lines else "- (no failing check)"


def cmd_feedback(args) -> int:
    report = load_json(args.report, {})
    plan = load_json(args.plan, None) if args.plan else None
    if not report:
        return 2
    sys.stdout.write(feedback_text(report, plan) + "\n")
    return 0


# ---------------------------------------------------------------------------------------------------- the pick
def report_summary_text(report: dict | None) -> str:
    if not report:
        return "no checks yet"
    s = report.get("summary", {})
    fails = [f"{f['check']}: {f['message'][:90]}" for f in report.get("hard", []) + report.get("soft", [])]
    head = f"about {s.get('seconds', '?')} s, {s.get('words', '?')} words, detect.py {s.get('detect', '?')}"
    return head + ("; failing checks: " + " | ".join(fails[:6]) if fails else "; every check passes")


def cmd_pick_data(args) -> int:
    drafts = [load_json(p, {}) for p in args.drafts]
    reports = [load_json(p, None) for p in args.reports] if args.reports else [None] * len(drafts)
    if any(not d for d in drafts):
        return 2
    labels = [d.get("label", str(i)) for i, d in enumerate(drafts)]
    order = list(range(len(drafts)))
    random.Random(args.seed or "pick").shuffle(order)
    out = {"order": [labels[i] for i in order], "texts": {}, "checks": {}, "tones": {}}
    for pos, i in enumerate(order, start=1):
        out["texts"][str(pos)] = draft_script_text(drafts[i])
        out["checks"][str(pos)] = report_summary_text(reports[i] if i < len(reports) else None)
        out["tones"][str(pos)] = drafts[i].get("tone", "")
    save_json(args.out, out)
    out_json({"order": out["order"], "text_1": out["texts"].get("1", ""), "text_2": out["texts"].get("2", ""),
              "checks_1": out["checks"].get("1", ""), "checks_2": out["checks"].get("2", ""),
              "tone_1": out["tones"].get("1", ""), "tone_2": out["tones"].get("2", "")})
    return 0


def cmd_pick(args) -> int:
    data = load_json(args.data, {})
    answer = load_json(args.answer, {})
    if not data or not isinstance(answer, dict):
        return 2
    order = data.get("order", [])
    winner = str(answer.get("winner", "")).strip().strip('"').lower()
    m = re.search(r"\d", winner)
    idx = int(m.group(0)) - 1 if m else -1
    lenient = False
    if not (0 <= idx < len(order)):
        idx, lenient = 0, True
    pick = {"winner": order[idx], "winner_position": idx + 1, "order": order, "reason": clean(answer.get("reason", "")),
            "notes": clean(answer.get("notes", "")), "lenient": lenient, "decided": time.strftime("%Y-%m-%d %H:%M:%S")}
    save_json(args.out, pick)
    out_json({"winner": pick["winner"], "position": idx + 1, "lenient": lenient, "reason": pick["reason"][:200]})
    return 0


# ---------------------------------------------------------------------------------------------------- compose
def cmd_compose(args) -> int:
    draft = load_json(args.draft, {})
    report = load_json(args.report, {})
    plan = load_json(args.plan, {})
    pick = load_json(args.pick, {}) if args.pick else {}
    rounds_log = load_json(args.rounds_log, []) if args.rounds_log else []
    flags = json.loads(args.flags) if args.flags else []
    if not draft or not report or not plan:
        print("compose: cannot read the draft, the report or the plan", file=sys.stderr)
        return 2
    drafts_info = {}
    for spec in args.draft_info or []:
        label, _, path = spec.partition("=")
        d = load_json(path, {})
        if d:
            drafts_info[label] = {"tone": d.get("tone", ""), "file": os.path.basename(path), "round": d.get("round", 0),
                                  "words": d.get("words", {}), "cut": {k: d.get("cut", {}).get(k) for k in ("ok", "removed_pct", "before_words", "after_words", "chosen")}}
    beats = []
    importance = derive_importance(draft["beats"])
    for b, imp in zip(draft["beats"], importance):
        beats.append({"id": b["id"], "type": b["type"], "display": b["display"], "spoken": b["spoken"], "emphasis": b.get("emphasis", []),
                      "importance": imp, "card": b["card"], "card_words": card_words(b["card"]), "facts": b.get("facts", []),
                      "seconds": next((r["dur"] for r in report["checks"]["beats"]["rows"] if r["id"] == b["id"]), None)})
    cut = draft.get("cut", {}) or {}
    script = {
        "written_by": "07-script", "checked": today(), "idea_id": plan.get("idea_id", ""), "wpm": plan["wpm"],
        "video_type": plan["video_type"], "length_s": plan["length_s"], "length_source": plan.get("length_source", ""),
        "target_seconds": plan["target_seconds"], "estimated_seconds": report["checks"]["length"]["seconds"],
        "estimated_seconds_spoken": report["checks"]["length"]["seconds_spoken"], "words": draft["words"]["display"], "spoken_words": draft["words"]["spoken"],
        "tone": draft.get("tone", ""), "tones": plan.get("tones", []), "tone_source": plan.get("tone_source", ""),
        "picked": draft.get("label", ""), "pick": pick, "drafts": drafts_info, "used_fallback_draft": bool(args.fallback),
        "hook": plan["hook"], "hook2": {k: v for k, v in draft.get("hook2", {}).items() if k != "spoken_changes"},
        "solution": plan.get("solution_decision") or {"type": "none", "name": "", "url": ""},
        "beats": beats,
        "ask": {"keyword": plan.get("keyword", ""), "line": draft["ask"]["line"], "loop_word": report["checks"]["ask"].get("loop_word", ""),
                "deliverable": plan.get("deliverable", ""), "deliverable_status": plan.get("deliverable_status", "new"), "deliverable_link": plan.get("deliverable_link", "")},
        "cut": {"ok": cut.get("ok", False), "before_words": cut.get("before_words"), "after_words": cut.get("after_words"),
                "removed_pct": cut.get("removed_pct"), "chosen": cut.get("chosen", ""), "tries": cut.get("tries", 0), "errors": cut.get("errors", [])},
        "checks": {"ok": report["ok"], "hard": report["hard"], "soft": report["soft"], "info": report.get("info", []),
                   "summary": report["summary"], "detail": report["checks"]},
        "rounds": int(args.rounds), "rounds_log": rounds_log, "flags": flags,
        "pronunciations": plan.get("pronunciations", []),
        "spoken_changes": {b["id"]: b.get("spoken_changes", []) for b in draft["beats"] if b.get("spoken_changes")},
        "humanize": report["checks"].get("humanize", {}),
        "rewrites": [],
        "notes": draft.get("notes", ""),
    }
    save_json(args.out, script)
    out_json({"ok": True, "beats": len(beats), "seconds": script["estimated_seconds"], "words": script["words"], "tone": script["tone"],
              "detect": report["summary"].get("detect"), "removed_pct": script["cut"]["removed_pct"], "picked": script["picked"]})
    return 0


# ---------------------------------------------------------------------------------------------------- S8's one-line rewrite
def cmd_rewrite_line_data(args) -> int:
    script = load_json(args.script, {})
    if not script:
        return 2
    beat = next((b for b in script.get("beats", []) if b["id"] == args.beat), None)
    if beat is None:
        print(f"rewrite-line-data: no beat {args.beat} in script.json", file=sys.stderr)
        return 3
    out_json({"display": beat["display"], "spoken": beat["spoken"], "type": beat["type"], "card": beat["card"],
              "words": n_words(beat["spoken"]), "all": "\n".join(f"{b['id']} [{b['type']}] {b['spoken']}" for b in script["beats"]),
              "pronunciations": "\n".join(f"- {w} = {s}" for w, s in script.get("pronunciations", [])) or "(none)"})
    return 0


def word_stem(word: str) -> str:
    """A light English stem for matching a phrase's words in a script: plural, possessive, -ing and -ed endings removed,
    a doubled final consonant undone (recordings, recording -> record; clips, clipping -> clip; cut, cutting -> cut)."""
    w = re.sub(r"'s?$", "", (word or "").lower())
    for _ in range(2):  # "recordings": the plural, then the -ing
        for suf, keep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                if suf == "es" and not re.search(r"(s|x|z|ch|sh)es$", w):
                    continue
                if suf == "s" and w.endswith("ss"):
                    continue
                w = w[: len(w) - len(suf)] + keep
                if suf in ("ing", "ed") and len(w) >= 4 and w[-1] == w[-2] and w[-1] not in "aeiouls":
                    w = w[:-1]
                break
    return w


def sound_skeleton(word: str) -> str:
    """A rough consonant skeleton of a word (Claude, Clawed and Clod are all "kld"), to catch a respelling."""
    w = re.sub(r"[^a-z]", "", (word or "").lower())
    w = re.sub(r"'s$", "", w)
    for a, b in (("ph", "f"), ("ck", "k"), ("qu", "k"), ("x", "ks"), ("c", "k"), ("q", "k"), ("z", "s")):
        w = w.replace(a, b)
    w = re.sub(r"[aeiouwhy]", "", w)
    return re.sub(r"(.)\1+", r"\1", w)


def respellings(before: str, after: str) -> list[tuple[str, str]]:
    """(old, new) pairs where the rewrite swapped a word for a different spelling of the same sound (M13, DECISIONS.md
    283): S8 then compares the transcription with the respelled text and fails a voice that says the name right, and
    the captions would show the respelling. Only names (capitalized) or long words count, with 2 or more consonants."""
    def words(text: str) -> list[str]:
        return [re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", w) for w in re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text or "").split()]
    old = [w for w in words(before) if w]
    new = [w for w in words(after) if w]
    old_l, new_l = {w.lower() for w in old}, {w.lower() for w in new}
    pairs = []
    for o in old:
        if o.lower() in new_l or not (o[:1].isupper() or len(o) >= 5):
            continue
        sk = sound_skeleton(o)
        if len(sk) < 2:
            continue
        for n in new:
            if n.lower() not in old_l and sound_skeleton(n) == sk and (o, n) not in pairs:
                pairs.append((o, n))
    return pairs


def cmd_rewrite_line_apply(args) -> int:
    script = load_json(args.script, {})
    answer = load_json(args.answer, {})
    if not script or not isinstance(answer, dict):
        return 2
    beat = next((b for b in script.get("beats", []) if b["id"] == args.beat), None)
    if beat is None:
        return 3
    pron = script.get("pronunciations", [])
    spoken_src = clean(answer.get("spoken", ""))
    display = clean(answer.get("display", "")) or beat["display"]
    errors: list[str] = []
    if not spoken_src:
        errors.append("the answer has no spoken line")
    for r in PLACEHOLDER_RES:
        if r.search(spoken_src) or r.search(display):
            errors.append("the answer holds a placeholder")
    spoken, changes = spoken_track(spoken_src, pron)
    for o, n in respellings(beat["spoken"], spoken_src):
        errors.append(f"the new line respells \"{o}\" as \"{n}\": keep every name spelled as the script spells it (the "
                      f"voice step handles the pronunciation); choose other words around it instead")
    if n_words(spoken) > n_words(beat["spoken"]) + 3:
        errors.append(f"the new line is longer ({n_words(spoken)} words against {n_words(beat['spoken'])}); it must be shorter or equal")
    if errors:
        out_json({"ok": False, "errors": errors})
        return 0
    entry = {"beat": args.beat, "reason": clean(args.reason or ""), "before_spoken": beat["spoken"], "after_spoken": spoken,
             "before_display": beat["display"], "after_display": display, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    beat["spoken"] = spoken
    if args.keep_display:
        pass
    else:
        beat["display"] = display
        beat["emphasis"] = filter_emphasis(beat.get("emphasis", []), display)
    script.setdefault("rewrites", []).append(entry)
    script["spoken_words"] = sum(n_words(b["spoken"]) for b in script["beats"])
    script["words"] = sum(n_words(b["display"]) for b in script["beats"])
    save_json(args.out or args.script, script)
    out_json({"ok": True, "spoken": spoken, "display": beat["display"], "changes": changes, "rewrites": len(script["rewrites"])})
    return 0


# ---------------------------------------------------------------------------------------------------- small helpers
def cmd_numbers(args) -> int:
    pron = read_pronunciations(args.pronunciations) if args.pronunciations else []
    text, changes = spoken_track(args.text, pron)
    out_json({"spoken": text, "changes": changes})
    return 0


def cmd_length_rule(args) -> int:
    out_json(tweaks_length(args.tweaks) or {})
    return 0


def cmd_tones(args) -> int:
    header = brief_header(read_text_or(args.brief)) if args.brief else {"tones": [], "video_type": ""}
    tones, source = choose_tones(header["tones"], args.family or "", TONES)
    out_json({"tones": tones, "source": source, "suggested": header["tones"], "video_type": header["video_type"]})
    return 0


def cmd_round_log(args) -> int:
    log = load_json(args.file, []) or []
    entry = {"round": int(args.round), "draft": args.label, "action": args.action, "ok": args.ok == "true",
             "hard": int(args.hard or 0), "soft": int(args.soft or 0), "note": clean(args.note or ""), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    log.append(entry)
    save_json(args.file, log)
    out_json({"entries": len(log)})
    return 0


def main(argv=None) -> int:
    setup_streams()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("setup")
    sp.add_argument("--config", required=True); sp.add_argument("--brief", required=True); sp.add_argument("--judge", required=True)
    sp.add_argument("--expansion", required=True); sp.add_argument("--voice", default=""); sp.add_argument("--pronunciations", default="")
    sp.add_argument("--tweaks", default=""); sp.add_argument("--style", default=""); sp.add_argument("--wpm", required=True)
    sp.add_argument("--rounds", default="3"); sp.add_argument("--idea-id", default=""); sp.add_argument("--idea-text", default="")
    sp.add_argument("--solution", default="", help="02-expansion/solution.json (M12: the solution rules)")
    sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_setup)

    sp = sub.add_parser("draft")
    sp.add_argument("--answer", required=True); sp.add_argument("--plan", required=True); sp.add_argument("--out", required=True)
    sp.add_argument("--label", default="a"); sp.add_argument("--tone", default=""); sp.add_argument("--round", default="1")
    sp.add_argument("--source", default="write"); sp.add_argument("--previous", default=""); sp.set_defaults(func=cmd_draft)

    sp = sub.add_parser("draft-text"); sp.add_argument("--draft", required=True); sp.add_argument("--plain", action="store_true")
    sp.add_argument("--no-spoken", action="store_true"); sp.add_argument("--as-answer", action="store_true"); sp.set_defaults(func=cmd_draft_text)

    sp = sub.add_parser("cut-data"); sp.add_argument("--draft", required=True); sp.add_argument("--plan", required=True); sp.set_defaults(func=cmd_cut_data)
    sp = sub.add_parser("cut-apply"); sp.add_argument("--draft", required=True); sp.add_argument("--answer", required=True)
    sp.add_argument("--plan", required=True); sp.add_argument("--out", required=True); sp.add_argument("--attempt", default="1"); sp.set_defaults(func=cmd_cut_apply)
    sp = sub.add_parser("cut-best"); sp.add_argument("--draft", required=True); sp.add_argument("--plan", required=True)
    sp.add_argument("--attempts", nargs="*", default=[]); sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_cut_best)

    sp = sub.add_parser("check"); sp.add_argument("--draft", required=True); sp.add_argument("--plan", required=True)
    sp.add_argument("--out", required=True); sp.add_argument("--vendor", default=""); sp.add_argument("--write", action="store_true"); sp.set_defaults(func=cmd_check)
    sp = sub.add_parser("claims-data"); sp.add_argument("--draft", required=True); sp.set_defaults(func=cmd_claims_data)
    sp = sub.add_parser("claims"); sp.add_argument("--report", required=True); sp.add_argument("--answer", required=True)
    sp.add_argument("--draft", default=""); sp.add_argument("--out", default=""); sp.set_defaults(func=cmd_claims)
    sp = sub.add_parser("feedback"); sp.add_argument("--report", required=True); sp.add_argument("--plan", default=""); sp.set_defaults(func=cmd_feedback)

    sp = sub.add_parser("pick-data"); sp.add_argument("--drafts", nargs="+", required=True); sp.add_argument("--reports", nargs="*", default=[])
    sp.add_argument("--seed", default=""); sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_pick_data)
    sp = sub.add_parser("pick"); sp.add_argument("--data", required=True); sp.add_argument("--answer", required=True)
    sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_pick)

    sp = sub.add_parser("compose"); sp.add_argument("--draft", required=True); sp.add_argument("--report", required=True)
    sp.add_argument("--plan", required=True); sp.add_argument("--pick", default=""); sp.add_argument("--rounds", default="1")
    sp.add_argument("--rounds-log", default=""); sp.add_argument("--flags", default=""); sp.add_argument("--fallback", default="")
    sp.add_argument("--draft-info", nargs="*", default=[]); sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_compose)

    sp = sub.add_parser("rewrite-line-data"); sp.add_argument("--script", required=True); sp.add_argument("--beat", required=True); sp.set_defaults(func=cmd_rewrite_line_data)
    sp = sub.add_parser("rewrite-line-apply"); sp.add_argument("--script", required=True); sp.add_argument("--beat", required=True)
    sp.add_argument("--answer", required=True); sp.add_argument("--reason", default=""); sp.add_argument("--out", default="")
    sp.add_argument("--keep-display", action="store_true"); sp.set_defaults(func=cmd_rewrite_line_apply)

    sp = sub.add_parser("numbers"); sp.add_argument("--text", required=True); sp.add_argument("--pronunciations", default=""); sp.set_defaults(func=cmd_numbers)
    sp = sub.add_parser("length-rule"); sp.add_argument("--tweaks", required=True); sp.set_defaults(func=cmd_length_rule)
    sp = sub.add_parser("tones"); sp.add_argument("--brief", default=""); sp.add_argument("--family", default=""); sp.set_defaults(func=cmd_tones)
    sp = sub.add_parser("round-log"); sp.add_argument("--file", required=True); sp.add_argument("--round", required=True)
    sp.add_argument("--label", required=True); sp.add_argument("--action", required=True); sp.add_argument("--ok", default="false")
    sp.add_argument("--hard", default="0"); sp.add_argument("--soft", default="0"); sp.add_argument("--note", default=""); sp.set_defaults(func=cmd_round_log)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
