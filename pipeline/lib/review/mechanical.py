"""pipeline/lib/review/mechanical.py: the mechanical checks of S12 (BUILD_SPEC.md S12, M11).

The built composition (10-build/project) is opened host by host in the Playwright harness of M9 (the same mount S10
verified the events in: the component's own file with the plan's props, the paper canvas behind), seeked to every
check time (every beat settled and at its middle, every emphasis hit, every landing, the built CTA) and measured:
every visible text leaf (its glyph box, font family, size and weight, color, effective opacity and scale) and every
image. Backgrounds are read from the pixels of a screenshot (the ring just outside each box), so a caption word on
its accent box, a chip's text on its fill and a logo on the surface under it are judged on what is drawn. At the
composition's own size (1080x1920) the numbers are exact; the draft's half resolution only matters for the video
checks (style_check.py), which scale their thresholds.

Rules, each issue tagged for the fix routing:
  zones         every text box inside tokens.json zones (safe_top, safe_bottom, margin_x) with the caption band
                exception of tweaks.md for the caption line and the CTA's DM card (DECISIONS.md 218)  [animation|text]
  right_rail    no text or logo in the right 230 px of the lower half                                    [animation]
  fonts         only the families of tokens.json, at no less than review.min_font_px (24) effective px; caption
                words at no less than 90 percent of the caption size (a chunk the component had to scale down) [text]
  overlaps      no two visible text leaves of different elements intersect; nothing off the canvas          [animation]
  contrast      text against the pixels around it: 4.5:1, or review.contrast_display_min (2.7) for the style's display
                colors (the accent family on paper, white on an accent box or pill, the success green): the look's
                own kicker and serif phrase measure 2.8 to 3.0 (DECISIONS.md M11)                            [text]
  emphasis      each caption emphasis lands within review.emphasis_tolerance_ms (80) of its word (the caption line's
                own events) and the word is on screen with its box                                             [text]
  branding      the CTA has the FlashFX lockup (300 px or wider) and the DM card's avatar (112 px or wider); no
                FlashFX logo outside the CTA unless the solution is flashfx; every logo file is in brand.json, drawn
                with its aspect ratio locked, its use_on matching the luminance of the surface under it (the pixels behind
                it, measured with the logo hidden) and readable against it (3:1), the bolt at least 64 px tall, clear
                space of a quarter of the bolt's height                                                       [animation]

  run(ctx, out_path) -> the report dict (also written as JSON): pass, issues[], counts, branding, emphasis,
                        images_by_time (the image boxes at the 1 fps sample times, for the style check)
"""
from __future__ import annotations

import math
import os
import re

from motion import common as mcommon, harness
from review import common as rc

