"""mapper.py: every captured layer to the most editable level the manifest allows (BUILD_SPEC.md S15 step 3, M21).

  native   the editor's own clip with the captured motion as keyframes: solid, text, image
  sprite   the layer rendered once at rest, isolated, as an image clip with the motion as keyframes
  overlay  a continuous look change the editor cannot key: the layer rendered isolated over its interval (alpha video, PNG
           sequence or animated WebP, by the manifest)
  plate    one opaque video of a scene's layers (the last resort, used by the downgrade ladder)

analyze(...) gives the items (what each part becomes and why); finalize_item(...) builds the clip dict once a sprite or an
overlay has been rendered (render.py). Everything that stops a layer from being native names the manifest key it lacks
(item["missing"]), which goes to FALLBACKS.md and logs/editor-gaps.md.
"""
from __future__ import annotations

import math
import re

from . import geom

# ---------------------------------------------------------------------------------------------------- css values

COLOR_RE = re.compile(r"rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:\s*[,/]\s*([\d.%]+))?\s*\)")
LABEL = {"sprite": "violet", "overlay": "orange", "plate": "red"}


def parse_color(css: str | None) -> dict | None:
    """rgb(), rgba() or color(srgb ...) to {r,g,b,a} (0..1); None when not a plain color."""
    if not css:
        return None
    css = css.strip()
    if css == "transparent":
        return {"r": 0, "g": 0, "b": 0, "a": 0}
    m = COLOR_RE.search(css)
    if m:
        a = m.group(4)
        alpha = 1.0 if a is None else (float(a[:-1]) / 100.0 if a.endswith("%") else float(a))
        return {"r": round(float(m.group(1)) / 255, 4), "g": round(float(m.group(2)) / 255, 4), "b": round(float(m.group(3)) / 255, 4), "a": round(alpha, 4)}
    m = re.match(r"color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*/\s*([\d.]+))?\)", css)
    if m:
        return {"r": round(float(m.group(1)), 4), "g": round(float(m.group(2)), 4), "b": round(float(m.group(3)), 4), "a": round(float(m.group(4) or 1), 4)}
    return None


def px(v) -> float:
    try:
        return float(str(v).replace("px", "").strip() or 0)
    except ValueError:
        return 0.0


