#!/usr/bin/env python
"""caption.py: the caption and the export manifest (BUILD_SPEC.md section 5, S14, and section 8), for
pipeline/stages/14-export/run.sh.

The caption's first line is hook 1, word for word (the feed shows about 125 characters before "... more", and the
hook is what the reel opens with); the model writes the body and the one ask (the comment keyword), plus 3 to 5
hashtags and the search terms. This script gathers what the prompt needs, then composes and checks the result:

  caption.py data --run-dir RUN --out FILE
      the prompt's data as JSON: hook 1 and hook 2, the keyword and its deliverable, the solution and its rules,
      the script's display lines, the brief's one idea, the voice hints, the facts the script cites
  caption.py compose --run-dir RUN --data FILE --answer FILE --out export.json [--force] [--vendor DIR]
      the checks: the first line is hook 1 and 125 characters or fewer; exactly one ask, the keyword once, as
      "Comment KEYWORD"; no second ask (follow, like, share, save, link in bio, DM me); hashtags 3 to 5 (config
      caption.hashtags), one word each, no generic tag, none in the body; no link; the solution rules of S7 (no
      FlashFX mention unless the solution is flashfx, nothing implying the reel was made in FlashFX, no ad
      language); the body length (config caption.body_chars). humanize.py cleans the text (em dashes, slop words,
      invisible characters) and the vendor caption.py lints the whole caption (no FAIL allowed, the WARNs are
      recorded). When every check holds (or --force) it writes export.json and caption.txt and prints
      {"ok": true, ...}; otherwise {"ok": false, "errors": [...]} so the stage asks the model again once.

export.json (14-export/schema.json): caption, hashtags, keyword, deliverable, deliverable_status, link, solution
{type, name, url}, hooks {hook1, hook2}, needs_review (state.json's flags as "<stage>: <text>"), facts (the claims
the script cites: claim, url, checked), files {reel, hook2} (13-render's outputs), lint, humanize, checks.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from errors import undash  # noqa: E402
import solution as solution_lib  # noqa: E402
import paths  # noqa: E402
import config as reels_config  # noqa: E402

STAGE = "14-export"
REPO = os.path.dirname(os.path.dirname(HERE))
VENDOR_DEFAULT = os.path.join(REPO, "pipeline", "vendor", "ig-agent-skill")
HASHTAG_RE = re.compile(r"^#[A-Za-z0-9_]+$")
HEX_COLOR_RE = re.compile(r"(?:^|\s)#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})\b")   # #D97757 is a color the script quotes, not a tag
BODY_TAG_RE = re.compile(r"(?:^|\s)#(?!(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})\b)[A-Za-z0-9_]+")
URL_RE = re.compile(r"https?://\S+|\bwww\.\S+", re.I)
SECOND_ASKS = [
    (re.compile(r"\bfollow (me|us|for|along)\b", re.I), "follow"),
    (re.compile(r"\blike (this|it|and)\b", re.I), "like"),
    (re.compile(r"\bshare (this|it|with)\b", re.I), "share"),
    (re.compile(r"\bsave (this|it|for)\b", re.I), "save"),
    (re.compile(r"\blink in (my |the )?bio\b", re.I), "link in bio"),
    (re.compile(r"\b(dm|message) me\b", re.I), "DM me"),
    (re.compile(r"\bsubscribe\b", re.I), "subscribe"),
    (re.compile(r"\btell me (in|below|what|which)\b|\bwhat would you\b|\bwhich one\b|\blet me know\b", re.I), "answer a question"),
]


def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def clean(value, one_line: bool = True) -> str:
    s = "" if value is None else str(value)
    s = undash(s.replace("\r\n", "\n").replace("\r", "\n"))
    if one_line:
        s = " ".join(s.split())
    return s.strip()


def load_json(path: str, default=None):
    try:
        with open(winpath(path), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def read_text(path: str) -> str:
    try:
        with open(winpath(path), encoding="utf-8-sig", errors="replace") as f:
            return f.read().replace("\r\n", "\n").replace("\r", "\n")
    except OSError:
        return ""


def save_json(path: str, data) -> None:
    with open(winpath(path), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def save_text(path: str, content: str) -> None:
    with open(winpath(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, winpath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def out_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False))


# ------------------------------------------------------------------------------------------------ the data

def section(md: str, heading: str) -> str:
    m = re.search(r"(?ms)^##\s+" + re.escape(heading) + r"\s*$\n(.*?)(?=^##\s|\Z)", md)
    return m.group(1).strip() if m else ""


def voice_hints(voice_md: str) -> str:
    """The filled lines of voice.md's 'What I sound like' and 'The ask' sections (no [FILL IN])."""
    out = []
    for head in ("What I sound like", "The ask", "How I promote"):
        for line in section(voice_md, head).split("\n"):
            s = line.strip()
            if s.startswith(("-", "*")) and "[FILL IN" not in s and len(s) > 4:
                out.append(clean(s))
    return "\n".join(out[:12]) or "(voice.md is still a draft: plain spoken English, short sentences, no hype, one emoji at most)"


