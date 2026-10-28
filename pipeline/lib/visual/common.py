"""pipeline/lib/visual/common.py: shared helpers of the visual stages S9 and S10 (M10): the inputs of a run (script.json,
words.json, solution.json, the research assets), tokens.json, catalog.json and brand.json, the timeline that snaps
every time to a spoken word, text widths measured with the style's own font files, and the approximate footprint
of a component instance on the 1080x1920 canvas (the plan-level zone check; the exact pixel checks are S12's).
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from motion import common as mcommon  # noqa: E402

REPO = mcommon.REPO
FPS = 30
BRAND_PREFIX = "brand/"
RESEARCH_PREFIX = "research/"
BRAND_SLOT_TOKEN = "@brand-slot"

# which props carry on-screen text, by role: a title-like prop is a card text (6 words or fewer), a body-like prop
# may run longer, a code prop is typed verbatim (commands, file names) and is never counted in words
TITLE_PROPS = {"title", "text", "kicker", "keyword", "verb", "unit", "label", "sub_label", "replacement", "sender", "pill"}
BODY_PROPS = {"body", "message", "reply", "placeholder", "line1", "line2", "prompt", "app_label", "time_label"}
CODE_PROPS = {"lines_json", "items_json", "rows_json", "values_json", "logos_json", "words_json", "chunks_json", "mascots_json"}
IMAGE_PROPS = {"image", "second_image", "avatar", "lockup", "kicker_mark"}
# the surface under each logo spot (BUILD_SPEC.md S9: light for paper and surface cards, dark for ink)
LOGO_SURFACES = {("headline", "kicker_mark"): "light", ("logo-tile", "image"): "light", ("logo-tile", "second_image"): "light",
                 ("end-card", "lockup"): "light", ("dm-card", "avatar"): "light", ("table-card", "logos_json"): "light",
                 ("card", "image"): "light", ("fly-in", "image"): "light", ("camera-move", "image"): "light",
                 ("thumb-grid", "items_json"): "light"}


class PlanError(Exception):
    pass


def setup_streams() -> None:
    mcommon.setup_streams()


def load_json(path: str):
    return mcommon.load_json(path)


def write_json(path: str, data, indent: int = 1) -> None:
    mcommon.write_json(path, data, indent)


def write_text(path: str, text: str) -> None:
    mcommon.write_text(path, text)


def mixed(path: str) -> str:
    return mcommon.mixed(path)


def norm(word: str) -> str:
    """A spoken word for matching: lower case, letters, digits and a few symbols, no trailing punctuation; a curly
    apostrophe (a model may type one) counts as the straight one."""
    return re.sub(r"[^a-z0-9#'%/.@-]", "", str(word).lower().replace("’", "'").replace("‘", "'")).strip(".,;:!?")


def words_of(text: str) -> list[str]:
    """The tokens of an on-screen text that count as words (a token with a letter or a digit)."""
    return [t for t in re.split(r"\s+", str(text).strip()) if re.search(r"[A-Za-z0-9]", t)]


def undash(text: str) -> str:
    return str(text).replace("\u2014", ", ").replace("\u2013", "-")  # the dash characters as escapes: no file of this project holds one


# ------------------------------------------------------------------------------------------------ the style and the library

def config_path() -> str:
    root = os.environ.get("REELS_ROOT") or REPO
    for p in (os.path.join(root, "config.json"), os.path.join(REPO, "config.json")):
        if os.path.isfile(p):
            return p
    return os.path.join(REPO, "config.json")


def load_config(path: str = "") -> dict:
    return load_json(path or config_path())


def cfg(config: dict, key: str, default=None):
    cur = config
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def tokens(path: str = "") -> dict:
    return load_json(path) if path else mcommon.tokens()


def motion_lib() -> str:
    return mcommon.motion_lib_dir()


def catalog(lib: str = "") -> dict:
    return mcommon.load_catalog(lib or motion_lib())


def catalog_by_id(cat: dict) -> dict:
    return {c["id"]: c for c in cat.get("components", [])}


def brand_dir() -> str:
    return mixed(os.environ.get("REELS_BRAND_DIR") or os.path.join(REPO, "library", "brand"))


def brand_json(path: str = "") -> dict:
    return load_json(path or os.path.join(brand_dir(), "brand.json"))


def brand_index(brand: dict) -> dict:
    """{'mark/avatar-dark.png': asset} keyed by the path under library/brand (the plan writes brand/<that path>)."""
    out = {}
    for a in brand.get("assets", []):
        rel = str(a.get("path", "")).replace("library/brand/", "")
        out[rel] = a
    return out


def brand_default(brand: dict, kind: str, surface: str) -> str:
    """The plan path of the kit's default lockup, mark, wordmark or avatar for a surface (brand.json defaults)."""
    d = brand.get("defaults", {}).get(kind)
    if isinstance(d, dict):
        d = d.get(surface) or d.get("light")
    if not d:
        return ""
    return BRAND_PREFIX + str(d).replace("library/brand/", "")