REVIEW_JS = r"""
(args) => {
  const tl = window.__timelines[args.id];
  const seekTo = (t) => {
    if (tl) tl.seek(t, false);
    try { window.dispatchEvent(new CustomEvent("hf-seek", { detail: { time: t, waitUntil: () => {} } })); } catch (e) {}
  };
  const effOpacity = (el) => {
    let op = 1, node = el;
    while (node && node.id !== "stage" && node !== document.body) {
      const cs = getComputedStyle(node);
      op *= parseFloat(cs.opacity);
      if (cs.visibility === "hidden" || cs.display === "none") op = 0;
      node = node.parentElement;
    }
    return op;
  };
  const scaleOf = (el) => {
    // the length of the transformed basis vectors (the 3D matrix's first two columns): a parallax rotation (E2) does
    // not read as a smaller scale the way hypot(a, b) did (cos 12 degrees)
    let s = 1, node = el;
    while (node && node.id !== "stage" && node !== document.body) {
      const cs = getComputedStyle(node);
      try { const m = new DOMMatrixReadOnly(cs.transform); const k = Math.max(Math.hypot(m.m11, m.m12, m.m13), Math.hypot(m.m21, m.m22, m.m23)); if (k > 0) s *= k; } catch (e) {}
      node = node.parentElement;
    }
    return s;
  };
  // the grammar marks every element's main animation (data-pcm-main) and exit (data-pcm-exit) windows in local
  // seconds (pc-motion.js PCM.mark): an element inside one of them, or inside an ancestor's, is arriving or leaving
  const transientAt = (el, t) => {
    let node = el;
    while (node && node.id !== "stage" && node !== document.body) {
      for (const name of ["data-pcm-main", "data-pcm-exit"]) {
        const v = node.getAttribute(name);
        if (!v) continue;
        const parts = v.split(",");
        const a = parseFloat(parts[0]), b = parseFloat(parts[1]);
        if (isFinite(a) && isFinite(b) && t >= a - 1e-4 && t < b - 1e-4) return name === "data-pcm-main" ? "main" : "exit";
      }
      node = node.parentElement;
    }
    return "";
  };
  const bgOf = (el) => {
    let node = el;
    while (node && node.id !== "stage" && node !== document.body) {
      const cs = getComputedStyle(node);
      const bg = cs.backgroundColor || "";
      const m = bg.match(/rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*([\d.]+))?\)/);
      if (m && (m[1] === undefined || parseFloat(m[1]) >= 0.9)) return { color: bg, id: node.id || "", cls: String(node.className || "") };
      if (cs.backgroundImage && cs.backgroundImage !== "none") return { image: true, id: node.id || "" };
      node = node.parentElement;
    }
    return null;
  };
  const isTextLeaf = (el) => {
    let hasText = false;
    for (const n of el.childNodes) { if (n.nodeType === 3 && n.textContent.trim()) { hasText = true; break; } }
    return hasText;
  };
  const rows = [];
  const allOnce = document.querySelectorAll("#stage *");
  let idx = 0;
  for (const el of allOnce) { el.setAttribute("data-rv-idx", String(idx++)); }
  const ancestorsOf = (el) => { const out = []; let node = el.parentElement; while (node && node.id !== "stage" && node !== document.body) { const v = node.getAttribute("data-rv-idx"); if (v !== null) out.push(parseInt(v, 10)); node = node.parentElement; } return out; };
  for (const t of args.times) {
    seekTo(t);
    const texts = [], images = [];
    const all = document.querySelectorAll("#stage *");
    for (const el of all) {
      if (el.closest("#paper-root")) continue;
      const tag = el.tagName;
      if (tag === "IMG") {
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        images.push({ id: el.id || "", cls: String(el.className || ""), src: el.getAttribute("src") || "", x: r.left, y: r.top, w: r.width, h: r.height,
                      opacity: effOpacity(el), nw: el.naturalWidth, nh: el.naturalHeight, fit: cs.objectFit, bg: bgOf(el.parentElement), idx: parseInt(el.getAttribute("data-rv-idx") || "-1", 10),
                      transient: transientAt(el, t) });
        continue;
      }
      if (tag === "SCRIPT" || tag === "STYLE" || tag === "svg" || el.closest("svg") || tag === "CANVAS") continue;
      if (!isTextLeaf(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 0.5 || r.height < 0.5) continue;
      const cs = getComputedStyle(el);
      let tb = r;
      try { const range = document.createRange(); range.selectNodeContents(el); const rr = range.getBoundingClientRect(); if (rr.width > 0 && rr.height > 0) tb = rr; } catch (e) {}
      texts.push({ id: el.id || "", cls: String(el.className || ""), parent_cls: String((el.parentElement && el.parentElement.className) || ""), idx: parseInt(el.getAttribute("data-rv-idx") || "-1", 10), anc: ancestorsOf(el),
                   text: (el.textContent || "").trim().slice(0, 60), x: tb.left, y: tb.top, w: tb.width, h: tb.height, ex: r.left, ey: r.top, ew: r.width, eh: r.height,
                   opacity: effOpacity(el), font: cs.fontFamily, size: parseFloat(cs.fontSize), weight: cs.fontWeight, color: cs.color, scale: scaleOf(el),
                   bg: bgOf(el), ignore: el.hasAttribute("data-layout-ignore") || !!el.closest("[data-layout-ignore]"), transient: transientAt(el, t) });
    }
    rows.push({ t: t, texts: texts, images: images });
  }
  return { rows: rows, events: window.__pcEvents || [] };
}
"""

VISIBLE = 0.5


def first_family(font: str) -> str:
    return (font or "").split(",")[0].strip().strip('"').strip("'")


def bg_rgb_for_text(img, box: dict, text_rgb, pad: int = 5):
    """The background behind a text: the median of the pixels around and between the glyphs (the box grown by pad),
    the pixels near the text's own color left out (the glyphs and their anti-aliased edges). Falls back to the ring."""
    import numpy as np
    W, H = img.size
    x0, y0 = max(0, int(math.floor(box["x"])) - pad), max(0, int(math.floor(box["y"])) - pad)
    x1, y1 = min(W, int(math.ceil(box["x"] + box["w"])) + pad), min(H, int(math.ceil(box["y"] + box["h"])) + pad)
    if x1 <= x0 or y1 <= y0:
        return None
    arr = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB")).astype(int)
    tr = np.array(text_rgb[:3], dtype=int)
    dist = np.abs(arr - tr).max(axis=2)
    keep = arr[dist >= 90]
    if len(keep) < max(20, 0.12 * arr.shape[0] * arr.shape[1]):
        return ring_rgb(img, box)
    med = np.median(keep, axis=0)
    return (float(med[0]), float(med[1]), float(med[2]))


