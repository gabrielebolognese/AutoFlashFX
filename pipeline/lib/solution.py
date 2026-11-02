#!/usr/bin/env python
"""solution.py: the problem-first solution of a reel (BUILD_SPEC.md section 0, S2, S3, S4, S7, S14, section 8),
shared by the stages (M12).

Every reel solves one problem with the best available solution: FlashFX, an external tool or repo, or a method
with no product. S2 decides it (with S4 deciding again after a failed honesty check) and writes
02-expansion/solution.json {type, name, url, reason, keyword, written_by, round, checked}; the later stages read
it through this module. A run without the file counts as "none" (not FlashFX; the history line shows "-").

  python pipeline/lib/solution.py type --run-dir RUN              flashfx | external | method | - (for history.txt)
  python pipeline/lib/solution.py block --run-dir RUN             the SOLUTION block's line (spec section 8)
  python pipeline/lib/solution.py balance --history FILE [--last N]   the recent exported reels' solution types
  python pipeline/lib/solution.py proof --voice FILE              the usable lines of voice.md "Proof I can use"
  python pipeline/lib/solution.py prompt --run-dir RUN --voice FILE --account FILE --history FILE [--deliverables FILE]
                                                                  the prompt section S2 and S4 get (the rules, the
                                                                  candidates, the proof, the balance)
  python pipeline/lib/solution.py check --solution FILE --texts FILE    the FlashFX rules on a JSON object of texts
                                                                  ({where: text}); prints {ok, problems}

Rules (BUILD_SPEC.md S2, S3, S7, S14):
  - the keyword follows the solution: FLASH for flashfx, LINK for an external tool or repo (the deliverable is its
    link), otherwise the deliverable that fits (deliverables.txt, or a concretely described new one)
  - FlashFX only when it genuinely solves the problem and every FlashFX claim is in voice.md "Proof I can use"
  - when the solution is not FlashFX, the script and the caption never mention FlashFX; when it is, no ad language,
    and nothing implying the reel itself was made in FlashFX (reels are rendered with HyperFrames)

Every text is cleaned of em dashes (errors.undash).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errors import undash  # noqa: E402

SOLUTION_TYPES = ("flashfx", "external", "method")
KEYWORD_FOR = {"flashfx": "FLASH", "external": "LINK"}
FLASHFX_NAME = "FlashFX"
FLASHFX_URL = "https://flashfx.app"
PLACEHOLDER = "[FILL IN"
FLASHFX_RE = re.compile(r"\bflash\s*-?\s*f\s*\.?\s*x\b|\bflashfx\b", re.I)
MADE_IN_RE = re.compile(
    r"\b(made|built|animated|edited|rendered|created|produced|designed|cut|assembled|put together|was done|is done)\b"
    r"[^.?!\n]{0,70}?\b(in|with|using|inside|on)\s+(flash\s*-?\s*f\s*x|flashfx)\b", re.I)
AD_PHRASES = [
    (re.compile(r"\bsign\s*up\b", re.I), "sign up"),
    (re.compile(r"\bbuy (it )?now\b", re.I), "buy now"),
    (re.compile(r"\blimited[- ]time\b", re.I), "limited time"),
    (re.compile(r"\bdiscount\b|\bpromo code\b|\bcoupon\b", re.I), "a discount or a code"),
    (re.compile(r"\bget yours\b|\bget it today\b|\bstart your free trial\b|\bfree trial\b", re.I), "a trial or purchase push"),
    (re.compile(r"\bgame[- ]chang(er|ing)\b", re.I), "game-changer"),
    (re.compile(r"\bthe (best|only|ultimate|number one|#1) (tool|editor|app|software|way)\b", re.I), "a superlative about the tool"),
    (re.compile(r"\byou need (to try|this tool|this app|this editor)\b", re.I), "you need to try"),
    (re.compile(r"\btrust me\b", re.I), "trust me"),
    (re.compile(r"\blink in (my )?bio\b", re.I), "link in bio"),
    (re.compile(r"\bgo (download|get|grab) it\b", re.I), "go get it"),
]
DEFAULT_RULES = (
    "Problem-first reels (BUILD_SPEC.md section 0): the reel solves one real problem of the viewer with the best "
    "solution available, chosen per reel. The choice: if the idea names the solution, use it; FlashFX only when it "
    "genuinely solves the problem and every FlashFX claim the reel would make is in voice.md \"Proof I can use\"; "
    "otherwise the best solution in facts.md, an external tool or repo (name and URL from facts.md) or a method with "
    "no product. Never force FlashFX into a problem it does not solve. The keyword follows the solution: FLASH for "
    "FlashFX, LINK for an external tool or repo (the deliverable is its link), otherwise the deliverable that fits."
)


def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def text(value, one_line: bool = True) -> str:
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


# ------------------------------------------------------------------------------------------------ the decision

def read_solution(run_dir: str) -> dict | None:
    """02-expansion/solution.json as written by S2 or S4, or None (an older run, or S2 has not run yet)."""
    sol = load_json(os.path.join(winpath(run_dir), "02-expansion", "solution.json"))
    if not isinstance(sol, dict) or str(sol.get("type", "")).lower() not in SOLUTION_TYPES:
        return None
    sol["type"] = str(sol["type"]).lower()
    return sol


def solution_type(run_dir: str) -> str:
    """The solution type for the history line: flashfx, external, method, or "-" before S2 decided."""
    sol = read_solution(run_dir)
    return sol["type"] if sol else "-"


def block_text(sol: dict | None) -> str:
    """The SOLUTION block's line of Ncaptions.txt (spec section 8): flashfx | external: name link | method."""
    if not sol:
        return "- (no solution decision: the run ended before S2 chose one, or it predates the solution choice)"
    stype = sol.get("type", "")
    name = text(sol.get("name"))
    url = text(sol.get("url"))
    if stype == "flashfx":
        return "flashfx"
    if stype == "external":
        return f"external: {name or '(unnamed tool)'}" + (f" {url}" if url else "")
    return "method" + (f": {name}" if name else "")