def split_top(text: str) -> list[str]:
    """Split a CSS list on top-level commas."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_shadows(css: str) -> list[dict] | None:
    """box-shadow or text-shadow to [{x, y, blur, spread, color, inset}]; None when it does not parse."""
    if not css or css == "none":
        return []
    out = []
    for part in split_top(css):
        col = COLOR_RE.search(part)
        color = parse_color(col.group(0)) if col else None
        rest = COLOR_RE.sub("", part).replace("inset", " ").split()
        nums = []
        for tkn in rest:
            try:
                nums.append(px(tkn))
            except ValueError:
                return None
        if len(nums) < 2 or color is None:
            return None
        out.append({"x": nums[0], "y": nums[1], "blur": nums[2] if len(nums) > 2 else 0.0, "spread": nums[3] if len(nums) > 3 else 0.0,
                    "color": color, "inset": "inset" in part})
    return out


def parse_gradient(css: str) -> dict | None:
    """background-image: linear-gradient(...) to {angle, stops:[(at, color)]}; None for anything else."""
    m = re.match(r"^linear-gradient\((.*)\)$", (css or "").strip(), re.S)
    if not m:
        return None
    parts = split_top(m.group(1))
    angle = 180.0
    if parts and re.match(r"^-?[\d.]+deg$", parts[0]):
        angle = float(parts[0][:-3])
        parts = parts[1:]
    elif parts and parts[0].startswith("to "):
        angle = {"to bottom": 180.0, "to top": 0.0, "to right": 90.0, "to left": 270.0}.get(parts[0], 180.0)
        parts = parts[1:]
    stops = []
    for i, p in enumerate(parts):
        col = COLOR_RE.search(p)
        c = parse_color(col.group(0)) if col else None
        if c is None:
            return None
        pos = re.search(r"([\d.]+)%", COLOR_RE.sub("", p))
        stops.append((float(pos.group(1)) / 100 if pos else i / max(1, len(parts) - 1), c))
    if len(stops) < 2:
        return None
    return {"angle": angle, "stops": stops}


# ---------------------------------------------------------------------------------------------------- context


class Ctx:
    def __init__(self, manifest, fonts: dict, fps: float, width: int, height: int, cfg: dict | None = None, downgrades: dict | None = None):
        self.m = manifest
        self.fonts = fonts            # {family lower: {"family", "source": library|user, "file", "origin"}}
        self.fps = fps
        self.W, self.H = width, height
        self.cfg = cfg or {}
        self.downgrades = downgrades or {}
        self.affine_tol = float(self.cfg.get("affine_tolerance_px", 1.5))
        self.z = 0
        self.images: dict[str, str] = {}   # source file -> media relpath (filled by the writer)

    def next_z(self) -> int:
        self.z += 1
        return self.z


# ---------------------------------------------------------------------------------------------------- local geometry


def local_point(pose: list, w: float, h: float, page_pt: tuple[float, float]) -> tuple[float, float]:
    """The point of the page in the box's own coordinates (0..w, 0..h), by the inverse of the pose's affine map."""
    cx, cy, sx, sy, rot = pose[0], pose[1], pose[2], pose[3], pose[4]
    dx, dy = page_pt[0] - cx, page_pt[1] - cy
    r = math.radians(-rot)
    ux, uy = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
    return ux / max(sx, 1e-9) + w / 2.0, uy / max(sy, 1e-9) + h / 2.0


def world_point(pose: list, w: float, h: float, local: tuple[float, float]) -> tuple[float, float]:
    cx, cy, sx, sy, rot = pose[0], pose[1], pose[2], pose[3], pose[4]
    ux, uy = (local[0] - w / 2.0) * sx, (local[1] - h / 2.0) * sy
    r = math.radians(rot)
    return cx + ux * math.cos(r) - uy * math.sin(r), cy + ux * math.sin(r) + uy * math.cos(r)


def text_lines(info: dict, pose: list, w: float, h: float) -> dict | None:
    """The browser's own line breaks of the layer's text and its bounds in the box's coordinates."""
    chars = [c for c in (info.get("chars") or []) if not (c[0].isspace() and c[3] - c[1] < 0.01)]
    if not chars:
        return None
    lines: list[list] = []
    for c in chars:
        mid = (c[2] + c[4]) / 2.0
        hgt = c[4] - c[2]
        if lines and abs(((lines[-1][0][2] + lines[-1][0][4]) / 2.0) - mid) < max(2.0, hgt * 0.5):
            lines[-1].append(c)
        else:
            lines.append([c])
    texts, rects = [], []
    for ln in lines:
        s = "".join(c[0] for c in ln).strip()
        if not s:
            continue
        texts.append(re.sub(r"\s+", " ", s))
        xs0, ys0 = min(c[1] for c in ln), min(c[2] for c in ln)
        xs1, ys1 = max(c[3] for c in ln), max(c[4] for c in ln)
        corners = [local_point(pose, w, h, p) for p in ((xs0, ys0), (xs1, ys0), (xs1, ys1), (xs0, ys1))]
        rects.append((min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners)))
    if not texts:
        return None
    return {"lines": texts, "rects": rects}


# ---------------------------------------------------------------------------------------------------- analysis


def gap(item: dict, keys: list[str], what: str) -> None:
    for k in keys:
        if k not in item["missing"]:
            item["missing"].append(k)
    item.setdefault("why", []).append(what)


def look_flags(info: dict) -> dict:
    """What the layer's own look needs, from its description."""
    bg = parse_color((info.get("bg") or {}).get("color"))
    image = (info.get("bg") or {}).get("image") or "none"
    border = info.get("border") or {}
    widths = [px(border.get(s, ["0"])[0]) if border.get(s) else 0.0 for s in ("top", "right", "bottom", "left")]
    styles = [border[s][1] if border.get(s) else "none" for s in ("top", "right", "bottom", "left")]
    colors = [border[s][2] if border.get(s) else "" for s in ("top", "right", "bottom", "left")]
    has_border = any(w > 0 and s not in ("none", "hidden") for w, s in zip(widths, styles))
    shadows = parse_shadows(info.get("shadow") or "none")
    radius = [px(r.split(" ")[0]) for r in (info.get("radius") or ["0"] * 4)]
    return {"bg": bg, "bg_image": image, "has_bg": bool(bg and bg["a"] > 0.001) or image != "none", "widths": widths, "styles": styles, "colors": colors,
            "has_border": has_border, "shadows": shadows, "radius": radius}


