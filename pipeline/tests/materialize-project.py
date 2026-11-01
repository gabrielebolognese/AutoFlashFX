#!/usr/bin/env python
"""materialize-project.py: rebuild a run's HyperFrames project folders from the frozen plans (M11 tests).

The frozen fixtures under pipeline/tests/fixtures/runs/test-idea/10-build/ keep only the project's index.html and
instances.json (the compositions and assets are the motion library's, copied in by the compiler). A test that starts
from the frozen build needs the full folders (S11 reads the hook 2 project's events, S12 mounts the compositions), so
this script runs the same compiler (pipeline/lib/motion/golden.py build_project) on 10-build/plan.json and
10-build/hook2/plan.json, then checks that the rebuilt index.html matches the frozen one.

  python pipeline/tests/materialize-project.py <run_dir> [--render-missing]   exit 0 when both projects were built and index.html
                                                                            matches; --render-missing renders draft.mp4 and hook2.mp4 when absent
"""
from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(HERE), "lib")
sys.path.insert(0, LIB)

from motion import golden  # noqa: E402
from visual import common  # noqa: E402


def main() -> int:
    common.setup_streams()
    run_dir = common.mixed(sys.argv[1])
    stage = os.path.join(run_dir, "10-build")
    cat = common.catalog()
    lib = common.motion_lib()
    assets = os.path.join(run_dir, "01-research", "assets")
    ok = True
    for folder, plan_rel in (("project", "plan.json"), ("hook2", os.path.join("hook2", "plan.json"))):
        plan_path = os.path.join(stage, plan_rel)
        if not os.path.isfile(plan_path):
            print(f"{folder}: no {plan_rel}, skipped")
            continue
        plan = common.load_json(plan_path)
        frozen_index = os.path.join(stage, folder, "index.html")
        frozen = open(frozen_index, encoding="utf-8").read() if os.path.isfile(frozen_index) else None
        keep = os.path.join(stage, folder + ".frozen.json")
        if folder == "hook2":
            golden.apply_transitions(plan, cat)
        info = golden.build_project(plan, stage, None, common.brand_dir(), assets, lib, cat, folder=folder,
                                    meta_id=(f"reel-{plan.get('idea_id', 'idea')}" if folder == "project" else f"hook2-{plan.get('idea_id', 'idea')}"),
                                    title=(f"reel {plan.get('idea_id', '')}" if folder == "project" else "hook 2 clip"))
        if folder == "hook2":
            common.write_json(os.path.join(stage, "hook2", "plan.json"), plan)
        rebuilt = open(os.path.join(stage, folder, "index.html"), encoding="utf-8").read()
        same = frozen is None or rebuilt == frozen
        if frozen is not None and not same:
            # the frozen file wins: it is what S10 produced; the compositions and assets come from the rebuild
            with open(os.path.join(stage, folder, "index.html"), "w", encoding="utf-8", newline="\n") as f:
                f.write(frozen)
        print(f"{folder}: {info['hosts']} hosts, assets {', '.join(info['assets']) or 'none'}; index.html {'matches the frozen one' if same else 'DIFFERS from the frozen one (kept the frozen)'}")
        ok = ok and same
        if os.path.isfile(keep):
            os.remove(keep)
    if "--render-missing" in sys.argv:
        # the drafts are not in git (*.mp4): render them when the fixtures lack them (about 2 minutes)
        from visual import project
        build = common.load_json(os.path.join(stage, "build.json")) if os.path.isfile(os.path.join(stage, "build.json")) else {}
        flag = build.get("render_flag", "") or ""
        for folder, mp4 in (("project", "draft.mp4"), ("hook2", "hook2.mp4")):
            out = os.path.join(stage, mp4)
            if os.path.isfile(out) or not os.path.isdir(os.path.join(stage, folder)):
                continue
            info = project.render_scaled(os.path.join(stage, folder), out, "draft", flag, 20, 3600)
            print(f"{mp4}: rendered ({info.get('stage')}, {info.get('seconds')} s)")
            if info.get("stage") != "done":
                ok = False
        sheet = os.path.join(stage, "contact-sheet.png")
        if not os.path.isfile(sheet) and os.path.isfile(os.path.join(stage, "draft.mp4")):
            golden.contact_sheet(os.path.join(stage, "draft.mp4"), common.load_json(os.path.join(stage, "plan.json")), sheet)
            print("contact-sheet.png: made")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