def cited_facts(script: dict, research: dict, expansion: dict) -> list[dict]:
    """The claims the script's beats cite (facts.md#n), in claim order; the expansion's evidence when the script cites none."""
    claims = {int(c["n"]): c for c in research.get("claims", []) if isinstance(c, dict) and "n" in c}
    refs: list[int] = []
    for b in script.get("beats", []):
        for f in b.get("facts", []) or []:
            m = re.search(r"(\d+)", str(f))
            if m:
                refs.append(int(m.group(1)))
    if not refs:
        refs = [int(x) for x in expansion.get("evidence_refs", []) if str(x).isdigit()]
    out = []
    for n in sorted(set(refs)):
        c = claims.get(n)
        if c and c.get("url"):
            out.append({"n": n, "claim": clean(c.get("claim")), "url": clean(c.get("url")), "checked": clean(c.get("checked")) or clean(research.get("checked"))})
    core = research.get("core_claim") or {}
    if not out and core.get("text"):
        first = next((c for c in research.get("claims", []) if c.get("status") == "verified"), None)
        if first:
            out.append({"n": first["n"], "claim": clean(first.get("claim")), "url": clean(first.get("url")), "checked": clean(first.get("checked"))})
    return out


def gather(run_dir: str, config: dict) -> dict:
    run_dir = winpath(run_dir)
    script = load_json(os.path.join(run_dir, "07-script", "script.json"), {}) or {}
    judge = load_json(os.path.join(run_dir, "06-judge", "judge.json"), {}) or {}
    expansion = load_json(os.path.join(run_dir, "02-expansion", "expansion.json"), {}) or {}
    research = load_json(os.path.join(run_dir, "01-research", "research.json"), {}) or {}
    state = load_json(os.path.join(run_dir, "state.json"), {}) or {}
    sol = solution_lib.read_solution(run_dir)
    brief = read_text(os.path.join(run_dir, "05-hooks", "brief.md"))
    hook1 = clean((script.get("hook") or {}).get("spoken")) or clean((judge.get("winner") or {}).get("spoken"))
    hook2 = clean((judge.get("runner_up") or {}).get("spoken")) or clean((script.get("hook2") or {}).get("display")) or clean((script.get("hook2") or {}).get("spoken"))
    ask = script.get("ask") or {}
    keyword = clean(ask.get("keyword")) or clean(expansion.get("keyword")) or clean((sol or {}).get("keyword"))
    keyword = keyword.strip("#").upper()
    deliverable = clean(ask.get("deliverable")) or clean(expansion.get("deliverable"))
    status = clean(ask.get("deliverable_status")) or clean(expansion.get("deliverable_status")) or "new"
    link = clean(ask.get("deliverable_link")) or clean(expansion.get("deliverable_link"))
    if sol and keyword in solution_lib.KEYWORD_FOR.values() and not link:
        link = clean(sol.get("url"))   # FLASH and LINK deliver the solution's own link
    beats = []
    for b in script.get("beats", []):
        beats.append(f"- {b.get('id')} [{b.get('type')}]: {clean(b.get('display'))}")
    stype = (sol or {}).get("type", "none")
    if stype == "flashfx":
        rules = ("The solution of this reel is FlashFX: name it as the tool that solves the problem, the way any tool would be named, no pitch, no "
                 "hype, no superlative, no sign-up language. Never say or imply that this reel itself was made, edited or animated in FlashFX.")
    elif stype in ("external", "method"):
        rules = (f"The solution of this reel is {solution_lib.line_text(sol)}. FlashFX is not mentioned anywhere in the caption, not the name, "
                 "not the editor; no other product is pitched either.")
    else:
        rules = "No solution decision exists for this run: the reel counts as not FlashFX, so FlashFX is not mentioned anywhere."
    cap_cfg = config.get("caption") or {}
    tags = cap_cfg.get("hashtags") or [3, 5]
    body = cap_cfg.get("body_chars") or [150, 900]
    one_idea = section(brief, "The one idea") or section(brief, "The promise and the payoff")
    flags = state.get("flags") or []
    return {
        "idea": clean((state.get("idea") or {}).get("text")) or clean(research.get("idea")) or clean(script.get("idea_text")),
        "hook1": hook1, "hook2": hook2, "keyword": keyword, "deliverable": deliverable, "deliverable_status": status, "link": link,
        "problem": clean(expansion.get("problem")), "identity": clean(expansion.get("share_identity")),
        "solution": {"type": stype, "name": clean((sol or {}).get("name")), "url": clean((sol or {}).get("url"))},
        "solution_line": solution_lib.line_text(sol), "solution_rules": rules,
        "beats": "\n".join(beats) or "(no script beats found)", "one_idea": clean(one_idea[:1500], one_line=False) or "(no brief)",
        "voice": voice_hints(read_text(os.path.join(paths.cfg_path(reels_config.load(), "paths.profile"), "voice.md"))),
        "hashtag_min": int(tags[0]), "hashtag_max": int(tags[1]), "body_min": int(body[0]), "body_max": int(body[1]),
        "first_line_max": int(cap_cfg.get("first_line_max_chars", 125)),
        "needs_review": [f"{f.get('stage', '?')}: {clean(f.get('text'))}" for f in flags if isinstance(f, dict) and clean(f.get("text"))],
        "facts": cited_facts(script, research, expansion),
        "files": {"reel": "../13-render/final.mp4", "hook2": "../13-render/hook2.mp4"},
    }