def frames_ms(n: float) -> int:
    return int(round(n * 1000 / FPS))


# ------------------------------------------------------------------------------------------------ the run's inputs

class Inputs:
    """The files of a run the visual stages read. Missing optional files are None."""

    def __init__(self, run_dir: str, config: dict | None = None):
        self.run_dir = mixed(run_dir)
        self.config = config or load_config()
        self.script = self._opt("07-script/script.json")
        self.words = self._opt("08-voiceover/words.json")
        self.words_hook2 = self._opt("08-voiceover/words_hook2.json")
        self.solution = self._opt("02-expansion/solution.json")
        self.expansion = self._opt("02-expansion/expansion.json")
        self.assets_json = self._opt("01-research/assets.json")
        self.numbers = self._opt("01-research/numbers.json")
        self.assets_dir = os.path.join(self.run_dir, "01-research", "assets")
        self.idea_id = ""
        state = self._opt("state.json")
        if state:
            self.idea_id = str((state.get("idea") or {}).get("id", ""))
        if not self.idea_id and self.script:
            self.idea_id = str(self.script.get("idea_id", ""))

    def _opt(self, rel: str):
        p = os.path.join(self.run_dir, rel)
        if os.path.isfile(p):
            try:
                return load_json(p)
            except ValueError:
                return None
        return None

    def asset_files(self) -> dict:
        """{file name: asset entry} of the research assets that exist on disk."""
        out = {}
        for a in self.assets_json or []:
            name = os.path.basename(str(a.get("file", "")))
            if name and os.path.isfile(os.path.join(self.assets_dir, name)):
                out[name] = a
        if os.path.isdir(self.assets_dir):
            for f in os.listdir(self.assets_dir):
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")) and f not in out:
                    out[f] = {"file": "assets/" + f, "name": os.path.splitext(f)[0], "what": ""}
        return out

    def solution_info(self) -> dict:
        """{type, name, url, logo}: solution.json when it exists (M12 writes it), else none (counts as not FlashFX)."""
        s = self.solution or {}
        stype = str(s.get("type", "none")).lower()
        if stype not in ("flashfx", "external", "method"):
            stype = "none"
        logo = s.get("logo") or None
        if not logo:
            for name, a in self.asset_files().items():
                label = (str(a.get("name", "")) + " " + str(a.get("what", ""))).lower()
                if re.search(r"\blogo\b|\bicon\b", label) and "favicon" not in label:
                    logo = name
                    break
        return {"type": stype, "name": str(s.get("name", "")), "url": str(s.get("url", "")),
                "logo": (RESEARCH_PREFIX + logo) if logo and not str(logo).startswith(RESEARCH_PREFIX) else logo}


