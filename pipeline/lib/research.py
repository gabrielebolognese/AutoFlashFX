#!/usr/bin/env python
"""research.py: the research stage's files (BUILD_SPEC.md section 5, S1), built from the model's structured output.

The research model answers with one JSON object (pipeline/stages/01-research/model.schema.json): the idea's core
claim with its status, the claims it checked (each with its source URL, tier and status), the numbers, the
pitfalls, the "one specific true thing" candidates, the screenshots it took and what cannot be verified. This
script turns that into the stage's files, so their format is always the same whatever the model wrote:

  research.py finish --run-dir RUN --model-out FILE --today YYYY-MM-DD --idea-id ID --idea TEXT [--max-assets N]
      writes 01-research/research.json (the primary output, validated by the runner against schema.json),
      facts.md (every claim numbered, with its URL and the date checked, primary sources first), numbers.json,
      assets.json (the screenshots whose files exist, from the sidecars pipeline/bin/screenshot wrote);
      prints a JSON summary {claims, verified, numbers, assets, core_status}
  research.py append-claims --run-dir RUN --claims FILE --today YYYY-MM-DD --added-by TEXT
      appends the claims of a JSON list (the angle stage's extra research) to research.json, numbering on, and
      renders facts.md again; prints {added, total}
  research.py claims --run-dir RUN
      the claims as a JSON list (n, claim, url, tier, status), for the expansion checks

Every text is cleaned of em dashes (errors.undash) and CR characters, and claim lines are one line each.
Claims are numbered after sorting: verified before unverified before false, and within a status primary
(the official repo or docs) before vendor (the maker's blog) before press before forum, in the model's order
otherwise. Pointers such as facts.md#3 in the expansion refer to these numbers, so append-claims never
renumbers: new claims continue the sequence.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errors import undash  # noqa: E402

STAGE = "01-research"
TIERS = ("primary", "vendor", "press", "forum")
STATUSES = ("verified", "unverified", "false")
URL_RE = re.compile(r"^https?://\S+$", re.I)


def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def text(value, one_line: bool = True) -> str:
    """A clean string: no em dash, no CR, collapsed whitespace when one_line."""
    s = "" if value is None else str(value)
    s = undash(s.replace("\r\n", "\n").replace("\r", "\n"))
    if one_line:
        s = " ".join(s.split())
    return s.strip()


def load_json(path: str):
    with open(winpath(path), encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: str, data) -> None:
    with open(winpath(path), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def save_text(path: str, content: str) -> None:
    with open(winpath(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text(name).lower()).strip("_")
    return s[:40] or "value"


def parse_value(value):
    """'12,345' -> 12345, '3.5' -> 3.5, 'v2.1.3' stays a string."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    s = text(value)
    plain = s.replace(",", "").replace("_", "")
    if re.fullmatch(r"[+-]?\d+", plain):
        return int(plain)
    if re.fullmatch(r"[+-]?\d+\.\d+", plain):
        return float(plain)
    return s


def clean_claim(raw: dict, today: str, added_by: str) -> dict | None:
    """A claim in the file's shape, or None when it has no usable text."""
    claim = text(raw.get("claim"))
    if not claim:
        return None
    url = text(raw.get("url"))
    tier = text(raw.get("tier")).lower()
    status = text(raw.get("status")).lower()
    if tier not in TIERS:
        tier = "press"
    if status not in STATUSES:
        status = "unverified"
    checked = text(raw.get("checked")) or today
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked):
        checked = today
    return {"claim": claim, "url": url, "tier": tier, "status": status, "checked": checked,
            "note": text(raw.get("note")), "added_by": added_by}


def sort_key(order: int, claim: dict):
    return (STATUSES.index(claim["status"]), TIERS.index(claim["tier"]), order)