def line_text(sol: dict | None) -> str:
    """One readable line for prompts and logs: 'external (frontend-design, https://...)'."""
    if not sol:
        return "none (no solution decision was written)"
    name = text(sol.get("name"))
    url = text(sol.get("url"))
    inner = ", ".join(x for x in (name, url) if x)
    return sol.get("type", "none") + (f" ({inner})" if inner else "")


def facts_hosts(research: dict | None) -> set[str]:
    hosts = set()
    if not isinstance(research, dict):
        return hosts
    urls = [c.get("url", "") for c in research.get("claims", []) if isinstance(c, dict)]
    urls += [a.get("url", "") for a in research.get("assets", []) if isinstance(a, dict)]
    urls += [c.get("url", "") for c in research.get("solution_candidates", []) if isinstance(c, dict)]
    urls += [n.get("url", "") for n in (research.get("numbers") or {}).values() if isinstance(n, dict)]
    for u in urls:
        m = re.match(r"^https?://([^/\s]+)", str(u or ""), re.I)
        if m:
            hosts.add(m.group(1).lower().removeprefix("www."))
    return hosts


def url_host(url: str) -> str:
    m = re.match(r"^https?://([^/\s]+)", url or "", re.I)
    return m.group(1).lower().removeprefix("www.") if m else ""


def normalize_decision(raw: dict | None, research: dict | None, deliverables: list[dict], keyword: str) -> tuple[dict, list[str], list[str]]:
    """The model's solution_decision checked against the rules.

    Returns (solution, errors, notes). solution: {type, name, url, reason, keyword, deliverable, deliverable_link,
    deliverable_status} with the keyword rule applied (FLASH, LINK, or the given keyword for a method). errors ask
    the model again; notes record what the code corrected."""
    raw = raw if isinstance(raw, dict) else {}
    errors: list[str] = []
    notes: list[str] = []
    stype = text(raw.get("type")).lower()
    name = text(raw.get("name"))
    url = text(raw.get("url"))
    reason = text(raw.get("reason"))
    known = {d["keyword"]: d for d in deliverables}
    if stype not in SOLUTION_TYPES:
        errors.append(f"solution_decision.type must be flashfx, external or method, got {raw.get('type')!r}")
        stype = "method"
    if not reason:
        errors.append("solution_decision.reason is empty: say in one or two sentences why this solution is the best one for the viewer's problem")
    if stype == "flashfx":
        name = FLASHFX_NAME
        if not re.match(r"^https?://", url, re.I):
            url = known.get("FLASH", {}).get("link") or FLASHFX_URL
    elif stype == "external":
        if not name:
            errors.append("solution_decision.name is empty: name the external tool or repo (as facts.md names it)")
        if not re.match(r"^https?://\S+$", url, re.I):
            errors.append(f"solution_decision.url must be the tool's URL from facts.md, got {url!r}")
        else:
            hosts = facts_hosts(research)
            if hosts and url_host(url) not in hosts:
                errors.append(f"solution_decision.url ({url}) is not a source of facts.md: use the URL of a claim about the tool (the repo, the docs or the product page)")
        if FLASHFX_RE.search(name):
            errors.append("an external solution cannot be FlashFX: choose type flashfx for it")
    else:
        if not name:
            errors.append("solution_decision.name is empty: give the method a short name (what the viewer does)")
        if url and not re.match(r"^https?://\S+$", url, re.I):
            url = ""
    forced = KEYWORD_FOR.get(stype)
    kw = text(keyword).strip("#").upper()
    if forced and kw != forced:
        notes.append(f"the comment keyword follows the solution: {forced} for a {stype} solution (the model wrote {kw or 'none'})")
        kw = forced
    sol = {"type": stype, "name": name, "url": url, "reason": reason, "keyword": kw}
    if stype == "flashfx":
        entry = known.get("FLASH")
        sol.update({"deliverable": (entry or {}).get("what") or f"access to {FLASHFX_NAME}, the editor shown in the reel",
                    "deliverable_link": (entry or {}).get("link") or url, "deliverable_status": "existing"})
    elif stype == "external":
        entry = known.get("LINK")
        sol.update({"deliverable": f"the link to {name or 'the tool'}" + (f" ({(entry or {}).get('what')})" if entry and entry.get("what") else ""),
                    "deliverable_link": url, "deliverable_status": "existing" if re.match(r"^https?://", url, re.I) else "new"})
    return sol, errors, notes


