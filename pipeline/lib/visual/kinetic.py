"""pipeline/lib/visual/kinetic.py: the group layout engine of the captions (BUILD_SPEC.md section 5, Motion and energy
rules E3; M15). A caption group is the graphic: 2 to 6 spoken words laid out as kinetic typography in the group caption
zone (the hero zone). The director chooses the mode and the anchor word; this engine places every word, so no model
positions words by hand.

What the layout guarantees (check_layout verifies all of it again, the plan validator and the tests call it):
  - roles: one anchor (the most important word, the biggest), connectors (small function words), secondaries
  - fonts: the anchor in the heavy grotesk, the other words cycling through the style's other caption fonts
    (tokens.json motion.grammar.captions.fonts), so a group of 3 words or more holds at least 3 fonts
  - sizes: the anchor at 2 to 3 times the caption size; the words beside it stacked so that their lines together are as
    tall as the anchor (n words at 1/n of the anchor's size); no word below the caption size
  - never one line, never symmetric: the anchor row, then the rest on the next lines, offset to one side; the block
    leans to one side of the zone and leaves air on the other
  - inside the group caption zone and clear of the right rail (no text in the right 230 px of the lower half)
  - the group fits or is split: layout_groups() splits a group that cannot fit at the smallest anchor size in two

Heights are line boxes (line-height 1: a word at N px is N px tall), which is how caption-group.html draws them, so
"quick" and "brown" at half the anchor's size are as tall as the anchor to the pixel.

  layout(words, toks, anchor=None, index=0) -> {"ok": True, ...} | {"ok": False, "reason": str}
  layout_groups(words, toks, anchors=None, index=0) -> [layout, ...]  (1 or more groups; splits what does not fit)
  check_layout(lay, toks) -> [problem, ...]
  group_runs(words, max_words=6) -> [[word dict, ...], ...]   the deterministic split of a beat's words into groups
  choose_anchor(words, toks) -> index
  word_motion(index), group_motion(index): the E3 motion of word mode and of a group
  python pipeline/lib/visual kinetic "the quick brown fox" [--anchor N] [--png out.png]
"""
from __future__ import annotations

import json
import os
import re

from visual import common

CONNECTORS = {"the", "a", "an", "to", "of", "and", "or", "in", "on", "at", "for", "with", "is", "are", "it", "its", "you", "your", "this", "that",
              "but", "so", "as", "be", "was", "i", "we", "my", "if", "by", "from", "then", "just", "do", "does", "not", "no", "can", "will"}
COLORS = {"grotesk": "ink", "serif-italic": "accent-deep", "handwritten": "script", "kicker": "accent"}
SENTENCE_END = re.compile(r"[.!?]$")
CLAUSE_END = re.compile(r"[,;:]$")
RATIOS = [3.0, 2.75, 2.5, 2.25, 2.0]
GAP_X = 0.12           # the gap between the anchor and the stack beside it, in anchor sizes
GAP_ROW = 0.04         # the gap between rows, in the row's size
WIDTH_PAD = 1.03       # a measured width is widened a little (the browser's shaping and rounding)
FILL_MAX = 0.9         # a block fills at most this share of the zone's width: the rest is the air of the asymmetry
CENTER_Y = 0.46        # the block's center sits at this share of the zone's height from its top
MIN_SIDE = 2           # words beside the anchor that make a stack


def grammar(toks: dict) -> dict:
    return ((toks.get("motion") or {}).get("grammar") or {}).get("captions") or {}


def caption_px(toks: dict) -> float:
    return float(((toks.get("type") or {}).get("caption") or {}).get("font_px", 67))


def group_zone(toks: dict) -> dict:
    """The group caption zone: the hero zone between the side margins (tokens.json motion.grammar.captions.group_zone)."""
    z = grammar(toks).get("group_zone")
    if z:
        return {k: float(z[k]) for k in ("x0", "y0", "x1", "y1")}
    zones = toks.get("zones") or {}
    m = float(zones.get("margin_x", 60))
    return {"x0": m, "y0": float(zones.get("safe_top", 230)), "x1": 1080.0 - m, "y1": float((zones.get("hero") or {}).get("bottom_max", 1176))}


def rail(toks: dict) -> dict:
    r = (toks.get("zones") or {}).get("right_rail") or {}
    return {"x": 1080.0 - float(r.get("width", 230)), "from_y": float(r.get("from_y", 960))}


