"""The motion library tools (M9). Run as `python pipeline/lib/motion <command> [options]`:

  frame-match   measure every component frame by frame and compare with the style's numbers and the reference strips
                (motion/framematch.py); writes motion-lib/gallery/frame-match.md and .json
  stills        one still per component into motion-lib/gallery/stills/ (motion/gallery.py)
  gallery       motion-lib/gallery/index.html, the page that plays each component, and the showreel index.html
  catalog       check catalog.json against the component files (every file listed, props and declared variables agree)
  golden-plan   write the golden reel's plan from the frozen script.json and words.json (motion/goldenplan.py)
  golden        build and render the golden reel from a plan (motion/golden.py)
  webgl         the WebGL test: hardware ANGLE first, then SwiftShader; writes motion-lib/webgl.json (motion/webgl.py)
  events        print the sound events a component registers for given props (debugging)
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motion import common  # noqa: E402


def main(argv: list[str]) -> int:
    common.setup_streams()
    ap = argparse.ArgumentParser(prog="python pipeline/lib/motion", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    fm = sub.add_parser("frame-match")
    fm.add_argument("--only", default="")
    fm.add_argument("--no-shots", action="store_true", help="skip the per-frame screenshots and the strip correlation")
    fm.add_argument("--apply", action="store_true", help="move failing components to candidates/ and update catalog.json")
    fm.add_argument("--gpu", default="auto", choices=["auto", "software", "hardware"])

    st = sub.add_parser("stills")
    st.add_argument("--only", default="")
    st.add_argument("--gpu", default="auto", choices=["auto", "software", "hardware"])

    ga = sub.add_parser("gallery")
    ga.add_argument("--no-stills", action="store_true")
    ga.add_argument("--gpu", default="auto", choices=["auto", "software", "hardware"])

    ca = sub.add_parser("catalog")
    ca.add_argument("--write", action="store_true", help="refresh the derived fields (props from the declarations, beat types from tokens)")

    go = sub.add_parser("golden")
    go.add_argument("--plan", required=True)
    go.add_argument("--out", required=True, help="the output folder (project/, golden.mp4, contact-sheet.png, README.md)")
    go.add_argument("--voice", required=True, help="the voiceover wav")
    go.add_argument("--words", default="", help="words.json (for the README's timeline)")
    go.add_argument("--assets", default="", help="a folder of research assets referenced by the plan as research/<file>")
    go.add_argument("--brand", default="", help="library/brand (default: config paths)")
    go.add_argument("--no-render", action="store_true")
    go.add_argument("--quality", default="looks")
    go.add_argument("--gpu", default="auto", choices=["auto", "software", "hardware"])

    gp = sub.add_parser("golden-plan")
    gp.add_argument("--script", required=True)
    gp.add_argument("--words", required=True)
    gp.add_argument("--out", required=True)
    gp.add_argument("--idea-id", default="")

    wg = sub.add_parser("webgl")
    wg.add_argument("--out", default="")

    ev = sub.add_parser("events")
    ev.add_argument("component")
    ev.add_argument("--props", default="{}")

    a = ap.parse_args(argv)
    if a.cmd == "frame-match":
        from motion import framematch
        return framematch.run(a)
    if a.cmd == "stills":
        from motion import gallery
        return gallery.run_stills(a)
    if a.cmd == "gallery":
        from motion import gallery
        return gallery.run_gallery(a)
    if a.cmd == "catalog":
        from motion import catalog
        return catalog.run(a)
    if a.cmd == "golden":
        from motion import golden
        return golden.run(a)
    if a.cmd == "golden-plan":
        from motion import goldenplan
        return goldenplan.run(a)
    if a.cmd == "webgl":
        from motion import webgl
        return webgl.run(a)
    if a.cmd == "events":
        import json
        from motion import harness
        path = os.path.join(common.motion_lib_dir(), "compositions", a.component + ".html")
        if not os.path.isfile(path):
            path = os.path.join(common.motion_lib_dir(), "candidates", a.component + ".html")
        comp = common.parse_component(path)
        with harness.Harness() as h:
            res = h.measure(comp, json.loads(a.props), [0.0], ["#root"])
        for e in res["events"]:
            print(json.dumps(e, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