def inside_rgb(img, box: dict):
    """The median color inside a box (the surface under a logo, measured with the logo hidden)."""
    import numpy as np
    W, H = img.size
    x0, y0 = max(0, int(math.floor(box["x"]))), max(0, int(math.floor(box["y"])))
    x1, y1 = min(W, int(math.ceil(box["x"] + box["w"]))), min(H, int(math.ceil(box["y"] + box["h"])))
    if x1 <= x0 or y1 <= y0:
        return None
    arr = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB"))
    med = np.median(arr.reshape(-1, 3), axis=0)
    return (float(med[0]), float(med[1]), float(med[2]))


HIDE_JS = """
(args) => { const el = document.querySelector('[data-rv-idx="' + args.idx + '"]'); if (!el) return false; el.style.visibility = args.hide ? "hidden" : ""; return true; }
"""


def ring_rgb(img, box: dict, inner: int = 2, outer: int = 7):
    """The median color of the pixels in the ring between inner and outer px outside the box (the background)."""
    import numpy as np
    W, H = img.size
    x0, y0 = int(math.floor(box["x"])), int(math.floor(box["y"]))
    x1, y1 = int(math.ceil(box["x"] + box["w"])), int(math.ceil(box["y"] + box["h"]))
    ox0, oy0, ox1, oy1 = max(0, x0 - outer), max(0, y0 - outer), min(W, x1 + outer), min(H, y1 + outer)
    ix0, iy0, ix1, iy1 = max(0, x0 - inner), max(0, y0 - inner), min(W, x1 + inner), min(H, y1 + inner)
    if ox1 <= ox0 or oy1 <= oy0:
        return None
    arr = np.asarray(img.crop((ox0, oy0, ox1, oy1)).convert("RGB"))
    mask = np.ones(arr.shape[:2], dtype=bool)
    mask[iy0 - oy0: iy1 - oy0, ix0 - ox0: ix1 - ox0] = False
    px = arr[mask]
    if len(px) == 0:
        return None
    med = np.median(px, axis=0)
    return (float(med[0]), float(med[1]), float(med[2]))


_PNG_LUM: dict = {}


def png_luminance_percentiles(path: str) -> tuple[float, float] | None:
    """The 5th and 95th percentile luminance of a PNG's opaque pixels (the logo's dark and bright parts)."""
    if path in _PNG_LUM:
        return _PNG_LUM[path]
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(path).convert("RGBA")
        im.thumbnail((400, 400))
        arr = np.asarray(im)
        op = arr[arr[:, :, 3] > 128][:, :3].astype(float)
        if len(op) == 0:
            _PNG_LUM[path] = None
            return None
        lin = op / 255.0
        lin = np.where(lin <= 0.03928, lin / 12.92, ((lin + 0.055) / 1.055) ** 2.4)
        lum = 0.2126 * lin[:, 0] + 0.7152 * lin[:, 1] + 0.0722 * lin[:, 2]
        out = (float(np.percentile(lum, 5)), float(np.percentile(lum, 95)))
    except Exception:
        out = None
    _PNG_LUM[path] = out
    return out


def drawn_box(im: dict) -> dict:
    """Where an object-fit contain image is drawn inside its box (the box itself for other fits)."""
    nw, nh = float(im.get("nw") or 0), float(im.get("nh") or 0)
    if im.get("fit") == "contain" and nw > 0 and nh > 0 and im["w"] > 0 and im["h"] > 0:
        ratio = nw / nh
        dw = min(im["w"], im["h"] * ratio)
        dh = dw / ratio
        return {"x": im["x"] + (im["w"] - dw) / 2, "y": im["y"] + (im["h"] - dh) / 2, "w": dw, "h": dh}
    return {"x": im["x"], "y": im["y"], "w": im["w"], "h": im["h"]}


