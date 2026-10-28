"""pipeline/lib/motion/golden.py: turn a merged visual plan (pipeline/stages/09-plan/schema.json) into a HyperFrames
project built from the motion library, check it, render it with its voiceover, probe the file and write a contact
sheet and a README. The golden reel of BUILD_SPEC.md M9 is made this way (pipeline/bin/render-golden); M10's S10
can start from the same compiler.

The project (out/project/): index.html mounts the paper canvas for the whole reel, one host per component instance of
the plan (data-composition-src into compositions/, its props as data-variable-values, its scene as data-scene),
the caption line once over the caption chunks, and the voice as <audio id="vo">. The library's compositions/ and
assets/ are copied in; image props written as brand/<path> (library/brand, checked against brand.json) and
research/<file> (the run's research assets) are copied under assets/ and rewritten. The transitions of the plan
become the exit props of the leaving scene's components. hero-3d gets its clip_start.

  python pipeline/lib/motion golden --plan plan.json --out golden/test-idea --voice vo.wav [--words words.json]
         [--assets <research assets dir>] [--brand library/brand] [--no-render] [--quality looks] [--gpu auto]
Exit 0 when the project checks, renders and probes clean; 1 on a plan or project problem; 2 on a render failure.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import shutil
import subprocess

from motion import captions, common

SCHEMA = os.path.join(common.REPO, "pipeline", "stages", "09-plan", "schema.json")


class PlanError(Exception):
    pass


def validate_plan(plan: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["the jsonschema package is missing: bash pipeline/bin/setup-python"]
    schema = common.load_json(SCHEMA)
    v = jsonschema.validators.validator_for(schema)(schema)
    errs = sorted(v.iter_errors(plan), key=lambda e: [str(p) for p in e.absolute_path])
    return [("/".join(str(p) for p in e.absolute_path) or "$") + ": " + e.message for e in errs]


def check_plan(plan: dict, cat: dict) -> list[str]:
    """What the schema cannot say: unique ids, known components and props, times inside the reel, the CTA branding."""
    problems = []
    by_id = {c["id"]: c for c in cat["components"]}
    seen = set()
    dur = plan["duration_ms"]
    for s in plan["scenes"]:
        if not (0 <= s["start_ms"] < s["end_ms"] <= dur + 1):
            problems.append(f"scene {s['id']}: times {s['start_ms']}..{s['end_ms']} outside 0..{dur}")
        for comp in s["components"]:
            if comp["id"] in seen:
                problems.append(f"component id {comp['id']} is used twice")
            seen.add(comp["id"])
            c = by_id.get(comp["component"])
            if not c:
                problems.append(f"{comp['id']}: unknown component {comp['component']}")
                continue
            if c["status"] != "approved":
                problems.append(f"{comp['id']}: {comp['component']} is a candidate, not an approved component")
            declared = {p["id"] for p in c["props"]}
            for k in comp["props"]:
                if k not in declared:
                    problems.append(f"{comp['id']}: prop {k} is not a declared variable of {comp['component']}")
            if not (s["start_ms"] <= comp["start_ms"] < comp["end_ms"] <= dur + 1):
                problems.append(f"{comp['id']}: times {comp['start_ms']}..{comp['end_ms']} outside its scene or the reel")
    cta = plan["branding"]["cta_scene"]
    cta_scene = next((s for s in plan["scenes"] if s["id"] == cta), None)
    if not cta_scene:
        problems.append(f"branding.cta_scene {cta} is not a scene")
    else:
        kinds = [c["component"] for c in cta_scene["components"]]
        if "dm-card" not in kinds:
            problems.append("the CTA scene has no dm-card")
        if "end-card" not in kinds:
            problems.append("the CTA scene has no end-card")
        for c in cta_scene["components"]:
            if c["component"] == "dm-card" and c["props"].get("avatar") != plan["branding"]["dm_avatar"]:
                problems.append("the dm-card's avatar is not branding.dm_avatar")
            if c["component"] == "end-card" and c["props"].get("lockup") != plan["branding"]["lockup"]:
                problems.append("the end-card's lockup is not branding.lockup")
    if not plan["branding"].get("flashfx_allowed_outside_cta", False):
        for s in plan["scenes"]:
            if s["id"] == cta:
                continue
            for comp in s["components"]:
                for v in comp["props"].values():
                    if isinstance(v, str) and v.startswith("brand/"):
                        problems.append(f"{comp['id']}: a FlashFX asset ({v}) outside the CTA while the solution is not FlashFX")
    return problems


# ------------------------------------------------------------------------------------------------ assets

def brand_assets(brand_dir: str) -> dict:
    data = common.load_json(os.path.join(brand_dir, "brand.json"))
    out = {}
    for a in data.get("assets", []):
        rel = a["path"].replace("library/brand/", "")
        out[rel] = a
    return out


def resolve_image(value: str, project: str, brand_dir: str, brand_index: dict, assets_dir: str, used: list[str]) -> str:
    if value.startswith("brand/"):
        rel = value[len("brand/"):]
        if rel not in brand_index:
            raise PlanError(f"brand asset {value} is not listed in brand.json")
        src = os.path.join(brand_dir, rel)
    elif value.startswith("research/"):
        if not assets_dir:
            raise PlanError(f"research asset {value} but no --assets folder")
        src = os.path.join(assets_dir, value[len("research/"):])
    else:
        return value  # already a project path (assets/...) or a demo asset
    if not os.path.isfile(src):
        raise PlanError(f"asset {value} not found at {src}")
    dst = os.path.join(project, "assets", value)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.isfile(dst):
        shutil.copy2(src, dst)
    used.append(value)
    return "assets/" + value


def resolve_props(props: dict, project: str, brand_dir: str, brand_index: dict, assets_dir: str, used: list[str]) -> dict:
    out = {}
    for k, v in props.items():
        if isinstance(v, str) and (v.startswith("brand/") or v.startswith("research/")):
            out[k] = resolve_image(v, project, brand_dir, brand_index, assets_dir, used)
        elif isinstance(v, list):
            out[k] = [({**item, "image": resolve_image(item["image"], project, brand_dir, brand_index, assets_dir, used)} if isinstance(item, dict) and isinstance(item.get("image"), str) else item) for item in v]
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------------------------------------ the project

def attr_json(value) -> str:
    """JSON inside a single-quoted HTML attribute: apostrophes and ampersands escaped."""
    return json.dumps(value, ensure_ascii=False).replace("&", "&amp;").replace("'", "&#39;")


def apply_transitions(plan: dict, cat: dict) -> None:
    scenes = {s["id"]: s for s in plan["scenes"]}
    kinds = {c["id"]: c["kind"] for c in cat["components"]}
    for t in plan.get("transitions", []):
        s = scenes.get(t["from"])
        if not s or t["type"] == "cut":
            continue
        for comp in s["components"]:
            if kinds.get(comp["component"]) in ("canvas", "captions"):
                continue
            props = comp["props"]
            if "exit" in props:
                continue
            if comp["component"] == "exit-move":
                continue
            exit_at = (s["end_ms"] - t["duration_ms"] - comp["start_ms"]) / 1000
            props["exit"] = t["type"]
            props["exit_at"] = round(max(0.0, exit_at), 3)


def canvas_seed(plan: dict) -> int:
    """A stable seed per reel for the canvas layers (M14): from the idea id, else from the plan's duration."""
    import hashlib
    key = str(plan.get("idea_id") or plan.get("duration_ms") or "reel")
    return int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:6], 16) % 1000000 + 1


