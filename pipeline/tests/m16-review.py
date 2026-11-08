#!/usr/bin/env python
"""m16-review.py: S12's M16 additions (test-m16 section 5): the energy check, the liveness checks and the early stop. No model call.
Prints `<name> ok` or `<name> FAIL <why>`.

  python pipeline/tests/m16-review.py <work dir> [--golden golden/test-idea]

  energy check   on the golden reel's own render: the reel and every scene pass; on a planted copy with one scene frozen
                 (ffmpeg freezeframes over s5): only that scene fails, with its numbers, tagged [animation], routed to 09a-animations;
                 on a video of one still frame: every scene fails and the reel too
  liveness       S12's mechanical checks on the compiled golden project: no element static, the edge layer present, nothing else; planted
                 copies: a component that never moves is caught ([animation] element_static), a canvas without its edge layer
                 ([animation] edge_layer)
  verdict        the energy report enters the verdict (checks_pass false, the issue routed to 9a); the edit review's energy score counts
                 (a 3 fails the round); an answer without the score (an older record) counts as a pass on it
  early stop     the same scores and the same issues in two rounds in a row end the loop (verdict stop, a NEEDS REVIEW flag); other scores
                 or other issues, or round 1, do not; review.early_stop false switches it off
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE)).replace("\\", "/")
sys.path.insert(0, os.path.join(REPO, "pipeline", "lib"))

from review import common as rc, energy_check, route  # noqa: E402


def say(name, ok, detail=""):
    print(name, "ok" if ok else f"FAIL {detail}", flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def cli(*args: str) -> subprocess.CompletedProcess:
    return run([sys.executable, os.path.join(REPO, "pipeline", "lib", "review"), *args], cwd=REPO)


def last_json(text: str) -> dict:
    for line in reversed((text or "").strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    return {}


def make_run(work: str, golden: str) -> str:
    rd = os.path.join(work, "run")
    r = run([sys.executable, os.path.join(REPO, "pipeline", "tests", "m15-mkrun.py"), rd, "--plan", os.path.join(golden, "plan.json")], cwd=REPO)
    if r.returncode != 0:
        raise SystemExit("m15-mkrun failed: " + (r.stdout + r.stderr)[-500:])
    return rd


def put_draft(rd: str, video: str) -> None:
    os.makedirs(os.path.join(rd, "10-build"), exist_ok=True)
    for dst in (os.path.join(rd, "10-build", "draft.mp4"),):
        shutil.copy2(video, dst)
    shutil.rmtree(os.path.join(rd, "11-sfx"), ignore_errors=True)


def energy_run(rd: str) -> dict:
    stage = os.path.join(rd, "12-review")
    os.makedirs(stage, exist_ok=True)
    r = cli("energy-check", "--run-dir", rd, "--stage-dir", stage)
    if r.returncode != 0:
        print(r.stdout[-600:], r.stderr[-600:])
    return json.load(open(os.path.join(stage, "energy.json"), encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--golden", default=os.path.join(REPO, "golden", "test-idea"))
    a = ap.parse_args()
    work = os.path.abspath(a.work).replace("\\", "/")
    os.makedirs(work, exist_ok=True)
    golden = a.golden
    video = os.path.join(golden, "golden.mp4")
    if not os.path.isfile(video):
        print("golden.mp4 is missing: bash pipeline/bin/render-golden first")
        return 1
    rd = make_run(work, golden)
    plan = json.load(open(os.path.join(rd, "10-build", "plan.json"), encoding="utf-8"))

    # ---------------------------------------------------------------- the energy check
    put_draft(rd, video)
    rep = energy_run(rd)
    say("energy-golden-passes", rep["pass"] and not rep["issues"], [i["text"][:160] for i in rep["issues"]] or rep.get("check"))
    say("energy-golden-whole-meets-every-target", rep["check"]["pass"], rep["check"]["checks"])
    say("energy-scene-bounds-are-80-percent", abs(rep["scene_bounds"]["moving_share_pct"] - rep["targets"]["moving_share_pct"] * 0.8) < 0.01 and abs(rep["scene_bounds"]["longest_still_s"] - rep["targets"]["longest_still_s"] / 0.8) < 0.01, rep["scene_bounds"])
    s5 = next(s for s in plan["scenes"] if s["id"] == "s5")
    f0, f1 = int(round(s5["start_ms"] * 30 / 1000)), int(round(s5["end_ms"] * 30 / 1000)) - 1
    frozen = os.path.join(work, "frozen-s5.mp4")
    r = run(["ffmpeg", "-v", "error", "-y", "-i", video, "-filter_complex", f"[0:v]split[a][b];[a][b]freezeframes=first={f0 + 4}:last={f1}:replace={f0 + 4}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", frozen])
    say("energy-planted-copy-made", r.returncode == 0 and os.path.isfile(frozen), r.stderr[-300:])
    put_draft(rd, frozen)
    rep2 = energy_run(rd)
    say("energy-frozen-scene-fails", not rep2["pass"] and rep2["failing_scenes"] == ["s5"], rep2["failing_scenes"])
    i0 = rep2["issues"][0] if rep2["issues"] else {}
    say("energy-issue-is-animation-with-numbers", i0.get("tag") == "animation" and i0.get("kind") == "energy" and i0.get("scene") == "s5" and re.search(r"moving share [0-9.]+%", i0.get("text", "")) and "scene s5" in i0.get("text", ""), i0.get("text"))
    ctx = rc.Ctx(rd, os.path.join(rd, "12-review"))
    rev = route.decide(ctx, 1, {"pass": True, "issues": []}, {"pass": True, "issues": []}, {"pass": True, "issues": []}, None, rep2)
    say("energy-routes-to-09a", rev["verdict"] == "fix" and rev["routing"]["owners"] == ["09a-animations"] and rev["routing"]["reopen"][0] == "09a-animations" and not rev["pass"], rev["routing"])
    say("energy-in-the-review-record", rev["energy"] and rev["energy"]["failing_scenes"] == ["s5"] and rev["energy"]["pass"] is False, rev.get("energy"))
    still = os.path.join(work, "still.mp4")
    r = run(["ffmpeg", "-v", "error", "-y", "-ss", "5", "-i", video, "-frames:v", "1", os.path.join(work, "still.png")])
    r = run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-i", os.path.join(work, "still.png"), "-t", str(plan["duration_ms"] / 1000), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", still])
    put_draft(rd, still)
    rep3 = energy_run(rd)
    body = [s["id"] for s in plan["scenes"] if s.get("beat_type") not in energy_check.EXEMPT_BEATS]
    say("energy-still-video-fails-everywhere", not rep3["pass"] and sorted(rep3["failing_scenes"]) == sorted(body) and not rep3["check"]["pass"], rep3["failing_scenes"])
    say("energy-ask-scene-left-out-of-the-routing", "s11" not in rep3["failing_scenes"] and any(s.get("scene_check", {}).get("exempt") for s in rep3["scenes"] if s.get("beat_type") == "ask"), "")
    say("energy-still-video-meter-reads-zero", (rep3["whole"].get("moving_share_pct") or 0) < 2, rep3["whole"].get("moving_share_pct"))
    put_draft(rd, video)

    # ---------------------------------------------------------------- the liveness checks (mechanical)
    mech_dir = os.path.join(rd, "12-review")
    r = cli("mechanical", "--run-dir", rd, "--stage-dir", mech_dir, "--no-cache")
    mj = json.load(open(os.path.join(mech_dir, "mechanical.json"), encoding="utf-8"))
    kinds = sorted({i["kind"] for i in mj["issues"]})
    say("liveness-golden-clean", mj["pass"] and not mj["issues"], [(i["kind"], i["text"][:140]) for i in mj["issues"]][:6])
    say("liveness-counted", mj["counts"].get("static_checked", 0) > 20 and mj["counts"].get("edge_elements", 0) >= 4, mj["counts"])
    proj = os.path.join(rd, "10-build", "project")
    index = os.path.join(proj, "index.html")
    orig = open(index, encoding="utf-8").read()
    # a component that never moves
    comp_html = '''<html data-composition-variables='[]'><template><div id="root" data-composition-id="frozen-box" data-width="1080" data-height="1920"><div id="fb" style="position:absolute;left:100px;top:800px;width:300px;height:100px;background:#1C110F"></div></div>
<script src="assets/vendor/gsap.min.js"></script><script>window.__timelines = window.__timelines || {}; window.__timelines["frozen-box"] = gsap.timeline({ paused: true });</script></template></html>'''
    open(os.path.join(proj, "compositions", "frozen-box.html"), "w", encoding="utf-8").write(comp_html)
    host = re.search(r'      <div id="s5-[^"]+" class="clip"[^\n]*></div>\n', orig)
    s5_start = s5["start_ms"] / 1000
    new_host = (f'      <div id="s5-frozen-9" class="clip" data-composition-id="s5-frozen-9" data-composition-src="compositions/frozen-box.html" data-start="{s5_start:.3f}" data-duration="3.000" '
                f'data-track-index="1" data-width="1080" data-height="1920" data-scene="s5" data-beat="b5" data-component="frozen-box" style="z-index: 2" data-variable-values=\'{{}}\'></div>\n')
    if host:
        open(index, "w", encoding="utf-8").write(orig.replace(host.group(0), host.group(0) + new_host, 1))
    r = cli("mechanical", "--run-dir", rd, "--stage-dir", mech_dir, "--no-cache")
    mj2 = json.load(open(os.path.join(mech_dir, "mechanical.json"), encoding="utf-8"))
    st = [i for i in mj2["issues"] if i["kind"] == "element_static"]
    say("liveness-static-element-caught", bool(host) and bool(st) and st[0]["tag"] == "animation" and st[0]["instance"] == "s5-frozen-9" and "0.5" in st[0]["text"] or "does not move" in (st[0]["text"] if st else ""), [(i["kind"], i["text"][:120]) for i in mj2["issues"]][:4])
    # a canvas without its edge layer
    open(index, "w", encoding="utf-8").write(orig)
    os.remove(os.path.join(proj, "compositions", "frozen-box.html"))
    m = re.search(r'(<div id="paper-canvas"[^>]*data-variable-values=\')([^\']*)(\')', orig)
    props = json.loads(m.group(2).replace("&amp;", "&").replace("&#39;", "'")) if m else {}
    props["edges"] = 0
    open(index, "w", encoding="utf-8").write(orig.replace(m.group(0), m.group(1) + json.dumps(props) + m.group(3), 1) if m else orig)
    r = cli("mechanical", "--run-dir", rd, "--stage-dir", mech_dir, "--no-cache")
    mj3 = json.load(open(os.path.join(mech_dir, "mechanical.json"), encoding="utf-8"))
    ed = [i for i in mj3["issues"] if i["kind"] == "edge_layer"]
    say("liveness-missing-edge-layer-caught", bool(m) and bool(ed) and ed[0]["tag"] == "animation" and "E5" in ed[0]["text"], [(i["kind"], i["text"][:120]) for i in mj3["issues"]][:4])
    open(index, "w", encoding="utf-8").write(orig)

    # ---------------------------------------------------------------- the verdict: the energy score and the early stop
    ctx = rc.Ctx(rd, os.path.join(work, "stage"))
    os.makedirs(ctx.stage_dir, exist_ok=True)
    ok = {"pass": True, "issues": []}
    keys = route.SCORE_KEYS
    good = {k: 4 for k in keys}
    answer = {"scores": dict(good, energy=3), "branding_natural": True, "issues": [{"tag": "animation", "text": "s3 stands still", "scene": "s3"}], "summary": "ok"}
    rev1 = route.decide(ctx, 1, ok, ok, ok, answer, {"pass": True, "issues": []})
    say("score-energy-is-scored", "energy" in keys and rev1["edit_review"]["scores"]["energy"] == 3 and "energy" in rev1["summary"]["low_scores"] and rev1["verdict"] == "fix", rev1["summary"])
    legacy = {"scores": {k: 4 for k in keys if k != "energy"}, "branding_natural": True, "issues": [], "summary": "ok"}
    revl = route.decide(ctx, 1, ok, ok, ok, legacy, None)
    say("score-energy-missing-counts-as-pass", revl["pass"] and revl["edit_review"]["scores"]["energy"] == 5, revl["edit_review"]["scores"])
    rc.write_json(os.path.join(ctx.stage_dir, "review-r1.json"), rev1)
    rev2 = route.decide(ctx, 2, ok, ok, ok, copy.deepcopy(answer), {"pass": True, "issues": []})
    say("early-stop-same-scores-same-issues", rev2["verdict"] == "stop" and rev2["early_stop"]["stop"] and rev2["flags"] and "early stop" in rev2["flags"][0] and not rev2["routing"]["reopen"], (rev2["verdict"], rev2["early_stop"]))
    say("early-stop-flag-names-the-scores", "variety 4" in rev2["flags"][0] and "energy 3" in rev2["flags"][0], rev2["flags"])
    answer_b = copy.deepcopy(answer); answer_b["scores"]["variety"] = 3
    rev2b = route.decide(ctx, 2, ok, ok, ok, answer_b, {"pass": True, "issues": []})
    say("no-early-stop-when-the-scores-change", rev2b["verdict"] == "fix" and not rev2b["early_stop"]["stop"], rev2b["early_stop"])
    answer_c = copy.deepcopy(answer); answer_c["issues"] = [{"tag": "animation", "text": "s6 stands still", "scene": "s6"}]
    rev2c = route.decide(ctx, 2, ok, ok, ok, answer_c, {"pass": True, "issues": []})
    say("no-early-stop-when-the-issues-change", rev2c["verdict"] == "fix", rev2c["early_stop"])
    revr1 = route.decide(ctx, 1, ok, ok, ok, copy.deepcopy(answer), {"pass": True, "issues": []})
    say("no-early-stop-in-round-1", revr1["verdict"] == "fix", revr1["early_stop"])
    ctx.config.setdefault("review", {})["early_stop"] = False
    rev2d = route.decide(ctx, 2, ok, ok, ok, copy.deepcopy(answer), {"pass": True, "issues": []})
    say("early-stop-can-be-switched-off", rev2d["verdict"] == "fix", rev2d["early_stop"])
    # through the CLI, the way the stage runs it
    stage = os.path.join(work, "cli-stage")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    for n in ("mechanical", "style", "audio", "energy"):
        rc.write_json(os.path.join(stage, n + ".json"), {"pass": True, "issues": [], "counts": {}})
    ans = os.path.join(work, "answer.json")
    rc.write_json(ans, answer)
    o1 = last_json(cli("verdict", "--run-dir", rd, "--stage-dir", stage, "--round", "1", "--answer", ans).stdout)
    o2 = last_json(cli("verdict", "--run-dir", rd, "--stage-dir", stage, "--round", "2", "--answer", ans).stdout)
    say("cli-round-1-fix", o1.get("verdict") == "fix" and o1.get("early_stop") is False, o1)
    say("cli-round-2-stop", o2.get("verdict") == "stop" and o2.get("early_stop") is True and o2.get("flags"), o2)
    run_sh = open(os.path.join(REPO, "pipeline", "stages", "12-review", "run.sh"), encoding="utf-8").read()
    say("run-sh-handles-stop-and-runs-the-energy-check-first", "cap|flag|stop)" in run_sh and run_sh.index("energy-check") < run_sh.index('"$LIB/review" mechanical'), "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
