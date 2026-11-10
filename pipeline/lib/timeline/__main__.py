"""The timeline tools (BUILD_SPEC.md 14.8, M20). Run as `python pipeline/lib/timeline <command> [options]`:

  build   --run-dir DIR [--out FILE] [--format ID]   write the timeline of a generated format's run from its plans, words, cues and composition
                                                     (default out: <run>/timeline/timeline.json); "@@SAY" and "@@ERROR" progress lines
  check   --run-dir DIR [--timeline FILE] [--json OUT] [--no-hash]
                                                     compare the timeline with the files it describes (check.py); exit 1 on a failed check
  render  --run-dir DIR --out FILE.mp4 [--timeline FILE] [--work DIR]
                                                     render a timeline with ffmpeg (render_ffmpeg.py: trims, joins, burned captions, the audio mix)
  validate FILE                                      the timeline against pipeline/schemas/timeline.schema.json
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timeline import check as tcheck  # noqa: E402
from timeline import common as tc  # noqa: E402
from timeline import compose  # noqa: E402
from timeline import render_ffmpeg  # noqa: E402


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--run-dir", required=True)
    b.add_argument("--out", default="")
    b.add_argument("--format", default="")
    b.add_argument("--channel", default="")
    b.set_defaults(func=lambda a: compose.main_build(_default_out(a)))
    c = sub.add_parser("check")
    c.add_argument("--run-dir", required=True)
    c.add_argument("--timeline", default="")
    c.add_argument("--json", default="")
    c.add_argument("--no-hash", action="store_true")
    c.set_defaults(func=tcheck.main_check)
    r = sub.add_parser("render")
    r.add_argument("--run-dir", required=True)
    r.add_argument("--timeline", default="")
    r.add_argument("--out", required=True)
    r.add_argument("--work", default="")
    r.add_argument("--json", default="")
    r.set_defaults(func=render_ffmpeg.main_render)
    v = sub.add_parser("validate")
    v.add_argument("file")
    v.set_defaults(func=_validate)
    a = ap.parse_args(argv)
    return a.func(a)


def _default_out(a):
    if not a.out:
        a.out = f"{tc.winpath(a.run_dir).rstrip('/')}/{tc.TIMELINE_DIR}/{tc.TIMELINE_FILE}"
    return a


def _validate(a) -> int:
    t = tc.read_json(a.file)
    errs = tcheck._schema_errors(t) if isinstance(t, dict) else ["not a JSON object"]
    for e in errs:
        print(e)
    print("valid" if not errs else f"{len(errs)} problems")
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