def complex_reason(info: dict) -> str | None:
    if info.get("filter") not in (None, "", "none"):
        return "filter"
    if info.get("clipPath") not in (None, "", "none"):
        return "clip-path"
    if info.get("mask") not in (None, "", "none"):
        return "mask"
    if info.get("blend") not in (None, "", "normal"):
        return "mix-blend-mode"
    if info.get("backdrop") not in (None, "", "none"):
        return "backdrop-filter"
    return None


def solid_native(ctx: Ctx, item: dict, info: dict, lf: dict, w: float, h: float) -> dict | None:
    """The native solid for the layer's box, or None (the missing keys go to the item)."""
    shadows = lf["shadows"]
    if shadows is None or any(s["inset"] for s in shadows) or len(shadows) > 1:
        gap(item, [], "a box-shadow the editor's single outer shadow cannot express")
        return None
    uniform = len(set(lf["widths"])) == 1 and len(set(lf["colors"])) == 1 and len(set(lf["styles"])) == 1
    if lf["has_border"] and (not uniform or lf["styles"][0] not in ("solid",)):
        gap(item, [], "a border that is not one solid line around the box")
        return None
    fill = None
    gradient = None
    grad_stops = None
    if lf["bg_image"] != "none":
        g = parse_gradient(lf["bg_image"])
        if g is None:
            gap(item, [], "a background image or gradient the solid fills do not cover")
            return None
        if len(g["stops"]) == 2 and abs(g["angle"] - 180.0) < 0.5 and ctx.m.lists("solid.fills", "gradient2"):
            gradient = {"from": g["stops"][0][1], "to": g["stops"][1][1]}
        elif ctx.m.lists("solid.fills", "linear"):
            grad_stops = {"type": "linear", "angle": round((g["angle"] - 180.0) % 360.0, 3), "center": {"x": 0.5, "y": 0.5}, "radius": 1,
                          "stops": [{"at": round(a, 4), "color": c} for a, c in g["stops"]]}
        else:
            gap(item, ["solid.fills:gradient2" if len(g["stops"]) == 2 else "solid.fills:linear"], "a gradient fill")
            return None
    else:
        fill = lf["bg"] or {"r": 0, "g": 0, "b": 0, "a": 0}
    radii = lf["radius"]
    rmax = min(w, h) / 2.0
    shape, radius, radii4 = "rect", 0.0, None
    if max(radii) > 0.01:
        if len(set(round(r, 2) for r in radii)) == 1:
            radius = min(radii[0], rmax)
            shape = "ellipse" if abs(w - h) < 1 and radii[0] >= rmax - 0.5 else "roundedRect"
        else:
            shape, radius, radii4 = "roundedRect", min(radii), [min(r, rmax) for r in radii]
    miss = ctx.m.solid_missing(lf["has_border"], bool(shadows), radii4 is not None, False)
    if miss:
        gap(item, miss, "solid style the editor cannot express yet")
        return None
    clip = {"kind": "solid", "shape": shape, "size": {"w": round(w, 2), "h": round(h, 2)}, "cornerRadius": round(radius, 2)}
    clip["fill"] = gradient or grad_stops or fill
    if radii4 is not None:
        clip["cornerRadii"] = [round(r, 2) for r in radii4]
    if lf["has_border"]:
        col = parse_color(lf["colors"][0]) or {"r": 0, "g": 0, "b": 0, "a": 1}
        clip["stroke"] = {"width": round(lf["widths"][0], 2), "color": col, "align": "inside"}
    if shadows:
        s = shadows[0]
        clip["shadow"] = {"x": s["x"], "y": s["y"], "blur": s["blur"], "spread": s["spread"], "color": s["color"]}
    return clip


