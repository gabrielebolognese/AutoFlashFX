#!/usr/bin/env python
"""exporter.py: the youtube-shorts platform exporter (BUILD_SPEC.md section 8, M19).

Reads runs/<run>/export/input.json (schema: input.schema.json next to this file), prepares the prompt's data,
checks the model's answer (title, description, pinned comment, hashtags) against the text rules of section 8,
composes export.json and renders the captions file text. Stdlib plus jsonschema and the vendored humanize.py and
slop.json of instagram-agent-skill (loaded by path, like pipeline/lib/caption.py does).

  exporter.py data    --input FILE --out FILE
      validates the input and writes the prompt's data (flat strings for run.sh's render_prompt, plus the serial
      part's facts); prints {"ok": true, ...}. An invalid input exits 2 with the problems on stderr.
  exporter.py check   --input FILE --answer FILE [--vendor DIR]
      every check on an answer as it stands (no humanizing): prints {"ok": bool, "errors": [...]}.
  exporter.py compose --input FILE --answer FILE --out FILE [--force] [--vendor DIR] [--reel PATH]
      humanize first (em dashes, slop words, odd bullets turned into "- "), then check. With no failure, or with
      --force, writes export.json and prints {"ok": <no failure>, "forced": <failures kept>, "errors": [...],
      "written": true, ...}; a failure without --force prints {"ok": false, "errors": [...], "written": false}
      (exit 0). With --force and failures the manifest's needs_review carries one
      "youtube-shorts exporter: <check text>" line per failed check after the input's own lines.
  exporter.py record  --input FILE --export FILE --descriptions FILE
      appends {run_id, title, description, date} to the descriptions.jsonl (once per run_id).
  exporter.py render  --export FILE --id ID --number N --run-id RUN [--editor-lines]
      the captions file text (section 8). Also importable: render_captions(manifest, channel_id, n, run_id) -> str.

export.json: title, description, pinned_comment, hashtags, story (title or null), part (int or null), upload_steps,
hooks {hook1}, needs_review, facts, files {reel}, run_id, channel, checks {ok, errors, forced}, humanize {changes}.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
VENDOR_DEFAULT = os.path.join(REPO, "pipeline", "vendor", "ig-agent-skill")
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
PREFIX = "youtube-shorts exporter: "
PARAGRAPH_MAX = 200
OVERLAP_MAX = 0.30          # the share of this description's trigrams that an earlier description may share
EARLIER_MAX = 30
LIST_MIN, LIST_MAX = 3, 6

HASHTAG_TOKEN = re.compile(r"^#[A-Za-z0-9_]+$")
HASHTAG_ANY = re.compile(r"(?<![\w&])#[A-Za-z0-9_]+")
LINK_RE = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9][a-z0-9-]*\.(?:com|net|org|io|co|app|dev|ly|tv|me|gg|xyz|info)\b", re.I)
NUMBER_WORDS = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
PART_COUNT_RE = re.compile(r"\bpart\s+(?:\d+|%s)\s+(?:of|out of|/)\s+(?:\d+|%s)\b" % (NUMBER_WORDS, NUMBER_WORDS), re.I)
OF_M_RE = re.compile(r"\b\d+\s+of\s+\d+\b|\bof\s+(?:\d+|%s)\s+parts\b" % NUMBER_WORDS, re.I)
BULLET_RE = re.compile("(?m)^[ \t]*[•·▪◦‣⁃●○■*+" + EN_DASH + EM_DASH + "−][ \t]+")
INDENTED_LIST_RE = re.compile(r"(?m)^[ \t]+(?=- )")
ABBREVIATIONS = re.compile(r"\b(mr|mrs|ms|dr|st|vs|jr|sr|no|etc|inc|ltd|co|approx)\.", re.I)


# ------------------------------------------------------------------------------------------------ plumbing

def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def load_json(path: str, default=None):
    try:
        with open(winpath(path), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path: str, data) -> None:
    with open(winpath(path), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def out_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False))


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, winpath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_VENDOR_CACHE: dict = {}


def vendor(vendor_dir: str = ""):
    """(humanize module, slop lexicon) from the vendored folder."""
    vdir = vendor_dir or VENDOR_DEFAULT
    if vdir not in _VENDOR_CACHE:
        hum = load_module("vendor_humanize_ytshorts", os.path.join(vdir, "humanize.py"))
        lex = hum.load_lexicon(winpath(os.path.join(vdir, "slop.json")))
        _VENDOR_CACHE[vdir] = (hum, lex)
    return _VENDOR_CACHE[vdir]


def platform_json() -> dict:
    return load_json(os.path.join(HERE, "platform.json"), {}) or {}


class InputError(Exception):
    pass


def load_input(path: str) -> dict:
    """input.json, validated against input.schema.json (InputError with every problem)."""
    inp = load_json(path)
    if not isinstance(inp, dict):
        raise InputError(f"{path} is missing or is not a JSON object")
    schema = load_json(os.path.join(HERE, "input.schema.json"))
    try:
        import jsonschema
    except ImportError:
        return inp
    validator = jsonschema.Draft202012Validator(schema)
    problems = []
    for err in sorted(validator.iter_errors(inp), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "(root)"
        problems.append(f"input.json {where}: {err.message}")
    if problems:
        raise InputError("; ".join(problems[:8]))
    return inp


def settings(inp: dict) -> dict:
    plat = platform_json()
    defaults = dict(plat.get("export_defaults") or {})
    limits = plat.get("text_limits") or {}
    s = {
        "caption_max": defaults.get("caption_max", limits.get("caption_max", 150)),
        "description_max": defaults.get("description_max", limits.get("description_max", 1000)),
        "pinned_comment_max": limits.get("pinned_comment_max", 200),
        "hashtags": defaults.get("hashtags", limits.get("hashtags", 4)),
        "required_hashtags": list(defaults.get("required_hashtags") or []),
        "pinned_comment": bool(defaults.get("pinned_comment", True)),
    }
    for key, value in (inp.get("export") or {}).items():
        if key in s and value is not None:
            s[key] = value
    return s


def serial_of(inp: dict):
    ser = inp.get("serial")
    return ser if isinstance(ser, dict) and ser.get("story_title") else None


# ------------------------------------------------------------------------------------------------ text helpers

def norm_text(value) -> str:
    return ("" if value is None else str(value)).replace("\r\n", "\n").replace("\r", "\n")


def norm_key(text: str) -> str:
    """lowercase, punctuation removed, whitespace collapsed (for equality of sentences)."""
    return " ".join(re.sub(r"[^\w\s]", " ", norm_text(text).lower()).split())


def nonempty_lines(text: str) -> list:
    return [ln for ln in norm_text(text).split("\n") if ln.strip()]


def is_hashtag_line(line: str) -> bool:
    toks = line.split()
    return bool(toks) and all(HASHTAG_TOKEN.match(t) for t in toks)


def trigrams(text: str) -> set:
    kept = [ln for ln in norm_text(text).split("\n") if not is_hashtag_line(ln.strip())]
    words = re.sub(r"[^\w\s]", "", " ".join(kept).lower()).split()
    return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}


def first_line(text: str) -> str:
    lines = nonempty_lines(text)
    return lines[0].strip() if lines else ""


def sentence_count(line: str) -> int:
    masked = ABBREVIATIONS.sub(lambda m: m.group(0)[:-1] + "\x00", line.strip())
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+(?=\S)", masked)
    return len([p for p in parts if p.strip()])


def split_title(title: str, ser: dict):
    """(hook phrase, ok) of a serial title `<hook phrase> | <Story title>, Part <N>`."""
    tail = f" | {ser['story_title']}, Part {ser['part']}"
    if title == tail.strip():
        return "", True
    if title.endswith(tail):
        return title[:-len(tail)].strip(), True
    return "", False


def slop_hits(text: str, lex: dict) -> list:
    hits = []
    for entry in sorted(lex["phrases"] + lex["words"], key=lambda e: len(e["find"]), reverse=True):
        find = entry["find"]
        pat = re.compile(r"\b" + re.escape(find).replace(r"\ ", r"\s+") + r"\b", re.I)
        if pat.search(text):
            hits.append(find)
    return hits


def has_next_part_line(line: str, next_part: int) -> bool:
    return bool(re.search(r"\bnext\s+part\b|\bpart\s+%d\b|\bnext\s+episode\b|\bnext\s+chapter\b" % next_part, line, re.I))


# ------------------------------------------------------------------------------------------------ the checks

def check_answer(inp: dict, answer: dict, lex: dict) -> list:
    """Every check of section 8 on an answer; the failures as readable lines, in a fixed order."""
    st = settings(inp)
    ser = serial_of(inp)
    errors: list = []
    title = norm_text(answer.get("title")).strip("\n")
    desc = norm_text(answer.get("description")).strip()
    pinned = norm_text(answer.get("pinned_comment")).strip()
    tags_field = answer.get("hashtags")
    cmax, dmax, pmax = int(st["caption_max"]), int(st["description_max"]), int(st["pinned_comment_max"])
    want_tags = int(st["hashtags"])
    required = [str(t) for t in st["required_hashtags"]]

    # TITLE
    if not title.strip():
        errors.append("title is empty")
    else:
        if "\n" in title.strip():
            errors.append("title is more than one line, it must be one line")
        if len(title) > cmax:
            errors.append(f"title is {len(title)} characters, the limit is {cmax} (count every character, shorten it by {len(title) - cmax})")
        if HASHTAG_ANY.search(title):
            errors.append("title contains a hashtag, hashtags go only in the description")
        if LINK_RE.search(title):
            errors.append("title contains a link")
        if ser:
            hook_phrase, ok = split_title(title.strip(), ser)
            suffix = f"{ser['story_title']}, Part {ser['part']}"
            if not ok:
                errors.append(f'title of a serial part must read "<hook phrase> | {suffix}" (after the " | " exactly "{suffix}")')
            elif not hook_phrase:
                errors.append(f'title has no hook phrase before " | {suffix}"')
            if PART_COUNT_RE.search(title) or OF_M_RE.search(title):
                errors.append('title states a part count ("of M"); the part count can change, never write it')

    # DESCRIPTION
    lines = norm_text(desc).split("\n")
    nonempty = [ln.strip() for ln in lines if ln.strip()]
    if not nonempty:
        errors.append("description is empty")
    else:
        if len(desc) > dmax:
            errors.append(f"description is {len(desc)} characters, the limit is {dmax} counting every character, line break and hashtag (cut {len(desc) - dmax})")
        first = nonempty[0]
        hook_phrase = split_title(title.strip(), ser)[0] if ser else ""
        if first.startswith("- ") or is_hashtag_line(first):
            errors.append("description's first line must be a one-sentence summary, not a list item or hashtags")
        else:
            if norm_key(first) and (norm_key(first) == norm_key(title) or (hook_phrase and norm_key(first) == norm_key(hook_phrase))):
                errors.append("description's first line repeats the title, it must be its own one-sentence summary")
            if sentence_count(first) > 1:
                errors.append("description's first line is more than one sentence, it must be a one-sentence summary")
        # paragraphs: consecutive lines that are not list items
        para: list = []
        paragraphs: list = []
        for ln in lines + [""]:
            if ln.strip() and not ln.startswith("- "):
                para.append(ln.strip())
            else:
                if para:
                    paragraphs.append(" ".join(para))
                para = []
        for p in paragraphs:
            if len(p) > PARAGRAPH_MAX:
                errors.append(f"description has a paragraph of {len(p)} characters, the limit is {PARAGRAPH_MAX} (break it into short lines): \"{p[:50]}...\"")
        # lists: runs of "- " lines
        runs: list = []
        run = 0
        for ln in lines + [""]:
            if ln.startswith("- "):
                run += 1
            else:
                if run:
                    runs.append(run)
                run = 0
        if not any(LIST_MIN <= r <= LIST_MAX for r in runs):
            found = f" (found runs of {', '.join(str(r) for r in runs)} lines)" if runs else ""
            errors.append(f'description has no list of {LIST_MIN} to {LIST_MAX} lines, one per line, each starting with "- "{found}')
        # hashtags: exactly N on the last line
        last = nonempty[-1]
        last_is_tags = is_hashtag_line(last)
        if not last_is_tags:
            errors.append(f"description does not end with a hashtag line: the last line must hold only the {want_tags} hashtags")
            tags_in_last: list = []
        else:
            tags_in_last = last.split()
            if len(tags_in_last) != want_tags:
                errors.append(f"description ends with {len(tags_in_last)} hashtags, it must be exactly {want_tags}")
            if " ".join(tags_in_last) != last.strip() or "  " in last or "\t" in last:
                errors.append("the hashtags on the last line must be separated by single spaces")
            lowered = [t.lower() for t in tags_in_last]
            if len(set(lowered)) != len(lowered):
                errors.append("the last line repeats a hashtag")
            for req in required:
                if req.lower() not in lowered:
                    errors.append(f"required hashtag {req} is missing from the last line")
        body_lines = nonempty[:-1] if last_is_tags else nonempty
        if any(HASHTAG_ANY.search(ln) for ln in body_lines):
            errors.append("description has a hashtag outside its last line, hashtags go only on the last line")
        if LINK_RE.search(desc):
            errors.append("description contains a link, no links and no promotion")
        if PART_COUNT_RE.search(desc):
            errors.append('description states a part count ("of M"); never write it')
        # not a copy of an earlier description
        earlier = [norm_text(e) for e in (inp.get("earlier_descriptions") or []) if norm_text(e).strip()][-EARLIER_MAX:]
        mine = trigrams(desc)
        for i, prev in enumerate(earlier, 1):
            if norm_key(first_line(prev)) and norm_key(first) == norm_key(first_line(prev)):
                errors.append(f"description's first line matches the first line of earlier description {i}: it must be new for this video")
                break
        worst = (0.0, 0)
        for i, prev in enumerate(earlier, 1):
            if not mine:
                break
            share = len(mine & trigrams(prev)) / len(mine)
            if share > worst[0]:
                worst = (share, i)
        if worst[0] > OVERLAP_MAX:
            errors.append(f"description overlaps {round(worst[0] * 100)} percent with earlier description {worst[1]} "
                          f"(three-word runs shared with this description's own), the limit is {round(OVERLAP_MAX * 100)} percent: write it fresh")
        # serial: from Part 2 on, one line says Part 1 is on the channel
        if ser and int(ser["part"]) >= 2:
            if not any(re.search(r"\bpart\s+1\b", ln, re.I) and not ln.startswith("- ") for ln in lines):
                errors.append("description from Part 2 on needs one line (not a list item) saying that Part 1 is on the channel")

    # hashtags field of the answer
    if isinstance(tags_field, list) and tags_field and nonempty and is_hashtag_line(nonempty[-1]):
        if [str(t).lower() for t in tags_field] != [t.lower() for t in nonempty[-1].split()]:
            errors.append("the hashtags field does not match the hashtags on the description's last line")

    # PINNED COMMENT
    if st["pinned_comment"]:
        if not pinned:
            errors.append("pinned comment is empty")
        else:
            if len(pinned) > pmax:
                errors.append(f"pinned comment is {len(pinned)} characters, the limit is {pmax}")
            if LINK_RE.search(pinned):
                errors.append("pinned comment contains a link")
            plines = [ln.strip() for ln in pinned.split("\n") if ln.strip()]
            if "?" not in plines[0] and not re.search(r"\bor\b", plines[0], re.I):
                errors.append('pinned comment asks no question or choice (its first line needs a "?" or an "or" choice)')
            if ser:
                nxt = int(ser["part"]) + 1
                if ser.get("final"):
                    if any(has_next_part_line(ln, nxt) for ln in plines):
                        errors.append("pinned comment of the final part must not say a next part is coming")
                elif len(plines) < 2 or not any(has_next_part_line(ln, nxt) for ln in plines[1:]):
                    errors.append(f"pinned comment needs a second line saying the next part is coming (\"next part\" or \"Part {nxt}\")")

    # every text: no em dash, no slop word
    for name, text in (("title", title), ("description", desc), ("pinned comment", pinned)):
        if EM_DASH in text:
            errors.append(f"{name} contains an em dash, use a comma, colon, period or parentheses")
        hits = slop_hits(text, lex)
        if hits:
            errors.append(f"{name} contains slop words ({', '.join(repr(h) for h in hits[:4])}): write it plainly")
    return errors


# ------------------------------------------------------------------------------------------------ humanize

def tidy(text: str) -> str:
    """odd bullets become "- ", list indents go, trailing spaces go (before humanize.py: it reads a leading dash as an em dash)."""
    t = norm_text(text)
    t = BULLET_RE.sub("- ", t)
    t = INDENTED_LIST_RE.sub("", t)
    t = "\n".join(ln.rstrip() for ln in t.split("\n"))
    return t.strip("\n")


def humanize_field(hum, lex, text: str, one_line: bool = False):
    """(clean text, number of edits)."""
    t = tidy(text)
    if one_line:
        t = " ".join(t.split())
    cleaned, rep = hum.humanize(t, lex)
    n = sum(h["count"] for k in ("invisible", "typographic", "lexical") for h in rep[k])
    cleaned = cleaned.replace(EM_DASH, ", ").strip()
    return cleaned, n


# ------------------------------------------------------------------------------------------------ prompt data

def bullets(items, empty="(none)") -> str:
    items = [str(i) for i in items if str(i).strip()]
    return "\n".join(f"- {i}" for i in items) if items else empty


def build_data(inp: dict) -> dict:
    st = settings(inp)
    ser = serial_of(inp)
    brand = inp.get("brand") or {}
    earlier = [norm_text(e) for e in (inp.get("earlier_descriptions") or []) if norm_text(e).strip()][-EARLIER_MAX:]
    beats = "\n".join(f"{i}. [{b.get('label', '')}] {b.get('narration', '')}" for i, b in enumerate(inp.get("beats") or [], 1))
    facts = bullets(f"{f.get('claim', '')} ({f.get('url', '')})" if f.get("url") else f.get("claim", "") for f in inp.get("facts") or [])
    required = " ".join(st["required_hashtags"])
    want = int(st["hashtags"])
    data = {
        "run_id": inp.get("run_id", ""), "channel": inp.get("channel", ""),
        "summary": inp.get("summary", ""), "hook1": inp.get("hook1", ""),
        "script": "\n".join(str(x) for x in inp.get("script_lines") or []), "beats": beats, "facts": facts,
        "brand_name": brand.get("display_name", ""), "brand_handle": brand.get("handle", ""),
        "caption_max": st["caption_max"], "description_max": st["description_max"], "pinned_max": st["pinned_comment_max"],
        "hashtag_count": want, "required_hashtags": required or "(none)", "pinned_comment": st["pinned_comment"],
        "paragraph_max": PARAGRAPH_MAX, "overlap_percent": round(OVERLAP_MAX * 100),
        "earlier_count": len(earlier),
        "earlier_openers": bullets(first_line(e) for e in earlier),
        "earlier_descriptions": "\n\n".join(f"Earlier description {i}:\n{e}" for i, e in enumerate(earlier, 1)) or "(none yet: this is the channel's first video)",
        "serial": bool(ser), "story_title": "", "part": 0, "final": False, "universe": "", "earlier_titles": [],
        "title_suffix": "", "upload_steps": [],
    }
    free_extra = max(0, want - len(st["required_hashtags"]))
    data["hashtag_rule"] = (f"exactly {want} hashtags, all on the last line, separated by single spaces; {required or 'none'} must be among them"
                            f" and the other {free_extra} are specific to this video; no hashtag anywhere else")
    if ser:
        part, final = int(ser["part"]), bool(ser.get("final"))
        suffix = f"{ser['story_title']}, Part {part}"
        data.update(story_title=ser["story_title"], part=part, final=final, universe=ser.get("universe", ""),
                    earlier_titles=list(ser.get("earlier_titles") or []), title_suffix=suffix)
        data["upload_steps"] = upload_steps(ser)
        data["serial_block"] = (
            f"This video is Part {part} of the story \"{ser['story_title']}\""
            + (f" (universe: {ser['universe']})" if ser.get("universe") else "")
            + (". It is the final part of the story." if final else ". More parts follow it.")
            + "\nThe titles of the earlier parts:\n" + bullets(ser.get("earlier_titles") or [], "(none: this is Part 1)"))
        data["title_rule"] = (f"one line, at most {st['caption_max']} characters counting every character, no hashtags, no links. It must read exactly "
                              f"`<hook phrase> | {suffix}`: a new hook phrase for this part, written for a viewer who has not seen the video, that never "
                              f"spoils the cliffhanger, then \" | \" and exactly \"{suffix}\". Never write the number of parts (no \"of 5\"). "
                              f"The hook phrase plus the {len(suffix) + 3} characters of \" | {suffix}\" must fit in {st['caption_max']}, so the hook phrase is at most "
                              f"{max(10, int(st['caption_max']) - len(suffix) - 3)} characters.")
        data["part_rule"] = ("From Part 2 on, one line of the description (not a list item) says that Part 1 is on the channel, for example "
                             "\"Part 1 is on the channel if you missed how it started.\"" if part >= 2 else
                             "This is Part 1: no line about an earlier part.")
        data["part_rule"] += " The description never spoils how this part ends."
        if not st["pinned_comment"]:
            data["pinned_rule"] = "No pinned comment is wanted: answer with an empty string for pinned_comment."
        elif final:
            data["pinned_rule"] = (f"at most {st['pinned_comment_max']} characters, no links. One line only: a question or a choice (with a \"?\" or an \"or\") "
                                   "that invites replies. This is the final part, so no line says a next part is coming.")
        else:
            data["pinned_rule"] = (f"at most {st['pinned_comment_max']} characters in all, no links. Two lines: the first a question or a choice (with a \"?\" or an \"or\") "
                                   f"that invites replies; the second says the next part is coming (use the words \"next part\" or \"Part {part + 1}\").")
    else:
        data["serial_block"] = "This is a single video, not part of a series."
        data["title_rule"] = (f"one line, at most {st['caption_max']} characters counting every character, no hashtags, no links: the hook as a title, "
                              "written for a viewer who has not seen the video.")
        data["part_rule"] = "This is a single video: no line about parts or other videos."
        data["pinned_rule"] = (f"at most {st['pinned_comment_max']} characters, no links, a question or a choice (with a \"?\" or an \"or\") that invites replies."
                               if st["pinned_comment"] else "No pinned comment is wanted: answer with an empty string for pinned_comment.")
    return data


def upload_steps(ser: dict) -> list:
    steps = []
    part = int(ser["part"])
    if part >= 2:
        steps.append(f"set the related video to \"{ser['story_title']}, Part {part - 1}\"")
    steps.append(f"add this part to the playlist \"{ser['story_title']}\"")
    return steps


# ------------------------------------------------------------------------------------------------ commands

def read_answer(path: str) -> dict:
    ans = load_json(path)
    if not isinstance(ans, dict):
        raise InputError(f"the answer file {path} is missing or is not a JSON object")
    return ans


def cmd_data(args) -> int:
    try:
        inp = load_input(args.input)
    except InputError as exc:
        print(f"exporter data: {exc}", file=sys.stderr)
        return 2
    data = build_data(inp)
    save_json(args.out, data)
    out_json({"ok": True, "path": args.out, "serial": data["serial"], "part": data["part"], "final": data["final"],
              "earlier": data["earlier_count"], "caption_max": data["caption_max"]})
    return 0


def cmd_check(args) -> int:
    try:
        inp = load_input(args.input)
        answer = read_answer(args.answer)
    except InputError as exc:
        out_json({"ok": False, "errors": [str(exc)]})
        return 0
    _, lex = vendor(args.vendor)
    errors = check_answer(inp, answer, lex)
    out_json({"ok": not errors, "errors": errors})
    return 0


def last_line_tags(desc: str) -> list:
    lines = nonempty_lines(desc)
    return lines[-1].split() if lines and is_hashtag_line(lines[-1]) else []


def cmd_compose(args) -> int:
    try:
        inp = load_input(args.input)
        answer = read_answer(args.answer)
    except InputError as exc:
        out_json({"ok": False, "errors": [str(exc)], "written": False})
        return 0
    hum, lex = vendor(args.vendor)
    st = settings(inp)
    ser = serial_of(inp)
    changes = 0
    cleaned = dict(answer)
    for key, one_line in (("title", True), ("description", False), ("pinned_comment", False)):
        cleaned[key], n = humanize_field(hum, lex, answer.get(key) or "", one_line=one_line) if answer.get(key) else ("", 0)
        changes += n
    if not st["pinned_comment"]:
        cleaned["pinned_comment"] = ""
    errors = check_answer(inp, cleaned, lex)
    ok = not errors
    result = {"ok": ok, "errors": errors, "humanize_changes": changes, "forced": (not ok) and bool(args.force), "written": False,
              "title_chars": len(cleaned["title"]), "description_chars": len(cleaned["description"]),
              "hashtags": last_line_tags(cleaned["description"])}
    if ok or args.force:
        needs = [str(x) for x in (inp.get("needs_review") or []) if str(x).strip()]
        needs += [PREFIX + e for e in errors]
        manifest = {
            "written_by": "youtube-shorts exporter", "checked": datetime.date.today().isoformat(),
            "run_id": inp["run_id"], "channel": inp["channel"],
            "title": cleaned["title"], "description": cleaned["description"], "pinned_comment": cleaned["pinned_comment"],
            "hashtags": last_line_tags(cleaned["description"]),
            "story": ser["story_title"] if ser else None, "part": int(ser["part"]) if ser else None,
            "upload_steps": upload_steps(ser) if ser else [],
            "hooks": {"hook1": inp["hook1"]},
            "needs_review": needs,
            "facts": [{"claim": f.get("claim", ""), "url": f.get("url", ""), "checked": f.get("checked", "")} for f in inp.get("facts") or []],
            "files": {"reel": args.reel or ""},
            "checks": {"ok": ok, "errors": errors, "forced": result["forced"]},
            "humanize": {"changes": changes},
        }
        save_json(args.out, manifest)
        result["written"] = True
        result["path"] = args.out
    out_json(result)
    return 0


def cmd_record(args) -> int:
    inp = load_json(args.input)
    man = load_json(args.export)
    if not isinstance(inp, dict) or not isinstance(man, dict):
        print("exporter record: cannot read the input or the export manifest", file=sys.stderr)
        return 2
    run_id = inp.get("run_id") or man.get("run_id") or ""
    path = winpath(args.descriptions)
    seen = False
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    if json.loads(line).get("run_id") == run_id:
                        seen = True
                        break
                except ValueError:
                    continue
    except OSError:
        pass
    if not seen:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        entry = {"run_id": run_id, "title": man.get("title", ""), "description": man.get("description", ""),
                 "date": datetime.date.today().isoformat()}
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    out_json({"ok": True, "recorded": not seen, "run_id": run_id})
    return 0


def render_captions(manifest: dict, channel_id: str, n, run_id: str, editor_lines=None) -> str:
    """<id>-Ncaptions.txt in the youtube-shorts format of BUILD_SPEC.md section 8, from export.json."""
    m = manifest
    hooks = m.get("hooks") or {}
    blocks: list = []
    story = (m.get("story") or "").strip()
    if story:
        part = m.get("part")
        blocks.append(["STORY", f"{story}, Part {part}" if part else story])
    blocks.append(["TITLE", (m.get("title") or "").strip()])
    blocks.append(["DESCRIPTION", (m.get("description") or "").rstrip()])
    pinned = (m.get("pinned_comment") or "").strip()
    if pinned:
        blocks.append(["PINNED COMMENT", pinned])
    steps = [str(s) for s in (m.get("upload_steps") or []) if str(s).strip()]
    if story and steps:
        blocks.append(["UPLOAD STEPS"] + [f"- {s}" for s in steps])
    blocks.append(["HOOKS", f'{channel_id}-{n}.mp4 uses: "{hooks.get("hook1", "")}"'])
    needs = [str(x) for x in (m.get("needs_review") or []) if str(x).strip()]
    if needs:
        blocks.append(["NEEDS REVIEW"] + needs)
    facts = m.get("facts") or []
    if facts:
        blocks.append(["FACTS AND SOURCES"] + [f"- {f.get('claim', '')}: {f.get('url', '')} (checked {f.get('checked', '')})" for f in facts])
    blocks.append(["RUN", f"channels/{channel_id}/runs/{run_id}"])
    if editor_lines:
        blocks.append(["EDITOR"] + [str(x) for x in editor_lines])
    text = "\n\n".join("\n".join(b) for b in blocks) + "\n"
    return text.replace(EM_DASH, ", ")


def cmd_render(args) -> int:
    man = load_json(args.export)
    if not isinstance(man, dict):
        print("exporter render: cannot read the export manifest", file=sys.stderr)
        return 2
    editor = man.get("editor_lines") if args.editor_lines else None
    sys.stdout.write(render_captions(man, args.id, args.number, args.run_id, editor))
    return 0


def main(argv=None) -> int:
    setup_streams()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("data")
    sp.add_argument("--input", required=True)
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_data)
    sp = sub.add_parser("check")
    sp.add_argument("--input", required=True)
    sp.add_argument("--answer", required=True)
    sp.add_argument("--vendor", default="")
    sp.set_defaults(func=cmd_check)
    sp = sub.add_parser("compose")
    sp.add_argument("--input", required=True)
    sp.add_argument("--answer", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--vendor", default="")
    sp.add_argument("--reel", default="", help="absolute path to put in files.reel")
    sp.set_defaults(func=cmd_compose)
    sp = sub.add_parser("record")
    sp.add_argument("--input", required=True)
    sp.add_argument("--export", required=True)
    sp.add_argument("--descriptions", required=True)
    sp.set_defaults(func=cmd_record)
    sp = sub.add_parser("render")
    sp.add_argument("--export", required=True)
    sp.add_argument("--id", required=True)
    sp.add_argument("--number", required=True)
    sp.add_argument("--run-id", required=True)
    sp.add_argument("--editor-lines", action="store_true")
    sp.set_defaults(func=cmd_render)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, KeyError, ValueError) as exc:
        print(f"exporter {args.cmd}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
