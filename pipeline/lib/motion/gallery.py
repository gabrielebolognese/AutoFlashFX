"""pipeline/lib/motion/gallery.py: the human-facing gallery of the motion library (BUILD_SPEC.md M9: "a gallery page
that plays each one") and the showreel index.

  stills    one 540x960 still per component into motion-lib/gallery/stills/<id>.png, taken in the harness at the
            component's still_at time (motion/expectations.py) with the catalog's demo props
  gallery   motion-lib/gallery/index.html (open it in a browser): every component with its still, what it does, its
            props, sound events, beat types and frame-match result, and a Play button that loads the component in an
            inline player (gallery/play/<id>.html: the harness page plus a looping clock that seeks the timeline and
            dispatches hf-seek, for eyes only; renders never use it); plus motion-lib/index.html, the showreel that
            `npx hyperframes check` and `snapshot` run on, regenerated from the catalog's demo props so the two agree
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os

from motion import common, expectations, harness


def components(lib: str, cat: dict) -> list[dict]:
    out = []
    for c in cat["components"]:
        path = os.path.join(lib, c["file"])
        if os.path.isfile(path):
            comp = common.parse_component(path)
            comp["catalog"] = c
            out.append(comp)
    return out


def demo_props(c: dict, spec: dict | None) -> dict:
    props = dict((spec or {}).get("props") or {})
    props.update(c.get("demo") or {})
    return props


def run_stills(args) -> int:
    lib = common.motion_lib_dir()
    cat = common.load_catalog(lib)
    specs = expectations.build(common.tokens())
    only = set(args.only.split(",")) if getattr(args, "only", "") else None
    out_dir = os.path.join(lib, "gallery", "stills")
    n = 0
    with harness.Harness(lib=lib, gpu=args.gpu) as h:
        for comp in components(lib, cat):
            cid = comp["id"]
            if only and cid not in only:
                continue
            spec = specs.get(cid) or {}
            t = spec.get("still_at", 1.0)
            if cid == "hero-3d":
                t = max(t, 1.5)
            h.still(comp, demo_props(comp["catalog"], spec), t, os.path.join(out_dir, cid + ".png"))
            n += 1
            print(f"still {cid} at {t:.2f}s")
    print(f"{n} stills -> {out_dir}")
    return 0


PLAYER_DRIVER = """
<script>
(function () {
  var id = %s, duration = %s;
  var tl = window.__timelines[id];
  var start = performance.now();
  function tick() {
    var t = ((performance.now() - start) / 1000) %% duration;
    if (tl) tl.seek(t, false);
    try { window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: t, waitUntil: function () {} } })); } catch (e) {}
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();
</script>
"""


def write_players(lib: str, comps: list[dict], specs: dict) -> None:
    folder = os.path.join(lib, "gallery", "play")
    os.makedirs(folder, exist_ok=True)
    for comp in comps:
        c = comp["catalog"]
        dur = c.get("demo_duration") or 3
        page = harness.build_page(comp, demo_props(c, specs.get(comp["id"])), lib)
        page = page.replace("</body>", PLAYER_DRIVER % (json.dumps(comp["id"]), json.dumps(dur)) + "</body>")
        common.write_text(os.path.join(folder, comp["id"] + ".html"), page)


def energy_text(c: dict) -> str:
    """The component's energy measures (frame-match renders it alone for 4 s: motion/framematch.py, review/energy.py)."""
    e = c.get("energy") or {}
    if not e or e.get("moving_share_pct") is None:
        return "not measured"
    return (f"moving {e.get('moving_share_pct')} percent of frames, middle band {e.get('middle_moving_share_pct')} percent, pixels changing {e.get('pixels_changing_pct')} percent, "
            f"longest still {e.get('longest_still_s')} s, static windows {e.get('static_windows', 0)}")


def fm_text(c: dict) -> str:
    fm = c.get("frame_match") or {}
    r = fm.get("result", "not run")
    if r in ("pass", "fail"):
        extra = f", {fm.get('checks_ok')}/{fm.get('checks')} checks"
        if fm.get("r") is not None:
            extra += f", strip r {fm.get('r')}"
        return r + extra
    return r