def text_native(ctx: Ctx, item: dict, info: dict, tl: dict, pose: list, w: float, h: float) -> dict | None:
    f = info.get("font") or {}
    fam = (f.get("family") or "").split(",")[0].strip().strip("'\"")
    entry = ctx.fonts.get(fam.lower())
    if entry is None:
        gap(item, [], f"the font {fam} is not in the editor's library and not a file of the composition")
        return None
    shadows = parse_shadows(f.get("shadow") or "none")
    if shadows is None or len(shadows) > 1 or (shadows and shadows[0]["inset"]):
        gap(item, [], "a text-shadow the editor's single shadow cannot express")
        return None
    sw = px(f.get("strokeWidth") or "0")
    scol = parse_color(f.get("strokeColor"))
    fill = parse_color(f.get("color"))
    if fill is None:
        gap(item, [], "a text fill that is not a plain color")
        return None
    miss = ctx.m.text_missing(sw > 0, bool(shadows), None, False, False, False)
    if miss:
        gap(item, miss, "text style the editor cannot express yet")
        return None
    weight = f.get("weight") or "400"
    try:
        weight = int(float(weight))
    except ValueError:
        weight = 700 if weight == "bold" else 400
    size = float(f.get("size") or 16)
    ls = px(f.get("letterSpacing") or "0") if f.get("letterSpacing") not in (None, "normal") else 0.0
    lh_css = f.get("lineHeight")
    lh = px(lh_css) / size if lh_css and lh_css != "normal" else 1.2
    rects = tl["rects"]
    lefts = [r[0] for r in rects]
    rights = [r[2] for r in rects]
    centers = [(r[0] + r[2]) / 2 for r in rects]
    tol = 2.0
    if len(rects) == 1 or (max(centers) - min(centers) < tol):
        align = "center"
    elif max(lefts) - min(lefts) < tol:
        align = "left"
    elif max(rights) - min(rights) < tol:
        align = "right"
    else:
        align = "center"
    style = {"fontFamily": entry["family"], "fontWeight": weight, "italic": f.get("style") == "italic", "fontSize": round(size, 3), "fill": fill,
             "stroke": {"enabled": sw > 0, "width": sw, "color": scol or {"r": 0, "g": 0, "b": 0, "a": 1}},
             "shadow": ({"enabled": True, "x": shadows[0]["x"], "y": shadows[0]["y"], "blur": shadows[0]["blur"], "color": shadows[0]["color"]} if shadows else
                        {"enabled": False, "x": 0, "y": 6, "blur": 16, "color": {"r": 0, "g": 0, "b": 0, "a": 0.6}}),
             "background": {"enabled": False, "color": {"r": 0, "g": 0, "b": 0, "a": 0.7}, "paddingX": 28, "paddingY": 12, "radius": 16, "mode": "block"},
             "textCase": "none", "letterSpacing": round(ls, 3), "lineHeight": round(lh, 4), "align": align, "verticalAnchor": "middle"}
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    return {"kind": "text", "text": {"value": "\n".join(tl["lines"]), "box": {"mode": "auto", "width": 900}}, "style": style,
            "bounds": (x0, y0, x1, y1), "font_entry": entry}


def image_native(ctx: Ctx, item: dict, info: dict, w: float, h: float, lf: dict) -> dict | None:
    src = info.get("src") or ""
    if not src or not info.get("nw"):
        gap(item, [], "an image with no source")
        return None
    nw, nh = float(info["nw"]), float(info["nh"])
    fit = info.get("fit") or "fill"
    pos_x, pos_y = 0.5, 0.0 if fit == "cover" else 0.5
    if fit == "cover":
        s = max(w / nw, h / nh)
        vis_w, vis_h = w / s, h / s
        crop = {"left": round((nw - vis_w) * pos_x / nw, 5), "right": round((nw - vis_w) * (1 - pos_x) / nw, 5),
                "top": round((nh - vis_h) * pos_y / nh, 5), "bottom": round((nh - vis_h) * (1 - pos_y) / nh, 5)}
        sx = sy = s
    elif fit == "contain":
        sx = sy = min(w / nw, h / nh)
        crop = {"left": 0, "right": 0, "top": 0, "bottom": 0}
        w, h = nw * sx, nh * sy
    else:
        sx, sy = w / nw, h / nh
        crop = {"left": 0, "right": 0, "top": 0, "bottom": 0}
    clip_info = info.get("clip") or {}
    radius = 0.0
    if clip_info:
        if abs(clip_info.get("w", 0) - w) < 1.5 and abs(clip_info.get("h", 0) - h) < 1.5:
            radius = max((px(r.split(" ")[0]) for r in clip_info.get("radius") or ["0"]), default=0.0)
        else:
            gap(item, [], "an image clipped by a box of another size")
            return None
    own_radius = max(lf["radius"]) if lf["radius"] else 0.0
    radius = max(radius, own_radius)
    if radius > 0.01 and not ctx.m.has("mediaFrame.cornerRadius"):
        gap(item, ["mediaFrame.cornerRadius"], "a rounded picture")
        return None
    if lf["has_border"] and not ctx.m.has("mediaFrame.stroke"):
        gap(item, ["mediaFrame.stroke"], "a picture with a border")
        return None
    shadows = lf["shadows"]
    if shadows and not ctx.m.has("mediaFrame.shadow"):
        gap(item, ["mediaFrame.shadow"], "a picture with a shadow")
        return None
    clip = {"kind": "image", "source": src, "crop": crop, "scale_x": sx, "scale_y": sy, "box": (w, h), "nw": nw, "nh": nh}
    if radius > 0.01:
        clip["cornerRadius"] = round(radius, 2)
    if lf["has_border"]:
        clip["stroke"] = {"width": round(lf["widths"][0], 2), "color": parse_color(lf["colors"][0]) or {"r": 0, "g": 0, "b": 0, "a": 1}, "align": "inside"}
    if shadows and len(shadows) == 1 and not shadows[0]["inset"]:
        s = shadows[0]
        clip["shadow"] = {"x": s["x"], "y": s["y"], "blur": s["blur"], "spread": s["spread"], "color": s["color"]}
    return clip


