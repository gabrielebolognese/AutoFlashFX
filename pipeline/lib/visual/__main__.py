"""The visual stages' tools (M10, BUILD_SPEC.md S9 and S10). Run as `python pipeline/lib/visual <command> [options]`:

  digest        write the prompt digests of a run for the visual director (the timeline, the catalog, the golden plan)
  animations    compose 09a-animations/plan.json from the director's answer (times snapped to words.json, the branding)
  text          compose 09b-text/plan.json from the director's answer (caption chunks from words.json, card texts, labels)
  transitions   compose 09c-transitions/plan.json from the director's answer and write the merged plan
  merge         the merged plan of a run (visual/plan_merge.py)
  validate      check a plan against tokens.json, catalog.json and brand.json (visual/plan_validate.py)
  build         S10: compile the merged plan into 10-build/project/, check it, render the draft and the hook 2 clip,
                write events.json and the contact sheet (visual/project.py, visual/events.py)
  events        events.json of a built project (visual/events.py)
  contact-sheet one still per beat of a draft (visual/project.py)
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visual import common  # noqa: E402


def main(argv: list[str]) -> int:
    common.setup_streams()
    ap = argparse.ArgumentParser(prog="python pipeline/lib/visual", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    dg = sub.add_parser("digest")
    dg.add_argument("--run-dir", required=True)
    dg.add_argument("--out", required=True, help="the folder for the digest files")
    dg.add_argument("--pass", dest="which", default="animations", choices=["animations", "text", "transitions"])

    for name in ("animations", "text", "transitions"):
        p = sub.add_parser(name)
        p.add_argument("--run-dir", required=True)
        p.add_argument("--answer", required=True, help="the director's structured answer (ai() AI_OUT)")
        p.add_argument("--out", required=True, help="the pass's plan.json")
        p.add_argument("--merged", default="", help="transitions: also write the merged plan here")

    mg = sub.add_parser("merge")
    mg.add_argument("--run-dir", required=True)
    mg.add_argument("--out", default="")

    va = sub.add_parser("validate")
    va.add_argument("plan")
    va.add_argument("--run-dir", default="")
    va.add_argument("--words", default="")
    va.add_argument("--script", default="")
    va.add_argument("--assets-json", default="")
    va.add_argument("--assets-exist", action="store_true", help="trust assets.json without checking the files")
    va.add_argument("--numbers", default="")
    va.add_argument("--parts", default="", help="scenes,captions,transitions (default: all)")
    va.add_argument("--json", action="store_true")

    bd = sub.add_parser("build")
    bd.add_argument("--run-dir", required=True)
    bd.add_argument("--stage-dir", required=True)
    bd.add_argument("--step", default="all", choices=["all", "compile", "check", "finish"], help="compile: merge, validate, compile, check; check: the check again; finish: events, the draft, hook 2, the sheet")
    bd.add_argument("--plan", default="", help="a merged plan instead of merging the run's pass files")
    bd.add_argument("--gpu", default="auto", choices=["auto", "software", "hardware"])
    bd.add_argument("--no-render", action="store_true")

    ev = sub.add_parser("events")
    ev.add_argument("--project", required=True)
    ev.add_argument("--plan", required=True)
    ev.add_argument("--out", required=True)
    ev.add_argument("--no-verify", action="store_true")
    ev.add_argument("--gpu", default="auto", choices=["auto", "software", "hardware"])

    cs = sub.add_parser("contact-sheet")
    cs.add_argument("video")
    cs.add_argument("plan")
    cs.add_argument("out")

    a = ap.parse_args(argv)
    if a.cmd == "digest":
        from visual import plan9
        return plan9.run_digest(a)
    if a.cmd in ("animations", "text", "transitions"):
        from visual import plan9
        return plan9.run_compose(a)
    if a.cmd == "merge":
        from visual import plan_merge
        return plan_merge.run(a)
    if a.cmd == "validate":
        from visual import plan_validate
        return plan_validate.run(a)
    if a.cmd == "build":
        from visual import project
        return project.run_build(a)
    if a.cmd == "events":
        from visual import events
        return events.run(a)
    if a.cmd == "contact-sheet":
        from visual import project
        return project.run_contact_sheet(a)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