def cmd_data(args) -> int:
    config = load_json(args.config, {}) if args.config else {}
    data = gather(args.run_dir, config or {})
    save_json(args.out, data)
    out_json({"ok": True, "hook1": data["hook1"], "keyword": data["keyword"], "solution": data["solution"]["type"], "facts": len(data["facts"]),
              "needs_review": len(data["needs_review"])})
    return 0


# ------------------------------------------------------------------------------------------------ compose and check

def n_changes(report) -> int:
    """How many edits humanize.py made (its report: invisible, typographic and lexical lists; structures are only noted)."""
    if not isinstance(report, dict):
        return 0
    return sum(len(v) for k, v in report.items() if k != "structures" and isinstance(v, list))


def normalize_tags(raw, keyword: str) -> tuple[list[str], list[str]]:
    tags, notes = [], []
    for t in raw if isinstance(raw, list) else []:
        s = clean(t).replace(" ", "")
        if not s:
            continue
        if not s.startswith("#"):
            s = "#" + s
        if not HASHTAG_RE.match(s):
            notes.append(f"dropped the hashtag {s!r} (letters, digits and underscores only)")
            continue
        if s.lower() in (x.lower() for x in tags):
            continue
        if keyword and s[1:].upper() == keyword:
            notes.append(f"dropped {s}: a hashtag must not repeat the comment keyword")
            continue
        tags.append(s)
    return tags, notes


