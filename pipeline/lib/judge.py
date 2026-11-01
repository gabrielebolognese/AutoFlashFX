#!/usr/bin/env python
"""judge.py: the scripted parts of the hook judge (BUILD_SPEC.md S6; PLAN.md M5).

The judge stage (pipeline/stages/06-judge/run.sh) filters the hooks with the vendor's hookscore.py, has the judge
model rank the survivors twice with different shuffles, merges the two rankings by Borda count, has the model
compare the top 4 pairwise in both orders in one call, and picks the winner and the runner-up. Every decision rule
lives here, with the labels the prompts use; the model only ranks and compares.

  judge.py score --hooks hooks.json --hookscore PATH --out scores.json [--min 50]
        run hookscore.py --json on the spoken lines; scores.json holds one record per hook (score, verdict, flags,
        weakest check); prints {survivors, dropped, n}
  judge.py feedback --hooks hooks.json --scores scores.json --out feedback.json
        the regeneration feedback for 05-hooks (survivors, failures with the filter's reasons)
  judge.py candidates --hooks hooks.json --scores scores.json [--min-survivors 4] [--top 4]
        the hooks the judge ranks: the survivors, or the best available by score when fewer than 2 survived
  judge.py rank-prompt --hooks hooks.json --candidates id,id --seed TEXT --out labels.json
        prints the labeled, shuffled hook list for the ranking prompt; labels.json maps label -> id
  judge.py parse-ranking --labels labels.json --answer OUT.json --out ranking.json
        the model's ranking as ids, best first (unknown labels ignored, missing ones appended), plus its notes
  judge.py borda --rankings r1.json r2.json [--top 4] --out borda.json
  judge.py pair-prompt --hooks hooks.json --top id,id,id,id --out pairs.json
        prints the four hooks with their labels and the numbered comparisons (every pair in both orders)
  judge.py tally --pairs pairs.json --answer OUT.json --borda borda.json --scores scores.json --out tally.json
        wins per hook; the winner and the runner-up (ties: Borda points, then hookscore)
  judge.py compose --hooks hooks.json --scores scores.json --rankings r1.json r2.json --borda borda.json
                   --tally tally.json --out judge.json [--regenerated 0|1] [--candidates-mode TEXT] [--today D]
        judge.json; prints the summary the stage logs and the stats payload for hooks.py stats-update

Texts from the model are cleaned of em dashes (errors.undash). Paths may be C:/... or /c/... (both work).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errors import undash  # noqa: E402

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PAIR_LABELS = ["W", "X", "Y", "Z", "V", "U", "T", "S"]
CRITERIA = ["stops the scroll", "sets up the problem", "credible", "fits the voice"]


def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def clean(value) -> str:
    s = "" if value is None else str(value)
    return " ".join(undash(s.replace("\r", "")).split())


def load_json(path: str, default=None):
    try:
        with open(winpath(path), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path: str, data) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def out_json(data) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")


def hooks_of(path: str) -> list[dict]:
    data = load_json(path, {})
    hooks = data.get("hooks", []) if isinstance(data, dict) else []
    return [h for h in hooks if isinstance(h, dict) and h.get("id")]


def hook_line(h: dict) -> str:
    return (f'spoken "{clean(h.get("spoken"))}" | on screen "{clean(h.get("on_screen"))}" | marker {clean(h.get("marker"))}'
            f' ({clean(h.get("marker_kind")) or "?"}) | family {clean(h.get("family"))}')


# ------------------------------------------------------------------------------------------------ hookscore
def cmd_score(args) -> int:
    hooks = hooks_of(args.hooks)
    if not hooks:
        print("judge.py score: no hooks in " + args.hooks, file=sys.stderr)
        return 2
    lines = [clean(h.get("spoken")) or "(empty)" for h in hooks]
    fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="hooks-")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        proc = subprocess.run([sys.executable, "-I", "-X", "utf8", winpath(args.hookscore), tmp, "--json"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if proc.returncode not in (0, 1) or not proc.stdout.strip():
        print(f"judge.py score: hookscore.py failed (exit {proc.returncode}): {proc.stderr.strip()[:300]}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(proc.stdout)
    except ValueError as exc:
        print(f"judge.py score: hookscore.py printed no JSON: {exc}", file=sys.stderr)
        return 2
    if isinstance(payload, dict):
        payload = [payload]
    if len(payload) != len(hooks):
        # hookscore skips empty lines; match by text where the counts differ
        by_text = {p.get("hook", ""): p for p in payload}
        payload = [by_text.get(line, {"hook": line, "score": 0.0, "verdict": "WEAK", "flags": ["not scored"],
                                      "weakest": "", "checks": {}}) for line in lines]
    records = {}
    survivors, dropped = [], []
    for h, p in zip(hooks, payload):
        score = float(p.get("score", 0) or 0)
        flags = [clean(x) for x in (p.get("flags") or [])]
        weakest = p.get("weakest", "")
        checks = p.get("checks", {}) or {}
        rec = {"score": round(score, 1), "verdict": p.get("verdict", ""), "flags": flags, "weakest": weakest,
               "weakest_detail": clean((checks.get(weakest) or {}).get("detail", "")) if weakest else "",
               "checks": {k: {"score": v.get("score"), "detail": clean(v.get("detail", ""))} for k, v in checks.items()
                          if isinstance(v, dict)}}
        records[h["id"]] = rec
        if flags or score < args.min:
            why = []
            if flags:
                why.append("dealbreaker: " + "; ".join(flags))
            if score < args.min:
                why.append(f"score {score:.0f} under {args.min:g}" + (f" (weakest: {weakest}: {rec['weakest_detail']})" if weakest else ""))
            dropped.append({"id": h["id"], "spoken": clean(h.get("spoken")), "score": round(score, 1), "flags": flags,
                            "weakest": weakest, "reason": "; ".join(why)})
        else:
            survivors.append(h["id"])
    save_json(args.out, {"min_score": args.min, "checked": time.strftime("%Y-%m-%d %H:%M"), "hooks": records,
                         "survivors": survivors, "dropped": dropped})
    out_json({"survivors": survivors, "dropped": [d["id"] for d in dropped], "n": len(hooks)})
    return 0


def cmd_feedback(args) -> int:
    hooks = {h["id"]: h for h in hooks_of(args.hooks)}
    scores = load_json(args.scores, {})
    survivors = scores.get("survivors", [])
    dropped = scores.get("dropped", [])
    surv_text = "\n".join(f"- {sid}: {hook_line(hooks[sid])}" for sid in survivors if sid in hooks) or "(none)"
    fail_lines = []
    for d in dropped:
        h = hooks.get(d["id"], {})
        fail_lines.append(f'- {d["id"]} "{clean(h.get("spoken"))}" (template {h.get("template_id", "?")}): {d["reason"]}')
    save_json(args.out, {"survivors": survivors, "survivors_text": surv_text,
                         "failures": dropped, "failures_text": "\n".join(fail_lines) or "(none)",
                         "min_score": scores.get("min_score", 50)})
    out_json({"survivors": len(survivors), "failures": len(dropped)})
    return 0


def cmd_candidates(args) -> int:
    hooks = hooks_of(args.hooks)
    scores = load_json(args.scores, {})
    recs = scores.get("hooks", {})
    survivors = [sid for sid in scores.get("survivors", []) if any(h["id"] == sid for h in hooks)]
    if len(survivors) >= 2:
        out_json({"candidates": survivors, "mode": "survivors" if len(survivors) >= args.min_survivors else "survivors (fewer than wanted)"})
        return 0
    # the best available: dealbreaker-free first, then by score
    ranked = sorted(hooks, key=lambda h: (1 if recs.get(h["id"], {}).get("flags") else 0,
                                          -float(recs.get(h["id"], {}).get("score", 0) or 0)))
    best = [h["id"] for h in ranked[:max(args.top, 2)]]
    out_json({"candidates": best, "mode": "best available"})
    return 0


# ------------------------------------------------------------------------------------------------ rankings
def cmd_rank_prompt(args) -> int:
    hooks = {h["id"]: h for h in hooks_of(args.hooks)}
    ids = [i for i in args.candidates.split(",") if i in hooks]
    if len(ids) > len(LETTERS):
        ids = ids[:len(LETTERS)]
    rng = random.Random(f"rank:{args.seed}")
    order = list(ids)
    rng.shuffle(order)
    labels = {LETTERS[i]: hid for i, hid in enumerate(order)}
    save_json(args.out, {"labels": labels, "order": order, "seed": args.seed})
    for label, hid in labels.items():
        sys.stdout.write(f"- {label}: {hook_line(hooks[hid])}\n")
    return 0


def cmd_parse_ranking(args) -> int:
    labels = load_json(args.labels, {}).get("labels", {})
    answer = load_json(args.answer, {})
    raw = answer.get("ranking", []) if isinstance(answer, dict) else []
    ranking: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        label = clean(item).strip().strip(".:)").upper()
        hid = labels.get(label)
        if hid and hid not in ranking:
            ranking.append(hid)
    complete = len(ranking) == len(labels)
    for label in sorted(labels):  # a label the model forgot goes last, in label order
        if labels[label] not in ranking:
            ranking.append(labels[label])
    notes = {}
    for n in (answer.get("notes", []) if isinstance(answer, dict) else []):
        if isinstance(n, dict):
            hid = labels.get(clean(n.get("label")).strip().upper())
            if hid:
                notes[hid] = clean(n.get("note"))
    save_json(args.out, {"ranking": ranking, "notes": notes, "complete": complete, "shown": [labels[k] for k in sorted(labels)]})
    out_json({"ranking": ranking, "complete": complete})
    return 0


def cmd_borda(args) -> int:
    rankings = [load_json(p, {}).get("ranking", []) for p in args.rankings]
    ids: list[str] = []
    for r in rankings:
        for hid in r:
            if hid not in ids:
                ids.append(hid)
    n = len(ids)
    points = {hid: 0 for hid in ids}
    positions = {hid: [] for hid in ids}
    for r in rankings:
        for pos, hid in enumerate(r):
            points[hid] += n - 1 - pos
            positions[hid].append(pos + 1)
        for hid in ids:
            if hid not in r:
                positions[hid].append(n)
    first = rankings[0] if rankings else []
    order = sorted(ids, key=lambda h: (-points[h], first.index(h) if h in first else n))
    top = order[:args.top]
    save_json(args.out, {"points": points, "order": order, "top": top, "positions": positions,
                         "max_points": max(0, (n - 1) * len(rankings)), "n": n, "rankings": rankings})
    out_json({"top": top, "order": order, "points": points})
    return 0


# ------------------------------------------------------------------------------------------------ pairwise
def cmd_pair_prompt(args) -> int:
    hooks = {h["id"]: h for h in hooks_of(args.hooks)}
    top = [i for i in args.top.split(",") if i in hooks][:len(PAIR_LABELS)]
    labels = {PAIR_LABELS[i]: hid for i, hid in enumerate(top)}
    comparisons = []
    n = 0
    keys = list(labels)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            for first, second in ((keys[i], keys[j]), (keys[j], keys[i])):
                n += 1
                comparisons.append({"n": n, "first": first, "second": second,
                                    "first_id": labels[first], "second_id": labels[second]})
    save_json(args.out, {"labels": labels, "comparisons": comparisons})
    sys.stdout.write("The four hooks:\n")
    for label, hid in labels.items():
        sys.stdout.write(f"- {label}: {hook_line(hooks[hid])}\n")
    sys.stdout.write("\nThe comparisons (judge each one on its own):\n")
    for c in comparisons:
        sys.stdout.write(f"{c['n']}. first {c['first']}, second {c['second']}\n")
    return 0


def cmd_tally(args) -> int:
    pairs = load_json(args.pairs, {})
    labels = pairs.get("labels", {})
    comparisons = {c["n"]: c for c in pairs.get("comparisons", [])}
    answer = load_json(args.answer, {})
    borda = load_json(args.borda, {})
    scores = load_json(args.scores, {}).get("hooks", {})
    wins = {hid: 0 for hid in labels.values()}
    results = []
    seen = set()
    for item in (answer.get("comparisons", []) if isinstance(answer, dict) else []):
        if not isinstance(item, dict):
            continue
        try:
            n = int(item.get("n"))
        except (TypeError, ValueError):
            continue
        c = comparisons.get(n)
        if not c or n in seen:
            continue
        seen.add(n)
        w = clean(item.get("winner")).strip().upper()
        if w not in (c["first"], c["second"]):
            continue
        wid = labels[w]
        wins[wid] += 1
        results.append({"n": n, "first": c["first_id"], "second": c["second_id"], "winner": wid, "why": clean(item.get("why"))})
    points = borda.get("points", {})
    order = sorted(wins, key=lambda h: (-wins[h], -points.get(h, 0), -float(scores.get(h, {}).get("score", 0) or 0)))
    winner = order[0] if order else ""
    runner_up = order[1] if len(order) > 1 else ""
    save_json(args.out, {"wins": wins, "order": order, "winner": winner, "runner_up": runner_up, "results": results,
                         "answered": len(results), "asked": len(comparisons)})
    out_json({"winner": winner, "runner_up": runner_up, "wins": wins, "answered": len(results), "asked": len(comparisons)})
    return 0


# ------------------------------------------------------------------------------------------------ judge.json
def cmd_compose(args) -> int:
    hooks_list = hooks_of(args.hooks)
    hooks = {h["id"]: h for h in hooks_list}
    scores = load_json(args.scores, {})
    recs = scores.get("hooks", {})
    rankings = [load_json(p, {}) for p in args.rankings]
    borda = load_json(args.borda, {})
    tally = load_json(args.tally, {})
    winner_id = tally.get("winner", "")
    runner_id = tally.get("runner_up", "")
    if winner_id not in hooks or runner_id not in hooks or winner_id == runner_id:
        order = borda.get("order", [])
        fallback = [h for h in order if h in hooks] + [h["id"] for h in hooks_list if h["id"] not in order]
        if winner_id not in hooks:
            winner_id = fallback[0] if fallback else ""
        if runner_id not in hooks or runner_id == winner_id:
            runner_id = next((h for h in fallback if h != winner_id), "")
    if not winner_id or not runner_id:
        print("judge.py compose: fewer than two hooks to choose from", file=sys.stderr)
        return 3

    def hook_record(hid: str) -> dict:
        h = dict(hooks[hid])
        h["hookscore"] = recs.get(hid, {}).get("score")
        h["borda_points"] = borda.get("points", {}).get(hid)
        h["pairwise_wins"] = tally.get("wins", {}).get(hid)
        return h

    reasons = []
    for r in tally.get("results", []):
        if r.get("winner") == winner_id and r.get("why"):
            loser = r["second"] if r["first"] == winner_id else r["first"]
            reasons.append(f"{winner_id} over {loser}: {r['why']}")
    for i, rk in enumerate(rankings, 1):
        note = rk.get("notes", {}).get(winner_id)
        if note:
            reasons.append(f"ranking {i} on {winner_id}: {note}")
    for i, rk in enumerate(rankings, 1):
        note = rk.get("notes", {}).get(runner_id)
        if note:
            reasons.append(f"ranking {i} on the runner-up {runner_id}: {note}")
    wins = tally.get("wins", {})
    reasons.append(f"pairwise: {winner_id} won {wins.get(winner_id, 0)} of its comparisons, {runner_id} won {wins.get(runner_id, 0)}; "
                   f"Borda points {borda.get('points', {}).get(winner_id, 0)} and {borda.get('points', {}).get(runner_id, 0)} "
                   f"of {borda.get('max_points', 0)}; hookscore {recs.get(winner_id, {}).get('score', '?')} and {recs.get(runner_id, {}).get('score', '?')}")
    reasons = reasons[:10]
    max_points = float(borda.get("max_points", 0) or 0)
    judge = {
        "winner": hook_record(winner_id), "runner_up": hook_record(runner_id), "reasons": reasons,
        "criteria": CRITERIA,
        "filtered_out": scores.get("dropped", []),
        "hookscore": {hid: recs.get(hid, {}).get("score") for hid in hooks},
        "hookscore_min": scores.get("min_score", 50),
        "candidates": borda.get("order", []), "candidates_mode": args.candidates_mode or "survivors",
        "rankings": [{"call": i, "shown": rk.get("shown", []), "ranking": rk.get("ranking", []), "notes": rk.get("notes", {}),
                      "complete": rk.get("complete", True)} for i, rk in enumerate(rankings, 1)],
        "borda": borda.get("points", {}), "top": borda.get("top", []),
        "pairwise": tally.get("results", []), "pairwise_wins": wins,
        "regenerated": bool(int(args.regenerated or 0)), "calls": len(rankings) + 1,
        "checked": args.today or time.strftime("%Y-%m-%d"),
    }
    save_json(args.out, judge)
    picked = sorted({h.get("template_id", "") for h in hooks_list if h.get("template_id")})
    tscores = {}
    texts = {}
    for h in hooks_list:
        tid = h.get("template_id", "")
        if tid and tid not in texts:
            texts[tid] = h.get("template", "")
        pts = borda.get("points", {}).get(h["id"])
        if tid and pts is not None and max_points > 0:
            tscores[tid] = max(tscores.get(tid, 0.0), round(pts / max_points, 3))
    out_json({"winner_id": winner_id, "winner_spoken": hooks[winner_id].get("spoken", ""),
              "winner_family": hooks[winner_id].get("family", ""), "winner_template": hooks[winner_id].get("template_id", ""),
              "runner_up_id": runner_id, "runner_up_spoken": hooks[runner_id].get("spoken", ""),
              "runner_up_family": hooks[runner_id].get("family", ""),
              "picked": picked, "scores": tscores, "texts": texts, "reasons": len(reasons)})
    return 0


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("score"); sp.add_argument("--hooks", required=True); sp.add_argument("--hookscore", required=True)
    sp.add_argument("--out", required=True); sp.add_argument("--min", type=float, default=50); sp.set_defaults(func=cmd_score)
    sp = sub.add_parser("feedback"); sp.add_argument("--hooks", required=True); sp.add_argument("--scores", required=True)
    sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_feedback)
    sp = sub.add_parser("candidates"); sp.add_argument("--hooks", required=True); sp.add_argument("--scores", required=True)
    sp.add_argument("--min-survivors", type=int, default=4); sp.add_argument("--top", type=int, default=4); sp.set_defaults(func=cmd_candidates)
    sp = sub.add_parser("rank-prompt"); sp.add_argument("--hooks", required=True); sp.add_argument("--candidates", required=True)
    sp.add_argument("--seed", default=""); sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_rank_prompt)
    sp = sub.add_parser("parse-ranking"); sp.add_argument("--labels", required=True); sp.add_argument("--answer", required=True)
    sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_parse_ranking)
    sp = sub.add_parser("borda"); sp.add_argument("--rankings", nargs="+", required=True); sp.add_argument("--top", type=int, default=4)
    sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_borda)
    sp = sub.add_parser("pair-prompt"); sp.add_argument("--hooks", required=True); sp.add_argument("--top", required=True)
    sp.add_argument("--out", required=True); sp.set_defaults(func=cmd_pair_prompt)
    sp = sub.add_parser("tally"); sp.add_argument("--pairs", required=True); sp.add_argument("--answer", required=True)
    sp.add_argument("--borda", required=True); sp.add_argument("--scores", required=True); sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_tally)
    sp = sub.add_parser("compose"); sp.add_argument("--hooks", required=True); sp.add_argument("--scores", required=True)
    sp.add_argument("--rankings", nargs="+", required=True); sp.add_argument("--borda", required=True); sp.add_argument("--tally", required=True)
    sp.add_argument("--out", required=True); sp.add_argument("--regenerated", default="0"); sp.add_argument("--candidates-mode", default="")
    sp.add_argument("--today", default=""); sp.set_defaults(func=cmd_compose)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except OSError as exc:
        print(f"judge.py {args.cmd}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
