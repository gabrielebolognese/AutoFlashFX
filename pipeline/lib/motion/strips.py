"""pipeline/lib/motion/strips.py: the 30 fps reference filmstrips of styles/paper-cards/analysis/<vXX>/extra/s30_*.png
(made by the analyzer's scratch tools: cells of equal size in rows of 8, a 16 px label band over each frame, the
frames in row-major order) and the per-frame change curves used by frame-match (DECISIONS.md 29).

The reference clips show other things moving too (captions, a mascot), so the comparison is made on shapes: the
change curve is measured inside the region that changes most at the move's peak, the move window runs from the
onset (walking back from the peak while the change stays over a fifth of it) until the change dies down, and both
windows are resampled to the same length before the Pearson correlation. An ease-out enter (big change decaying), a
pop (rise then fall), a count-up (a plateau) and typing (a long plateau) give distinct shapes.

  strips.cells(png) -> [PIL images], one per frame (the label band removed), in order
  strips.change_curve(images) -> [floats], mean absolute difference between consecutive frames inside the active
                                  region, normalized to the maximum (the first value is 0)
  strips.move_window(curve) -> (onset, end)
  strips.correlate(ref_curve, cur_curve, frames) -> (r, ref_onset, cur_onset)
"""
from __future__ import annotations

import math
import os

LABEL_PX = 16
COLS = 8


def cells(png: str, analysis_size: tuple[int, int] = (90, 160)) -> list:
    from PIL import Image
    im = Image.open(png).convert("L")
    w, h = im.size
    cell_w = w / COLS
    cell_h = round(cell_w * 16 / 9) + LABEL_PX
    rows = max(1, round(h / cell_h))
    cell_h = h / rows
    out = []
    for r in range(rows):
        for c in range(COLS):
            left, top = round(c * cell_w), round(r * cell_h + LABEL_PX)
            box = (left, top, round((c + 1) * cell_w), round((r + 1) * cell_h))
            cell = im.crop(box)
            lo, hi = cell.getextrema()
            if hi - lo < 8:  # an empty cell: the unused tail of the last row
                return out
            out.append(cell.resize(analysis_size))
    return out


def frames_from_folder(folder: str, analysis_size: tuple[int, int] = (90, 160)) -> list:
    from PIL import Image
    names = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
    return [Image.open(os.path.join(folder, n)).convert("L").resize(analysis_size) for n in names]


def _diff(a: list[int], b: list[int], w: int, box: tuple[int, int, int, int] | None) -> float:
    if box is None:
        n = len(a)
        return sum(abs(x - y) for x, y in zip(a, b)) / max(1, n)
    x0, y0, x1, y1 = box
    total = 0
    count = 0
    for y in range(y0, y1):
        row = y * w
        for x in range(x0, x1):
            total += abs(a[row + x] - b[row + x])
            count += 1
    return total / max(1, count)


def _raw_curve(datas: list[list[int]], w: int, box=None) -> list[float]:
    curve = [0.0]
    for prev, cur in zip(datas, datas[1:]):
        curve.append(_diff(prev, cur, w, box))
    return curve


def _active_box(a: list[int], b: list[int], w: int, h: int, thr: int = 24, pad: float = 0.12) -> tuple[int, int, int, int] | None:
    xs, ys = [], []
    for y in range(h):
        row = y * w
        for x in range(w):
            if abs(a[row + x] - b[row + x]) > thr:
                xs.append(x); ys.append(y)
    if len(xs) < 6:
        return None
    px, py = int(w * pad), int(h * pad)
    return (max(0, min(xs) - px), max(0, min(ys) - py), min(w, max(xs) + px + 1), min(h, max(ys) + py + 1))