def new_item(ctx: Ctx, host: dict, layer: dict, run: dict, ri: int, part: str) -> dict:
    key = f"{host['id']}/{layer['id']}#{ri}"
    return {"key": key, "layer_key": f"{host['id']}/{layer['id']}", "host": host["id"], "component": host["component"], "scene": host.get("scene", ""), "layer": layer["id"],
            "layer_name": layer["name"], "run": ri, "part": part, "start": run["start"], "end": run["end"], "z": ctx.next_z(), "missing": [], "why": [],
            "poses": run["pose"], "opacity": run["opacity"], "quads": run["quad"], "mode": run.get("mode", "static"), "info_frame": run.get("info_frame", run["start"])}


def analyze(ctx: Ctx, layers_json: dict) -> list[dict]:
    """The items of the whole composition, bottom to top."""
    items: list[dict] = []
    for host in layers_json["hosts"]:
        if host.get("captions"):
            continue
        for li, layer in enumerate(host["layers"]):
            for ri, run in enumerate(layer["runs"]):
                for it in analyze_run(ctx, host, layer, run, ri):
                    it["li"] = li
                    items.append(it)
    return items


def raster_item(ctx: Ctx, base: dict, level: str, reason: str) -> dict:
    it = dict(base)
    it["level"] = level
    it["kind"] = "sprite" if level == "sprite" else "overlay" if level == "overlay" else "plate"
    it["part"] = "raster"
    if reason:
        it["why"] = list(base.get("why", [])) + [reason]
    return it