def fonts_cycle(toks: dict) -> list[str]:
    fonts = list(grammar(toks).get("fonts") or ["grotesk", "serif-italic", "handwritten", "kicker"])
    return [f for f in fonts if f != "grotesk"] or ["serif-italic", "handwritten", "kicker"]


def _text(w) -> str:
    return str(w.get("word") if isinstance(w, dict) else w)


def _wid(text: str, px: float, toks: dict, font: str) -> float:
    return common.text_width(text, px, toks, font) * WIDTH_PAD + 2.0


# ------------------------------------------------------------------------------------------------ choices

def choose_anchor(words: list, toks: dict | None = None) -> int:
    """The most important word: an emphasis word (the longest), else the longest word that is not a connector."""
    texts = [_text(w) for w in words]
    emph = [i for i, w in enumerate(words) if isinstance(w, dict) and (w.get("emphasis") or w.get("em"))]
    pool = emph or [i for i, t in enumerate(texts) if common.norm(t) not in CONNECTORS] or list(range(len(texts)))
    return max(pool, key=lambda i: (len(re.sub(r"[^A-Za-z0-9]", "", texts[i])), -i))


def roles_of(words: list, anchor: int) -> list[str]:
    return ["anchor" if i == anchor else ("connector" if common.norm(_text(w)) in CONNECTORS else "secondary") for i, w in enumerate(words)]


def assign_fonts(n: int, anchor: int, toks: dict) -> list[str]:
    cyc = fonts_cycle(toks)
    out, k = [], 0
    for i in range(n):
        if i == anchor:
            out.append("grotesk")
        else:
            out.append(cyc[k % len(cyc)])
            k += 1
    return out


