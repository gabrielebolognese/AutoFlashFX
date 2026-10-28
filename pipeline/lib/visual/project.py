"""pipeline/lib/visual/project.py: S10, build visuals and the draft render (BUILD_SPEC.md S10). The merged plan of S9 is
compiled into a HyperFrames project built from the motion library (pipeline/lib/motion/golden.py build_project: one
host per component instance, the captions once, tokens.css, the logos as image files with their aspect ratio
locked, the plan's transitions as exit props), checked with `npx hyperframes check --json`, measured for its sound
events (visual/events.py), rendered as a silent draft at the draft resolution (540x960, same timing and fps), and
summarized in a contact sheet; the hook 2 alternate clip is built and rendered the same way (3.5 s at most).

  python pipeline/lib/visual build --run-dir DIR --stage-dir DIR/10-build --step compile|check|finish|all [--plan merged.json]
      compile: merge and validate the plan, replace 3D when WebGL is missing, compile project/, run the check
               exit 0 ok, 5 when the check reports errors (the stage calls the builder model to repair the project,
               then --step check), 1 on a code error
      check:   run the check again (after a repair); exit 0 or 5
      finish:  events.json, the draft, the hook 2 clip, the contact sheet, build.json; exit 0, 2 on a render failure
  Progress lines for the stage script: "@@ACTIVITY text", "@@SAY TAG text", "@@FLAG text", "@@ERROR text".
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess

from motion import golden
from visual import common, plan_merge, plan_validate

DRAFT_W, DRAFT_H = 540, 960


def say(tag: str, text: str) -> None:
    print(f"@@SAY {tag} {common.undash(text)}", flush=True)


def activity(text: str) -> None:
    print(f"@@ACTIVITY {text}", flush=True)


def flag(text: str) -> None:
    print(f"@@FLAG {common.undash(text)}", flush=True)


def error(text: str) -> None:
    print(f"@@ERROR {common.undash(text)}", flush=True)


def webgl_info(lib: str) -> dict:
    p = os.path.join(lib, "webgl.json")
    if os.path.isfile(p):
        try:
            return common.load_json(p)
        except ValueError:
            pass
    return {"webgl": None, "render_flag": ""}


def replace_3d(plan: dict, cat_by_id: dict) -> list[str]:
    """Without WebGL the 3D beats become 2D components (BUILD_SPEC.md S10): a card popping in with the object's label."""
    replaced = []
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            entry = cat_by_id.get(c["component"], {})
            if entry.get("kind") != "3d" or entry.get("fallback") == "css":
                continue  # icon-3d draws its CSS-extruded fallback itself (M14)
            p = c.get("props", {})
            label = str(p.get("label") or "").strip()
            w = float(p.get("w", 600) or 600)
            new_props = {"x": float(p.get("x", 240)), "y": float(p.get("y", 560)) + 60, "w": w, "title": label or " ", "body": "", "enter": "pop", "enter_at": float(p.get("enter_at", 0) or 0), "align": "center"}
            replaced.append(c["id"])
            c["component"] = "card"
            c["props"] = new_props
            c["role"] = c.get("role") or "set-piece"
    return replaced


def three_d_count(plan: dict, cat_by_id: dict) -> int:
    return sum(1 for s in plan.get("scenes", []) for c in s.get("components", []) if cat_by_id.get(c["component"], {}).get("kind") == "3d")


def ffmpeg_downscale(src: str, dst: str, crf: int, timeout: int) -> dict:
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"scale={DRAFT_W}:{DRAFT_H}:flags=lanczos", "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    return {"rc": proc.returncode, "stderr": (proc.stderr or "")[-800:]}