def run(ctx: rc.Ctx, out_path: str, sample_every_ms: int = 1000) -> dict:
    from PIL import Image
    toks = ctx.toks
    z = toks.get("zones") or {}
    safe_top, safe_bottom, margin_x = float(z.get("safe_top", 230)), float(z.get("safe_bottom", 1440)), float(z.get("margin_x", 60))
    cap_zone = z.get("caption") or {}
    cap_cy, cap_x0, cap_x1 = float(cap_zone.get("center_y", 1480)), float(cap_zone.get("x0", 230)), float(cap_zone.get("x1", 850))
    band_top, band_bottom = cap_cy - float(ctx.c("review.caption_band_above_px", 180)), cap_cy + float(ctx.c("review.caption_band_below_px", 80))
    rail = z.get("right_rail") or {}
    rail_x, rail_from_y = rc.CANVAS_W - float(rail.get("width", 230)), float(rail.get("from_y", rc.CANVAS_H / 2))
    tol = float(ctx.c("review.zone_tolerance_px", 4))
    min_font = float(ctx.c("review.min_font_px", 24))
    cap_font = float(((toks.get("type") or {}).get("caption") or {}).get("font_px", 67))
    cap_min_share = float(ctx.c("review.caption_min_size_share", 0.9))
    families = {str(f.get("family")) for f in (toks.get("fonts") or {}).values() if f.get("family")}
    accents = rc.accent_tokens(toks)
    c_min, c_large = float(ctx.c("review.contrast_min", 4.5)), float(ctx.c("review.contrast_display_min", 2.7))
    em_tol = float(ctx.c("review.emphasis_tolerance_ms", 80))
    br = toks.get("branding") or {}
    lockup_min = float(br.get("lockup_min_width", 300))
    bolt_min = float(br.get("bolt_min_height", 64))
    avatar_min = float(ctx.c("review.avatar_min_px", 112))
    cta = ctx.cta_scene()
    cta_id = cta.get("id") if cta else None
    cta_time = int(cta["end_ms"]) - 300 if cta else None
    flashfx = ctx.solution.get("type") == "flashfx"
    hosts = rc.read_hosts(ctx.project)
    times = rc.check_times(ctx, hosts)
    check_ms = sorted(times)
    sample_ms = list(range(500, max(1, ctx.duration_ms), sample_every_ms))
    all_ms = sorted(set(check_ms) | set(sample_ms))
    shots_dir = os.path.join(ctx.stage_dir, ".shots")
    os.makedirs(shots_dir, exist_ok=True)
    per_time: dict = {ms: {"texts": [], "images": []} for ms in all_ms}
    caption_events: list[dict] = []
    harness_errors: list[str] = []
    fonts_seen: dict = {}
    issues: list[dict] = []
    counts = {"hosts": 0, "texts": 0, "images": 0, "times": len(check_ms), "screenshots": 0, "transient": 0}
    gpu = "auto"
    with harness.Harness(lib=ctx.project, gpu=gpu) as h:
        for host in hosts:
            if host.get("no_timeline") or host["component"] == "paper-canvas":
                continue
            comp_file = os.path.join(ctx.project, host["src"])
            if not os.path.isfile(comp_file):
                harness_errors.append(f"{host['id']}: {host['src']} is missing")
                continue
            local_ms = [T for T in all_ms if host["start_ms"] <= T < host["end_ms"]]
            if not local_ms:
                continue
            comp = mcommon.parse_component(comp_file)
            props = dict(host["props"])
            if host["component"] in ("hero-3d", "icon-3d"):
                props["clip_start"] = 0
            h.open(comp, props)
            counts["hosts"] += 1
            res = h.page.evaluate(REVIEW_JS, {"id": comp["id"], "times": [round((T - host["start_ms"]) / 1000.0, 4) for T in local_ms]})
            if host.get("captions"):
                for e in res.get("events", []):
                    if e.get("type") in ("caption_word", "caption_chunk", "caption_overflow"):
                        caption_events.append({**e, "abs_ms": host["start_ms"] + float(e.get("t", 0)) * 1000.0})
            harness_errors += [f"{host['id']}: {x}" for x in h.errors if "Failed to load resource" not in x][:3]
            for T, row in zip(local_ms, res.get("rows", [])):
                shot = None
                if T in times:
                    png = os.path.join(shots_dir, f"{host['id']}-{T}.png")
                    h.page.evaluate(harness.SEEK_JS, {"id": comp["id"], "t": round((T - host["start_ms"]) / 1000.0, 4)})
                    h.page.screenshot(path=png)
                    counts["screenshots"] += 1
                    shot = Image.open(png).convert("RGB")
                for tx in row.get("texts", []):
                    if tx["opacity"] < VISIBLE:
                        continue
                    tx.update({"instance": host["id"], "component": host["component"], "scene": host["scene"], "captions": bool(host.get("captions"))})
                    if shot is not None:
                        fr, fg, fb, _ = rc.parse_css_color(tx["color"])
                        tx["bg_rgb"] = bg_rgb_for_text(shot, {"x": tx["x"], "y": tx["y"], "w": tx["w"], "h": tx["h"]}, (fr, fg, fb))
                    per_time[T]["texts"].append(tx)
                for im in row.get("images", []):
                    if im["opacity"] < VISIBLE or im["w"] < 1 or im["h"] < 1:
                        continue
                    im.update({"instance": host["id"], "component": host["component"], "scene": host["scene"]})
                    if shot is not None and im["src"].startswith("assets/brand/") and im.get("idx", -1) >= 0:
                        # the surface under a logo: the pixels behind it, with the logo hidden for one screenshot
                        png2 = os.path.join(shots_dir, f"{host['id']}-{T}-nologo.png")
                        if h.page.evaluate(HIDE_JS, {"idx": im["idx"], "hide": True}):
                            h.page.screenshot(path=png2)
                            counts["screenshots"] += 1
                            with Image.open(png2) as bare:
                                im["bg_rgb"] = inside_rgb(bare.convert("RGB"), drawn_box(im))
                            h.page.evaluate(HIDE_JS, {"idx": im["idx"], "hide": False})
                            try:
                                os.remove(png2)
                            except OSError:
                                pass
                    elif shot is not None:
                        im["bg_rgb"] = ring_rgb(shot, {"x": im["x"], "y": im["y"], "w": im["w"], "h": im["h"]}, inner=3, outer=9)
                    per_time[T]["images"].append(im)
                if shot is not None:
                    shot.close()
                    try:
                        os.remove(png)
                    except OSError:
                        pass
    try:
        os.rmdir(shots_dir)
    except OSError:
        pass

    # a short-lived instance (its life shorter than the main animation window: a chip on a last word) never settles,
    # so it is judged once, at the last check time of its life that is not an exit, for its geometry
    for host in hosts:
        if host.get("no_timeline") or host["component"] == "paper-canvas" or not rc.short_lived(ctx, host["start_ms"], host["end_ms"]):
            continue
        cands = [T for T in check_ms if any(t["instance"] == host["id"] and t.get("transient") != "exit" for t in per_time[T]["texts"] + per_time[T]["images"])]
        if cands:
            T_last = max(cands)
            for t in per_time[T_last]["texts"] + per_time[T_last]["images"]:
                if t["instance"] == host["id"] and t.get("transient") != "exit":
                    t["judge_anyway"] = True

    # ---------------------------------------------------------------- the rules, at the check times
    seen_issue: set = set()

    def add(iss: dict, key=None) -> None:
        key = key or (iss["kind"], iss.get("instance"), iss.get("text")[:60])
        if key in seen_issue:
            return
        seen_issue.add(key)
        issues.append(iss)

    tag_place = lambda tx: "text" if tx.get("captions") else "animation"  # noqa: E731
    n_checked_texts = 0
    for T in check_ms:
        label = ", ".join(times.get(T, []))
        texts = per_time[T]["texts"]
        images = per_time[T]["images"]
        n_checked_texts += len(texts)
        for tx in texts:
            counts["texts"] += 1
            if tx.get("transient") and not tx.get("judge_anyway"):
                # arriving or leaving (E1's main animation with E2's zoom and rotation, or the exit): a transient by
                # design, judged at the next sample of its life (a short-lived instance once, at its last sample)
                counts["transient"] += 1
                continue
            x0, y0, x1, y1 = tx["x"], tx["y"], tx["x"] + tx["w"], tx["y"] + tx["h"]
            where = f"\"{tx['text']}\" ({tx['component']} {tx['instance']}, scene {tx['scene']}, {rc.fmt_ms(T)})"
            k = (tx["instance"], tx["text"])
            # zones
            in_band = band_top <= (y0 + y1) / 2 <= band_bottom
            if tx.get("captions"):
                if not in_band or x0 < cap_x0 - tol or x1 > cap_x1 + tol:
                    add(rc.issue("text", "zone", f"caption {where} is outside the caption band (x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f}; the band is x {cap_x0:.0f}..{cap_x1:.0f} around y {cap_cy:.0f})", tx["scene"], tx["instance"], T), ("zone",) + k)
            else:
                dm_exception = tx["component"] == "dm-card" and tx["scene"] == cta_id and y1 <= band_bottom + tol
                if y0 < safe_top - tol:
                    add(rc.issue(tag_place(tx), "zone", f"text {where} starts at y {y0:.0f}, above the safe top {safe_top:.0f}", tx["scene"], tx["instance"], T), ("zone",) + k)
                if y1 > safe_bottom + tol and not dm_exception:
                    add(rc.issue(tag_place(tx), "zone", f"text {where} ends at y {y1:.0f}, below the safe bottom {safe_bottom:.0f}", tx["scene"], tx["instance"], T), ("zone",) + k)
                if x0 < margin_x - tol or x1 > rc.CANVAS_W - margin_x + tol:
                    add(rc.issue(tag_place(tx), "zone", f"text {where} runs x {x0:.0f}..{x1:.0f}, outside the {margin_x:.0f} px side margins", tx["scene"], tx["instance"], T), ("zone",) + k)
            # the right rail
            if x1 > rail_x + tol and y1 > rail_from_y:
                add(rc.issue("animation", "right_rail", f"text {where} reaches x {x1:.0f} in the lower half: the right {rc.CANVAS_W - rail_x:.0f} px are Instagram's buttons", tx["scene"], tx["instance"], T), ("right_rail",) + k)
            # off canvas
            if x0 < -tol or y0 < -tol or x1 > rc.CANVAS_W + tol or y1 > rc.CANVAS_H + tol:
                add(rc.issue("animation", "off_canvas", f"text {where} is off the canvas (x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f})", tx["scene"], tx["instance"], T), ("off_canvas",) + k)
            # fonts
            fam = first_family(tx["font"])
            fonts_seen[fam] = fonts_seen.get(fam, 0) + 1
            if families and fam not in families:
                add(rc.issue("text", "font_family", f"text {where} uses the font {fam}, not one of tokens.json ({', '.join(sorted(families))})", tx["scene"], tx["instance"], T), ("font_family",) + k)
            eff = float(tx["size"]) * float(tx.get("scale") or 1)
            if tx.get("transient"):
                eff = float(tx["size"])  # a short-lived element judged mid-zoom: its size is the designed one
            if not tx.get("ignore") and eff < min_font - 0.5:
                add(rc.issue("text", "font_size", f"text {where} is {eff:.0f} px, under the {min_font:.0f} px floor", tx["scene"], tx["instance"], T), ("font_size",) + k)
            if tx.get("captions") and eff < cap_font * cap_min_share - 0.5:
                add(rc.issue("text", "caption_scaled", f"caption {where} was scaled to {eff:.0f} px (the chunk is wider than the {cap_x1 - cap_x0:.0f} px line): split it", tx["scene"], tx["instance"], T), ("caption_scaled",) + k)
            # contrast (only for text at full opacity: a word mid-fade reads as a dark smear over the paper)
            if tx.get("bg_rgb") is not None and tx["opacity"] >= 0.95:
                fr, fg, fb, fa = rc.parse_css_color(tx["color"])
                lt = rc.luminance((fr, fg, fb))
                lb = rc.luminance(tx["bg_rgb"])
                ratio = rc.contrast(lt, lb)
                hexc = "#%02X%02X%02X" % (int(fr), int(fg), int(fb))
                bg_name, bg_dist = rc.nearest_token(tx["bg_rgb"], toks)
                display = hexc in accents or (bg_dist < 40 and ((toks.get("colors") or {}).get(bg_name, "").upper() in accents))
                need = c_large if display else c_min
                if ratio < need - 0.05:
                    add(rc.issue("text", "contrast", f"text {where} has a contrast of {ratio:.2f}:1 against its background ({f'the accent family, {c_large:g}:1 allowed' if display else f'{c_min:g}:1 needed'})", tx["scene"], tx["instance"], T, ratio=round(ratio, 2)), ("contrast",) + k)
        # overlaps between different elements (the arriving and leaving ones left out)
        vis = [t for t in texts if not t.get("ignore") and (not t.get("transient") or t.get("judge_anyway"))]
        for i in range(len(vis)):
            for j in range(i + 1, len(vis)):
                a, b = vis[i], vis[j]
                if a["instance"] == b["instance"] and (a.get("idx") in (b.get("anc") or []) or b.get("idx") in (a.get("anc") or [])):
                    continue  # a word span inside its own line's text (the chip's accent word)
                # the glyphs sit in the middle of the line box: an inset of a sixth of the smaller box keeps adjacent
                # lines of one headline (113 px apart, 122 px line boxes) from counting as an overlap
                inset = max(2.0, 0.17 * min(a["h"], b["h"]))
                area = rc.boxes_intersect({"x": a["x"], "y": a["y"], "w": a["w"], "h": a["h"]}, {"x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"]}, inset=inset)
                if area > 0:
                    add(rc.issue("animation", "overlap", f"\"{a['text']}\" ({a['instance']}) and \"{b['text']}\" ({b['instance']}) overlap at {rc.fmt_ms(T)} ({label})", a["scene"], a["instance"], T),
                        ("overlap", a["instance"], a["text"], b["instance"], b["text"]))
        for im in images:
            counts["images"] += 1
            if im.get("transient") and not im.get("judge_anyway"):
                counts["transient"] += 1
                continue
            x0, y0, x1, y1 = im["x"], im["y"], im["x"] + im["w"], im["y"] + im["h"]
            if x0 < -tol or y0 < -tol or x1 > rc.CANVAS_W + tol or y1 > rc.CANVAS_H + tol:
                add(rc.issue("animation", "off_canvas", f"the image {im['src']} ({im['instance']}) is off the canvas at {rc.fmt_ms(T)}", im["scene"], im["instance"], T))
            if im["src"].startswith("assets/brand/") and x1 > rail_x + tol and y1 > rail_from_y:
                add(rc.issue("animation", "right_rail", f"the logo {im['src']} ({im['instance']}) sits in the right rail of the lower half at {rc.fmt_ms(T)}", im["scene"], im["instance"], T))

    # ---------------------------------------------------------------- emphasis
    emphasis = {"checked": 0, "ok": 0, "results": []}
    em_events = [e for e in caption_events if e.get("type") == "caption_word" and e.get("em")]
    for s in ctx.plan.get("scenes", []):
        for hit in s.get("emphasis_hits", []) or []:
            word = rc.vcommon.norm(str(hit.get("word", "")))
            ms = int(hit.get("ms", 0))
            emphasis["checked"] += 1
            cands = [e for e in em_events if rc.vcommon.norm(str(e.get("text", ""))) == word]
            best = min(cands, key=lambda e: abs(e["abs_ms"] - ms)) if cands else None
            if s.get("beat_type") in ("hook", "ask") and not cands:
                emphasis["results"].append({"word": hit.get("word"), "ms": ms, "ok": True, "note": "no caption in this beat (the headline or the end card carries the words)"})
                emphasis["ok"] += 1
                continue
            if best is None:
                add(rc.issue("text", "emphasis_missing", f"the emphasis on \"{hit.get('word')}\" at {rc.fmt_ms(ms)} (scene {s['id']}) has no accent box in the caption line", s["id"], "captions", ms))
                emphasis["results"].append({"word": hit.get("word"), "ms": ms, "ok": False})
                continue
            err = best["abs_ms"] - ms
            T = min(check_ms, key=lambda t: abs(t - (ms + 150))) if check_ms else None
            on_screen = any(t.get("captions") and rc.vcommon.norm(t["text"]) == word and "em" in (t.get("parent_cls") or "").split() for t in per_time.get(T, {}).get("texts", [])) if T is not None else True
            ok = abs(err) <= em_tol and on_screen
            emphasis["results"].append({"word": hit.get("word"), "ms": ms, "box_ms": round(best["abs_ms"]), "error_ms": round(err), "on_screen": on_screen, "ok": ok})
            if ok:
                emphasis["ok"] += 1
            else:
                add(rc.issue("text", "emphasis_timing", f"the emphasis on \"{hit.get('word')}\" lands {err:+.0f} ms from its word at {rc.fmt_ms(ms)}" + ("" if on_screen else " and the boxed word is not on screen"), s["id"], "captions", ms))

    # ---------------------------------------------------------------- branding
    branding = {"cta_scene": cta_id, "solution": ctx.solution.get("type"), "lockup": None, "avatar": None, "logos": [], "outside_cta": []}
    logo_rows = []
    for T in check_ms:
        for im in per_time[T]["images"]:
            if im["src"].startswith("assets/brand/") and (not im.get("transient") or im.get("judge_anyway")):
                logo_rows.append((T, im))
    seen_logo: set = set()
    for T, im in logo_rows:
        rel = im["src"][len("assets/brand/"):]
        asset = ctx.brand_index.get(rel)
        key = (im["instance"], rel)
        first = key not in seen_logo
        seen_logo.add(key)
        box = drawn_box(im)
        info = {"instance": im["instance"], "scene": im["scene"], "ms": T, "file": rel, "type": asset.get("type") if asset else None, "box": {k: round(v, 1) for k, v in box.items()}, "fit": im.get("fit")}
        if asset is None:
            if first:
                add(rc.issue("animation", "brand_unknown", f"the logo {rel} ({im['instance']}) is not a file of brand.json", im["scene"], im["instance"], T))
            branding["logos"].append(info)
            continue
        W, H = float(asset.get("width") or 1), float(asset.get("height") or 1)
        nw, nh = float(im.get("nw") or 0), float(im.get("nh") or 0)
        natural_ratio = (nw / nh) if nh else (W / H)
        box_ratio = im["w"] / im["h"] if im["h"] else 0
        locked = im.get("fit") == "contain" or abs(box_ratio - natural_ratio) / natural_ratio <= 0.02
        info["aspect_locked"] = locked
        if not locked and first:
            add(rc.issue("animation", "brand_stretched", f"the logo {rel} ({im['instance']}) is drawn at {im['w']:.0f}x{im['h']:.0f} (ratio {box_ratio:.2f}) against the file's {natural_ratio:.2f}: stretched", im["scene"], im["instance"], T))
        bolt_px = None
        if asset.get("bolt_height"):
            bolt_px = box["h"] * float(asset["bolt_height"]) / H
            info["bolt_px"] = round(bolt_px, 1)
            if bolt_px < bolt_min - 0.5 and first:
                add(rc.issue("animation", "brand_small", f"the bolt of {rel} ({im['instance']}) is {bolt_px:.0f} px tall, under {bolt_min:.0f}", im["scene"], im["instance"], T))
        if asset.get("type") == "lockup" and box["w"] < lockup_min - 0.5 and first:
            add(rc.issue("animation", "brand_small", f"the lockup {rel} ({im['instance']}) is {box['w']:.0f} px wide, under {lockup_min:.0f}", im["scene"], im["instance"], T))
        if asset.get("type") == "avatar" and min(box["w"], box["h"]) < avatar_min - 0.5 and first:
            add(rc.issue("animation", "brand_small", f"the avatar {rel} ({im['instance']}) is {min(box['w'], box['h']):.0f} px across, under {avatar_min:.0f}", im["scene"], im["instance"], T))
        # the surface under it
        surf = im.get("bg_rgb")
        if surf is not None:
            lum = rc.luminance(surf)
            surface = "light" if lum >= 0.5 else "dark"
            info["surface"] = surface
            info["surface_luminance"] = round(lum, 3)
            use_on = asset.get("use_on", "both")
            if use_on not in ("both", surface) and first:
                add(rc.issue("animation", "brand_variant", f"the logo {rel} ({im['instance']}) is a {use_on}-surface variant on a {surface} surface (luminance {lum:.2f})", im["scene"], im["instance"], T))
            pct = png_luminance_percentiles(os.path.join(rc.vcommon.brand_dir(), rel))
            if pct:
                ratio = max(rc.contrast(pct[0], lum), rc.contrast(pct[1], lum))
                info["contrast"] = round(ratio, 2)
                if ratio < c_large - 0.05 and first:
                    add(rc.issue("animation", "brand_contrast", f"the logo {rel} ({im['instance']}) reads at {ratio:.2f}:1 against the {surface} surface under it", im["scene"], im["instance"], T))
        # clear space: nothing of another element within a quarter of the bolt's height around the content box
        if bolt_px:
            cb = asset.get("content_box") or [0, 0, W, H]
            content = {"x": box["x"] + cb[0] / W * box["w"], "y": box["y"] + cb[1] / H * box["h"], "w": (cb[2] - cb[0]) / W * box["w"], "h": (cb[3] - cb[1]) / H * box["h"]}
            clear = bolt_px * 0.25
            grown = {"x": content["x"] - clear, "y": content["y"] - clear, "w": content["w"] + 2 * clear, "h": content["h"] + 2 * clear}
            intruders = []
            for tx in per_time[T]["texts"]:
                if rc.boxes_intersect(grown, {"x": tx["x"], "y": tx["y"], "w": tx["w"], "h": tx["h"]}, inset=0.0) > 0:
                    intruders.append(f"\"{tx['text']}\" ({tx['instance']})")
            for other in per_time[T]["images"]:
                if other is im:
                    continue
                if rc.boxes_intersect(grown, {"x": other["x"], "y": other["y"], "w": other["w"], "h": other["h"]}, inset=0.0) > 0:
                    intruders.append(f"{other['src']} ({other['instance']})")
            info["clear_space_px"] = round(clear, 1)
            if intruders and first:
                add(rc.issue("animation", "brand_clear_space", f"the logo {rel} ({im['instance']}) has {', '.join(intruders[:3])} inside its clear space ({clear:.0f} px)", im["scene"], im["instance"], T))
        if im["scene"] != cta_id and not flashfx:
            branding["outside_cta"].append(info)
            if first:
                add(rc.issue("animation", "brand_outside", f"the FlashFX logo {rel} shows in the body ({im['instance']}, scene {im['scene']}) although the reel's solution is {ctx.solution.get('type')}", im["scene"], im["instance"], T))
        if im["scene"] == cta_id and asset.get("type") == "lockup" and (branding["lockup"] is None or T == cta_time):
            branding["lockup"] = info
        if im["scene"] == cta_id and asset.get("type") == "avatar" and (branding["avatar"] is None or T == cta_time):
            branding["avatar"] = info
        branding["logos"].append(info)
    if cta:
        if branding["lockup"] is None:
            add(rc.issue("animation", "brand_cta", f"the CTA scene {cta_id} shows no FlashFX lockup (tweaks.md Branding: the end card carries it, {lockup_min:.0f} px or wider)", cta_id, "", cta_time))
        if branding["avatar"] is None:
            add(rc.issue("animation", "brand_cta", f"the CTA scene {cta_id} shows no DM card with the FlashFX avatar (mark/avatar-dark.png, {avatar_min:.0f} px or wider)", cta_id, "", cta_time))
    else:
        add(rc.issue("animation", "brand_cta", "the plan has no CTA scene (no ask beat)", "", ""))

    images_by_time = {str(T): [[round(im["x"]), round(im["y"]), round(im["w"]), round(im["h"]), "logo" if im["src"].startswith("assets/brand/") else "image"] for im in per_time[T]["images"]] for T in sample_ms}
    report = {"written_by": "12-review", "pass": not issues, "issues": issues, "counts": counts, "times": {str(k): v for k, v in times.items()},
              "fonts_seen": fonts_seen, "emphasis": emphasis, "branding": branding, "images_by_time": images_by_time, "harness_errors": harness_errors[:20],
              "thresholds": {"safe_top": safe_top, "safe_bottom": safe_bottom, "margin_x": margin_x, "caption_band": [band_top, band_bottom], "right_rail_x": rail_x,
                             "min_font_px": min_font, "contrast": [c_min, c_large], "emphasis_tolerance_ms": em_tol, "lockup_min": lockup_min, "bolt_min": bolt_min, "avatar_min": avatar_min}}
    rc.write_json(out_path, report)
    return report
