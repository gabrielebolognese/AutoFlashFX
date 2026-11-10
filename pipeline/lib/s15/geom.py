"""geom.py: quads to poses, eases, and the fewest keyframes that reproduce a captured curve (BUILD_SPEC.md S15 steps 2 and 3).

A pose is the 2D affine of a layer's border box: its center, the two scales, the rotation and how far the captured
quad is from an affine one (err, in px: the fourth corner against the parallelogram the first three give; a 3D transform
shows as a large err). Keyframes are reduced within the spec's tolerances: 0.25 px, 0.1 degree, 0.002 scale, 0.004 opacity.
"""
from __future__ import annotations

import math

TOL = {"transform.x": 0.25, "transform.y": 0.25, "transform.rotation": 0.1, "transform.scale": 0.002, "transform.scaleY": 0.002,
       "opacity": 0.004, "default": 0.25}

# ---------------------------------------------------------------------------------------------------- eases (Penner, standard definitions)


def _bounce_out(t: float) -> float:
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def _in_out(f):
    return lambda t: f(2 * t) / 2 if t < 0.5 else 1 - f(2 * (1 - t)) / 2


def _out(f):
    return lambda t: 1 - f(1 - t)


_IN = {
    "sine": lambda t: 1 - math.cos(t * math.pi / 2),
    "quad": lambda t: t ** 2,
    "cubic": lambda t: t ** 3,
    "quart": lambda t: t ** 4,
    "quint": lambda t: t ** 5,
    "expo": lambda t: 0.0 if t == 0 else 2 ** (10 * t - 10),
    "circ": lambda t: 1 - math.sqrt(max(0.0, 1 - t * t)),
    "back": lambda t: 2.70158 * t ** 3 - 1.70158 * t ** 2,
    "elastic": lambda t: 0.0 if t == 0 else 1.0 if t == 1 else -(2 ** (10 * t - 10)) * math.sin((t * 10 - 10.75) * (2 * math.pi / 3)),
    "bounce": lambda t: 1 - _bounce_out(1 - t),
}

EASES = {"linear": lambda t: t}
for _name, _f in _IN.items():
    EASES[_name + "In"] = _f
    EASES[_name + "Out"] = _out(_f)
    EASES[_name + "InOut"] = _in_out(_f)
# the editor's own v1 eases (easeIn, easeOut, easeInOut, smooth, snap, overshoot) have curves this module does not know:
# it never picks them, so a key never depends on a guess; hold is the jump
PENNER_ORDER = ["linear", "quadOut", "cubicOut", "quartOut", "quintOut", "expoOut", "sineOut", "circOut", "backOut",
                "quadIn", "cubicIn", "expoIn", "sineIn", "quadInOut", "cubicInOut", "sineInOut", "expoInOut", "backInOut"]

GSAP_EASE_MAP = {"none": "linear", "power1.out": "quadOut", "power2.out": "cubicOut", "power3.out": "quartOut", "power4.out": "quintOut",
                 "expo.out": "expoOut", "sine.out": "sineOut", "circ.out": "circOut", "back.out": "backOut", "power1.in": "quadIn",
                 "power2.in": "cubicIn", "expo.in": "expoIn", "power1.inOut": "quadInOut", "power2.inOut": "cubicInOut", "sine.inOut": "sineInOut"}

# ---------------------------------------------------------------------------------------------------- poses


def pose_from_quad(quad: list[float], w: float, h: float) -> dict:
    """quad: [x0,y0,x1,y1,x2,y2,x3,y3] (top-left, top-right, bottom-right, bottom-left of the border box, page px);
    w, h: the box's layout size. Returns the pose of the least-squares affine map of the box onto the quad: the center is the mean of the
    corners, the basis vectors come from the corner differences (exact for an affine quad, the best fit for a 3D one), and err is the largest
    distance between a corner the fit predicts and the captured one."""
    x0, y0, x1, y1, x2, y2, x3, y3 = quad
    cx, cy = (x0 + x1 + x2 + x3) / 4.0, (y0 + y1 + y2 + y3) / 4.0
    w, h = max(w, 1e-6), max(h, 1e-6)
    ux, uy = (-x0 + x1 + x2 - x3) / (2.0 * w), (-y0 + y1 + y2 - y3) / (2.0 * w)
    vx, vy = (-x0 - x1 + x2 + x3) / (2.0 * h), (-y0 - y1 + y2 + y3) / (2.0 * h)
    sx, sy = math.hypot(ux, uy), math.hypot(vx, vy)
    rot = math.degrees(math.atan2(uy, ux))
    cross = ux * vy - uy * vx
    skew = (ux * vx + uy * vy) / max(sx * sy, 1e-9)   # cos of the angle between the basis vectors: 0 for a rotation and scale
    err = 0.0
    for (qx, qy), (lx, ly) in zip(((x0, y0), (x1, y1), (x2, y2), (x3, y3)), ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))):
        px_ = cx + ux * lx * w + vx * ly * h
        py_ = cy + uy * lx * w + vy * ly * h
        err = max(err, math.hypot(qx - px_, qy - py_))
    return {"cx": cx, "cy": cy, "sx": sx, "sy": sy, "rot": rot, "skew": skew, "flip": cross < 0, "err": err}