def render_scaled(project: str, out_mp4: str, quality: str, gpu_flag: str, crf: int, timeout: int) -> dict:
    """A HyperFrames render at the composition's size, then the draft size with ffmpeg (the CLI renders presets only)."""
    full = out_mp4[:-4] + ".full.mp4"
    t0 = dt.datetime.now()
    info = golden.render(project, full, quality, gpu_flag, timeout=timeout)
    if info["rc"] != 0 or not os.path.isfile(full):
        info["stage"] = "render"
        return info
    sc = ffmpeg_downscale(full, out_mp4, crf, max(120, timeout // 4))
    try:
        os.remove(full)
    except OSError:
        pass
    if sc["rc"] != 0 or not os.path.isfile(out_mp4):
        return {"rc": sc["rc"] or 1, "stage": "scale", "stderr": sc["stderr"], "seconds": round((dt.datetime.now() - t0).total_seconds(), 1)}
    info["seconds"] = round((dt.datetime.now() - t0).total_seconds(), 1)
    info["probe"] = golden.probe(out_mp4)
    info["stage"] = "done"
    return info


def hook2_plan(plan: dict, inp: common.Inputs, toks: dict, config: dict) -> dict | None:
    """The alternate clip: the hook scene's visuals with hook 2's headline and timing, 3.5 s at most."""
    if not inp.words_hook2 or not plan.get("hook2"):
        return None
    tl2 = common.Timeline(inp.words_hook2)
    hook = next((s for s in plan["scenes"] if s.get("beat_type") == "hook"), None)
    if not hook or not tl2.words:
        return None
    max_ms = int(float(common.cfg(config, "visual.hook2_max_s", 3.5)) * 1000)
    hold = int(common.cfg(config, "visual.hook2_hold_ms", 800))
    last_end = max(int(w["end_ms"]) for w in tl2.words)
    dur = min(max_ms, max(last_end + hold, tl2.duration_ms))
    hook_words = [w for w in common.Timeline(inp.words).beat_words(hook["beat"])] if inp.words else []
    hook_last = max([int(w["end_ms"]) for w in hook_words] + [0])
    comps = []
    h2 = plan["hook2"]
    for c in hook["components"]:
        nc = json.loads(json.dumps(c))
        nc["id"] = "h2-" + c["id"]
        p = nc["props"]
        p.pop("exit", None); p.pop("exit_at", None); p.pop("clip_start", None)
        if c["component"] == "headline":
            p["lines_json"] = list(h2.get("lines", []))
            if h2.get("kicker"):
                p["kicker"] = str(h2["kicker"])
            p["words_json"] = [{"w": w["word"], "t": round(int(w["start_ms"]) / 1000, 3)} for w in tl2.words]
            nc["start_ms"], nc["end_ms"] = 0, dur
        else:
            offset = int(c["start_ms"]) - hook_last  # keep the set piece's distance from the last spoken word
            start = max(0, min(last_end + offset, dur - 500))
            nc["start_ms"], nc["end_ms"] = int(start), dur
        nc["land_ms"] = nc["start_ms"] + common.frames_ms(common.enter_frames(c["component"], p))
        comps.append(nc)
    scene = {"id": "h2", "beat": "hook2", "beat_type": "hook", "start_ms": 0, "end_ms": dur, "set_piece": bool(h2.get("set_piece", True)),
             "hook_set_piece": bool(h2.get("set_piece", True)), "honesty_label": None, "emphasis_hits": [], "components": comps}
    return {"plan_version": 1, "style": plan.get("style", "paper-cards"), "idea_id": plan.get("idea_id", ""), "source": "10-build hook2", "fps": common.FPS,
            "duration_ms": dur, "voice": "08-voiceover/vo_hook2.wav", "solution": plan.get("solution", {"type": "none"}), "tracker": plan.get("tracker", {"enabled": False}),
            "branding": plan.get("branding"), "scenes": [scene], "captions": [], "cards": [], "labels": [], "transitions": [],
            "notes": "the hook 2 alternate clip: the hook scene with hook 2's headline, timed to words_hook2.json"}


def check_errors(info: dict) -> list[str]:
    out = []
    for sec, s in info.get("sections", {}).items():
        for f in s.get("findings", []):
            if f.get("severity") == "error":
                out.append(f"{sec}: {f.get('code')}: {f.get('message')}")
    if not info.get("ok") and not out:
        out.append("hyperframes check reported not ok without an error finding (see check.json)")
    return out


def write_build_json(stage_dir: str, data: dict) -> None:
    p = os.path.join(stage_dir, "build.json")
    cur = common.load_json(p) if os.path.isfile(p) else {}
    cur.update(data)
    cur["written_by"] = "10-build"
    cur["updated"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    common.write_json(p, cur)


# ------------------------------------------------------------------------------------------------ the steps

def step_compile(args, inp: common.Inputs, toks: dict, cat: dict, lib: str) -> int:
    stage_dir = common.mixed(args.stage_dir)
    os.makedirs(stage_dir, exist_ok=True)
    by_id = common.catalog_by_id(cat)
    activity("building visuals")
    if args.plan:
        plan = common.load_json(args.plan)
    else:
        try:
            plan = plan_merge.merge_run(args.run_dir, toks)
        except common.PlanError as exc:
            error(f"cannot merge the plans: {exc}")
            return 1
    ctx = plan_validate.Context.from_run(args.run_dir, config=inp.config, toks=toks, cat=cat)
    res = plan_validate.validate(plan, ctx)
    if not res["ok"]:
        for e in res["errors"][:8]:
            print(f"plan: rule={e['rule']}: {e['message']}")
        error(f"the merged plan fails the validator ({res['errors'][0]['rule']}: {res['errors'][0]['message'][:140]}); the plan stages passed it, so the code changed under them")
        return 1
    wg = webgl_info(lib)
    flags = []
    n3d = three_d_count(plan, by_id)
    if n3d and wg.get("webgl") is False:
        replaced = replace_3d(plan, by_id)
        flags.append(f"3D beats replaced with 2D cards ({', '.join(replaced)}): WebGL is not available in headless Chrome on this PC (motion-lib/webgl.json)")
    # the director's wishlist (a component the library lacks) was flagged by 9a already (visual.sh); S10 only records it
    wishlist = [str(w.get("name")) for w in (plan.get("wishlist", []) or []) if isinstance(w, dict) and w.get("name")]
    for f in flags:
        flag(f)
    role = "builder"
    heavy = int(common.cfg(inp.config, "visual.three_d_heavy_objects", 2))
    review_rounds = 0
    state_path = os.path.join(args.run_dir, "state.json")
    if os.path.isfile(state_path):
        try:
            review_rounds = int((common.load_json(state_path).get("rounds") or {}).get("review", 0) or 0)
        except (ValueError, TypeError):
            review_rounds = 0
    if n3d >= heavy or review_rounds >= 2:
        role = "builder_escalation"
    try:
        info = golden.build_project(plan, stage_dir, None, common.brand_dir(), inp.assets_dir, lib, cat, folder="project",
                                    meta_id=f"reel-{plan.get('idea_id', 'idea')}", title=f"reel {plan.get('idea_id', '')}")
    except golden.PlanError as exc:
        error(f"cannot build the project: {exc}")
        return 1
    common.write_json(os.path.join(stage_dir, "plan.json"), plan)  # the plan as compiled (with the exit props of the transitions)
    say("INFO", f"S10: project built from the plan: {info['hosts']} hosts, {len(plan['scenes'])} scenes, assets {', '.join(info['assets']) or 'none'}; builder role {role}" + (f" ({n3d} 3D objects)" if n3d else ""))
    write_build_json(stage_dir, {"project": info["project"], "hosts": info["hosts"], "assets": info["assets"], "webgl": wg.get("webgl"), "render_flag": wg.get("render_flag", ""),
                                 "three_d_objects": n3d, "builder_role": role, "review_rounds": review_rounds, "flags": flags, "wishlist": wishlist, "fix_rounds": 0})
    return step_check(args, inp, toks, cat, lib)


def step_check(args, inp: common.Inputs, toks: dict, cat: dict, lib: str) -> int:
    stage_dir = common.mixed(args.stage_dir)
    project = os.path.join(stage_dir, "project")
    activity("building visuals")
    info = golden.check_project(project)
    common.write_json(os.path.join(stage_dir, "check.json"), info)
    errs = check_errors(info)
    warn = sum(int(s.get("warningCount") or 0) for s in info.get("sections", {}).values())
    if errs:
        for e in errs[:10]:
            print("check: " + e)
        say("WARN", f"S10: hyperframes check found {len(errs)} {'error' if len(errs) == 1 else 'errors'} ({errs[0][:120]})")
        write_build_json(stage_dir, {"check_ok": False, "check_errors": errs})
        print(json.dumps({"ok": False, "check_errors": errs}))
        return 5
    say("INFO", f"S10: hyperframes check ok ({warn} warnings)")
    write_build_json(stage_dir, {"check_ok": True, "check_errors": [], "check_warnings": warn})
    return 0


def step_finish(args, inp: common.Inputs, toks: dict, cat: dict, lib: str) -> int:
    from visual import events as events_mod
    stage_dir = common.mixed(args.stage_dir)
    project = os.path.join(stage_dir, "project")
    plan = common.load_json(os.path.join(stage_dir, "plan.json"))
    build = common.load_json(os.path.join(stage_dir, "build.json")) if os.path.isfile(os.path.join(stage_dir, "build.json")) else {}
    gpu_flag = build.get("render_flag", "") or ""
    if args.gpu == "software":
        gpu_flag = "--no-browser-gpu"
    elif args.gpu == "hardware":
        gpu_flag = "--browser-gpu"
    quality = str(common.cfg(inp.config, "visual.draft_quality", "draft"))
    crf = int(common.cfg(inp.config, "visual.draft_crf", 20))
    t_render = int(common.cfg(inp.config, "timeouts.render_draft_seconds", 3600))
    # 1. the events
    activity("building visuals")
    ev = events_mod.build_events(project, plan, verify=True, gpu=args.gpu)
    common.write_json(os.path.join(stage_dir, "events.json"), ev)
    v = ev.get("verified", {})
    say("INFO", f"S10: events.json: {len(ev['events'])} events ({ev.get('counts', {}).get('scene_change', 0)} scene changes); {v.get('changed', 0)} of {v.get('checked', 0)} element events verified on screen" + (f", {len(v.get('failed', []))} not: {', '.join(v['failed'][:3])}" if v.get("failed") else ""))
    tc = ev.get("timeline_check") or {}
    if tc and not tc.get("ok", True):
        say("WARN", f"S10: the project's timeline differs from the plan for {len(tc.get('mismatches', []))} clips ({tc['mismatches'][0] if tc.get('mismatches') else ''})")
    # 2. the draft
    if not args.no_render:
        activity("rendering draft")
        out_mp4 = os.path.join(stage_dir, "draft.mp4")
        info = render_scaled(project, out_mp4, quality, gpu_flag, crf, t_render)
        common.write_json(os.path.join(stage_dir, "render.json"), info)
        if info.get("stage") != "done":
            error(f"the draft render failed at {info.get('stage')}: {(info.get('stderr') or info.get('stdout') or '')[-300:]}")
            return 2
        pr = info.get("probe", {})
        vid = pr.get("video", {})
        want = plan["duration_ms"] / 1000
        ok = vid.get("width") == DRAFT_W and vid.get("height") == DRAFT_H and abs(float(vid.get("fps", 0)) - common.FPS) < 0.01 and abs(float(pr.get("duration", 0)) - want) <= 0.2 and "audio" not in pr
        say("INFO", f"S10: draft.mp4 {vid.get('width')}x{vid.get('height')} {vid.get('fps')} fps, {float(pr.get('duration', 0)):.2f} s (plan {want:.2f} s), silent, rendered in {info.get('seconds')} s{'' if ok else ': NOT as expected'}")
        if not ok:
            error(f"draft.mp4 is {vid.get('width')}x{vid.get('height')} at {vid.get('fps')} fps, {float(pr.get('duration', 0)):.2f} s against {want:.2f} s, audio {'present' if 'audio' in pr else 'absent'}")
            return 2
        # 3. hook 2
        h2 = hook2_plan(plan, inp, toks, inp.config)
        h2_info = {}
        if h2:
            activity("rendering draft")
            golden.apply_transitions(h2, cat)
            golden.build_project(h2, stage_dir, None, common.brand_dir(), inp.assets_dir, lib, cat, folder="hook2", meta_id=f"hook2-{plan.get('idea_id', 'idea')}", title="hook 2 clip")
            common.write_json(os.path.join(stage_dir, "hook2", "plan.json"), h2)
            h2_info = render_scaled(os.path.join(stage_dir, "hook2"), os.path.join(stage_dir, "hook2.mp4"), quality, gpu_flag, crf, t_render)
            common.write_json(os.path.join(stage_dir, "render-hook2.json"), h2_info)
            if h2_info.get("stage") != "done":
                error(f"the hook 2 render failed at {h2_info.get('stage')}: {(h2_info.get('stderr') or '')[-300:]}")
                return 2
            say("INFO", f"S10: hook2.mp4 {float(h2_info.get('probe', {}).get('duration', 0)):.2f} s ({h2['duration_ms']} ms planned), rendered in {h2_info.get('seconds')} s")
        else:
            flag("no hook 2 clip: words_hook2.json or the plan's hook2 design is missing")
        # 4. the contact sheet
        try:
            golden.contact_sheet(out_mp4, plan, os.path.join(stage_dir, "contact-sheet.png"))
        except Exception as exc:  # the sheet is a convenience for the reviewer, never a reason to fail
            say("WARN", f"S10: no contact sheet ({type(exc).__name__}: {exc})")
        write_build_json(stage_dir, {"draft": "draft.mp4", "draft_probe": pr, "render_seconds": info.get("seconds"), "hook2": "hook2.mp4" if h2 else None,
                                     "hook2_ms": h2["duration_ms"] if h2 else None, "events": len(ev["events"]), "events_verified": v})
    return 0


def run_build(args) -> int:
    inp = common.Inputs(args.run_dir)
    toks = common.tokens()
    cat = common.catalog()
    lib = common.motion_lib()
    steps = {"compile": [step_compile], "check": [step_check], "finish": [step_finish], "all": [step_compile, step_finish]}[args.step]
    for fn in steps:
        rc = fn(args, inp, toks, cat, lib)
        if rc != 0:
            return rc
    return 0


def run_contact_sheet(args) -> int:
    plan = common.load_json(args.plan)
    out = golden.contact_sheet(args.video, plan, args.out)
    print(f"contact sheet: {out}")
    return 0
