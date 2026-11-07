"""pipeline/lib/review/common.py: shared helpers of the review stage S12 (M11): the run's context (config, tokens,
brand.json, the catalog), the built project's hosts read from 10-build/project/index.html (the source of truth for
what is on screen: a planted fault in the project is caught, not what the plan says), the check times, colors and
contrast, the issue records with their tags, the progress lines for the stage script.

Tags (BUILD_SPEC.md S12): [voice], [animation], [text], [transition], [sfx]. The fix routing (route.py) sends each tag
to the step that owns it: voice -> 08-voiceover, animation -> 09a-animations, text -> 09b-text,
transition -> 09c-transitions, sfx -> 11-sfx.
"""
from __future__ import annotations

import html
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from motion import common as mcommon  # noqa: E402
from visual import common as vcommon  # noqa: E402

REPO = mcommon.REPO
FPS = 30
TAGS = ("voice", "animation", "text", "transition", "sfx")
TAG_STAGE = {"voice": "08-voiceover", "animation": "09a-animations", "text": "09b-text", "transition": "09c-transitions", "sfx": "11-sfx"}
STAGE_ORDER = ["08-voiceover", "09a-animations", "09b-text", "09c-transitions", "10-build", "11-sfx", "12-review"]
CANVAS_W, CANVAS_H = 1080, 1920


def say(tag: str, text: str) -> None:
    print(f"@@SAY {tag} {undash(text)}", flush=True)


def activity(text: str) -> None:
    print(f"@@ACTIVITY {text}", flush=True)


def flag(text: str) -> None:
    print(f"@@FLAG {undash(text)}", flush=True)


def error(text: str) -> None:
    print(f"@@ERROR {undash(text)}", flush=True)


def log(text: str) -> None:
    print(undash(text), flush=True)


def undash(text) -> str:
    return str(text).replace("\u2014", ", ").replace("\u2013", "-")


def mixed(path: str) -> str:
    return mcommon.mixed(path)


def load_json(path: str, default=None):
    try:
        return mcommon.load_json(path)
    except (OSError, ValueError):
        return default


def write_json(path: str, data) -> None:
    mcommon.write_json(path, data)


def write_text(path: str, text: str) -> None:
    mcommon.write_text(path, text)


def cfg(config: dict, key: str, default=None):
    return vcommon.cfg(config, key, default)