def write_index(lib: str, cat: dict, comps: list[dict], specs: dict) -> str:
    esc = html.escape
    rows = []
    for comp in comps:
        c = comp["catalog"]
        props = "".join(f"<tr><td><code>{esc(p['id'])}</code></td><td>{esc(p['type'])}</td><td>{esc(json.dumps(p.get('default'), ensure_ascii=False))}</td><td>{esc(p.get('label', ''))}</td></tr>" for p in c["props"])
        events = "".join(f"<li><code>{esc(str(e['event']))}</code> at frame {esc(str(e.get('frame')))}" + (f" for {esc(str(e['duration_frames']))} frames" if e.get("duration_frames") is not None else "") +
                         (f": cue <b>{esc(str(e['cue']))}</b>" if e.get("cue") else ": no sound of its own") + (f" ({esc(e['note'])})" if e.get("note") else "") + "</li>" for e in c["sound_events"]) or "<li>none</li>"
        demo = esc(json.dumps(demo_props(c, specs.get(comp["id"])), ensure_ascii=False))
        item = f"vocabulary.md item {c['item']}" if c.get("item") else "not in vocabulary.md (branding or 3D)"
        rows.append(f"""
<section class="comp" id="c-{esc(comp['id'])}">
  <div class="still"><img src="stills/{esc(comp['id'])}.png" alt="{esc(c['name'])}" loading="lazy"><div class="player" id="p-{esc(comp['id'])}"></div>
    <button onclick="play('{esc(comp['id'])}')">Play</button> <button onclick="stop('{esc(comp['id'])}')">Stop</button></div>
  <div class="info">
    <h2>{esc(c['name'])} <small>{esc(comp['id'])}, {esc(item)}, {esc(c['kind'])}, <span class="{'ok' if c['status'] == 'approved' else 'cand'}">{esc(c['status'])}</span></small></h2>
    <p>{esc(c['does'])}</p>
    <p><b>Frame match:</b> {esc(fm_text(c))}. <b>Energy (alone, 4 s):</b> {esc(energy_text(c))}. <b>Beat types:</b> {esc(', '.join(c['beat_types']))}. <b>File:</b> <code>{esc(c['file'])}</code></p>
    <details><summary>Props ({len(c['props'])})</summary><table><tr><th>prop</th><th>type</th><th>default</th><th>label</th></tr>{props}</table><p>Demo props: <code>{demo}</code></p></details>
    <details><summary>Sound events</summary><ul>{events}</ul></details>
  </div>
</section>""")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>paper-cards motion library</title>
<style>
  body {{ margin: 0; font-family: "Inter Tight", system-ui, sans-serif; background: #F5EEE3; color: #100904; }}
  header {{ padding: 28px 36px 10px; }} header h1 {{ margin: 0 0 6px; font-size: 30px; }} header p {{ margin: 4px 0; max-width: 1100px; line-height: 1.4; }}
  .comp {{ display: grid; grid-template-columns: 300px 1fr; gap: 28px; padding: 24px 36px; border-top: 1px solid #D7C5BA; }}
  .still {{ position: relative; width: 300px; }} .still img {{ width: 270px; height: 480px; object-fit: cover; border-radius: 16px; box-shadow: 0 18px 28px -10px rgba(133,112,92,0.4); display: block; }}
  .player {{ position: absolute; left: 0; top: 0; width: 270px; height: 480px; display: none; border-radius: 16px; overflow: hidden; }}
  .player iframe {{ width: 1080px; height: 1920px; border: 0; transform: scale(0.25); transform-origin: 0 0; }}
  .still button {{ margin-top: 10px; padding: 6px 14px; border-radius: 999px; border: 1px solid #D7C5BA; background: #FFFAF7; cursor: pointer; font: inherit; }}
  h2 {{ margin: 0 0 8px; font-size: 24px; }} h2 small {{ font-size: 14px; font-weight: 500; color: #6b5e55; }}
  .ok {{ color: #289C5C; font-weight: 700; }} .cand {{ color: #DC6532; font-weight: 700; }}
  table {{ border-collapse: collapse; font-size: 14px; }} td, th {{ padding: 4px 10px; border-bottom: 1px solid #E4D5C9; text-align: left; vertical-align: top; }}
  code {{ font-family: "JetBrains Mono", Consolas, monospace; font-size: 13px; }} details {{ margin: 6px 0; }} summary {{ cursor: pointer; font-weight: 700; }}
  .toc a {{ margin-right: 10px; white-space: nowrap; }}
</style></head>
<body>
<header>
  <h1>paper-cards motion library</h1>
  <p>{len(comps)} components ({sum(1 for x in comps if x['catalog']['status'] == 'approved')} approved, {sum(1 for x in comps if x['catalog']['status'] != 'approved')} candidates), built {esc(cat.get('generated', ''))}, gallery {dt.date.today().isoformat()}.
  Every still is the component at a telling moment; Play loops it in the browser (a clock drives the same timeline HyperFrames seeks frame by frame in a render).
  The numbers behind each move are in <code>styles/paper-cards/vocabulary.md</code> and <code>tokens.json</code>; the measurements are in <a href="frame-match.md">frame-match.md</a>.
  To change a look or a timing, edit the component in <code>motion-lib/compositions/</code>, then run <code>bash pipeline/bin/frame-match</code> and <code>bash pipeline/bin/gallery</code>.
  Since M14 every component lives through the four phases of the Motion and energy rules (main animation, inertia, hold, exit; <code>motion-lib/assets/pc-motion.js</code>) and the energy line shows what it measures rendered alone for 4 s (<code>python pipeline/lib/review energy</code> measures a whole reel).</p>
  <p class="toc">{' '.join(f'<a href="#c-{esc(x["id"])}">{esc(x["id"])}</a>' for x in comps)}</p>
</header>
{''.join(rows)}
<script>
  function play(id) {{ var p = document.getElementById("p-" + id); p.innerHTML = '<iframe src="play/' + id + '.html"></iframe>'; p.style.display = "block"; }}
  function stop(id) {{ var p = document.getElementById("p-" + id); p.innerHTML = ""; p.style.display = "none"; }}
</script>
</body></html>
"""
    out = os.path.join(lib, "gallery", "index.html")
    common.write_text(out, page)
    return out


def write_showreel(lib: str, cat: dict, comps: list[dict], specs: dict) -> str:
    """motion-lib/index.html: every component once with its demo props, in a row over the paper canvas."""
    hosts = []
    t = 0.0
    canvas = next((x for x in comps if x["id"] == "paper-canvas"), None)
    body = [x for x in comps if x["id"] != "paper-canvas"]
    for comp in body:
        c = comp["catalog"]
        dur = c.get("demo_duration") or 3
        props = demo_props(c, specs.get(comp["id"]))
        if comp["id"] == "hero-3d":
            props = dict(props, clip_start=t)
        attrs = f' data-variable-values=\'{json.dumps(props, ensure_ascii=False)}\'' if props else ""
        hosts.append(f'      <div id="{comp["id"]}" class="clip" data-composition-id="{comp["id"]}" data-composition-src="{c["file"]}" data-start="{t:g}" data-duration="{dur}" '
                     f'data-track-index="1" data-width="1080" data-height="1920" data-scene="{comp["id"]}" style="z-index: {c.get("z", 2)}"{attrs}></div>')
        t += dur
    total = t
    canvas_host = ""
    if canvas:
        canvas_host = (f'      <div id="paper-canvas" class="clip" data-composition-id="paper-canvas" data-composition-src="{canvas["catalog"]["file"]}" data-start="0" '
                       f'data-duration="{total:g}" data-track-index="0" data-width="1080" data-height="1920" style="z-index: 0" '
                       f'data-variable-values=\'{json.dumps({"seed": 7, "duration": round(total + 1, 3)})}\'></div>')
    page = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>paper-cards motion library: the showreel</title>
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      html, body {{ margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: #F5EEE3; }}
      #root {{ width: 100%; height: 100%; position: relative; }}
    </style>
  </head>
  <body>
    <!-- The showreel root, generated by `bash pipeline/bin/gallery` from catalog.json: every component once with its
         demo props, in a row over the paper canvas ({total:g} s). `npx hyperframes check` and `snapshot --composition <id>`
         run on this file; the human gallery is gallery/index.html. Do not edit by hand: change catalog.py META or the
         component and run the gallery again. -->
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total:g}" data-width="1080" data-height="1920">
{canvas_host}
{chr(10).join(hosts)}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""
    out = os.path.join(lib, "index.html")
    common.write_text(out, page)
    return out


def run_gallery(args) -> int:
    lib = common.motion_lib_dir()
    cat = common.load_catalog(lib)
    specs = expectations.build(common.tokens())
    comps = components(lib, cat)
    if not getattr(args, "no_stills", False):
        class A:
            only = ""
            gpu = args.gpu
        run_stills(A)
    write_players(lib, comps, specs)
    index = write_index(lib, cat, comps, specs)
    reel = write_showreel(lib, cat, comps, specs)
    print(f"gallery -> {index}")
    print(f"showreel -> {reel}")
    return 0
