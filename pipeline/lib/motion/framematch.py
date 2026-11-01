"""pipeline/lib/motion/framematch.py: frame-match the library components against the style's numbers and the reference
filmstrips (BUILD_SPEC.md M9, PLAN.md M9, DECISIONS.md 29).

For every component the harness (motion/harness.py) mounts it with the props of motion/expectations.py, seeks it
frame by frame at 30 fps and measures the tracked elements; the checks compare what was measured with the numbers
of vocabulary.md and style.md (through tokens.json): 1 frame of tolerance on timings, 10 percent on distances and
overshoots. Durations are measured by fitting the element's curve against the move's ease over a range of
durations (an expo-out tween is within 1 px long before it ends, so a threshold would under-read it). The per-frame
change curve of the component's own frames is correlated with the reference strip of the same move
(styles/paper-cards/analysis/<vXX>/extra/s30_*.png, when the analysis folder exists on this PC): a match needs
r >= 0.5 on the best strip; with no strip the numbers alone decide.

Writes motion-lib/gallery/frame-match.md and frame-match.json. With --apply, a component that fails moves to
motion-lib/candidates/ (and a candidate that passes comes back), and catalog.json's frame_match fields are updated.

  python pipeline/lib/motion frame-match [--only id,id] [--no-shots] [--apply] [--gpu auto|software|hardware]
"""
from __future__ import annotations

import datetime as dt
import math
import os
import shutil

from motion import common, expectations, harness, strips

FRAME_TOL = 1
RATIO_TOL = 0.10
MIN_R = 0.5

EASES = {
    "expo.out": lambda p: 1 - math.pow(2, -10 * p) if p < 1 else 1.0,
    "power3.out": lambda p: 1 - (1 - p) ** 4,
    "power2.out": lambda p: 1 - (1 - p) ** 3,
    "power1.out": lambda p: 1 - (1 - p) ** 2,
    "power2.in": lambda p: p ** 3,
    "power1.inOut": lambda p: (2 * p * p) if p < 0.5 else (1 - ((-2 * p + 2) ** 2) / 2),
    "none": lambda p: p,
}


# ------------------------------------------------------------------------------------------------ measurement helpers

def idx(at: float) -> int:
    return int(round(at * common.FPS))


def series(rows: list[dict], sel: str, key: str) -> list[float | None]:
    out = []
    for row in rows:
        m = row.get(sel)
        out.append(None if m is None else m.get(key))
    return out


def first_index(values: list, i0: int, pred) -> int | None:
    for i in range(max(0, i0), len(values)):
        v = values[i]
        if v is not None and pred(v):
            return i
    return None


def opacity_frames(rows, sel, at) -> int | None:
    op = series(rows, sel, "opacity")
    i0 = idx(at)
    i = first_index(op, i0, lambda v: v >= 0.99)
    return None if i is None else i - i0


def first_visible(rows, sel, thr: float = 0.02, key: str = "opacity") -> int | None:
    vals = series(rows, sel, key)
    return first_index(vals, 0, lambda v: v > thr)


def fit_duration(values: list[float | None], i0: int, expected: int, eases: tuple[str, ...], span: int = 3) -> dict:
    """Fit v(i) = end + (start - end) * (1 - ease((i - i0) / d)) for d around expected; the best d and its residual."""
    start = values[i0] if i0 < len(values) else None
    tail = [v for v in values[i0:] if v is not None]
    if start is None or not tail:
        return {"d": None, "ease": None, "residual": None}
    end = tail[-1]
    dist = start - end
    if abs(dist) < 0.5:
        return {"d": None, "ease": None, "residual": None, "distance": dist}
    best = None
    for d in range(max(1, expected - span), expected + span + 1):
        for name in eases:
            ease = EASES[name]
            err = 0.0
            for i in range(i0, min(len(values), i0 + d + 3)):
                v = values[i]
                if v is None:
                    continue
                p = min(1.0, (i - i0) / d)
                pred = end + dist * (1 - ease(p))
                err = max(err, abs(pred - v))
            score = err / abs(dist)
            if best is None or score < best["residual"] - 1e-9 or (abs(score - best["residual"]) <= 1e-9 and abs(d - expected) < abs(best["d"] - expected)):
                best = {"d": d, "ease": name, "residual": score, "distance": dist}
    return best