def change_curve(images: list) -> list[float]:
    """The normalized change curve inside the region that changes most at the peak frame."""
    if len(images) < 2:
        return [0.0] * len(images)
    w, h = images[0].size
    datas = [list(im.getdata()) for im in images]
    raw = _raw_curve(datas, w)
    peak = max(range(len(raw)), key=lambda i: raw[i])
    box = _active_box(datas[peak - 1], datas[peak], w, h) if peak >= 1 else None
    curve = _raw_curve(datas, w, box) if box else raw
    top = max(curve) or 1.0
    return [c / top for c in curve]


def move_window(curve: list[float], low: float = 0.2) -> tuple[int, int]:
    """(onset, end): walk back from the peak while the change stays over `low`; the end is where it dies down."""
    if not curve:
        return 0, 0
    peak = max(range(len(curve)), key=lambda i: curve[i])
    onset = peak
    while onset > 0 and curve[onset - 1] >= low:
        onset -= 1
    end = peak
    quiet = 0
    while end < len(curve) - 1:
        end += 1
        quiet = quiet + 1 if curve[end] < low else 0
        if quiet >= 2:
            end -= 1
            break
    return onset, end


def onset(curve: list[float], threshold: float = 0.2) -> int:
    return move_window(curve, threshold)[0]


def resample(values: list[float], n: int) -> list[float]:
    if not values:
        return [0.0] * n
    if len(values) == 1:
        return [values[0]] * n
    out = []
    for i in range(n):
        p = i * (len(values) - 1) / max(1, n - 1)
        a, b = int(math.floor(p)), min(len(values) - 1, int(math.ceil(p)))
        f = p - a
        out.append(values[a] * (1 - f) + values[b] * f)
    return out


def pearson(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)) or 1e-9
    sb = math.sqrt(sum((x - mb) ** 2 for x in b)) or 1e-9
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def correlate_sliding(ref_curve: list[float], cur_curve: list[float], frames: int, points: int = 12) -> tuple[float, int, int]:
    """The reference's move window against every window of `frames` frames in the component's curve (M14: the combined
    entrance of E2 puts a zoom before the move a strip shows, so the biggest change is not always the strip's move);
    the best Pearson r over the onsets and a 1-frame shift of the reference onset."""
    o_ref, e_ref = move_window(ref_curve)
    e_ref = min(e_ref, o_ref + max(3, frames) - 1)
    best = (-1.0, o_ref, 0)
    n = max(3, frames)
    for shift in (-1, 0, 1):
        r0 = max(0, o_ref + shift)
        seg = ref_curve[r0:e_ref + 1] + [0.0]
        if len(seg) < 3:
            continue
        ref_rs = resample(seg, points)
        for onset in range(0, max(1, len(cur_curve) - 2)):
            win = cur_curve[onset:onset + n]
            if len(win) < 3 or max(win) <= 0:
                continue
            r = pearson(ref_rs, resample(win + [0.0], points))
            if r > best[0]:
                best = (r, r0, onset)
    return best


def correlate(ref_curve: list[float], cur_curve: list[float], frames: int, points: int = 12) -> tuple[float, int, int]:
    """The shapes of the two move windows (resampled to `points`), the best of a 1-frame shift of the reference onset.
    `frames` caps the window length (about the expected move plus a few frames)."""
    o_ref, e_ref = move_window(ref_curve)
    o_cur, e_cur = move_window(cur_curve)
    e_ref = min(e_ref, o_ref + max(3, frames) - 1)
    e_cur = min(e_cur, o_cur + max(3, frames) - 1)
    best = (-1.0, o_ref, o_cur)
    cur = resample(cur_curve[o_cur:e_cur + 1] + [0.0], points)
    for shift in (-1, 0, 1):
        r0 = max(0, o_ref + shift)
        seg = ref_curve[r0:e_ref + 1] + [0.0]
        if len(seg) < 3 or len(cur_curve[o_cur:e_cur + 1]) < 2:
            continue
        r = pearson(resample(seg, points), cur)
        if r > best[0]:
            best = (r, r0, o_cur)
    return best