def analyze_run(ctx: Ctx, host: dict, layer: dict, run: dict, ri: int) -> list[dict]:
    info = run["info"] or {}
    w, h = float(info.get("w") or layer["w"] or 0), float(info.get("h") or layer["h"] or 0)
    lf = look_flags(info)
    base = new_item(ctx, host, layer, run, ri, "raster")
    forced = ctx.downgrades.get(base["layer_key"])
    max_err = max((p[6] for p in run["pose"]), default=0.0)
    max_skew = max((abs(p[5]) for p in run["pose"]), default=0.0)
    flat = [p for p in run["pose"]]
    has_text = bool(info.get("chars"))
    is_img = info.get("tag") == "img"
    is_dynamic = (layer["kind"] == "dynamic") or info.get("hasCanvas") or info.get("hasVideo") or layer["tag"] == "canvas"
    own_visual = lf["has_bg"] or lf["has_border"] or bool(lf["shadows"])
    if layer["annotated"] is False:
        own_visual = True   # the synthetic layer: the whole component, rendered
    is_svg = info.get("tag") == "svg" and layer["kind"] != "text"
    # a layer with nothing of its own to draw (a container): its children are layers of their own
    if not (has_text or is_img or own_visual or is_dynamic or is_svg):
        return []
    # the level the look allows
    if run.get("mode") == "continuous" or is_dynamic:
        want = "overlay"
        why = "its look changes continuously" if not is_dynamic else "dynamic content (canvas, video or 3D)"
    elif is_svg or complex_reason(info) or not layer["annotated"]:
        want = "sprite"
        why = f"drawn with {complex_reason(info)}" if complex_reason(info) else ("svg artwork" if is_svg else "a component without editor annotations")
    else:
        want = "native"
        why = ""
    if want in ("native", "sprite") and (max_err > ctx.affine_tol or max_skew > 0.02):
        want, why = "overlay", f"a 3D or skewed transform (an affine fit is off by {max_err:.1f} px)"
    if is_svg and want == "sprite" and run.get("mode") == "continuous":
        want = "overlay"
    if forced:
        order = ["native", "sprite", "overlay", "plate"]
        if order.index(forced) > order.index(want):
            want, why = forced, f"dropped one level after a failed check ({forced})"
    if want in ("sprite", "overlay", "plate"):
        it = raster_item(ctx, base, want, why)
        if want == "sprite":
            it["f_star"] = best_rest_frame(run)
        return [it]
    # native: every part must be expressible, otherwise the whole layer is one raster
    parts: list[dict] = []
    pose_c = run["pose"][min(len(run["pose"]) - 1, max(0, run.get("info_frame", run["start"]) - run["start"]))]
    if own_visual and not is_img:
        p = new_item(ctx, host, layer, run, ri, "solid")
        clip = solid_native(ctx, p, info, lf, w, h)
        if clip is None:
            fail = p
        else:
            p.update({"level": "native", "kind": "solid", "native": clip, "name": f"{layer['name']}"})
            parts.append(p)
            fail = None
        if fail is not None:
            miss, whys = fail["missing"], fail["why"]
            it = raster_item(ctx, base, "sprite", "; ".join(whys))
            it["missing"] = miss
            stand = stand_in_solid(ctx, base, info, lf, w, h)
            if stand:
                it["stand_in"] = stand
            it["f_star"] = best_rest_frame(run)
            if max_err > ctx.affine_tol:
                it["level"], it["kind"] = "overlay", "overlay"
            return [it]
    if is_img:
        p = new_item(ctx, host, layer, run, ri, "image")
        clip = image_native(ctx, p, info, w, h, lf)
        if clip is None:
            it = raster_item(ctx, base, "sprite", "; ".join(p["why"]))
            it["missing"] = p["missing"]
            it["f_star"] = best_rest_frame(run)
            return [it]
        p.update({"level": "native", "kind": "image", "native": clip, "name": layer["name"]})
        parts.append(p)
    if has_text:
        p = new_item(ctx, host, layer, run, ri, "text")
        tl = text_lines(info, pose_c, w, h)
        clip = text_native(ctx, p, info, tl, pose_c, w, h) if tl else None
        if clip is None:
            it = raster_item(ctx, base, "sprite", "; ".join(p["why"]) or "text the editor cannot express")
            it["missing"] = p["missing"]
            it["f_star"] = best_rest_frame(run)
            return [it]
        p.update({"level": "native", "kind": "text", "native": clip, "name": f"{layer['name']}: {clip['text']['value'].splitlines()[0][:40]}", "box": (w, h)})
        parts.append(p)
    for p in parts:
        p["box"] = (w, h)
    return parts


class _Everything:
    """A manifest that supports every key: used to describe the native clip a sprite stands in for (fallbackOf.data)."""
    schema_version = 99

    def has(self, path): return True
    def lists(self, path, value): return True
    def clip_kind(self, kind): return True
    def key_prop(self, prop): return True
    def ease(self, name): return True
    def get(self, path, default=None): return default
    def solid_missing(self, *a, **k): return []
    def text_missing(self, *a, **k): return []


def stand_in_solid(ctx: Ctx, base: dict, info: dict, lf: dict, w: float, h: float) -> dict | None:
    """The native solid a baked layer stands for, in the editor's JSON (sparse: no id, track, start or duration)."""
    perm = Ctx(_Everything(), ctx.fonts, ctx.fps, ctx.W, ctx.H, ctx.cfg)
    tmp = {"missing": [], "why": []}
    clip = solid_native(perm, tmp, info, lf, w, h)
    if clip is None:
        return None
    out = {k: v for k, v in clip.items()}
    out["name"] = base["layer_name"]
    return out


def best_rest_frame(run: dict) -> int:
    """The frame the sprite is rendered at: the largest scale reached while (nearly) opaque, nearest the end of its life."""
    ops, poses = run["opacity"], run["pose"]
    best, best_score = 0, None
    top = max(ops)
    for k, (o, p) in enumerate(zip(ops, poses)):
        if o < top - 0.02:
            continue
        score = (round(max(p[2], p[3]), 3), k)
        if best_score is None or score > best_score:
            best, best_score = k, score
    return run["start"] + best


# ---------------------------------------------------------------------------------------------------- keyframes


