"""pipeline/lib/review/energy_check.py: the energy check of S12 (BUILD_SPEC.md S12 "Energy check", Motion and energy rules E0 and E9, M16).

It runs first and needs no model: the mixed draft (11-sfx/draft_mixed.mp4, else the silent draft) is measured as a whole and scene by
scene (the scene times of the merged plan, 10-build/plan.json) with review/energy.py against tokens.json energy.targets. The reel
must meet every target. A scene must reach config review.energy_scene_share (0.8) of every lower bound (the moving share, the middle
band, the pixels changing) and stay within 1 / share of every upper bound (the still share, the longest still): the golden reel is held
to the same number (BUILD_SPEC.md M16). The ask scene is left out of the per-scene routing (its content is fixed by the branding rules; it counts in the reel's numbers). A failing scene becomes an [animation] issue carrying its numbers and goes back to 9a; when
the reel fails as a whole and no scene does, one reel-level [animation] issue says which measures are short.

  run(ctx, out_path) -> the report written to 12-review/energy.json: {pass, whole, targets, scenes: [...], failing_scenes, issues}
  scene_targets(targets, share) -> the per-scene bounds
  scene_issues(rep, share) -> the issues of a measured report (used by the test on the golden reel)
"""
from __future__ import annotations

import os

from review import common as rc
from review import energy

EXEMPT_BEATS = ("ask",)  # the CTA: the end card, the DM card and the lockup are placed by tweaks.md Branding, so no scene fix can move it
MIN_SCENE_S = 1.0  # a scene shorter than this has too few frames to say anything about its energy

NAMES = {"moving_share_pct": "moving share", "middle_moving_share_pct": "middle band", "pixels_changing_pct": "pixels changing",
         "still_share_pct": "still stretches", "longest_still_s": "longest still"}
UNITS = {"moving_share_pct": "%", "middle_moving_share_pct": "%", "pixels_changing_pct": "%", "still_share_pct": "%", "longest_still_s": " s"}
HINTS = {"moving_share_pct": "more of the frames must carry real motion (a recording or a clip playing in a card, a camera move, a fan or a grid building, a count or typing)",
         "middle_moving_share_pct": "the middle of the screen must move: put the moving content (a recording, a zoom over a page, a stack) in the hero zone",
         "pixels_changing_pct": "more of the picture must change from frame to frame: a bigger moving card, a second moving layer, content that plays inside the card",
         "still_share_pct": "no stretch of a second or more may stand still: a scene change or a new element should land inside it",
         "longest_still_s": "no stretch of a second or more may stand still: a scene change or a new element should land inside it"}


def scene_targets(targets: dict, share: float) -> dict:
    """The per-scene bounds: lower bounds times share, upper bounds divided by it."""
    out = {}
    for name, direction, _nd in energy.MEASURES:
        want = targets.get(name)
        if want is None:
            continue
        out[name] = round(want * share, 3) if direction == "min" else round(want / share, 3)
    return out


def fmt(v) -> str:
    return "?" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


def scene_issue_text(entry: dict, bad: dict, bounds: dict) -> str:
    parts = []
    for name, c in bad.items():
        parts.append(f"{NAMES[name]} {fmt(c['got'])}{UNITS[name]} ({c['direction']} {fmt(bounds[name])}{UNITS[name]})")
    hint = next((HINTS[n] for n in bad if n in HINTS), "")
    where = f"scene {entry.get('id')} ({entry.get('beat_type')}, {entry['start_ms'] / 1000:.1f} to {entry['end_ms'] / 1000:.1f} s)"
    return f"{where} lacks energy: " + ", ".join(parts) + (f"; {hint}" if hint else "")


def scene_issues(rep: dict, share: float) -> list[dict]:
    bounds = scene_targets(rep["targets"], share)
    out = []
    for s in rep.get("scenes", []):
        m = s.get("measures") or {}
        if not m.get("frames") or m["frames"] < MIN_SCENE_S * energy.FPS:
            continue
        if s.get("beat_type") in EXEMPT_BEATS:
            s["scene_check"] = {"pass": None, "exempt": "the ask scene's content is fixed by the branding rules (tweaks.md): it counts in the reel's numbers only"}
            continue
        chk = energy.check_targets(m, bounds)
        bad = {k: v for k, v in chk["checks"].items() if not v["ok"]}
        s["scene_check"] = {"pass": not bad, "bounds": bounds, "failing": sorted(bad)}
        if bad:
            out.append(rc.issue("animation", "energy", scene_issue_text(s, bad, bounds), s.get("id") or "", "", s["start_ms"], severity="major",
                                measures={k: v["got"] for k, v in bad.items()}))
    return out


def run(ctx: rc.Ctx, out_path: str) -> dict:
    if not ctx.c("review.energy_check", True):
        out = {"written_by": "12-review", "pass": True, "skipped": "config review.energy_check is off", "whole": {}, "targets": {}, "check": {"pass": True, "checks": {}},
               "scenes": [], "failing_scenes": [], "issues": []}
        rc.write_json(out_path, out)
        return out
    video = ctx.draft_mixed if os.path.isfile(ctx.draft_mixed) else ctx.draft
    if not os.path.isfile(video):
        raise FileNotFoundError(f"no draft to measure: {ctx.draft_mixed} and {ctx.draft} are missing")
    share = float(ctx.c("review.energy_scene_share", 0.8))
    rep = energy.measure_video(video, plan=ctx.plan, tokens=ctx.toks)
    issues = scene_issues(rep, share)
    whole_bad = {k: v for k, v in rep["check"]["checks"].items() if not v["ok"]}
    if whole_bad and not issues:
        parts = ", ".join(f"{NAMES[k]} {fmt(v['got'])}{UNITS[k]} ({v['direction']} {fmt(v['want'])}{UNITS[k]})" for k, v in whole_bad.items())
        hint = next((HINTS[n] for n in whole_bad if n in HINTS), "")
        issues.append(rc.issue("animation", "energy_reel", f"the reel as a whole lacks energy: {parts}; {hint}", "", "", None, severity="major", measures={k: v["got"] for k, v in whole_bad.items()}))
    passed = not whole_bad and not issues
    out = {"written_by": "12-review", "video": rc.mixed(video), "pass": passed, "whole": rep["whole"], "targets": rep["targets"], "scene_share": share,
           "scene_bounds": scene_targets(rep["targets"], share), "check": rep["check"], "scenes": rep["scenes"], "failing_scenes": [i["scene"] for i in issues if i.get("scene")],
           "issues": issues, "still_stretches": rep.get("still_stretches", [])}
    rc.write_json(out_path, out)
    return out