def _recording_fields(folder: str, side: dict) -> dict:
    """M16 (E8): the scroll recording next to the screenshot, when its mp4 exists: {recording: "assets/NN-name.mp4", recording_seconds}."""
    rec = text(side.get("recording"))
    if rec and os.path.isfile(os.path.join(folder, rec)):
        return {"recording": f"assets/{rec}", "recording_seconds": side.get("recording_seconds")}
    return {}


def collect_assets(run_dir: str, declared: list, max_assets: int) -> list[dict]:
    """The screenshots whose PNG exists, from the sidecars pipeline/bin/screenshot wrote, with the model's captions."""
    folder = os.path.join(run_dir, STAGE, "assets")
    if not os.path.isdir(folder):
        return []
    captions = {}
    for item in declared or []:
        if isinstance(item, dict):
            key = re.sub(r"[^a-z0-9]+", "-", text(item.get("name") or item.get("file")).lower()).strip("-")
            key = re.sub(r"^\d{2}-", "", key).removesuffix("-png")
            if key:
                captions[key] = text(item.get("what"))
    assets = []
    for entry in sorted(os.listdir(folder)):
        if not entry.endswith(".json"):
            continue
        try:
            side = json.load(open(os.path.join(folder, entry), encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(side, dict) or not side.get("ok") or not side.get("file"):
            continue
        if not os.path.isfile(os.path.join(folder, side["file"])):
            continue
        name = text(side.get("name"))
        what = captions.get(name) or captions.get(re.sub(r"^\d{2}-", "", side["file"]).removesuffix(".png")) or text(side.get("title"))
        assets.append({"file": f"assets/{side['file']}", "name": name, "url": text(side.get("url")),
                       "final_url": text(side.get("final_url")), "title": text(side.get("title")),
                       "captured": text(side.get("captured")), "checked": text(side.get("checked")),
                       "width": side.get("width"), "height": side.get("height"), "what": what}
                      | _recording_fields(folder, side))
    return assets[:max_assets] if max_assets > 0 else assets


def clean_candidates(raw) -> list[dict]:
    """The solution candidates (M12, spec S1): type external or method, a name, a URL for an external one, a why."""
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = text(item.get("name"))
        if not name:
            continue
        stype = text(item.get("type")).lower()
        url = text(item.get("url"))
        if stype not in ("external", "method"):
            stype = "external" if URL_RE.match(url) else "method"
        if stype == "external" and not URL_RE.match(url):
            continue   # an external tool without a verified URL cannot be the solution (S2 needs the link)
        if stype == "method":
            url = url if URL_RE.match(url) else ""
        out.append({"type": stype, "name": name, "url": url, "why": text(item.get("why"))})
        if len(out) >= 6:
            break
    return out


def render_facts(r: dict) -> str:
    lines = [f"# Facts: {text(r.get('idea'))[:100]}", "",
             f"Checked {r['checked']}. Every claim carries its source and the date it was checked; the claims are listed",
             "in order of trust (primary: the official repo or docs; vendor: the maker's blog or announcement; press;",
             "forum). A claim marked unverified could not be confirmed on that day; one marked false is contradicted",
             "by its source. Numbers such as facts.md#3 point to the claims below.", "",
             "## Core claim of the idea",
             text(r["core_claim"].get("text")) or "(none stated)",
             f"Status: {r['core_claim'].get('status')}. {text(r['core_claim'].get('note'))}".rstrip(), "",
             "## Claims"]
    if r["claims"]:
        for c in r["claims"]:
            lines.append(f"{c['n']}. {c['claim']} [{c['tier']}, {c['status']}]: {c['url']} (checked {c['checked']})")
            if c.get("note"):
                lines.append(f"   Note: {c['note']}")
            if c.get("added_by") and c["added_by"] != STAGE:
                lines.append(f"   Added by {c['added_by']}.")
    else:
        lines.append("(no sourced claims)")
    lines += ["", "## Numbers"]
    if r["numbers"]:
        for key, num in r["numbers"].items():
            unit = f" {num['unit']}" if num.get("unit") else ""
            note = f"; {num['note']}" if num.get("note") else ""
            lines.append(f"- {key}: {num['value']}{unit} ({num['url']}, checked {num['checked']}{note})")
    else:
        lines.append("(none)")
    lines += ["", "## Pitfalls"] + ([f"- {p}" for p in r["pitfalls"]] or ["(none found)"])
    lines += ["", "## One specific true thing (candidates)"] + ([f"- {p}" for p in r["one_true_thing"]] or ["(none found)"])
    lines += ["", "## Solution candidates (the best available ways to solve the viewer's problem; S2 decides)"]
    if r.get("solution_candidates"):
        for c in r["solution_candidates"]:
            url = f" ({c['url']})" if c.get("url") else ""
            lines.append(f"- {c['type']}: {c['name']}{url}: {c['why']}")
    else:
        lines.append("(none listed)")
    lines += ["", "## Unverified or unsourced"] + ([f"- {p}" for p in r["unverified"]] or ["(nothing)"])
    lines += ["", "## Assets (screenshots in 01-research/assets/)"]
    if r["assets"]:
        for a in r["assets"]:
            rec = f"; scroll recording {os.path.basename(a['recording'])}, {a.get('recording_seconds')} s" if a.get("recording") else ""
            lines.append(f"- {os.path.basename(a['file'])}: {a['what']} ({a['url']}, captured {a['captured']}{rec})")
    else:
        lines.append("(no screenshots)")
    lines += ["", "## Research summary", text(r.get("summary"), one_line=False) or "(none)", ""]
    return "\n".join(lines)


def write_files(run_dir: str, r: dict) -> None:
    out = os.path.join(run_dir, STAGE)
    os.makedirs(out, exist_ok=True)
    save_json(os.path.join(out, "research.json"), r)
    save_text(os.path.join(out, "facts.md"), render_facts(r))
    save_json(os.path.join(out, "numbers.json"), r["numbers"])
    save_json(os.path.join(out, "assets.json"), r["assets"])


def cmd_finish(args) -> int:
    run_dir = winpath(args.run_dir)
    model = load_json(args.model_out)
    if not isinstance(model, dict):
        print("research.py: the model output is not a JSON object", file=sys.stderr)
        return 1
    core = model.get("core_claim") if isinstance(model.get("core_claim"), dict) else {}
    core_status = text(core.get("status")).lower()
    if core_status not in STATUSES:
        core_status = "unverified"
    unverified = [text(u) for u in (model.get("unverified") or []) if text(u)]
    claims = []
    for i, raw in enumerate(model.get("claims") or []):
        if not isinstance(raw, dict):
            continue
        c = clean_claim(raw, args.today, STAGE)
        if c is None:
            continue
        if not URL_RE.match(c["url"]):
            unverified.append(f"{c['claim']} (no usable source URL given)")
            continue
        claims.append((i, c))
    claims.sort(key=lambda pair: sort_key(pair[0], pair[1]))
    numbered = []
    for n, (_, c) in enumerate(claims, 1):
        c["n"] = n
        numbered.append(c)
    numbers = {}
    for raw in model.get("numbers") or []:
        if not isinstance(raw, dict) or not text(raw.get("name")):
            continue
        url = text(raw.get("url"))
        if not URL_RE.match(url):
            unverified.append(f"number {text(raw.get('name'))} = {text(raw.get('value'))} (no usable source URL given)")
            continue
        key = slug(raw.get("name"))
        base, k = key, 2
        while key in numbers:
            key = f"{base}_{k}"
            k += 1
        checked = text(raw.get("checked")) or args.today
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked):
            checked = args.today
        numbers[key] = {"name": text(raw.get("name")), "value": parse_value(raw.get("value")),
                        "unit": text(raw.get("unit")), "url": url, "checked": checked, "note": text(raw.get("note"))}
    assets = collect_assets(run_dir, model.get("assets") or [], args.max_assets)
    candidates = clean_candidates(model.get("solution_candidates"))
    r = {
        "idea_id": args.idea_id,
        "idea": text(args.idea),
        "checked": args.today,
        "stage": STAGE,
        "core_claim": {"text": text(core.get("text")), "status": core_status, "note": text(core.get("note"))},
        "claims": numbered,
        "numbers": numbers,
        "pitfalls": [text(p) for p in (model.get("pitfalls") or []) if text(p)],
        "one_true_thing": [text(p) for p in (model.get("one_true_thing") or []) if text(p)],
        "unverified": unverified,
        "assets": assets,
        "solution_candidates": candidates,
        "summary": text(model.get("summary"), one_line=False),
        "sources": {tier: sum(1 for c in numbered if c["tier"] == tier) for tier in TIERS},
        "counts": {"claims": len(numbered), "verified": sum(1 for c in numbered if c["status"] == "verified"),
                   "false": sum(1 for c in numbered if c["status"] == "false")},
    }
    write_files(run_dir, r)
    print(json.dumps({"claims": len(numbered), "verified": r["counts"]["verified"], "false": r["counts"]["false"],
                      "numbers": len(numbers), "assets": len(assets), "core_status": core_status,
                      "one_true_thing": len(r["one_true_thing"]), "solution_candidates": len(candidates)}, ensure_ascii=False))
    return 0


def cmd_append(args) -> int:
    run_dir = winpath(args.run_dir)
    path = os.path.join(run_dir, STAGE, "research.json")
    r = load_json(path)
    raw_list = load_json(args.claims)
    if isinstance(raw_list, dict):
        raw_list = raw_list.get("new_claims") or raw_list.get("claims") or []
    existing = {(c["claim"].lower(), c["url"].lower()) for c in r["claims"]}
    existing_text = {c["claim"].lower() for c in r["claims"]}
    n = max([c["n"] for c in r["claims"]] + [0])
    added = 0
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue
        c = clean_claim(raw, args.today, args.added_by)
        if c is None or not URL_RE.match(c["url"]):
            continue
        if (c["claim"].lower(), c["url"].lower()) in existing or c["claim"].lower() in existing_text:
            continue
        n += 1
        c["n"] = n
        r["claims"].append(c)
        existing.add((c["claim"].lower(), c["url"].lower()))
        existing_text.add(c["claim"].lower())
        added += 1
    r["sources"] = {tier: sum(1 for c in r["claims"] if c["tier"] == tier) for tier in TIERS}
    r["counts"] = {"claims": len(r["claims"]), "verified": sum(1 for c in r["claims"] if c["status"] == "verified"),
                   "false": sum(1 for c in r["claims"] if c["status"] == "false")}
    write_files(run_dir, r)
    print(json.dumps({"added": added, "total": len(r["claims"])}))
    return 0


def cmd_claims(args) -> int:
    r = load_json(os.path.join(winpath(args.run_dir), STAGE, "research.json"))
    print(json.dumps([{k: c.get(k) for k in ("n", "claim", "url", "tier", "status")} for c in r["claims"]],
                     ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("finish")
    sp.add_argument("--run-dir", required=True); sp.add_argument("--model-out", required=True)
    sp.add_argument("--today", required=True); sp.add_argument("--idea-id", required=True)
    sp.add_argument("--idea", default=""); sp.add_argument("--max-assets", type=int, default=6)
    sp.set_defaults(func=cmd_finish)
    sp = sub.add_parser("append-claims")
    sp.add_argument("--run-dir", required=True); sp.add_argument("--claims", required=True)
    sp.add_argument("--today", required=True); sp.add_argument("--added-by", required=True)
    sp.set_defaults(func=cmd_append)
    sp = sub.add_parser("claims")
    sp.add_argument("--run-dir", required=True)
    sp.set_defaults(func=cmd_claims)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"research.py: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