def fmt(v) -> str:
    if v is None:
        return "none"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


def within_frames(measured, expected) -> bool:
    return measured is not None and abs(measured - expected) <= FRAME_TOL + 1e-9


def within_ratio(measured, expected) -> bool:
    if measured is None or expected is None:
        return False
    if expected == 0:
        return abs(measured) <= 0.5
    return abs(measured - expected) <= RATIO_TOL * abs(expected) + 1e-9


# ------------------------------------------------------------------------------------------------ the checks

def run_check(check: dict, rows: list[dict], result: dict) -> list[dict]:
    kind = check["kind"]
    out = []

    def add(name, expected, measured, ok, unit=""):
        out.append({"check": f"{kind}: {name}", "expected": expected, "measured": measured, "ok": bool(ok), "unit": unit})

    if kind == "static":
        add("renders", "no page errors", len(result.get("errors", [])), not result.get("errors"))
        return out
    if kind == "webgl":
        ok = result.get("webgl")
        out.append({"check": "webgl: a WebGL context in the harness", "expected": "yes", "measured": "yes" if ok else ("no (2D fallback shown)" if ok is False else "unknown"),
                    "ok": True, "unit": "", "warning": "" if ok else "WebGL unavailable: the 3D beat falls back to 2D and S10 flags NEEDS REVIEW"})
        return out
    if kind == "visible_at_zero":
        op = series(rows, check["selector"], "opacity")
        add("visible at frame 0", 1, op[0] if op else None, op and op[0] is not None and op[0] >= 0.99)
        return out

    sel = check.get("selector")
    at = check.get("at", 0)
    i0 = idx(at)
    if kind == "fade":
        got = opacity_frames(rows, sel, at)
        add("opacity frames", check["frames"], got, within_frames(got, check["frames"]), "frames")
    elif kind == "enter":
        got = opacity_frames(rows, sel, at)
        add("opacity frames", check["opacity_frames"], got, within_frames(got, check["opacity_frames"]), "frames")
        ys = series(rows, sel, "y")
        fit = fit_duration(ys, i0, int(round(check["position_frames"])), ("expo.out", "power3.out", "power2.out"))
        add("rise px", check["rise"], None if fit.get("distance") is None else round(fit["distance"], 1), within_ratio(fit.get("distance"), check["rise"]), "px")
        add("position frames (fit)", check["position_frames"], fit["d"], within_frames(fit["d"], check["position_frames"]) and (fit["residual"] or 1) <= RATIO_TOL, "frames")
        add("ease", "ease-out", fit["ease"], fit["ease"] in ("expo.out", "power3.out", "power2.out"))
    elif kind == "fly":
        axis = check.get("axis", "y")
        vals = series(rows, sel, axis)
        if "overshoot" in check:
            # a slide that overshoots by a few px and settles (v08 logo tile): distance, the overshoot and the frames to settle
            tail = [v for v in vals[i0:] if v is not None]
            final = tail[-1] if tail else None
            start_v = vals[i0] if i0 < len(vals) else None
            dist = None if final is None or start_v is None else abs(final - start_v)
            add(f"distance {axis}", check["distance"], None if dist is None else round(dist, 1), within_ratio(dist, check["distance"]), "px")
            window = [v for v in vals[i0:i0 + int(check["frames"]) + 6] if v is not None]
            over = None
            if window and final is not None and start_v is not None:
                over = (max(window) - final) if final > start_v else (final - min(window))
            add("overshoot px", check["overshoot"], None if over is None else round(over, 1), over is not None and abs(over - check["overshoot"]) <= max(1.0, RATIO_TOL * check["overshoot"]), "px")
            settle = None
            if final is not None:
                peak_i = None
                for i in range(i0, min(len(vals), i0 + len(window))):
                    if vals[i] is not None and over is not None and abs(abs(vals[i] - final) - over) < 1e-6:
                        peak_i = i
                        break
                settle = first_index(vals, (peak_i if peak_i is not None else i0) + 1, lambda v: abs(v - final) <= 0.5)
            got = None if settle is None else settle - i0
            add("frames to settle", check["frames"], got, within_frames(got, check["frames"]), "frames")
        else:
            fit = fit_duration(vals, i0, int(round(check["frames"])), ("expo.out", "power3.out", "power2.out"))
            add(f"distance {axis}", check["distance"], None if fit.get("distance") is None else round(abs(fit["distance"]), 1), within_ratio(abs(fit.get("distance") or 0), check["distance"]), "px")
            add("frames (fit)", check["frames"], fit["d"], within_frames(fit["d"], check["frames"]) and (fit["residual"] or 1) <= RATIO_TOL + 0.05, "frames")
    elif kind == "pop":
        sc = series(rows, sel, "scale")
        window = [v for v in sc[i0:i0 + int(check["frames"]) + 6] if v is not None]
        peak = max(window) if window else None
        over = None if peak is None else peak - 1
        rng = check.get("overshoot_range")
        if rng:
            ok_over = over is not None and (rng[0] - 0.004) <= over <= (rng[1] + 0.004)
            add("overshoot", f"{rng[0]} to {rng[1]}", None if over is None else round(over, 4), ok_over, "ratio")
        else:
            add("overshoot", check["overshoot"], None if over is None else round(over, 4), over is not None and abs(over - check["overshoot"]) <= max(0.004, RATIO_TOL * check["overshoot"]), "ratio")
        peak_i = None
        if peak is not None:
            for i in range(i0, min(len(sc), i0 + int(check["frames"]) + 6)):
                if sc[i] is not None and abs(sc[i] - peak) < 1e-6:
                    peak_i = i
                    break
        settle = first_index(sc, (peak_i or i0) + 1, lambda v: abs(v - 1) <= 2e-4)
        got = None if settle is None else settle - i0
        add("frames to settle", check["frames"], got, within_frames(got, check["frames"]), "frames")
        opf = opacity_frames(rows, sel, at)
        add("opacity within 4 frames", "<= 4", opf, opf is not None and opf <= 4 + FRAME_TOL, "frames")
    elif kind == "count":
        texts = series(rows, sel, "text")
        i = first_index(texts, i0, lambda v: v == check["text"])
        got = None if i is None else i - i0
        add("frames to the final value", check["frames"], got, got is not None and abs(got - check["frames"]) <= FRAME_TOL + 0.5, "frames")
    elif kind == "typing":
        texts = series(rows, sel, "text")
        lens = [None if t is None else len(t) for t in texts]
        base_text = texts[i0] if i0 < len(texts) else None
        start = first_index(texts, i0, lambda v: base_text is not None and v != base_text)
        final = max(v for v in lens if v is not None) if any(v is not None for v in lens) else None
        end = first_index(lens, i0, lambda v: v == final) if final is not None else None
        chars = check["chars"]
        got = None
        if start is not None and end is not None and chars > 1:
            got = (end - start) / (chars - 1)
        exp = check["frames_per_char"]
        add("frames per character", exp, None if got is None else round(got, 3), got is not None and abs(got - exp) <= max(0.25, RATIO_TOL * exp), "frames")
    elif kind == "exit":
        if check.get("mode") == "fade":
            op = series(rows, sel, "opacity")
            i = first_index(op, i0, lambda v: v <= 0.01)
            got = None if i is None else i - i0
            add("frames to fade out", check["frames"], got, within_frames(got, check["frames"]), "frames")
        else:
            ys = series(rows, sel, "y")
            xs = series(rows, sel, "x")
            moved_y = [None if v is None else v for v in ys]
            fit_y = fit_duration(moved_y, i0, int(check["frames"]), ("power2.in",))
            fit_x = fit_duration(xs, i0, int(check["frames"]), ("power2.in",))
            fit = fit_y if abs(fit_y.get("distance") or 0) >= abs(fit_x.get("distance") or 0) else fit_x
            add("frames (fit, ease-in)", check["frames"], fit["d"], within_frames(fit["d"], check["frames"]) and (fit["residual"] or 1) <= RATIO_TOL + 0.05, "frames")
            gone = first_index(rows, i0, lambda row: (row.get(sel) is None) or row[sel]["opacity"] <= 0.01 or row[sel]["y"] >= 1920 or (row[sel]["x"] + row[sel]["w"]) <= 0 or row[sel]["x"] >= 1080)
            add("leaves the frame", "yes", "yes" if gone is not None else "no", gone is not None)
    elif kind == "grow":
        key = check.get("axis", "w")
        vals = series(rows, sel, key)
        fit = fit_duration(vals, i0, int(check["frames"]), ("power3.out", "power2.out", "expo.out", "power1.out"))
        add(f"{key} growth frames (fit)", check["frames"], fit["d"], within_frames(fit["d"], check["frames"]) and (fit["residual"] or 1) <= RATIO_TOL + 0.05, "frames")
    elif kind == "shrink":
        sc = series(rows, sel, "scale")
        fit = fit_duration(sc, i0, int(check["frames"]), ("power2.out", "power3.out", "power1.inOut"))
        tail = [v for v in sc[i0:] if v is not None]
        add("end scale", check["scale"], None if not tail else round(tail[-1], 3), tail and within_ratio(tail[-1], check["scale"]), "ratio")
        add("frames (fit)", check["frames"], fit["d"], within_frames(fit["d"], check["frames"]) and (fit["residual"] or 1) <= RATIO_TOL + 0.05, "frames")
    elif kind == "stagger":
        sels = check["selectors"]
        mode = check.get("mode", "opacity")
        firsts = []
        for s in sels:
            if mode == "grow":
                firsts.append(first_visible(rows, s, thr=1.0, key="h"))
            else:
                firsts.append(first_visible(rows, s))
        gaps = []
        for a, b in zip(firsts, firsts[1:]):
            gaps.append(None if a is None or b is None else b - a)
        ok = all(g is not None and abs(g - check["gap_frames"]) <= FRAME_TOL for g in gaps) and bool(gaps)
        add("gap frames between neighbours", check["gap_frames"], gaps, ok, "frames")
    elif kind == "after":
        ref = check["ref_selector"]
        if check.get("ref_mode") == "gone":
            op = series(rows, ref, "opacity")
            ref_end = first_index(op, 0, lambda v: v <= 0.01)
        else:
            ys = series(rows, ref, "y")
            start_i = first_visible(rows, ref) or 0
            fit = fit_duration(ys, start_i, int(check.get("ref_frames", 8)), ("expo.out", "power3.out", "power2.out"))
            ref_end = None if fit["d"] is None else start_i + fit["d"]
        target = first_visible(rows, check["selector"])
        got = None if ref_end is None or target is None else target - ref_end
        add("frames after the reference", check["delay_frames"], got, within_frames(got, check["delay_frames"]), "frames")
    elif kind == "bubble":
        cys = series(rows, sel, "cy")
        tail = [v for v in cys[i0:] if v is not None]
        final = tail[-1] if tail else None
        window = cys[i0:i0 + int(check["frames"]) + int(check["settle_frames"]) + 4]
        vals = [v for v in window if v is not None]
        top = min(vals) if vals else None
        over = None if top is None or final is None else final - top
        add("overshoot y px", check["overshoot_y"], None if over is None else round(over, 1), within_ratio(over, check["overshoot_y"]), "px")
        peak_i = None
        if top is not None:
            for i in range(i0, min(len(cys), i0 + len(window))):
                if cys[i] is not None and abs(cys[i] - top) < 1e-6:
                    peak_i = i
                    break
        add("frames to the peak", check["frames"], None if peak_i is None else peak_i - i0, peak_i is not None and within_frames(peak_i - i0, check["frames"]), "frames")
        settle = first_index(cys, (peak_i or i0) + 1, lambda v: final is not None and abs(v - final) <= 0.5)
        got = None if settle is None or peak_i is None else settle - peak_i
        add("settle frames after the peak", check["settle_frames"], got, within_frames(got, check["settle_frames"]), "frames")
    else:
        out.append({"check": kind, "expected": "", "measured": "unknown check kind", "ok": False})
    return out


