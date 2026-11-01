#!/usr/bin/env python
"""gate.py: the idea gate's decision (BUILD_SPEC.md section 5, S3). The gate model scores, this code decides.

  gate.py decide --run-dir RUN --model-out FILE --round R --angles-done N --cap C --core-status S --today D
                 [--idea TEXT]
      the model's structured output (pipeline/stages/03-gate/model.schema.json) holds the scores P, S, C (0 to 3)
      with quoted evidence, its F verdict with its kind (F_kind: "core" when the idea itself does not hold,
      "wording" when a statement of the expansion is not in facts.md while the idea holds without it), a reason,
      an angle hint and, rarely, a different-topic suggestion.
      The rules of spec S3, applied here so they never depend on the model's mood (DECISIONS.md 100 and 112):
        - F fails with kind core whatever the model said when the research found the idea's core claim false or
          could not verify it (--core-status); an F fail of kind core drops the idea at once ("facts don't hold")
        - pass: P, S and C at least 2 and F ok
        - the model says only a different topic would work: drop, with the suggestion for logs/suggested-ideas.txt
        - P, S or C failing, or F failing for wording, with angle rounds left (--angles-done below --cap):
          decision angle (S4 rewrites the expansion: a better angle, or the unbacked statements removed or
          reworded from facts.md)
        - no rounds left: drop ("still failing after N angle rounds")
      Writes 03-gate/gate.json (the primary output) and a copy gate-<round>.json; prints one JSON line with
      decision, scores_text ("P3 S2 C3 F ok"), failing_text ("S1", "F wording", "S1 F wording"), reason (the drop
      reason or the pass note), suggested_idea, angle_hint and F_kind.
  gate.py suggest --logs DIR --idea TEXT --suggestion TEXT [--source STAGE]
      appends the suggestion to logs/suggested-ideas.txt (a comment line, then the suggestion in braces, ready to
      paste into add-idea.sh); never writes ideas.txt
  gate.py angle-rounds --run-dir RUN
      how many gate rounds decided "angle" so far (the angle stage's round number); counts 03-gate/gate-*.json

Every text is cleaned of em dashes (errors.undash) and CR characters.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from errors import undash  # noqa: E402

STAGE = "03-gate"
LETTERS = ("P", "S", "C")
F_KINDS = ("core", "wording")


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


def save_json(path: str, data) -> None:
    with open(winpath(path), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def score(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(3, n))


def cmd_decide(args) -> int:
    run_dir = winpath(args.run_dir)
    model = load_json(args.model_out)
    if not isinstance(model, dict):
        print("gate.py: the model output is not a JSON object", file=sys.stderr)
        return 1
    raw_scores = model.get("scores") if isinstance(model.get("scores"), dict) else {}
    scores = {k: score(raw_scores.get(k)) for k in LETTERS}
    raw_evidence = model.get("evidence") if isinstance(model.get("evidence"), dict) else {}
    evidence = {k: text(raw_evidence.get(k)) for k in LETTERS + ("F",)}
    model_f = "ok" if text(model.get("F")).lower() == "ok" else "fail"
    # the kind of F failure the model found: "core" (the idea does not hold) or "wording" (a statement of the
    # expansion is not in facts.md, the idea holds without it); a missing or unknown kind on a fail is read as
    # core, the spec's strict default
    model_kind = text(model.get("F_kind")).lower()
    if model_kind not in F_KINDS:
        model_kind = "core" if model_f == "fail" else ""
    core_status = (args.core_status or "unverified").lower()
    core_note = ""
    research_path = os.path.join(run_dir, "01-research", "research.json")
    if os.path.isfile(research_path):
        try:
            core_note = text(load_json(research_path).get("core_claim", {}).get("note"))
        except (OSError, ValueError, AttributeError):
            core_note = ""
    if core_status != "verified":
        f_verdict, f_kind = "fail", "core"      # code-forced: a false or unverified core claim is never a wording slip
    elif model_f == "fail":
        f_verdict, f_kind = "fail", model_kind
    else:
        f_verdict, f_kind = "ok", ""
    model_reason = text(model.get("reason"))
    angle_hint = text(model.get("angle_hint"))
    different_topic = bool(model.get("different_topic"))
    suggested = text(model.get("suggested_idea"))
    failing_letters = [f"{k}{scores[k]}" for k in LETTERS if scores[k] < 2]
    failing = failing_letters + (["F"] if f_verdict == "fail" else [])
    failing_text = " ".join(failing_letters + ([f"F {f_kind}"] if f_verdict == "fail" else []))
    scores_text = f"P{scores['P']} S{scores['S']} C{scores['C']} F {f_verdict}"
    passed = not failing_letters and f_verdict == "ok"
    wording_fail = f_verdict == "fail" and f_kind == "wording"
    if wording_fail and not angle_hint:
        angle_hint = ("remove or reword the statements of the expansion that facts.md does not back: "
                      + (evidence["F"] or model_reason or "see the gate's F evidence"))
    short_fail = "; ".join(([" ".join(failing_letters) + " below 2"] if failing_letters else [])
                           + (["a statement of the expansion is not in facts.md"] if wording_fail else []))

    if f_verdict == "fail" and f_kind == "core":
        decision = "drop"
        if core_status != "verified":
            why = f"the idea's core claim is {core_status}" + (f" ({core_note[:160].rstrip()})" if core_note else "")
            if model_reason:
                why += f"; {model_reason}"
        else:
            why = model_reason or evidence["F"] or "the tool does not do what the idea assumes"
        reason = f"facts don't hold ({scores_text}): {why}"
    elif passed:
        decision = "pass"
        reason = model_reason or "passes"
    elif different_topic and suggested:
        decision = "drop"
        reason = (f"no angle keeps the core topic ({scores_text}): {model_reason or angle_hint or 'the model found no angle inside the topic'}"
                  "; suggestion written to logs/suggested-ideas.txt")
    elif args.angles_done < args.cap:
        decision = "angle"
        reason = model_reason or short_fail
    else:
        decision = "drop"
        rounds = "round" if args.angles_done == 1 else "rounds"
        reason = f"still failing after {args.angles_done} angle {rounds} ({scores_text}): {model_reason or short_fail}"

    gate = {
        "round": args.round,
        "scores": scores,
        "F": f_verdict,
        "F_kind": f_kind,
        "pass": passed,
        "decision": decision,
        "evidence": evidence,
        "reason": reason,
        "model_reason": model_reason,
        "model_F": model_f,
        "model_F_kind": model_kind,
        "failing": failing,
        "angle_hint": angle_hint,
        "different_topic": different_topic,
        "suggested_idea": suggested if (decision == "drop" and different_topic) else "",
        "angles_done": args.angles_done,
        "angle_cap": args.cap,
        "core_claim_status": core_status,
        "checked": args.today,
        "decided_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    out_dir = os.path.join(run_dir, STAGE)
    os.makedirs(out_dir, exist_ok=True)
    save_json(os.path.join(out_dir, "gate.json"), gate)
    save_json(os.path.join(out_dir, f"gate-{args.round}.json"), gate)
    print(json.dumps({"decision": decision, "scores_text": scores_text, "failing_text": failing_text,
                      "reason": reason, "suggested_idea": gate["suggested_idea"], "angle_hint": angle_hint,
                      "scores": scores, "F": f_verdict, "F_kind": f_kind}, ensure_ascii=False))
    return 0


def cmd_suggest(args) -> int:
    logs = winpath(args.logs)
    os.makedirs(logs, exist_ok=True)
    suggestion = text(args.suggestion).replace("{", "(").replace("}", ")")
    idea = text(args.idea)
    with open(os.path.join(logs, "suggested-ideas.txt"), "a", encoding="utf-8", newline="\n") as f:
        f.write(f"# {time.strftime('%Y-%m-%d %H:%M')} | from {args.source} | the idea was: {idea}\n")
        f.write("{" + suggestion + "}\n")
    print(json.dumps({"written": True}))
    return 0


def cmd_angle_rounds(args) -> int:
    run_dir = winpath(args.run_dir)
    n = 0
    for path in glob.glob(os.path.join(run_dir, STAGE, "gate-*.json")):
        try:
            if load_json(path).get("decision") == "angle":
                n += 1
        except (OSError, ValueError, AttributeError):
            continue
    print(n)
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("decide")
    sp.add_argument("--run-dir", required=True); sp.add_argument("--model-out", required=True)
    sp.add_argument("--round", type=int, required=True); sp.add_argument("--angles-done", type=int, required=True)
    sp.add_argument("--cap", type=int, required=True); sp.add_argument("--core-status", default="unverified")
    sp.add_argument("--today", required=True); sp.add_argument("--idea", default="")
    sp.set_defaults(func=cmd_decide)
    sp = sub.add_parser("suggest")
    sp.add_argument("--logs", required=True); sp.add_argument("--idea", required=True)
    sp.add_argument("--suggestion", required=True); sp.add_argument("--source", default=STAGE)
    sp.set_defaults(func=cmd_suggest)
    sp = sub.add_parser("angle-rounds")
    sp.add_argument("--run-dir", required=True)
    sp.set_defaults(func=cmd_angle_rounds)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"gate.py: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
