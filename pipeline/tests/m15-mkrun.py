#!/usr/bin/env python
"""m15-mkrun.py: a review-ready run folder for test-m15 (M15): the frozen test-idea run with its 10-build/plan.json replaced by
the golden plan (word mode in normal talk, caption groups on the beats without text) and 10-build/project built from it by
the project compiler (pipeline/lib/motion/golden.py build_project). The mechanical checks of S12 then run on it
(`python pipeline/lib/review mechanical --run-dir <run_dir>`).

  python pipeline/tests/m15-mkrun.py <out_run_dir> [--plan plan.json]     a copy of the frozen run, the golden plan (or --plan) built into it
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "pipeline", "lib"))

from motion import golden  # noqa: E402
from visual import common  # noqa: E402


def main() -> int:
    common.setup_streams()
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--plan", default=os.path.join(REPO, "golden", "test-idea", "plan.json"))
    a = ap.parse_args()
    out = common.mixed(a.out)
    src = os.path.join(REPO, "pipeline", "tests", "fixtures", "runs", "test-idea")
    golden.reset_dir(out)
    for name in os.listdir(src):
        if name in ("11-sfx", "12-review"):
            continue
        s, d = os.path.join(src, name), os.path.join(out, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    plan = common.load_json(a.plan)
    stage = os.path.join(out, "10-build")
    cat = common.catalog()
    common.write_json(os.path.join(stage, "plan.json"), plan)
    golden.build_project(plan, stage, None, common.brand_dir(), os.path.join(out, "01-research", "assets"), common.motion_lib(), cat, folder="project",
                         meta_id="reel-m15", title="reel m15")
    print(f"run folder {out}: plan {os.path.basename(a.plan)}, {len(plan.get('captions', []))} caption entries, project built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