class Ctx:
    """The run under review: its folders, the config, the style numbers, the brand kit, the catalog."""

    def __init__(self, run_dir: str, stage_dir: str = ""):
        self.repo = (os.environ.get("REELS_REPO") or REPO).replace("\\", "/")
        self.root = (os.environ.get("REELS_ROOT") or self.repo).replace("\\", "/")
        self.run_dir = mixed(run_dir)
        self.stage_dir = mixed(stage_dir or os.path.join(self.run_dir, "12-review"))
        self.config = vcommon.load_config()
        self.toks = vcommon.tokens()
        self.brand = vcommon.brand_json()
        self.brand_index = vcommon.brand_index(self.brand)
        self.cat = vcommon.catalog()
        self.by_id = vcommon.catalog_by_id(self.cat)
        self.build_dir = os.path.join(self.run_dir, "10-build")
        self.project = os.path.join(self.build_dir, "project")
        self.plan = load_json(os.path.join(self.build_dir, "plan.json"), {}) or {}
        self.events = load_json(os.path.join(self.build_dir, "events.json"), {}) or {}
        self.words = load_json(os.path.join(self.run_dir, "08-voiceover", "words.json"), {}) or {}
        self.script = load_json(os.path.join(self.run_dir, "07-script", "script.json"), {}) or {}
        self.cues = load_json(os.path.join(self.run_dir, "11-sfx", "cues.json"), {}) or {}
        self.state = load_json(os.path.join(self.run_dir, "state.json"), {}) or {}
        self.inputs = vcommon.Inputs(self.run_dir, self.config)
        self.solution = self.inputs.solution_info()
        self.draft = os.path.join(self.build_dir, "draft.mp4")
        self.draft_mixed = os.path.join(self.run_dir, "11-sfx", "draft_mixed.mp4")
        self.duration_ms = int(self.plan.get("duration_ms") or self.events.get("duration_ms") or self.words.get("duration_ms") or 0)
        self.style_dir = mcommon.style_dir()
        self.analysis_dir = os.environ.get("REELS_STYLE_ANALYSIS") or os.path.join(self.style_dir, "analysis")

    def c(self, key: str, default=None):
        return cfg(self.config, key, default)

    def round(self) -> int:
        try:
            return int((self.state.get("rounds") or {}).get("review", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def cta_scene(self) -> dict | None:
        want = (self.plan.get("branding") or {}).get("cta_scene")
        for s in self.plan.get("scenes", []):
            if s.get("id") == want:
                return s
        for s in self.plan.get("scenes", []):
            if s.get("beat_type") == "ask":
                return s
        return None


# ------------------------------------------------------------------------------------------------ the project's hosts

HOST_RE = re.compile(r'<div\s+id="(?P<id>[^"]+)"\s+class="clip"(?P<attrs>[^>]*)>', re.S)
ATTR_RE = re.compile(r'(?P<k>[a-zA-Z-]+)=(?:"(?P<v1>[^"]*)"|\'(?P<v2>[^\']*)\')')


def read_hosts(project: str) -> list[dict]:
    """The composition's hosts from index.html: id, component, src, start_ms, end_ms, scene, beat, props, z."""
    path = os.path.join(project, "index.html")
    text = open(path, encoding="utf-8").read()
    hosts = []
    for m in HOST_RE.finditer(text):
        attrs = {}
        for a in ATTR_RE.finditer(m.group("attrs")):
            attrs[a.group("k")] = a.group("v1") if a.group("v1") is not None else a.group("v2")
        hid = m.group("id")
        src = attrs.get("data-composition-src", "")
        comp = attrs.get("data-component") or os.path.splitext(os.path.basename(src))[0]
        start = float(attrs.get("data-start", 0) or 0)
        dur = float(attrs.get("data-duration", 0) or 0)
        raw_props = attrs.get("data-variable-values")
        props = {}
        if raw_props:
            try:
                props = json.loads(html.unescape(raw_props))
            except ValueError:
                props = {}
        z = 0
        mz = re.search(r"z-index:\s*(-?\d+)", attrs.get("style", "") or "")
        if mz:
            z = int(mz.group(1))
        hosts.append({"id": hid, "component": comp, "src": src, "start_ms": int(round(start * 1000)), "end_ms": int(round((start + dur) * 1000)),
                      "scene": attrs.get("data-scene", ""), "beat": attrs.get("data-beat", ""), "props": props, "z": z,
                      "captions": attrs.get("data-track-kind") == "captions" or comp == "caption-line", "no_timeline": "data-no-timeline" in m.group("attrs")})
    return hosts


# ------------------------------------------------------------------------------------------------ times

def check_times(ctx: Ctx, hosts: list[dict]) -> dict:
    """{ms: [labels]}: every beat (the scene start plus settle_ms, or its middle when short, and its middle), every
    emphasis hit (plus the box's fade), every instance's landing (after the combined main animation and its lagging
    rotation, E2: the grammar's main frames plus the lag, from tokens.json motion.grammar), the CTA's built state."""
    settle = int(ctx.c("review.settle_ms", 600))
    em_lead = int(ctx.c("review.emphasis_settle_ms", 150))
    grammar = ((ctx.toks.get("motion") or {}).get("grammar") or {}) if isinstance(getattr(ctx, "toks", None), dict) else {}
    main_frames = int((grammar.get("main") or {}).get("frames", 18)) + int((grammar.get("main") or {}).get("rotate_lag_frames", 3))
    main_ms = int(round(main_frames * 1000.0 / 30.0))
    times: dict = {}

    def add(ms: int, label: str):
        ms = int(max(0, min(ctx.duration_ms - 1, ms)))
        ms = int(round(ms / 10.0) * 10)
        times.setdefault(ms, [])
        if label not in times[ms]:
            times[ms].append(label)

    for s in ctx.plan.get("scenes", []):
        a, b = int(s["start_ms"]), int(s["end_ms"])
        add(a + settle if b - a > 2 * settle else (a + b) // 2, f"beat {s.get('beat')} ({s.get('beat_type')}) settled")
        add((a + b) // 2, f"beat {s.get('beat')} middle")
        for h in s.get("emphasis_hits", []) or []:
            add(int(h.get("ms", a)) + em_lead, f"emphasis {h.get('word')}")
        for c in s.get("components", []):
            land = c.get("land_ms")
            if land is None:
                continue
            last = min(b, int(c.get("end_ms", b)))
            settled = max(int(land), int(c.get("start_ms", land)) + main_ms) + 100
            for t in (settled, int(land) + 100):
                if t < last:
                    add(t, f"{c['id']} landed")
                    break
    cta = ctx.cta_scene()
    if cta:
        add(int(cta["end_ms"]) - 300, "the CTA built")
    return dict(sorted(times.items()))


# ------------------------------------------------------------------------------------------------ colors

def parse_css_color(text: str) -> tuple[float, float, float, float]:
    m = re.match(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", text or "")
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)) if m.group(4) is not None else 1.0
    m = re.match(r"#([0-9a-fA-F]{6})$", (text or "").strip())
    if m:
        v = int(m.group(1), 16)
        return float((v >> 16) & 255), float((v >> 8) & 255), float(v & 255), 1.0
    return 0.0, 0.0, 0.0, 1.0


def hex_rgb(text: str) -> tuple[int, int, int]:
    v = int(text.lstrip("#"), 16)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def luminance(rgb) -> float:
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(l1: float, l2: float) -> float:
    a, b = max(l1, l2), min(l1, l2)
    return (a + 0.05) / (b + 0.05)


def rgb_to_lab(rgb) -> tuple[float, float, float]:
    def ch(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in rgb[:3])
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 1.0
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def accent_tokens(toks: dict) -> set:
    """The colors whose text is display work at the style's own contrast (3:1): the accent family, the brand pill,
    the success green (DECISIONS.md M11)."""
    colors = toks.get("colors") or {}
    names = ("accent", "accent-deep", "script", "unit-serif", "keyword-pill", "success", "mascot")
    return {colors[n].upper() for n in names if n in colors}


def nearest_token(rgb, toks: dict) -> tuple[str, float]:
    best = ("", 1e9)
    for name, hx in (toks.get("colors") or {}).items():
        d = math.dist(rgb[:3], hex_rgb(hx))
        if d < best[1]:
            best = (name, d)
    return best


# ------------------------------------------------------------------------------------------------ issues

def issue(tag: str, kind: str, text: str, scene: str = "", instance: str = "", ms=None, **extra) -> dict:
    out = {"tag": tag, "kind": kind, "text": undash(text), "scene": scene, "instance": instance}
    if ms is not None:
        out["ms"] = int(ms)
    out.update(extra)
    return out


def boxes_intersect(a: dict, b: dict, inset: float = 2.0) -> float:
    """The intersection area of two boxes {x, y, w, h}, each shrunk by inset."""
    ax0, ay0, ax1, ay1 = a["x"] + inset, a["y"] + inset, a["x"] + a["w"] - inset, a["y"] + a["h"] - inset
    bx0, by0, bx1, by1 = b["x"] + inset, b["y"] + inset, b["x"] + b["w"] - inset, b["y"] + b["h"] - inset
    w = min(ax1, bx1) - max(ax0, bx0)
    h = min(ay1, by1) - max(ay0, by0)
    return w * h if w > 0 and h > 0 else 0.0


def fmt_ms(ms) -> str:
    return f"{int(ms) / 1000:.2f}s"