class Timeline:
    """words.json as a timeline: the beats in order, each scene's window, the words of a beat with their times."""

    def __init__(self, words: dict):
        self.words = list(words.get("words", []))
        self.beats = {b["id"]: b for b in words.get("beats", [])}
        self.order = [b["id"] for b in words.get("beats", [])]
        self.breath = words.get("breath") or None
        self.duration_ms = int(words["duration_ms"])

    def beat_words(self, beat: str) -> list[dict]:
        return [w for w in self.words if w.get("beat") == beat]

    def find_word(self, beat: str, token: str, nth: int = 1) -> dict | None:
        """The nth word of the beat that starts with the token (case and punctuation do not count)."""
        t = norm(token)
        if not t:
            return None
        n = 0
        for w in self.beat_words(beat):
            if norm(w["word"]) == t or norm(w["word"]).startswith(t):
                n += 1
                if n >= nth:
                    return w
        return None

    def word_ms(self, beat: str, token: str, which: str = "start") -> int:
        w = self.find_word(beat, token)
        if not w:
            raise PlanError(f"the word {token!r} is not spoken in beat {beat}")
        return int(w["start_ms" if which == "start" else "end_ms"])

    def scene_span(self, beat: str) -> tuple[int, int]:
        if beat not in self.beats:
            raise PlanError(f"beat {beat} is not in words.json")
        i = self.order.index(beat)
        start = int(self.beats[beat]["start_ms"])
        if i == 0:
            start = 0
        end = int(self.beats[self.order[i + 1]]["start_ms"]) if i + 1 < len(self.order) else self.duration_ms
        return start, end

    def boundaries(self) -> set[int]:
        out = {0, self.duration_ms}
        for w in self.words:
            out.add(int(w["start_ms"]))
            out.add(int(w["end_ms"]))
        for b in self.beats.values():
            out.add(int(b["start_ms"]))
            out.add(int(b["end_ms"]))
        if self.breath:
            out.add(int(self.breath["start_ms"]))
            out.add(int(self.breath["end_ms"]))
        return out


# ------------------------------------------------------------------------------------------------ text widths

_FONTS: dict = {}


def font_file(toks: dict, role: str) -> str:
    f = (toks.get("fonts") or {}).get(role) or {}
    name = f.get("file", "")
    return os.path.join(motion_lib(), "assets", "fonts", name) if name else ""


def text_width(text: str, px: float, toks: dict, role: str = "grotesk", weight: int | None = None) -> float:
    """The width of a text in px with the style's font at the given size; a character estimate when PIL cannot."""
    key = (role, round(px, 2), weight)
    font = _FONTS.get(key)
    if font is None:
        font = False
        path = font_file(toks, role)
        if path and os.path.isfile(path):
            try:
                from PIL import ImageFont
                font = ImageFont.truetype(path, int(round(px)))
                w = weight if weight is not None else int(((toks.get("fonts") or {}).get(role) or {}).get("weight", 400))
                try:
                    font.set_variation_by_axes([w])
                except Exception:
                    pass
            except Exception:
                font = False
        _FONTS[key] = font
    if font:
        try:
            return float(font.getlength(str(text)))
        except Exception:
            pass
    return len(str(text)) * px * 0.52


def caption_chunk_width(words: list[dict], toks: dict) -> float:
    """The caption-line's layout of one chunk: the words at the caption size with a 0.14 em margin, emphasis words with
    14 px margins and a box reaching 14 px beyond the word (motion-lib/compositions/caption-line.html)."""
    px = float((toks.get("type") or {}).get("caption", {}).get("font_px", 67))
    total = 0.0
    for i, w in enumerate(words):
        em = bool(w.get("emphasis") or w.get("em"))
        total += text_width(w.get("word") or w.get("w") or "", px, toks, "grotesk") + (28 if em else 2 * 0.14 * px)
    return total


# ------------------------------------------------------------------------------------------------ footprints

def _num(props: dict, key: str, default: float) -> float:
    v = props.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _lines(v) -> list:
    if isinstance(v, str):
        try:
            v = json.loads(v) if v.strip() else []
        except ValueError:
            return [v]
    return list(v) if isinstance(v, list) else []