# ------------------------------------------------------------------------------------------------ the run

def analysis_dir() -> str:
    return os.path.join(common.style_dir(), "analysis")


def strip_correlation(spec: dict, shots: list[str], move_frames: int) -> dict:
    out = {"best": None, "strips": []}
    if not shots:
        return out
    cur = strips.change_curve([__import__("PIL.Image", fromlist=["Image"]).open(p) for p in shots])
    for rel in spec.get("strips", []):
        path = os.path.join(analysis_dir(), rel)
        if not os.path.isfile(path):
            out["strips"].append({"strip": rel, "r": None, "note": "missing"})
            continue
        try:
            ref = strips.change_curve(strips.cells(path))
        except Exception as exc:  # noqa: BLE001
            out["strips"].append({"strip": rel, "r": None, "note": f"unreadable: {exc}"})
            continue
        r, o_ref, o_cur = strips.correlate(ref, cur, move_frames)
        entry = {"strip": rel, "r": round(r, 3), "ref_onset": o_ref, "cur_onset": o_cur, "frames": move_frames}
        out["strips"].append(entry)
        if out["best"] is None or (entry["r"] is not None and entry["r"] > out["best"]["r"]):
            out["best"] = entry
    return out


def move_frames_of(spec: dict) -> int:
    for c in spec["checks"]:
        for key in ("position_frames", "frames", "settle_frames"):
            if key in c and isinstance(c[key], (int, float)):
                return int(round(c[key])) + 3
    return 10