def cmd_compose(args) -> int:
    data = load_json(args.data, {}) or {}
    answer = load_json(args.answer, {})
    if not data or not isinstance(answer, dict):
        print("compose: cannot read the data or the answer", file=sys.stderr)
        return 2
    vendor_dir = args.vendor or VENDOR_DEFAULT
    cap = load_module("vendor_caption", os.path.join(vendor_dir, "caption.py"))
    hum = load_module("vendor_humanize", os.path.join(vendor_dir, "humanize.py"))
    lex = hum.load_lexicon(os.path.join(vendor_dir, "slop.json"))
    errors: list[str] = []
    notes: list[str] = []
    keyword = data.get("keyword", "")
    first_max = int(data.get("first_line_max", 125))
    # the first line: hook 1, word for word, inside the feed's window
    first = clean(data.get("hook1"))
    if not first:
        errors.append("hook 1 is empty: script.json has no hook")
    if len(first) > first_max:
        cut = first[:first_max - 3].rsplit(" ", 1)[0].rstrip(",;:") + "..."
        notes.append(f"hook 1 runs {len(first)} characters: cut to {len(cut)} for the first line")
        first = cut
    # the body and the ask, cleaned by humanize.py (em dashes, slop words, invisible characters)
    body_raw = clean(answer.get("body"), one_line=False)
    ask_raw = clean(answer.get("ask_line"))
    body_h, rep_body = hum.humanize(body_raw, lex)
    ask_h, rep_ask = hum.humanize(ask_raw, lex)
    first_h, rep_first = hum.humanize(first, lex)
    body = "\n".join(l.rstrip() for l in body_h.strip().split("\n"))
    body = re.sub(r"\n{3,}", "\n\n", body)
    ask_line = " ".join(ask_h.split())
    first = " ".join(first_h.split())
    changed = sum(n_changes(r) for r in (rep_body, rep_ask, rep_first))
    body_min, body_max = int(data.get("body_min", 150)), int(data.get("body_max", 900))
    if len(body) < body_min:
        errors.append(f"the body is {len(body)} characters; write at least {body_min} (2 to 5 short lines that say what the reel shows and why it matters)")
    if len(body) > body_max:
        errors.append(f"the body is {len(body)} characters; keep it under {body_max}")
    if BODY_TAG_RE.search(body):
        errors.append(f"a hashtag sits inside the body ({BODY_TAG_RE.search(body).group(0).strip()}): hashtags go in the hashtags list only")
    if URL_RE.search(body) or URL_RE.search(ask_line):
        errors.append("a link sits in the caption: captions are not clickable; the keyword's DM carries the link")
    if not ask_line:
        errors.append("ask_line is empty")
    elif not re.search(r"\bcomment\b", ask_line, re.I) or not re.search(r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])", ask_line):
        errors.append(f"the ask line must ask for a comment with the keyword, as 'Comment {keyword} ...', got: {ask_line[:100]!r}")
    kw_count = len(re.findall(r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])", body + "\n" + ask_line)) if keyword else 0
    if keyword and kw_count != 1:
        errors.append(f"the keyword {keyword} must appear exactly once, in the ask line (found {kw_count} times)")
    for rx, label in SECOND_ASKS:
        for where, t in (("body", body), ("ask line", ask_line)):
            if rx.search(t):
                errors.append(f"a second ask in the {where}: '{rx.search(t).group(0)}' ({label}); the only ask is the comment keyword")
    if re.search(r"\bin this (reel|video)\b|^(hey|hi|hello)\b", body, re.I):
        errors.append("no greeting and no 'in this reel': start the body with the point")
    tags, tag_notes = normalize_tags(answer.get("hashtags"), keyword)
    notes += tag_notes
    tag_min, tag_max = int(data.get("hashtag_min", 3)), int(data.get("hashtag_max", 5))
    if len(tags) > tag_max:
        notes.append(f"{len(tags)} hashtags given, kept the first {tag_max}")
        tags = tags[:tag_max]
    if len(tags) < tag_min:
        errors.append(f"only {len(tags)} usable hashtags; give {tag_min} to {tag_max}, one word each, specific to the topic")
    filler = [t for t in tags if t.lower() in cap.FILLER_TAGS]
    if filler:
        errors.append("generic hashtags: " + ", ".join(filler) + "; use tags that name the tool, the practice or the audience")
    caption = first + "\n\n" + body + ("\n\n" + ask_line if ask_line else "")
    caption = undash(caption).replace(chr(0x2014), ", ")
    # the solution rules (S7 and S14): FlashFX only when it is the solution, never "made in FlashFX", no ad language
    sol = data.get("solution") or {"type": "none"}
    sol_res = solution_lib.check_texts(sol, {"caption": caption, "hashtags": " ".join(tags)})
    for p in sol_res["problems"]:
        errors.append(p["message"])
    # the vendor lint on the whole caption (hashtags last, below the fold)
    full = caption + ("\n\n" + " ".join(tags) if tags else "")
    search_terms = [clean(t) for t in (answer.get("search_terms") or []) if clean(t)][:6]
    lint = cap.analyse(full, cut=first_max, keywords=search_terms)
    fails = [c for c in lint["checks"] if c["status"] == "FAIL"]
    warns = [c for c in lint["checks"] if c["status"] == "WARN"]
    hex_colors = len(HEX_COLOR_RE.findall(caption))
    for c in fails:
        if c["check"] == "HASHTAGS" and hex_colors and len(tags) <= tag_max:
            notes.append(f"caption.py counts {hex_colors} hex color(s) of the script as hashtags; the real tags are {len(tags)}")
            continue
        errors.append(f"caption.py {c['check']}: {c['detail']}")
    if len(lint.get("asks") or []) != 1:
        errors.append(f"caption.py counts {len(lint.get('asks') or [])} asks ({', '.join(lint.get('asks') or []) or 'none'}); the caption needs exactly one: the comment keyword")
    if lint.get("first_line_chars", 0) > first_max:
        errors.append(f"the first line runs {lint['first_line_chars']} characters, over the {first_max} the feed shows")
    ok = not errors
    result = {"ok": ok, "errors": errors, "notes": notes, "caption_chars": len(caption), "first_line_chars": len(first), "body_chars": len(body),
              "hashtags": tags, "lint_verdict": lint.get("verdict"), "lint_warnings": [f"{c['check']}: {c['detail']}" for c in warns],
              "humanize_changes": changed, "forced": (not ok) and args.force}
    if ok or args.force:
        manifest = {
            "written_by": STAGE, "checked": __import__("time").strftime("%Y-%m-%d"),
            "caption": caption, "hashtags": tags, "search_terms": search_terms,
            "keyword": keyword, "deliverable": data.get("deliverable", ""), "deliverable_status": data.get("deliverable_status", "new"),
            "link": data.get("link", ""), "solution": sol, "hooks": {"hook1": data.get("hook1", ""), "hook2": data.get("hook2", "")},
            "needs_review": list(data.get("needs_review") or []), "facts": [{k: f[k] for k in ("claim", "url", "checked")} for f in data.get("facts") or []],
            "files": data.get("files") or {"reel": "../13-render/final.mp4", "hook2": "../13-render/hook2.mp4"},
            "lint": {"verdict": lint.get("verdict"), "characters": lint.get("characters"), "asks": lint.get("asks"), "checks": lint.get("checks"),
                     "visible": lint.get("visible")},
            "humanize": {"changes": changed, "body": rep_body, "ask_line": rep_ask, "first_line": rep_first},
            "checks": {"ok": ok, "errors": errors, "notes": notes, "forced": (not ok) and args.force, "model_notes": clean(answer.get("notes"))},
        }
        save_json(args.out, manifest)
        save_text(os.path.join(os.path.dirname(winpath(args.out)), "caption.txt"), full + "\n")
        result["path"] = args.out
    out_json(result)
    return 0


def main(argv=None) -> int:
    setup_streams()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("data"); sp.add_argument("--run-dir", required=True); sp.add_argument("--out", required=True)
    sp.add_argument("--config", default=""); sp.set_defaults(func=cmd_data)
    sp = sub.add_parser("compose"); sp.add_argument("--run-dir", required=True); sp.add_argument("--data", required=True)
    sp.add_argument("--answer", required=True); sp.add_argument("--out", required=True); sp.add_argument("--force", action="store_true")
    sp.add_argument("--vendor", default=""); sp.set_defaults(func=cmd_compose)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"caption.py: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
