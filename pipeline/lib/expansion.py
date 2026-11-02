#!/usr/bin/env python
"""expansion.py: the expansion files (BUILD_SPEC.md section 5, S2 and S4), composed from the model's structured output.

The model (session A, with the research in context) answers with the five parts of spec S2 as fields; this
script checks them against the rules and composes 02-expansion/expansion.md in one fixed layout, so the gate
always reads the same shape and the length is measured here, not guessed by the model.

  expansion.py compose --run-dir RUN --model-out FILE --deliverables FILE --written-by TEXT --round N
                       [--min 500] [--max 1500] [--force]
      checks: the problem is one first-person sentence; the share driver names an identity; the comment keyword
      is one word in capitals and its deliverable status matches library/profile/deliverables.txt (a keyword that
      is not in the file is NEW, whatever the model said); 2 to 6 evidence pointers, each naming a verified claim
      of facts.md (facts.md#n); the composed text is between --min and --max characters. When every check holds
      (or --force) it writes 02-expansion/expansion.json and expansion.md and prints {"ok": true, ...};
      otherwise it prints {"ok": false, "errors": [...], "chars": N} and writes only expansion.candidate.md, so
      the stage can ask the model again with the exact problems (its own quality loop, not an error).
  expansion.py deliverables --file FILE [--format text|json]
      the comment keywords of deliverables.txt (KEYWORD | what they get | link, or "to create" instead of a link)

Every text is cleaned of em dashes (errors.undash) and CR characters.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errors import undash  # noqa: E402
import solution as solution_lib  # noqa: E402

STAGE = "02-expansion"
FIRST_PERSON = re.compile(r"(?:^|[^A-Za-z])(I|I'm|I’m|I've|I’ve|I'd|I’d|I'll|I’ll|my|me|mine|myself)(?=$|[^A-Za-z])")
KEYWORD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{2,19}$")
MIN_EVIDENCE, MAX_EVIDENCE = 2, 6


def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def text(value, one_line: bool = True) -> str:
    s = "" if value is None else str(value)
    s = undash(s.replace("\r\n", "\n").replace("\r", "\n"))
    if one_line:
        s = " ".join(s.split())
    return s.strip()


def load_json(path: str):
    with open(winpath(path), encoding="utf-8-sig") as f:
        return json.load(f)


def read_deliverables(path: str) -> list[dict]:
    items = []
    try:
        with open(winpath(path), encoding="utf-8-sig") as f:
            lines = f.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    except OSError:
        return items
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2 or not parts[0]:
            continue
        keyword = parts[0].upper()
        what = parts[1]
        link = parts[2] if len(parts) > 2 else ""
        status = "new" if (not link or link.lower() in ("to create", "tocreate", "todo", "-")) else "existing"
        items.append({"keyword": keyword, "what": text(what), "link": "" if status == "new" else text(link),
                      "status": status})
    return items


def one_sentence(s: str) -> bool:
    body = s.strip().rstrip(".!?")
    return not re.search(r"[.!?]\s+[A-Z]", body)


def decision_line(sol: dict | None) -> str:
    """The solution decision as one line of expansion.md (M12, spec S2): type, name, URL, reason."""
    if not sol:
        return "Solution decision: none yet"
    return f"Solution decision: {solution_lib.line_text(sol)}: {sol.get('reason') or 'no reason given'}"


def compose_md(idea: str, f: dict) -> str:
    deliverable = f["deliverable"]
    if f["deliverable_status"] == "existing":
        link = f" ({f['deliverable_link']})" if f.get("deliverable_link") else ""
        deliverable_line = f"Comment keyword: {f['keyword']}. Deliverable (existing): {deliverable}{link}"
    else:
        deliverable_line = f"Comment keyword: {f['keyword']}. Deliverable (NEW, to create): {deliverable}"
    lines = [f"# Expansion: {idea[:90]}", "",
             f"Problem: {f['problem']}", "",
             f"Solution: {f['solution']}", "",
             decision_line(f.get("solution_decision")), "",
             f"Share driver: {f['share_identity']}. Takeaway worth forwarding: {f['takeaway']}", "",
             deliverable_line, "",
             f"One specific true thing: {f['one_true_thing']}", "",
             "Evidence:"]
    lines += [f"- facts.md#{e['fact']}: {e['note']}" for e in f["evidence"]]
    return "\n".join(lines) + "\n"


def cmd_compose(args) -> int:
    run_dir = winpath(args.run_dir)
    model = load_json(args.model_out)
    if not isinstance(model, dict):
        print("expansion.py: the model output is not a JSON object", file=sys.stderr)
        return 1
    research_path = os.path.join(run_dir, "01-research", "research.json")
    research = load_json(research_path) if os.path.isfile(research_path) else {"claims": [], "idea": ""}
    claims = {int(c["n"]): c for c in research.get("claims", []) if isinstance(c, dict) and "n" in c}
    idea = text(research.get("idea")) or text(args.idea)
    deliverables = read_deliverables(args.deliverables)
    errors: list[str] = []

    f = {k: text(model.get(k)) for k in ("problem", "solution", "share_identity", "takeaway", "keyword",
                                         "deliverable", "one_true_thing")}
    for key, label in (("problem", "the problem sentence"), ("solution", "the solution"),
                       ("share_identity", "the share identity"), ("takeaway", "the takeaway"),
                       ("deliverable", "the deliverable"), ("one_true_thing", "the one specific true thing")):
        if not f[key]:
            errors.append(f"{label} is empty")
    if f["problem"]:
        if not FIRST_PERSON.search(f["problem"]):
            errors.append("the problem must be one first-person sentence spoken by the viewer (I, my, me), for example: I ship sites with AI and they all look the same")
        elif not one_sentence(f["problem"]):
            errors.append("the problem must be a single sentence (it has more than one)")
    if f["share_identity"] and len(f["share_identity"].split()) < 2:
        errors.append("the share identity must name who should forward this, for example: if you edit reels for clients")
    keyword = f["keyword"].strip().strip("#").upper()
    if not KEYWORD_RE.match(keyword):
        errors.append(f"the comment keyword must be one word of 3 to 20 letters or digits, got {f['keyword']!r}")
    # the solution decision (M12, spec S2): flashfx, external or method, checked against facts.md; the keyword
    # follows it (FLASH, LINK, or the deliverable that fits for a method), whatever the model wrote
    sol, sol_errors, sol_notes = solution_lib.normalize_decision(model.get("solution_decision"), research, deliverables, keyword)
    errors += sol_errors
    keyword = sol["keyword"]
    f["keyword"] = keyword
    known = {d["keyword"]: d for d in deliverables}
    status_given = text(model.get("deliverable_status")).lower()
    corrected = False
    if sol["type"] in ("flashfx", "external"):
        f["deliverable_status"] = sol["deliverable_status"]
        f["deliverable_link"] = sol["deliverable_link"]
        f["deliverable"] = sol["deliverable"]
    elif keyword in known and known[keyword]["status"] == "existing":
        f["deliverable_status"] = "existing"
        f["deliverable_link"] = known[keyword]["link"]
        if not f["deliverable"]:
            f["deliverable"] = known[keyword]["what"]
    else:
        f["deliverable_status"] = "new"
        f["deliverable_link"] = ""
        corrected = status_given == "existing"
    if f["deliverable_status"] == "new" and f["deliverable"] and len(f["deliverable"].split()) < 4:
        errors.append("a NEW deliverable must be described concretely (what the viewer receives, in at least a few words)")
    f["solution_decision"] = {k: sol[k] for k in ("type", "name", "url", "reason")}

    evidence = []
    seen = set()
    for item in model.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        try:
            n = int(item.get("fact"))
        except (TypeError, ValueError):
            errors.append(f"an evidence pointer is not a claim number: {item.get('fact')!r}")
            continue
        if n in seen:
            continue
        seen.add(n)
        if n not in claims:
            errors.append(f"facts.md#{n} does not exist (facts.md has {len(claims)} claims)")
            continue
        if claims[n].get("status") != "verified":
            errors.append(f"facts.md#{n} is marked {claims[n].get('status')}: cite only verified claims")
            continue
        evidence.append({"fact": n, "note": text(item.get("note")) or claims[n]["claim"][:120]})
    if len(evidence) < MIN_EVIDENCE:
        errors.append(f"give at least {MIN_EVIDENCE} evidence pointers to verified claims of facts.md (facts.md#n), {len(evidence)} given")
    if len(evidence) > MAX_EVIDENCE:
        evidence = evidence[:MAX_EVIDENCE]
    f["evidence"] = evidence

    md = compose_md(idea, f)
    chars = len(md)
    if chars > args.max:
        errors.append(f"expansion.md would be {chars} characters, the limit is {args.max}: cut about {chars - args.max + 40} characters (shorten the solution, the takeaway and the evidence notes)")
    elif chars < args.min:
        errors.append(f"expansion.md would be {chars} characters, the minimum is {args.min}: add about {args.min - chars + 40} characters (a more specific problem sentence, a fuller takeaway or one more evidence note)")

    out_dir = os.path.join(run_dir, STAGE)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "expansion.candidate.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)
    ok = not errors
    result = {"ok": ok, "errors": errors, "chars": chars, "forced": (not ok) and args.force, "keyword": keyword,
              "deliverable_status": f.get("deliverable_status"), "deliverable_status_corrected": corrected,
              "evidence_refs": [e["fact"] for e in evidence], "solution_type": sol["type"], "solution_name": sol["name"],
              "solution_notes": sol_notes}
    if ok or args.force:
        record = dict(f)
        record.update({"evidence": [f"facts.md#{e['fact']}: {e['note']}" for e in evidence],
                       "evidence_refs": [e["fact"] for e in evidence], "chars": chars, "round": args.round,
                       "written_by": args.written_by, "checked": research.get("checked", ""),
                       "rule_errors": errors})
        with open(os.path.join(out_dir, "expansion.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        with open(os.path.join(out_dir, "expansion.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(md)
        # 02-expansion/solution.json: what every later stage reads (the branding of S9, the rules of S7 and S14, the
        # SOLUTION block of the captions file, the history line)
        solution_record = {"type": sol["type"], "name": sol["name"], "url": sol["url"], "reason": sol["reason"],
                           "keyword": keyword, "deliverable": f.get("deliverable", ""), "deliverable_link": f.get("deliverable_link", ""),
                           "written_by": args.written_by, "round": args.round, "checked": research.get("checked", ""),
                           "notes": sol_notes}
        with open(os.path.join(out_dir, "solution.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(solution_record, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        result["path"] = os.path.join(out_dir, "expansion.md").replace("\\", "/")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_deliverables(args) -> int:
    items = read_deliverables(args.file)
    if args.format == "json":
        print(json.dumps(items, ensure_ascii=False))
        return 0
    if not items:
        print("(none yet: library/profile/deliverables.txt lists no keyword, so every deliverable is NEW and must be described concretely)")
        return 0
    for d in items:
        tail = f" ({d['link']})" if d["status"] == "existing" else " (to create)"
        print(f"- {d['keyword']}: {d['what']}{tail}")
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("compose")
    sp.add_argument("--run-dir", required=True); sp.add_argument("--model-out", required=True)
    sp.add_argument("--deliverables", required=True); sp.add_argument("--written-by", required=True)
    sp.add_argument("--round", type=int, default=0); sp.add_argument("--idea", default="")
    sp.add_argument("--min", type=int, default=500); sp.add_argument("--max", type=int, default=1500)
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_compose)
    sp = sub.add_parser("deliverables")
    sp.add_argument("--file", required=True); sp.add_argument("--format", choices=("text", "json"), default="text")
    sp.set_defaults(func=cmd_deliverables)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"expansion.py: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