def unwrap(angles: list[float]) -> list[float]:
    """Degrees made continuous (no 359 to 1 jump)."""
    out, prev = [], None
    for a in angles:
        if prev is not None:
            while a - prev > 180:
                a -= 360
            while a - prev < -180:
                a += 360
        out.append(a)
        prev = a
    return out


# ---------------------------------------------------------------------------------------------------- keyframe reduction


def _fit_segment(vals: list[float], i: int, j: int, tol: float, ease: str) -> float:
    """Largest error of `ease` between sample i and sample j (frames i..j of vals), 0 when j == i + 1."""
    v0, v1 = vals[i], vals[j]
    f = EASES[ease]
    worst = 0.0
    n = j - i
    for k in range(i + 1, j):
        pred = v0 + (v1 - v0) * f((k - i) / n)
        worst = max(worst, abs(pred - vals[k]))
        if worst > tol:
            return worst
    return worst


def reduce_scalar(frames: list[int], vals: list[float], tol: float, allowed: list[str] | None = None) -> list[dict]:
    """The fewest keys {frame, value, ease} (frames relative to whatever the caller subtracted) that reproduce vals within tol.
    allowed: ease ids the manifest lists (Penner names this module knows); linear is always allowed."""
    n = len(vals)
    if n == 0:
        return []
    cands = [e for e in PENNER_ORDER if e == "linear" or (allowed is not None and e in allowed)]
    if n == 1 or all(abs(v - vals[0]) <= tol for v in vals):
        return [{"frame": frames[0], "value": round(vals[0], 4), "ease": "linear"}]
    keys = []
    i = 0
    while i < n - 1:
        best_j, best_ease = i + 1, "linear"
        # greedy: the farthest j any candidate ease reproduces
        for j in range(n - 1, i, -1):
            found = None
            for e in cands:
                if _fit_segment(vals, i, j, tol, e) <= tol:
                    found = e
                    break
            if found:
                best_j, best_ease = j, found
                break
        keys.append({"frame": frames[i], "value": round(vals[i], 4), "ease": best_ease})
        i = best_j
    keys.append({"frame": frames[-1], "value": round(vals[-1], 4), "ease": "linear"})
    return keys


def reduce_constant_tail(keys: list[dict]) -> list[dict]:
    """Drop a key that repeats its neighbours' value (a plateau needs its two ends only)."""
    if len(keys) < 3:
        return keys
    out = [keys[0]]
    for k in range(1, len(keys) - 1):
        a, b, c = out[-1], keys[k], keys[k + 1]
        if abs(a["value"] - b["value"]) < 1e-9 and abs(b["value"] - c["value"]) < 1e-9 and a["ease"] == "linear":
            continue
        out.append(b)
    out.append(keys[-1])
    return out


def eval_keys(keys: list[dict], frame: float) -> float:
    """The value of a key list at a frame (before the first key and after the last the value stays)."""
    if not keys:
        return 0.0
    if frame <= keys[0]["frame"]:
        return float(keys[0]["value"])
    for a, b in zip(keys, keys[1:]):
        if frame <= b["frame"]:
            span = b["frame"] - a["frame"]
            if a["ease"] == "hold":
                return float(a["value"])
            t = (frame - a["frame"]) / span if span else 1.0
            f = EASES.get(a["ease"], EASES["linear"])
            return float(a["value"]) + (float(b["value"]) - float(a["value"])) * f(t)
    return float(keys[-1]["value"])


def check_keys(keys: list[dict], frames: list[int], vals: list[float], tol: float) -> float:
    """The worst error of the key list against the samples."""
    return max((abs(eval_keys(keys, f) - v) for f, v in zip(frames, vals)), default=0.0)