def reset_dir(path: str) -> None:
    """Empty a folder, surviving OneDrive and Windows handles: retry, then fall back to clearing what can be cleared."""
    import time
    for _ in range(4):
        if not os.path.isdir(path):
            break
        shutil.rmtree(path, ignore_errors=True)
        if os.path.isdir(path):
            time.sleep(0.5)
    os.makedirs(path, exist_ok=True)


def build_project(plan: dict, out_dir: str, voice: str | None, brand_dir: str, assets_dir: str, lib: str, cat: dict,
                  folder: str = "project", meta_id: str = "", title: str = "") -> dict:
    """voice None (M10): a silent project, no <audio> element (S10's draft; S13 adds the mix). folder, meta_id and title
    name the project folder under out_dir and its meta.json."""
    project = os.path.join(out_dir, folder)
    reset_dir(project)
    shutil.copytree(os.path.join(lib, "compositions"), os.path.join(project, "compositions"), dirs_exist_ok=True)
    for name in ("fonts", "vendor"):
        shutil.copytree(os.path.join(lib, "assets", name), os.path.join(project, "assets", name), dirs_exist_ok=True)
    for name in ("paper-cards.css", "paper-cards.js", "pc-motion.js", "tokens.css"):
        shutil.copy2(os.path.join(lib, "assets", name), os.path.join(project, "assets", name))
    shutil.copy2(os.path.join(lib, "hyperframes.json"), os.path.join(project, "hyperframes.json"))
    common.write_json(os.path.join(project, "meta.json"), {"id": meta_id or ("golden-" + plan.get("idea_id", "reel")), "name": title or ("golden reel " + plan.get("idea_id", ""))})
    os.makedirs(os.path.join(project, "assets"), exist_ok=True)
    if voice:
        shutil.copy2(voice, os.path.join(project, "assets", "vo.wav"))
    brand_index = brand_assets(brand_dir)
    used: list[str] = []
    apply_transitions(plan, cat)
    by_id = {c["id"]: c for c in cat["components"]}
    dur_s = plan["duration_ms"] / 1000
    hosts = []
    canvas_file = by_id["paper-canvas"]["file"]
    canvas_props = {"seed": canvas_seed(plan), "duration": round(dur_s + 1, 3)}  # M14: the edge and ambient layers, seeded per reel
    hosts.append(f'      <div id="paper-canvas" class="clip" data-composition-id="paper-canvas" data-composition-src="{canvas_file}" data-start="0" data-duration="{dur_s:.3f}" '
                 f'data-track-index="0" data-width="1080" data-height="1920" data-scene="all" style="z-index: 0" data-variable-values=\'{attr_json(canvas_props)}\'></div>')
    events_hint = []
    for s in plan["scenes"]:
        for comp in s["components"]:
            c = by_id[comp["component"]]
            props = resolve_props(dict(comp["props"]), project, brand_dir, brand_index, assets_dir, used)
            start = comp["start_ms"] / 1000
            dur = (comp["end_ms"] - comp["start_ms"]) / 1000
            if comp["component"] in ("hero-3d", "icon-3d"):
                props["clip_start"] = round(start, 3)
            z = comp.get("z", c.get("z", 2))
            hosts.append(f'      <div id="{comp["id"]}" class="clip" data-composition-id="{comp["id"]}" data-composition-src="{c["file"]}" data-start="{start:.3f}" data-duration="{dur:.3f}" '
                         f'data-track-index="1" data-width="1080" data-height="1920" data-scene="{s["id"]}" data-beat="{s["beat"]}" data-component="{comp["component"]}" style="z-index: {z}" '
                         f'data-variable-values=\'{attr_json(props)}\'></div>')
            events_hint.append({"instance": comp["id"], "component": comp["component"], "scene": s["id"], "start_ms": comp["start_ms"], "end_ms": comp["end_ms"],
                                "sound_events": c.get("sound_events", []), "props": props})
    if plan.get("captions"):
        first = min(ch["start_ms"] for ch in plan["captions"])
        last = max(ch["end_ms"] for ch in plan["captions"])
        clip_start = max(0, first - 200)
        chunks = captions.to_component_chunks(plan["captions"], clip_start)
        cap = by_id["caption-line"]
        cap_props = {"chunks_json": json.dumps(chunks, ensure_ascii=False)}
        hosts.append(f'      <div id="captions" class="clip" data-composition-id="captions" data-composition-src="{cap["file"]}" data-start="{clip_start / 1000:.3f}" data-duration="{(min(plan["duration_ms"], last + 100) - clip_start) / 1000:.3f}" '
                     f'data-track-index="2" data-track-kind="captions" data-width="1080" data-height="1920" data-scene="captions" style="z-index: {cap.get("z", 5)}" data-variable-values=\'{attr_json(cap_props)}\'></div>')
    index = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>{html.escape(title or ('golden reel ' + plan.get('idea_id', '')))}</title>
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      html, body {{ margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: #F5EEE3; }}
      #root {{ width: 100%; height: 100%; position: relative; }}
    </style>
  </head>
  <body>
    <!-- Built by pipeline/lib/motion/golden.py build_project from the merged plan: one host per component instance of the
         plan, over the paper canvas, the captions once, the voice as audio when the project has one. Edit the plan and
         build again (render-golden for the golden reel, the S10 stage for a run). -->
    <div id="root" data-composition-id="main" data-start="0" data-duration="{dur_s:.3f}" data-width="1080" data-height="1920">
{chr(10).join(hosts)}
{'      <audio id="vo" src="assets/vo.wav" data-start="0" data-volume="1"></audio>' if voice else '      <!-- silent: no audio track in this project -->'}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""
    common.write_text(os.path.join(project, "index.html"), index)
    common.write_json(os.path.join(project, "instances.json"), {"duration_ms": plan["duration_ms"], "instances": events_hint, "assets": sorted(set(used))})
    return {"project": project, "assets": sorted(set(used)), "hosts": len(hosts)}


# ------------------------------------------------------------------------------------------------ check, render, probe

def npx_cmd() -> list[str]:
    # REELS_NODE_PREFIX (M10): the folder whose node_modules holds hyperframes (the tests' sandboxes point it at the real repo)
    return [("npx.cmd" if os.name == "nt" else "npx"), "--prefix", os.environ.get("REELS_NODE_PREFIX") or common.REPO, "hyperframes"]


def hf_json(args: list[str], cwd: str, timeout: int = 900) -> dict:
    proc = subprocess.run(npx_cmd() + args, cwd=cwd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    raw = proc.stdout or ""
    i = raw.find("{")
    try:
        d = json.loads(raw[i:]) if i >= 0 else {}
    except ValueError:
        d = {}
    d["_rc"] = proc.returncode
    d["_stderr"] = (proc.stderr or "")[-2000:]
    return d


def check_project(project: str) -> dict:
    d = hf_json(["check", "--json", "--timeout", "90000", "--samples", "16"], project)
    out = {"ok": bool(d.get("ok")), "browserSkipped": d.get("browserSkipped"), "sections": {}}
    for sec in ("lint", "runtime", "layout", "motion", "contrast", "craft"):
        s = d.get(sec) or {}
        items = s.get("findings") or s.get("issues") or []
        out["sections"][sec] = {"errorCount": s.get("errorCount"), "warningCount": s.get("warningCount"),
                                "findings": [{"severity": f.get("severity"), "code": f.get("code") or f.get("rule"), "message": (f.get("message") or "")[:300]} for f in items[:30]]}
    return out


def render(project: str, out_mp4: str, quality: str, gpu_flag: str, timeout: int = 3600) -> dict:
    args = ["render", "-o", common.mixed(out_mp4), "--fps", "30", "--quality", quality, "--quiet"]
    if gpu_flag:
        args.append(gpu_flag)
    t0 = dt.datetime.now()
    proc = subprocess.run(npx_cmd() + args, cwd=project, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    secs = (dt.datetime.now() - t0).total_seconds()
    return {"rc": proc.returncode, "seconds": round(secs, 1), "stdout": (proc.stdout or "")[-1500:], "stderr": (proc.stderr or "")[-1500:]}


def probe(path: str) -> dict:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,profile,pix_fmt:format=duration",
           "-of", "json", path]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        d = json.loads(proc.stdout or "{}")
    except ValueError:
        d = {}
    out = {"duration": float((d.get("format") or {}).get("duration") or 0)}
    for s in d.get("streams", []):
        if s.get("codec_type") == "video":
            num, den = (s.get("r_frame_rate") or "0/1").split("/")
            out["video"] = {"codec": s.get("codec_name"), "width": s.get("width"), "height": s.get("height"), "fps": round(float(num) / float(den or 1), 3), "profile": s.get("profile"), "pix_fmt": s.get("pix_fmt")}
        elif s.get("codec_type") == "audio":
            out["audio"] = {"codec": s.get("codec_name"), "sample_rate": int(s.get("sample_rate") or 0), "channels": s.get("channels")}
    return out


def contact_sheet(mp4: str, plan: dict, out_png: str) -> str:
    """One still per scene at its start plus 0.3 s (and the hook breath), tiled four per row with labels."""
    from PIL import Image, ImageDraw
    times = []
    for s in plan["scenes"]:
        times.append((s["id"] + " " + s["beat"], (s["start_ms"] + 300) / 1000))
        if s.get("hook_set_piece") or s["beat_type"] == "hook":
            times.append((s["id"] + " breath", min(plan["duration_ms"], s["end_ms"] - 400) / 1000))
    cells = []
    tmp_dir = os.path.join(os.path.dirname(out_png), ".sheet")
    os.makedirs(tmp_dir, exist_ok=True)
    for i, (label, t) in enumerate(times):
        png = os.path.join(tmp_dir, f"s{i:02d}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=270:480", png], capture_output=True)
        if os.path.isfile(png):
            cells.append((label, t, Image.open(png).convert("RGB")))
    cols = 4
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 280 + 10, rows * 510 + 10), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for i, (label, t, im) in enumerate(cells):
        x = 10 + (i % cols) * 280
        y = 10 + (i // cols) * 510
        draw.text((x, y + 2), f"{label} {t:.1f}s", fill=(255, 255, 255))
        sheet.paste(im, (x, y + 20))
    sheet.save(out_png)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return out_png


def write_readme(out_dir: str, plan: dict, info: dict, probe_info: dict, check_info: dict, render_info: dict) -> None:
    lines = [f"# Golden reel: {plan.get('idea_id', '')}", "",
             "The example reel the visual director (S9) reads: plan.json is the merged visual plan (pipeline/stages/09-plan/schema.json), "
             "project/ the HyperFrames project built from it by pipeline/lib/motion/golden.py, golden.mp4 the render (ignored by git, "
             "rebuilt by `bash pipeline/bin/render-golden`), contact-sheet.png one still per scene.", "",
             f"- Duration: {plan['duration_ms']} ms, {len(plan['scenes'])} scenes, {sum(len(s['components']) for s in plan['scenes'])} component instances, {len(plan.get('captions', []))} caption chunks",
             f"- Solution: {plan.get('solution', {}).get('type', 'none')} ({plan.get('solution', {}).get('name', '')}); branding: the CTA scene {plan['branding']['cta_scene']} carries the DM card ({plan['branding']['dm_avatar']}) and the lockup ({plan['branding']['lockup']}); brand slot: {plan['branding'].get('brand_slot')}",
             (f"- Render: {probe_info.get('video', {}).get('width')}x{probe_info.get('video', {}).get('height')} at {probe_info.get('video', {}).get('fps')} fps, {probe_info.get('duration', 0):.2f} s, audio {probe_info.get('audio', {}).get('codec')} {probe_info.get('audio', {}).get('sample_rate')} Hz (the render time is in render.json)" if probe_info else "- Render: not rendered in this run (--no-render)"),
             f"- HyperFrames check: {'ok' if check_info.get('ok') else 'NOT ok'}" + "".join(f", {k} warnings {v.get('warningCount')}" for k, v in check_info.get("sections", {}).items() if v.get("warningCount")),
             "", "## Scenes", "", "| scene | beat | type | start | end | components |", "|---|---|---|---|---|---|"]
    for s in plan["scenes"]:
        comps = ", ".join(f"{c['component']} ({c['id']})" for c in s["components"])
        lines.append(f"| {s['id']} | {s['beat']} | {s['beat_type']} | {s['start_ms'] / 1000:.2f} s | {s['end_ms'] / 1000:.2f} s | {comps} |")
    lines += ["", "## Transitions", ""]
    for t in plan.get("transitions", []):
        lines.append(f"- {t['from']} to {t['to']}: {t['type']} ({t['duration_ms']} ms)")
    if plan.get("notes"):
        lines += ["", "## Notes", "", plan["notes"]]
    common.write_text(os.path.join(out_dir, "README.md"), "\n".join(lines) + "\n")


def run(args) -> int:
    lib = common.motion_lib_dir()
    cat = common.load_catalog(lib)
    plan = common.load_json(args.plan)
    errs = validate_plan(plan)
    if errs:
        for e in errs:
            print("plan: " + e)
        return 1
    problems = check_plan(plan, cat)
    if problems:
        for p in problems:
            print("plan: " + p)
        return 1
    brand_dir = args.brand or os.path.join(common.REPO, "library", "brand")
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    try:
        info = build_project(plan, out_dir, args.voice, brand_dir, args.assets, lib, cat)
    except PlanError as exc:
        print("plan: " + str(exc))
        return 1
    print(f"project written: {info['project']} ({info['hosts']} hosts, assets: {', '.join(info['assets']) or 'none'})")
    check_info = check_project(info["project"])
    common.write_json(os.path.join(out_dir, "check.json"), check_info)
    for sec, s in check_info["sections"].items():
        for f in s["findings"]:
            if f["severity"] in ("error",):
                print(f"check {sec} {f['severity']}: {f['code']}: {f['message']}")
    print(f"hyperframes check: {'ok' if check_info['ok'] else 'NOT ok'}")
    if not check_info["ok"]:
        return 1
    render_info = {}
    probe_info = {}
    if not args.no_render:
        gpu_flag = ""
        wg = os.path.join(lib, "webgl.json")
        if os.path.isfile(wg):
            gpu_flag = common.load_json(wg).get("render_flag", "")
        if args.gpu == "software":
            gpu_flag = "--no-browser-gpu"
        elif args.gpu == "hardware":
            gpu_flag = "--browser-gpu"
        out_mp4 = os.path.join(out_dir, "golden.mp4")
        render_info = render(info["project"], out_mp4, args.quality, gpu_flag)
        common.write_json(os.path.join(out_dir, "render.json"), render_info)
        if render_info["rc"] != 0 or not os.path.isfile(out_mp4):
            print("render failed: " + (render_info.get("stderr") or render_info.get("stdout") or "")[-600:])
            return 2
        probe_info = probe(out_mp4)
        common.write_json(os.path.join(out_dir, "probe.json"), probe_info)
        want = plan["duration_ms"] / 1000
        v = probe_info.get("video", {})
        ok = v.get("width") == 1080 and v.get("height") == 1920 and abs(v.get("fps", 0) - 30) < 0.01 and abs(probe_info["duration"] - want) <= 0.2 and "audio" in probe_info
        print(f"render: {render_info['seconds']} s, {v.get('width')}x{v.get('height')} {v.get('fps')} fps, {probe_info['duration']:.2f} s (voice {want:.2f} s), audio {probe_info.get('audio', {}).get('codec')}: {'ok' if ok else 'NOT ok'}")
        contact_sheet(out_mp4, plan, os.path.join(out_dir, "contact-sheet.png"))
        print(f"contact sheet: {os.path.join(out_dir, 'contact-sheet.png')}")
        if not ok:
            return 2
    write_readme(out_dir, plan, info, probe_info, check_info, render_info)
    return 0