def footprint(component: str, props: dict, toks: dict) -> dict | None:
    """An approximate box {x, y, w, h, text_boxes: [{x, y, w, h, prop}]} of a component instance at 1080x1920.
    The plan-level zone check reads it (BUILD_SPEC.md S9); S12 measures the real pixels. None for layers that
    have no box of their own (the canvas, the captions, the moves that wrap the scene)."""
    z = toks.get("zones") or {}
    sh = toks.get("shapes") or {}
    p = props
    x = _num(p, "x", 90); y = _num(p, "y", 560); w = _num(p, "w", 900); h = _num(p, "h", 0)
    tb: list[dict] = []
    if component in ("paper-canvas", "caption-line", "camera-move", "exit-move"):
        return None
    if component in ("card", "fly-in"):
        body_w = max(100, w - 104)
        hh = 96
        if p.get("image"):
            hh += _num(p, "image_h", 520) + 22
        if p.get("title"):
            tb.append({"x": x + 52, "y": y + hh, "w": min(body_w, text_width(str(p["title"]), 56, toks, "grotesk")), "h": 64, "prop": "title"})
            hh += 64 + 22
        if p.get("body"):
            lines = max(1, int(text_width(str(p["body"]), 38, toks, "grotesk") // body_w) + 1)
            tb.append({"x": x + 52, "y": y + hh, "w": min(body_w, text_width(str(p["body"]), 38, toks, "grotesk")), "h": 50 * lines, "prop": "body"})
            hh += 50 * lines
        hh += 48
        return {"x": x, "y": y, "w": w, "h": h if h > 0 else hh, "text_boxes": tb}
    if component == "window-card":
        hh = h if h > 0 else 760
        if p.get("title"):
            tb.append({"x": x + 110, "y": y + 14, "w": min(w - 160, text_width(str(p["title"]), 30, toks, "kicker")), "h": 40, "prop": "title"})
        for i, line in enumerate(_lines(p.get("lines_json"))[:12]):
            txt = line.get("text", "") if isinstance(line, dict) else str(line)
            tb.append({"x": x + 48, "y": y + 92 + i * 46, "w": min(w - 96, text_width(txt, 30, toks, "mono")), "h": 40, "prop": "lines_json"})
        return {"x": x, "y": y, "w": w, "h": hh, "text_boxes": tb}
    if component == "terminal-card":
        lines = _lines(p.get("lines_json"))
        fpx = _num(p, "font_px", 30)
        hh = h if h > 0 else 92 + 48 + len(lines) * fpx * 1.6
        for i, line in enumerate(lines[:12]):
            txt = line.get("text", "") if isinstance(line, dict) else str(line)
            tb.append({"x": x + 48, "y": y + 92 + i * fpx * 1.6, "w": min(w - 96, text_width(str(p.get("prompt", "")) + txt, fpx, toks, "mono")), "h": fpx * 1.4, "prop": "lines_json"})
        return {"x": x, "y": y, "w": w, "h": hh, "text_boxes": tb}
    if component == "chart-card":
        hh = h if h > 0 else 620
        if p.get("title"):
            tb.append({"x": x + 52, "y": y + 40, "w": min(w - 104, text_width(str(p["title"]), 44, toks, "grotesk")), "h": 52, "prop": "title"})
        return {"x": x, "y": y, "w": w, "h": hh, "text_boxes": tb}
    if component == "thumb-grid":
        items = _lines(p.get("items_json"))
        cols = max(1, int(_num(p, "cols", 3)))
        gap = _num(p, "gap", 18)
        ratio = max(0.3, _num(p, "ratio", 1.4))
        rows = max(1, (len(items) + cols - 1) // cols)
        cw = (w - gap * (cols - 1)) / cols
        hh = rows * cw * ratio + gap * (rows - 1)
        return {"x": x, "y": y, "w": w, "h": hh, "text_boxes": []}
    if component == "table-card":
        rows = _lines(p.get("rows_json"))
        hh = 150 + 74 * max(1, len(rows)) + (70 if p.get("title") else 0)
        for i, r in enumerate(rows[:10]):
            tb.append({"x": x + 52, "y": y + 150 + i * 74, "w": w - 104, "h": 60, "prop": "rows_json"})
        return {"x": x, "y": y, "w": w, "h": hh, "text_boxes": tb}
    if component == "chat-card":
        hh = 230 + (120 if p.get("reply") else 0)
        tb.append({"x": x + 52, "y": y + 48, "w": w - 180, "h": 60, "prop": "prompt"})
        if p.get("reply"):
            tb.append({"x": x + 52, "y": y + 150, "w": w - 104, "h": 90, "prop": "reply"})
        return {"x": x, "y": y, "w": w, "h": hh, "text_boxes": tb}
    if component == "stat-number":
        digits = str(p.get("prefix", "")) + "{:,}".format(int(_num(p, "value", 0))) + str(p.get("suffix", ""))
        num_w = text_width(digits, 90, toks, "grotesk")
        unit_w = text_width(str(p.get("unit", "")), 60, toks, "serif-italic") if p.get("unit") else 0
        icon_w = 110 if p.get("icon") not in (None, "", "none") else 0
        ww = 120 + icon_w + num_w + 24 + unit_w
        hh = sh.get("stat_pill_h", 168) if p.get("container", "pill") == "pill" else sh.get("stat_chip_h", 141)
        tb.append({"x": x + 60 + icon_w, "y": y + 30, "w": num_w + 24 + unit_w, "h": hh - 60, "prop": "unit"})
        return {"x": x, "y": y, "w": ww, "h": hh + (70 if p.get("sub_label") else 0), "text_boxes": tb}
    if component == "dark-chip":
        tw = text_width(str(p.get("text", "")), 28, toks, "grotesk")
        icon_w = 40 if p.get("icon") not in (None, "", "none") else 0
        ww = tw + 56 + icon_w
        tb.append({"x": x + 28 + icon_w, "y": y + 10, "w": tw, "h": 36, "prop": "text"})
        return {"x": x, "y": y, "w": ww, "h": sh.get("dark_chip_h", 55), "text_boxes": tb}
    if component == "light-chip":
        tw = text_width(str(p.get("text", "")), 32, toks, "grotesk")
        tb.append({"x": x + 30, "y": y + 14, "w": tw, "h": 40, "prop": "text"})
        return {"x": x, "y": y, "w": tw + 60, "h": sh.get("light_chip_h", 67), "text_boxes": tb}
    if component == "check-badge":
        if p.get("mode", "badge") == "list":
            items = _lines(p.get("items_json"))
            hh = 80 + 78 * max(1, len(items))
            for i, it in enumerate(items[:10]):
                tb.append({"x": x + 110, "y": y + 48 + i * 78, "w": min(w - 160, text_width(str(it), 40, toks, "grotesk")), "h": 56, "prop": "items_json"})
            return {"x": x, "y": y, "w": w, "h": hh, "text_boxes": tb}
        size = _num(p, "size", 84)
        return {"x": x, "y": y, "w": size, "h": size, "text_boxes": []}
    if component == "progress-bar":
        tb.append({"x": x + 40, "y": y + 20, "w": min(w - 80, text_width(str(p.get("label", "")), 34, toks, "grotesk")), "h": 44, "prop": "label"})
        return {"x": x, "y": y, "w": w, "h": 140 if p.get("in_card", True) else 70, "text_boxes": tb}
    if component == "strike-through":
        fpx = _num(p, "font_px", 48)
        tw = text_width(str(p.get("text", "")), fpx, toks, "grotesk")
        rep = text_width(str(p.get("replacement", "")), fpx, toks, "grotesk") if p.get("replacement") else 0
        ww = tw + 60 + (rep + 40 if rep else 0)
        tb.append({"x": x + 30, "y": y + 12, "w": ww - 60, "h": fpx * 1.2, "prop": "text"})
        return {"x": x, "y": y, "w": ww, "h": fpx * 1.7, "text_boxes": tb}
    if component == "handwritten-callout":
        lines = str(p.get("text", "")).split("|")
        lw = max([text_width(ln, 58, toks, "handwritten") for ln in lines] + [60])
        hh = 69 * len(lines)
        tb.append({"x": x, "y": y, "w": lw, "h": hh, "prop": "text"})
        arrow = _num(p, "arrow_len", 150)
        return {"x": x - (arrow if "left" in str(p.get("arrow", "")) else 0), "y": y - (arrow if "up" in str(p.get("arrow", "")) else 0),
                "w": lw + arrow, "h": hh + arrow, "text_boxes": tb}
    if component == "logo-tile":
        size = _num(p, "size", 160)
        ww = size * (2.25 if p.get("second_image") else 1)
        return {"x": x, "y": y, "w": ww, "h": size, "text_boxes": []}
    if component in ("hero-3d", "icon-3d"):
        tb2 = [{"x": x, "y": y + h + 10, "w": w, "h": 50, "prop": "label"}] if p.get("label") else []
        return {"x": x, "y": y, "w": w if w > 0 else 600, "h": (h if h > 0 else 600) + (60 if p.get("label") else 0), "text_boxes": tb2}
    if component == "pop":
        size = _num(p, "size", 160)
        ww = size if p.get("kind") != "pill" else max(size, text_width(str(p.get("text", "")), 48, toks, "grotesk") + 100)
        tb2 = [{"x": x, "y": y, "w": ww, "h": size, "prop": "text"}] if p.get("kind") == "pill" and p.get("text") else []
        return {"x": x, "y": y, "w": ww, "h": size, "text_boxes": tb2}
    if component == "mascot":
        s = _num(p, "scale", 1)
        return {"x": x, "y": y, "w": 85 * s, "h": 58 * s, "text_boxes": []}
    if component == "speech-bubble":
        tw = text_width(str(p.get("text", "")), 44, toks, "grotesk") + 90
        tb.append({"x": x + 40, "y": y + 30, "w": tw - 80, "h": 56, "prop": "text"})
        return {"x": x, "y": y, "w": tw, "h": 130 + (90 if p.get("keyword") else 0), "text_boxes": tb}
    if component == "headline":
        lines = _lines(p.get("lines_json"))
        top = float(z.get("kicker_top", 253))
        line_px = float((toks.get("type") or {}).get("headline", {}).get("line_px", 113))
        hh = 60 + line_px * max(1, len(lines))
        tb.append({"x": x, "y": top, "w": w, "h": hh, "prop": "lines_json"})
        return {"x": x, "y": top, "w": w, "h": hh, "text_boxes": tb}
    if component == "end-card":
        ec = z.get("end_card") or {}
        return {"x": float(ec.get("x", 105)), "y": float(ec.get("top", 324)), "w": float(ec.get("width", 858)),
                "h": (_num(p, "lockup_y", 1230) + 160) - float(ec.get("top", 324)), "text_boxes": []}
    if component == "dm-card":
        tb.append({"x": x + 30 + _num(p, "avatar_size", 120) + 24, "y": y + 24, "w": w - 60 - _num(p, "avatar_size", 120) - 24, "h": 110, "prop": "message"})
        return {"x": x, "y": y, "w": w, "h": _num(p, "avatar_size", 120) + 48, "text_boxes": tb}
    return {"x": x, "y": y, "w": w if w > 0 else 200, "h": h if h > 0 else 200, "text_boxes": []}


def enter_frames(component: str, props: dict) -> float:
    """How many frames after its start a component has landed (its first visible change is at frame 0)."""
    if component in ("hero-3d", "icon-3d"):
        return _num(props, "enter_frames", 12)
    if component in ("card", "window-card", "fly-in") and props.get("enter") == "fly-in":
        return 14
    if component == "fly-in":
        return _num(props, "frames", 14)
    if component in ("dark-chip",):
        return _num(props, "pop_frames", 3)
    if component in ("light-chip",):
        return _num(props, "fade_frames", 4)
    if component == "logo-tile":
        return _num(props, "frames", 14)
    if component == "end-card":
        return _num(props, "fade_frames", 6)
    if component == "table-card":
        return _num(props, "enter_frames", 7)
    if component == "pop":
        return _num(props, "frames", 7)
    if component == "check-badge":
        return _num(props, "pop_frames", 12) if props.get("mode", "badge") == "badge" else 8
    return 8