# ------------------------------------------------------------------------------------------------ the profile and the history

def section(md: str, heading: str) -> str:
    """The text of a '## heading' section of a markdown file (until the next '## '), or ""."""
    m = re.search(r"(?ms)^##\s+" + re.escape(heading) + r"\s*$\n(.*?)(?=^##\s|\Z)", md)
    return m.group(1).strip() if m else ""


def proof_lines(voice_md: str) -> list[str]:
    """The usable bullet lines of voice.md 'Proof I can use' (no [FILL IN] placeholders, no empty lines)."""
    body = section(voice_md, "Proof I can use")
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if not s or PLACEHOLDER in s:
            continue
        if s.startswith(("-", "*")):
            s = s.lstrip("-* ").strip()
            if s and PLACEHOLDER not in s:
                out.append(text(s))
    return out


def strategy_text(account_md: str) -> str:
    """account.md's 'Content strategy' section (the problem-first rules and the balance target), or ""."""
    body = section(account_md, "Content strategy")
    if not body or PLACEHOLDER in body and len([l for l in body.split("\n") if l.strip() and PLACEHOLDER not in l]) == 0:
        return ""
    return undash(body)


def history_balance(history_path: str, last_n: int = 10) -> dict:
    """The solution types of the last exported reels in logs/history.txt (date | idea | solution | exported N)."""
    lines = [l for l in read_text(history_path).split("\n") if l.strip()]
    last: list[str] = []
    for line in reversed(lines):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4 and parts[-1].startswith("exported"):
            stype = parts[-2].lower()
            last.append(stype if stype in SOLUTION_TYPES else "-")
            if len(last) >= last_n:
                break
    counts = {t: last.count(t) for t in SOLUTION_TYPES}
    if not last:
        txt = "no reel has been exported yet (no balance to keep)"
    else:
        txt = (f"the last {len(last)} exported reels: " + ", ".join(f"{counts[t]} {t}" for t in SOLUTION_TYPES)
               + (f", {last.count('-')} before the solution choice existed" if "-" in last else "")
               + "; newest first: " + ", ".join(last))
    return {"last": last, "counts": counts, "text": txt}


def candidates_text(research: dict | None) -> str:
    cands = (research or {}).get("solution_candidates") if isinstance(research, dict) else None
    if not cands:
        return "(the research listed no solution candidates: choose from the claims of facts.md, naming the tool or the method they describe)"
    lines = []
    for c in cands:
        if not isinstance(c, dict):
            continue
        lines.append(f"- {text(c.get('type')) or 'external'}: {text(c.get('name'))}" + (f" ({text(c.get('url'))})" if text(c.get("url")) else "")
                     + (f": {text(c.get('why'))}" if text(c.get("why")) else ""))
    return "\n".join(lines) or "(none)"