def group_runs(words: list[dict], max_words: int = 6, min_words: int = 2, pause_ms: int = 150) -> list[list[dict]]:
    """A beat's spoken words split into caption groups of min_words to max_words, deterministic: first at sentence ends,
    then a segment longer than max_words is cut into near-equal parts at the best break (a clause end, else the longest
    pause), and a lone word joins its neighbor. A beat of one word stays one group of one (the caller uses word mode)."""
    if not words:
        return []
    segs: list[list[dict]] = []
    cur: list[dict] = []
    for i, w in enumerate(words):
        cur.append(w)
        if SENTENCE_END.search(_text(w)):
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)

    def cut(seg: list[dict]) -> list[list[dict]]:
        if len(seg) <= max_words:
            return [seg]
        parts = -(-len(seg) // max_words)
        target = len(seg) / parts
        best = None
        # the cut position nearest the middle among the breaks (clause end, pause), else the middle itself
        cands = []
        for j in range(min_words, len(seg) - min_words + 1):
            gap = int(seg[j].get("start_ms", 0)) - int(seg[j - 1].get("end_ms", 0)) if isinstance(seg[j], dict) and isinstance(seg[j - 1], dict) else 0
            pri = 2 if CLAUSE_END.search(_text(seg[j - 1])) else (1 if gap >= pause_ms else 0)
            cands.append((pri, -abs(j - target), j))
        if cands:
            cands.sort(reverse=True)
            best = cands[0][2]
            if abs(best - target) > max(1.5, 0.35 * len(seg)):
                best = int(round(target))
        else:
            best = int(round(target))
        left, right = seg[:best], seg[best:]
        return cut(left) + cut(right)

    groups: list[list[dict]] = []
    for s in segs:
        groups += cut(s)
    # a lone word joins a neighbor when the pair fits
    merged: list[list[dict]] = []
    for g in groups:
        if len(g) < min_words and merged and len(merged[-1]) + len(g) <= max_words:
            merged[-1] += g
        else:
            merged.append(g)
    if len(merged) > 1 and len(merged[0]) < min_words and len(merged[0]) + len(merged[1]) <= max_words:
        merged[1] = merged[0] + merged[1]
        merged.pop(0)
    return merged


def word_motion(index: int = 0, toks: dict | None = None) -> dict:
    """Word mode (E3): every word rises 8 to 16 px over its life, deterministic by its position in the reel."""
    lo, hi = ((grammar(toks or {}).get("word_rise_px")) or [8, 16])[:2]
    span = int(hi - lo) + 1
    return {"kind": "rise", "px": float(lo + (index * 5) % span)}


def group_motion(index: int = 0, toks: dict | None = None) -> dict:
    """Group mode (E3): the block rises 20 to 40 px over its life, or turns 3 to 6 degrees of parallax rotation."""
    g = grammar(toks or {})
    if index % 3 == 2:
        lo, hi = (g.get("group_rotate_deg") or [3, 6])[:2]
        return {"kind": "turn", "deg": float((lo + hi) / 2), "dir": 1 if (index // 3) % 2 == 0 else -1}
    lo, hi = (g.get("group_rise_px") or [20, 40])[:2]
    return {"kind": "rise", "px": float((lo + hi) / 2)}


# ------------------------------------------------------------------------------------------------ the layout

def _row_width(items: list[tuple[str, float, str]], toks: dict, gap_px: float) -> float:
    return sum(_wid(t, px, toks, f) for t, px, f in items) + gap_px * max(0, len(items) - 1)


def _build(words: list, anchor: int, ratio: float, n_side: int, toks: dict, fonts: list[str], lean: str, width_max: float) -> dict | None:
    """The local layout (origin top left of the block) for one ratio and one number of words beside the anchor; None when
    a row is wider than width_max or the block would need a word under the caption size."""
    C = caption_px(toks)
    A = round(C * ratio, 1)
    texts = [_text(w) for w in words]
    pre = list(range(0, anchor))
    post = list(range(anchor + 1, len(words)))
    side = post[:n_side]
    tail = post[n_side:]
    boxes: dict[int, dict] = {}
    rows: list[dict] = []
    y = 0.0
    # words before the anchor: one small row above it
    if pre:
        p_px = round(max(C, 0.4 * A), 1)
        gap = 0.25 * p_px
        x = 0.0
        for i in pre:
            w = _wid(texts[i], p_px, toks, fonts[i])
            boxes[i] = {"x": x, "y": y, "w": w, "h": p_px, "px": p_px}
            x += w + gap
        rows.append({"words": pre, "x": 0.0, "y": y, "w": x - gap, "h": p_px})
        y += p_px * (1 + GAP_ROW)
    # the anchor row: the anchor with the stack beside it
    aw = _wid(texts[anchor], A, toks, fonts[anchor])
    boxes[anchor] = {"x": 0.0, "y": y, "w": aw, "h": A, "px": A}
    row_w = aw
    stack = []
    if side:
        n = len(side)
        s_px = round(A / n, 2) if n >= MIN_SIDE else round(max(C, 0.5 * A), 1)
        if s_px < C - 0.01:
            return None
        sx = aw + GAP_X * A
        sy = y
        sw = 0.0
        for i in side:
            w = _wid(texts[i], s_px, toks, fonts[i])
            boxes[i] = {"x": sx, "y": sy, "w": w, "h": s_px, "px": s_px}
            stack.append(i)
            sw = max(sw, w)
            sy += s_px
        row_w = sx + sw
    rows.append({"words": [anchor] + side, "x": 0.0, "y": y, "w": row_w, "h": A})
    y += A * (1 + GAP_ROW)
    # the tail: the remaining words on the next rows, at 0.42 of the anchor (never under the caption size), two to a row
    if tail:
        t_px = round(max(C, 0.42 * A), 1)
        i = 0
        while i < len(tail):
            take = tail[i:i + 2]
            while len(take) > 1 and _row_width([(texts[k], t_px, fonts[k]) for k in take], toks, 0.25 * t_px) > width_max:
                take = take[:-1]
            gap = 0.25 * t_px
            x = 0.0
            for k in take:
                w = _wid(texts[k], t_px, toks, fonts[k])
                boxes[k] = {"x": x, "y": y, "w": w, "h": t_px, "px": t_px}
                x += w + gap
            rows.append({"words": take, "x": 0.0, "y": y, "w": x - gap, "h": t_px, "tail": True})
            y += t_px * (1 + GAP_ROW)
            i += len(take)
    bw = max(r["w"] for r in rows)
    bh = max(b["y"] + b["h"] for b in boxes.values())
    if bw > width_max + 0.01:
        return None
    # the rows start at different x: leaning left, the pre and anchor rows sit at the block's left edge and the tail rows
    # against its right edge; leaning right, the other way round
    for r in rows:
        at_right = (lean == "left") == bool(r.get("tail"))
        off = (bw - r["w"]) if at_right else 0.0
        if off:
            for k in r["words"]:
                boxes[k]["x"] += off
            r["x"] += off
    return {"ratio": ratio, "anchor_px": A, "n_side": len(side), "boxes": boxes, "rows": rows, "w": bw, "h": bh, "stack": stack}


def _row_starts_differ(rows: list[dict], min_dx: float = 24.0) -> bool:
    xs = [r["x"] for r in rows]
    return len(rows) > 1 and (max(xs) - min(xs)) >= min_dx


def layout(words: list, toks: dict, anchor: int | None = None, index: int = 0, avoid: list | None = None) -> dict:
    """Lay out one group (1 to 6 words). `words` are strings or dicts with a "word" key. `avoid` lists boxes {x, y, w, h}
    (graphics on screen with the group): the block sits in the zone clear of them, above or below. Returns the layout dict,
    or {"ok": False, "reason": ...} when the group cannot fit at the smallest anchor ratio (split it: layout_groups)."""
    texts = [_text(w) for w in words]
    n = len(texts)
    if n == 0:
        return {"ok": False, "reason": "no words"}
    C = caption_px(toks)
    zone = group_zone(toks)
    rl = rail(toks)
    zone_w = zone["x1"] - zone["x0"]
    if anchor is None or not (0 <= anchor < n):
        anchor = choose_anchor(words, toks)
    fonts = assign_fonts(n, anchor, toks)
    roles = roles_of(words, anchor)
    lean0 = "left" if index % 2 == 0 else "right"
    widths = [zone_w * FILL_MAX, (rl["x"] - zone["x0"]) * FILL_MAX]  # the full zone, then the zone left of the rail

    def search(lean: str):
        for width_max in widths:
            for ratio in RATIOS:
                post_n = n - anchor - 1
                sides = [MIN_SIDE, 0] if post_n >= MIN_SIDE else [0]   # two words stacked beside the anchor, else the anchor alone
                for n_side in sides:
                    if n_side >= MIN_SIDE and ratio < n_side - 1e-9:   # the stack's words would drop under the caption size
                        continue
                    built = _build(words, anchor, ratio, n_side, toks, fonts, lean, width_max)
                    if built is None or built["h"] > (zone["y1"] - zone["y0"]) + 0.01:
                        continue
                    if n >= 3 and len(built["rows"]) < 2:   # never one line
                        continue
                    placed = _place(built, zone, rl, lean, toks, avoid)
                    if placed is not None:
                        return (built, placed, width_max)
        # the last resort: the anchor at the largest ratio under 2 that fits, every other word at the caption size or more
        for ratio in (1.75, 1.5, 1.25, 1.0):
            built = _build(words, anchor, ratio, 0, toks, fonts, lean, widths[1])
            if built is not None:
                placed = _place(built, zone, rl, lean, toks, avoid)
                if placed is not None:
                    return (built, placed, widths[1])
        return None

    best = search(lean0)
    lean = lean0
    if best is None:
        lean = "right" if lean0 == "left" else "left"
        best = search(lean)
    if best is None:
        return {"ok": False, "reason": f"{n} words do not fit the zone at an anchor of {RATIOS[-1]} times the caption size" + (" beside the graphics on screen" if avoid else "")}
    built, placed, width_max = best
    out_words = []
    for i in range(n):
        b = built["boxes"][i]
        out_words.append({"i": i, "text": texts[i], "role": roles[i], "font": fonts[i], "color": COLORS.get(fonts[i], "ink"), "px": b["px"],
                          "x": round(placed["dx"] + b["x"], 1), "y": round(placed["dy"] + b["y"], 1), "w": round(b["w"], 1), "h": round(b["h"], 1)})
    box = {"x": round(placed["dx"], 1), "y": round(placed["dy"], 1), "w": round(built["w"], 1), "h": round(built["h"], 1)}
    lay = {"ok": True, "anchor": anchor, "anchor_px": built["anchor_px"], "ratio": round(built["anchor_px"] / C, 3), "caption_px": C, "lean": lean,
           "words": out_words, "box": box, "zone": {k: round(v, 1) for k, v in zone.items()}, "stack": built["stack"],
           "rows": [{"words": r["words"], "x": round(placed["dx"] + r["x"], 1), "y": round(placed["dy"] + r["y"], 1), "w": round(r["w"], 1), "h": round(r["h"], 1)} for r in built["rows"]],
           "fonts": sorted({w["font"] for w in out_words}), "motion": group_motion(index, toks), "relaxed": built["anchor_px"] < 2 * C - 0.01, "avoid": len(avoid or [])}
    return lay


def _place(built: dict, zone: dict, rl: dict, lean: str, toks: dict, avoid: list | None = None) -> dict | None:
    """The block's offset inside the zone: leaning to one side, centered a little above the middle vertically (or in the
    nearest free band when graphics are on screen), and clear of the right rail (the lower half's words end left of it)."""
    bw, bh = built["w"], built["h"]
    zone_w = zone["x1"] - zone["x0"]
    dx = zone["x0"] if lean == "left" else zone["x1"] - bw
    cy = zone["y0"] + CENTER_Y * (zone["y1"] - zone["y0"])
    dy0 = min(max(cy - bh / 2.0, zone["y0"]), zone["y1"] - bh)
    lo_y, hi_y = zone["y0"], zone["y1"] - bh
    cands = [dy0]
    k = 1
    while dy0 - 20.0 * k >= lo_y - 0.01 or dy0 + 20.0 * k <= hi_y + 0.01:
        for d in (dy0 + 20.0 * k, dy0 - 20.0 * k):
            if lo_y - 0.01 <= d <= hi_y + 0.01:
                cands.append(d)
        k += 1
    cands += [lo_y, hi_y]
    margin = 24.0
    placed = None
    for dy in cands:
        if avoid:
            hit = False
            for a in avoid:
                ox = min(a["x"] + a["w"] + margin, dx + bw) - max(a["x"] - margin, dx)
                oy = min(a["y"] + a["h"] + margin, dy + bh) - max(a["y"] - margin, dy)
                if ox > 0 and oy > 0:
                    hit = True
                    break
            if hit:
                continue
        low = [b for b in built["boxes"].values() if dy + b["y"] + b["h"] > rl["from_y"]]
        over = max([dx + b["x"] + b["w"] - rl["x"] for b in low] + [0.0])
        if over <= 0.01:
            placed = (dx, dy)
            break
        if dx - over >= zone["x0"] - 0.01:
            placed = (dx - over, dy)
            break
    if placed is None:
        return None
    dx, dy = placed
    if dx < zone["x0"] - 0.01 or dx + bw > zone["x1"] + 0.01 or dy < zone["y0"] - 0.01 or dy + bh > zone["y1"] + 0.01:
        return None
    # the air: one side holds at least 8 percent of the zone's width more than the other, or the rows start apart
    left_air, right_air = dx - zone["x0"], zone["x1"] - (dx + bw)
    if abs(left_air - right_air) < 0.08 * zone_w and not _row_starts_differ(built["rows"]):
        return None
    return {"dx": dx, "dy": dy}


def layout_groups(words: list, toks: dict, anchors: list | None = None, index: int = 0, avoid: list | None = None) -> list[dict]:
    """One layout per group: the words as one group when they fit, else split in two at the best break, recursively.
    anchors[i] is the anchor index of the whole word list (None: choose). Returns the layouts in spoken order, each with
    "span": [first, last] word positions of the input."""
    def rec(lo: int, hi: int, idx: int, anchor) -> list[dict]:
        chunk = words[lo:hi]
        a = anchor - lo if isinstance(anchor, int) and lo <= anchor < hi else None
        lay = layout(chunk, toks, anchor=a, index=idx, avoid=avoid)
        if lay.get("ok") and not (lay.get("relaxed") and len(chunk) >= 4):
            lay["span"] = [lo, hi - 1]
            return [lay]
        if len(chunk) < 2:
            lay["span"] = [lo, hi - 1]
            return [lay]
        mid = len(chunk) // 2
        pos = [k for k in range(2, len(chunk) - 1) if CLAUSE_END.search(_text(chunk[k - 1]))]
        if pos:
            mid = min(pos, key=lambda k: abs(k - len(chunk) / 2))
        left = rec(lo, lo + mid, idx, anchor)
        right = rec(lo + mid, hi, idx + 1, anchor)
        parts = left + right
        if lay.get("ok") and any(not p.get("ok") or p.get("relaxed") for p in parts):
            lay["span"] = [lo, hi - 1]   # splitting did not help: the single group at a smaller anchor
            return [lay]
        return parts
    anchor = anchors if isinstance(anchors, int) else None
    return rec(0, len(words), index, anchor)


# ------------------------------------------------------------------------------------------------ checks

def check_layout(lay: dict, toks: dict) -> list[str]:
    """Every rule of E3 for one group layout (as stored in the plan); the problems, empty when it is sound."""
    problems: list[str] = []
    if not isinstance(lay, dict) or not lay.get("words"):
        return ["the group has no layout"]
    C = caption_px(toks)
    g = grammar(toks)
    zone = group_zone(toks)
    rl = rail(toks)
    ws = lay["words"]
    n = len(ws)
    lo_g, hi_g = (g.get("group_words") or [2, 6])[:2]
    if n > int(hi_g):
        problems.append(f"a group holds at most {hi_g} words, this one has {n}")
    fonts = [w.get("font") for w in ws]
    allowed = set(g.get("fonts") or ["grotesk", "serif-italic", "handwritten", "kicker"])
    for w in ws:
        if w.get("font") not in allowed:
            problems.append(f"\"{w['text']}\" uses the font {w.get('font')}, not one of the caption fonts ({', '.join(sorted(allowed))})")
        if float(w["px"]) < C - 0.5:
            problems.append(f"\"{w['text']}\" is {w['px']} px, under the caption size {C:g} px")
        if w["x"] < zone["x0"] - 1 or w["x"] + w["w"] > zone["x1"] + 1 or w["y"] < zone["y0"] - 1 or w["y"] + w["h"] > zone["y1"] + 1:
            problems.append(f"\"{w['text']}\" (x {w['x']:.0f}..{w['x'] + w['w']:.0f}, y {w['y']:.0f}..{w['y'] + w['h']:.0f}) is outside the group caption zone (x {zone['x0']:.0f}..{zone['x1']:.0f}, y {zone['y0']:.0f}..{zone['y1']:.0f})")
        if w["y"] + w["h"] > rl["from_y"] and w["x"] + w["w"] > rl["x"] + 1:
            problems.append(f"\"{w['text']}\" reaches x {w['x'] + w['w']:.0f} in the lower half: no text in the right {1080 - rl['x']:.0f} px below y {rl['from_y']:.0f}")
    if n >= int(g.get("min_words_for_fonts", 3)) and len(set(fonts)) < int(g.get("min_fonts_in_group", 3)):
        problems.append(f"a group of {n} words needs at least {g.get('min_fonts_in_group', 3)} fonts, this one has {len(set(fonts))}")
    anchor = lay.get("anchor")
    if not isinstance(anchor, int) or not (0 <= anchor < n):
        problems.append("the group has no anchor word")
    else:
        aw = ws[anchor]
        lo_r, hi_r = (g.get("anchor_size_ratio") or [2, 3])[:2]
        r = float(aw["px"]) / C
        if (r < lo_r - 0.01 or r > hi_r + 0.01) and not lay.get("relaxed"):
            problems.append(f"the anchor \"{aw['text']}\" is {r:.2f} times the caption size; it must be {lo_r:g} to {hi_r:g} times")
        if any(w["px"] > aw["px"] + 0.01 for w in ws):
            problems.append("a word is bigger than the anchor")
    stack = lay.get("stack") or []
    if len(stack) >= 2 and isinstance(anchor, int):
        total = sum(ws[i]["h"] for i in stack)
        if abs(total - ws[anchor]["h"]) > 2.0:
            problems.append(f"the stacked words are {total:.1f} px tall together, the anchor {ws[anchor]['h']:.1f} px: they must match within 2 px")
        tops = [ws[i]["y"] for i in stack]
        if abs(min(tops) - ws[anchor]["y"]) > 2.0:
            problems.append("the stack is not top aligned with the anchor")
    box = lay.get("box") or {}
    if box:
        zone_w = zone["x1"] - zone["x0"]
        left_air, right_air = box["x"] - zone["x0"], zone["x1"] - (box["x"] + box["w"])
        rows = lay.get("rows") or []
        starts_differ = _row_starts_differ(rows)
        if abs(left_air - right_air) < 0.08 * zone_w and not starts_differ:
            problems.append("the group is symmetric: its rows start at the same x and it leaves the same air on both sides")
    if n >= 3 and len(lay.get("rows") or []) < 2:
        problems.append("the group is a single line; it needs the anchor row and at least one more row")
    for i in range(n):
        for j in range(i + 1, n):
            a, b = ws[i], ws[j]
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if ox > 4 and oy > 4:
                problems.append(f"\"{a['text']}\" and \"{b['text']}\" overlap")
    mo = lay.get("motion") or {}
    if mo.get("kind") == "rise":
        lo_m, hi_m = (g.get("group_rise_px") or [20, 40])[:2]
        if not (lo_m - 0.01 <= float(mo.get("px", 0)) <= hi_m + 0.01):
            problems.append(f"the group's rise is {mo.get('px')} px; it must be {lo_m:g} to {hi_m:g} px over its life")
    elif mo.get("kind") == "turn":
        lo_m, hi_m = (g.get("group_rotate_deg") or [3, 6])[:2]
        if not (lo_m - 0.01 <= float(mo.get("deg", 0)) <= hi_m + 0.01):
            problems.append(f"the group's turn is {mo.get('deg')} degrees; it must be {lo_m:g} to {hi_m:g}")
    else:
        problems.append("the group does not move: it needs a slow rise or a parallax turn (E3, nothing is ever static)")
    return problems


def check_motion(entry: dict, toks: dict) -> list[str]:
    """The motion of a word-mode entry (a rise of 8 to 16 px over each word's life or a turn of 2 to 4 degrees)."""
    g = grammar(toks)
    mo = entry.get("motion") or {}
    if mo.get("kind") == "rise":
        lo, hi = (g.get("word_rise_px") or [8, 16])[:2]
        if not (lo - 0.01 <= float(mo.get("px", 0)) <= hi + 0.01):
            return [f"the words rise {mo.get('px')} px over their life; it must be {lo:g} to {hi:g} px"]
        return []
    if mo.get("kind") == "turn":
        lo, hi = (g.get("word_rotate_deg") or [2, 4])[:2]
        if not (lo - 0.01 <= float(mo.get("deg", 0)) <= hi + 0.01):
            return [f"the words turn {mo.get('deg')} degrees; it must be {lo:g} to {hi:g}"]
        return []
    return ["the caption words do not move: each must rise 8 to 16 px or turn 2 to 4 degrees over its life (E3, nothing is ever static)"]


# ------------------------------------------------------------------------------------------------ preview and CLI

def render_png(lay: dict, toks: dict, out_path: str) -> None:
    """A picture of one layout on the 1080x1920 canvas (the zone outlined), with the style's own font files."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (1080, 1920), (246, 235, 226))
    d = ImageDraw.Draw(im)
    z = lay["zone"]
    d.rectangle([z["x0"], z["y0"], z["x1"], z["y1"]], outline=(200, 170, 150), width=2)
    rl = rail(toks)
    d.rectangle([rl["x"], rl["from_y"], 1080, 1920], outline=(220, 120, 120), width=1)
    colors = {"ink": (20, 20, 25), "accent-deep": (160, 70, 40), "script": (60, 90, 160), "accent": (217, 119, 87)}
    for w in lay["words"]:
        path = common.font_file(toks, w["font"])
        font = ImageFont.truetype(path, int(round(w["px"])))
        try:
            font.set_variation_by_axes([int(((toks.get("fonts") or {}).get(w["font"]) or {}).get("weight", 400))])
        except Exception:
            pass
        d.rectangle([w["x"], w["y"], w["x"] + w["w"], w["y"] + w["h"]], outline=(230, 200, 180))
        d.text((w["x"], w["y"]), w["text"], font=font, fill=colors.get(w["color"], (20, 20, 25)))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    im.save(out_path)


def run(args) -> int:
    toks = common.tokens()
    words = args.text.split()
    layouts = layout_groups(words, toks, anchors=args.anchor)
    if args.json:
        print(json.dumps(layouts, ensure_ascii=False, indent=1))
    else:
        for k, lay in enumerate(layouts):
            if not lay.get("ok"):
                print(f"group {k}: {lay.get('reason')}")
                continue
            print(f"group {k} words {lay['span'][0]}..{lay['span'][1]}: anchor \"{lay['words'][lay['anchor']]['text']}\" at {lay['anchor_px']} px ({lay['ratio']} x caption), lean {lay['lean']}, fonts {', '.join(lay['fonts'])}")
            for w in lay["words"]:
                print(f"  {w['text']:>14} {w['role']:<9} {w['font']:<13} {w['px']:>6} px  x {w['x']:>6} y {w['y']:>6} w {w['w']:>6} h {w['h']:>6}")
            for p in check_layout(lay, toks):
                print("  problem: " + p)
            if args.png:
                out = args.png if len(layouts) == 1 else args.png.replace(".png", f"-{k}.png")
                render_png(lay, toks, out)
    return 0