def match_component(h: harness.Harness, comp: dict, spec: dict, shots: bool, work: str) -> dict:
    n = int(spec["frames"]) + 1
    times = [i / common.FPS for i in range(n)]
    shots_dir = os.path.join(work, "shots", comp["id"]) if shots else None
    result = h.measure(comp, spec.get("props"), times, spec["selectors"], shots_dir=shots_dir)
    checks = []
    for c in spec["checks"]:
        try:
            checks.extend(run_check(c, result["rows"], result))
        except Exception as exc:  # noqa: BLE001
            checks.append({"check": c.get("kind", "?"), "expected": "", "measured": f"error: {exc}", "ok": False})
    corr = strip_correlation(spec, result.get("shots", []), move_frames_of(spec)) if shots else {"best": None, "strips": []}
    has_strip = any(s.get("r") is not None for s in corr["strips"])
    numbers_ok = all(c["ok"] for c in checks)
    strip_ok = (not has_strip) or (corr["best"] is not None and corr["best"]["r"] is not None and corr["best"]["r"] >= MIN_R)
    errors = [e for e in result.get("errors", []) if "three.min.js" not in e and "deprecated" not in e]
    return {"id": comp["id"], "pass": numbers_ok and strip_ok and not errors, "numbers_ok": numbers_ok, "strip_ok": strip_ok,
            "checks": checks, "correlation": corr, "errors": errors, "webgl": result.get("webgl"), "events": result.get("events", [])[:40],
            "frames_measured": n}