def prompt_section(run_dir: str, voice_path: str, account_path: str, history_path: str, deliverables: list[dict] | None = None) -> str:
    """The solution section of the expansion and angle prompts: the rules, the candidates, the proof, the balance."""
    research = load_json(os.path.join(winpath(run_dir), "01-research", "research.json")) or {}
    strategy = strategy_text(read_text(account_path)) if account_path else ""
    proof = proof_lines(read_text(voice_path)) if voice_path else []
    balance = history_balance(history_path) if history_path else {"text": "unknown"}
    known = {d["keyword"]: d for d in (deliverables or [])}
    lines = ["The rules:"]
    if strategy:
        lines += ["From library/profile/account.md, Content strategy:", strategy, "", "And in every case: " + DEFAULT_RULES]
    else:
        lines += [DEFAULT_RULES, "(account.md has no Content strategy section yet: these rules apply with no balance target.)"]
    lines += ["", "Solution candidates the research found (01-research/research.json):", candidates_text(research), ""]
    if proof:
        lines += ["voice.md \"Proof I can use\" (the only FlashFX claims a reel may make):"] + [f"- {p}" for p in proof]
    else:
        lines += ["voice.md \"Proof I can use\" is empty: no FlashFX claim can be backed today, so FlashFX can be the solution only if the reel makes no claim about it beyond what facts.md verifies (the gate's honesty check fails it otherwise)."]
    lines += ["", "Recent balance (logs/history.txt): " + balance["text"], "",
              "The keyword rule: flashfx -> FLASH" + (f" ({known['FLASH']['what']})" if "FLASH" in known else "")
              + "; external -> LINK (the deliverable is the tool's link)" + (f" ({known['LINK']['what']})" if "LINK" in known else "")
              + "; method -> the deliverable that fits (an existing keyword, or a NEW one described concretely). The runner enforces FLASH and LINK whatever keyword you write."]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ the text rules

def find_flashfx(texts: dict) -> list[str]:
    """Every text that names FlashFX: ['b3 display: ...snippet...']."""
    out = []
    for where, t in texts.items():
        for m in FLASHFX_RE.finditer(str(t or "")):
            s = max(0, m.start() - 30)
            out.append(f"{where}: ...{str(t)[s:m.end() + 30].strip()}...")
            break
    return out


def find_made_in(texts: dict) -> list[str]:
    out = []
    for where, t in texts.items():
        m = MADE_IN_RE.search(str(t or ""))
        if m:
            out.append(f"{where}: '{m.group(0)}'")
    return out


def find_ad_language(texts: dict) -> list[str]:
    out = []
    for where, t in texts.items():
        for rx, label in AD_PHRASES:
            m = rx.search(str(t or ""))
            if m:
                out.append(f"{where}: '{m.group(0)}' ({label})")
    return out


def check_texts(sol: dict | None, texts: dict) -> dict:
    """The solution rules on a set of texts: no FlashFX mention unless the solution is flashfx; never 'made in
    FlashFX'; no ad language (a short scripted list; the checks model judges the rest in S7)."""
    stype = (sol or {}).get("type", "none")
    problems: list[dict] = []
    if stype != "flashfx":
        for hit in find_flashfx(texts):
            problems.append({"kind": "flashfx_mention", "text": hit,
                             "message": f"FlashFX is named although the reel's solution is {stype}: {hit}. Remove the mention (the solution rules of BUILD_SPEC.md S7)"})
    for hit in find_made_in(texts):
        problems.append({"kind": "made_in_flashfx", "text": hit,
                         "message": f"this implies the reel itself was made in FlashFX (reels are rendered with HyperFrames): {hit}. Say what the viewer does with the tool, never what made this video"})
    for hit in find_ad_language(texts):
        problems.append({"kind": "ad_language", "text": hit,
                         "message": f"ad language: {hit}. Show the solution solving the problem, the way any tool would be shown: no pitch, no hype"})
    return {"ok": not problems, "problems": problems, "solution_type": stype}


# ------------------------------------------------------------------------------------------------ CLI

def read_deliverables(path: str) -> list[dict]:
    from expansion import read_deliverables as _rd  # noqa: WPS433 (the same parser as S2)
    return _rd(path) if path else []


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("type"); sp.add_argument("--run-dir", required=True)
    sp = sub.add_parser("block"); sp.add_argument("--run-dir", required=True)
    sp = sub.add_parser("balance"); sp.add_argument("--history", required=True); sp.add_argument("--last", type=int, default=10)
    sp = sub.add_parser("proof"); sp.add_argument("--voice", required=True)
    sp = sub.add_parser("prompt"); sp.add_argument("--run-dir", required=True); sp.add_argument("--voice", default="")
    sp.add_argument("--account", default=""); sp.add_argument("--history", default=""); sp.add_argument("--deliverables", default="")
    sp = sub.add_parser("check"); sp.add_argument("--solution", required=True); sp.add_argument("--texts", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "type":
        print(solution_type(args.run_dir))
    elif args.cmd == "block":
        print(block_text(read_solution(args.run_dir)))
    elif args.cmd == "balance":
        print(json.dumps(history_balance(args.history, args.last), ensure_ascii=False))
    elif args.cmd == "proof":
        for p in proof_lines(read_text(args.voice)):
            print(p)
    elif args.cmd == "prompt":
        print(prompt_section(args.run_dir, args.voice, args.account, args.history, read_deliverables(args.deliverables)))
    elif args.cmd == "check":
        sol = load_json(args.solution)
        texts = load_json(args.texts) or {}
        print(json.dumps(check_texts(sol if isinstance(sol, dict) else None, texts), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