def _unwrapped_rotation(poses: list) -> list[float]:
    return geom.unwrap([p[4] for p in poses])


def key_tracks(ctx: Ctx, item: dict, point_fn, scale_ref=(1.0, 1.0), rot_ref=0.0, opacity_ref=1.0, flip=False) -> tuple[dict, dict]:
    """(transform, keyframes) for an item: per frame the clip's x and y (point_fn(pose) in page px -> project px from the frame center), scale,
    rotation and opacity, reduced to the fewest keys within the spec's tolerances. Frames are relative to the clip start."""
    poses, ops = item["poses"], item["opacity"]
    n = len(poses)
    frames = list(range(n))
    rots = _unwrapped_rotation(poses)
    xs, ys, ss, sys_, rs, os_ = [], [], [], [], [], []
    for k, p in enumerate(poses):
        px_, py_ = point_fn(p)
        xs.append(px_ - ctx.W / 2.0)
        ys.append(py_ - ctx.H / 2.0)
        ss.append(p[2] / scale_ref[0])
        sys_.append(p[3] / scale_ref[1])
        rs.append(rots[k] - rot_ref)
        os_.append(min(1.0, ops[k] / opacity_ref))
    allowed = [e for e in geom.PENNER_ORDER if e != "linear" and ctx.m.ease(e)]
    series = {"transform.x": xs, "transform.y": ys, "transform.scale": ss, "transform.rotation": rs, "opacity": os_}
    uniform = max(abs(a - b) for a, b in zip(ss, sys_)) <= geom.TOL["transform.scale"]
    if not uniform:
        series["transform.scaleY"] = sys_
    keyframes: dict[str, list] = {}
    base = {"x": round(xs[0], 3), "y": round(ys[0], 3), "scale": round(ss[0], 5), "rotation": round(rs[0], 4), "anchor": {"x": 0.5, "y": 0.5}, "flipH": False, "flipV": False}
    opacity = round(os_[0], 4)
    if not uniform:
        base["scaleY"] = round(sys_[0], 5)
    for prop, vals in series.items():
        if not ctx.m.key_prop(prop):
            # the manifest cannot key it: the first value stays (the layout check reports a layer that moved)
            continue
        tol = geom.TOL.get(prop, geom.TOL["default"])
        if max(vals) - min(vals) <= tol:
            continue
        keys = geom.reduce_constant_tail(geom.reduce_scalar(frames, vals, tol, allowed))
        if geom.check_keys(keys, frames, vals, tol * 1.01) > tol * 1.01:
            keys = [{"frame": f, "value": round(v, 4), "ease": "linear"} for f, v in zip(frames, vals)]
        keyframes[prop] = keys
    return {"transform": base, "opacity": opacity, "keyframes": keyframes}, {}


def native_motion(ctx: Ctx, item: dict) -> dict:
    """x, y, scale, rotation and opacity keys of a native item. A text's clip center is the center of its text bounds."""
    w, h = item["box"]
    if item["kind"] == "text":
        x0, y0, x1, y1 = item["native"]["bounds"]
        local = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        point = lambda p: world_point(p, w, h, local)   # noqa: E731
    else:
        point = lambda p: (p[0], p[1])   # noqa: E731
    res, _ = key_tracks(ctx, item, point)
    return res


def sprite_motion(ctx: Ctx, item: dict, rr: dict) -> dict:
    """The motion of a sprite: its image keeps the pose it was rendered at (f_star) and moves with the layer."""
    k = item["f_star"] - item["start"]
    ref = item["poses"][k]
    ox, oy = (rr["x0"] + rr["x1"]) / 2.0 - ref[0], (rr["y0"] + rr["y1"]) / 2.0 - ref[1]
    rr_w = max(1.0, ref[2]), max(1.0, ref[3])

    def point(p):
        r = math.radians(p[4] - ref[4])
        dx, dy = ox * p[2] / rr_w[0], oy * p[3] / rr_w[1]
        return p[0] + dx * math.cos(r) - dy * math.sin(r), p[1] + dx * math.sin(r) + dy * math.cos(r)

    rot_ref = geom.unwrap([q[4] for q in item["poses"]])[k]
    res, _ = key_tracks(ctx, item, point, scale_ref=(ref[2] * rr["dsf"], ref[3] * rr["dsf"]), rot_ref=rot_ref, opacity_ref=max(0.05, item["opacity"][k]))
    return res