def write_report(results: list[dict], lib: str, applied: bool) -> str:
    lines = ["# frame-match: the library components against the style's numbers and the reference strips", "",
             f"Run {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by pipeline/bin/frame-match. Tolerances: {FRAME_TOL} frame on timings, "
             f"{int(RATIO_TOL * 100)} percent on distances and overshoots; a reference strip must correlate at r >= {MIN_R} (DECISIONS.md 29). "
             "Numbers: styles/paper-cards/vocabulary.md and style.md through tokens.json; strips: styles/paper-cards/analysis/<vXX>/extra/s30_*.png"
             + (" (applied: failing components moved to candidates/)." if applied else "."), ""]
    passed = [r for r in results if r["pass"]]
    failed = [r for r in results if not r["pass"]]
    lines.append(f"**{len(passed)} pass, {len(failed)} fail** of {len(results)} components.")
    lines.append("")
    lines.append("| component | result | checks | best strip | r |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        okn = sum(1 for c in r["checks"] if c["ok"])
        best = r["correlation"].get("best") or {}
        lines.append(f"| {r['id']} | {'pass' if r['pass'] else 'FAIL'} | {okn}/{len(r['checks'])} | {best.get('strip', 'none')} | {fmt(best.get('r'))} |")
    lines.append("")
    for r in results:
        lines.append(f"## {r['id']}: {'pass' if r['pass'] else 'FAIL'}")
        lines.append("")
        lines.append("| check | expected | measured | ok |")
        lines.append("|---|---|---|---|")
        for c in r["checks"]:
            unit = f" {c.get('unit')}" if c.get("unit") else ""
            lines.append(f"| {c['check']} | {fmt(c['expected'])}{unit} | {fmt(c['measured'])} | {'yes' if c['ok'] else 'NO'} |")
            if c.get("warning"):
                lines.append(f"| | | WARN: {c['warning']} | |")
        if r["correlation"]["strips"]:
            parts = [f"{s['strip']} r={fmt(s.get('r'))}" + (f" ({s['note']})" if s.get("note") else "") for s in r["correlation"]["strips"]]
            lines.append("")
            lines.append("Strips: " + "; ".join(parts))
        if r["errors"]:
            lines.append("")
            lines.append("Page errors: " + "; ".join(r["errors"])[:600])
        lines.append("")
    text = "\n".join(lines) + "\n"
    common.write_text(os.path.join(lib, "gallery", "frame-match.md"), text)
    common.write_json(os.path.join(lib, "gallery", "frame-match.json"), {"run": dt.datetime.now().isoformat(timespec="seconds"), "results": results})
    return text


def apply_moves(results: list[dict], lib: str) -> list[str]:
    moves = []
    for r in results:
        cid = r["id"]
        src_ok = os.path.join(lib, "compositions", cid + ".html")
        src_cand = os.path.join(lib, "candidates", cid + ".html")
        if r["pass"] and os.path.isfile(src_cand) and not os.path.isfile(src_ok):
            shutil.move(src_cand, src_ok)
            moves.append(f"{cid}: candidates -> compositions")
        elif not r["pass"] and os.path.isfile(src_ok) and cid != "paper-canvas":
            os.makedirs(os.path.join(lib, "candidates"), exist_ok=True)
            shutil.move(src_ok, src_cand)
            moves.append(f"{cid}: compositions -> candidates")
    return moves


def update_catalog(results: list[dict], lib: str, moved: bool) -> None:
    """Record every result in catalog.json; status and file change only when the files were moved (--apply)."""
    path = common.catalog_path(lib)
    if not os.path.isfile(path):
        return
    cat = common.load_json(path)
    by_id = {r["id"]: r for r in results}
    for c in cat.get("components", []):
        r = by_id.get(c["id"])
        if not r:
            continue
        best = r["correlation"].get("best") or {}
        c["frame_match"] = {"result": "pass" if r["pass"] else "fail", "checks_ok": sum(1 for x in r["checks"] if x["ok"]), "checks": len(r["checks"]),
                            "best_strip": best.get("strip"), "r": best.get("r"), "run": dt.date.today().isoformat()}
        if moved:
            c["status"] = "approved" if r["pass"] else "candidate"
            c["file"] = ("compositions/" if r["pass"] else "candidates/") + c["id"] + ".html"
    common.write_json(path, cat)


def run(args) -> int:
    lib = common.motion_lib_dir()
    toks = common.tokens()
    specs = expectations.build(toks)
    files = common.component_files(lib)
    all_paths = files["compositions"] + files["candidates"]
    only = set(args.only.split(",")) if args.only else None
    work = os.path.join(lib, ".harness")
    results = []
    with harness.Harness(lib=lib, gpu=args.gpu) as h:
        for path in all_paths:
            comp = common.parse_component(path)
            if only and comp["id"] not in only:
                continue
            spec = specs.get(comp["id"])
            if not spec:
                results.append({"id": comp["id"], "pass": False, "numbers_ok": False, "strip_ok": False, "checks": [{"check": "expectations", "expected": "an entry in motion/expectations.py", "measured": "none", "ok": False}],
                                "correlation": {"best": None, "strips": []}, "errors": [], "webgl": None, "events": [], "frames_measured": 0})
                print(f"{comp['id']}: no expectations entry")
                continue
            r = match_component(h, comp, spec, not args.no_shots, work)
            results.append(r)
            okn = sum(1 for c in r["checks"] if c["ok"])
            best = r["correlation"].get("best") or {}
            print(f"{comp['id']}: {'pass' if r['pass'] else 'FAIL'} ({okn}/{len(r['checks'])} checks, strip r={fmt(best.get('r'))})")
            for c in r["checks"]:
                if not c["ok"]:
                    print(f"    {c['check']}: expected {fmt(c['expected'])}, measured {fmt(c['measured'])}")
            for e in r["errors"]:
                print(f"    page error: {e[:200]}")
    moves = apply_moves(results, lib) if args.apply else []
    write_report(results, lib, bool(args.apply))
    update_catalog(results, lib, bool(args.apply))
    for m in moves:
        print("moved " + m)
    failed = [r["id"] for r in results if not r["pass"]]
    print(f"frame-match: {len(results) - len(failed)} pass, {len(failed)} fail -> {os.path.join(lib, 'gallery', 'frame-match.md')}")
    return 0 if not failed else 1
