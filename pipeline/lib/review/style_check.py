"""pipeline/lib/review/style_check.py: the style conformance check of S12 (BUILD_SPEC.md S12, M11).

tools/analyze_refs.py runs on the mixed draft (540x960) into 12-review/analysis/ and its numbers are compared with
the reference analysis of styles/paper-cards/analysis (one summary.json per reference video; tokens.json's pacing
block when none is there):
  cadence   the hero zone's (the middle screen band's) visual-change gap median and gap maximum within the
            references' range, plus or minus 20 percent (config review.cadence_tolerance_pct)        [animation]
  palette   at least review.palette_min_share_pct (90) of the non-image pixels of the 1 fps frames within
            delta E review.palette_delta_e (5, CIE76) of a token color (the token colors, the paper's two glows and
            the card shadow as gradients between tokens, white); the research screenshots and the logos are image
            pixels (their boxes come from the mechanical pass, images_by_time)                        [animation]
  accent    the UI accent (hue 8 to 30 degrees, saturation over 0.55, value over 0.7, the measure of
            analysis/accent_share.txt) under tokens.json limits.accent_share_max_pct (5) of every frame, logos
            excluded                                                                                   [animation]
  loudness  the mixed draft at voice.loudness_lufs plus or minus 1 LU, true peak at most voice.true_peak_dbtp plus
            review.aac_peak_tolerance_db (the AAC encode moves peaks a little)                              [sfx]
Every pixel threshold is applied at the draft's resolution (the boxes are scaled from the composition's 1080 px).

  run(ctx, mech_report, out_path) -> the report dict (also written as JSON)
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys

import numpy as np

from review import common as rc


def run_analyzer(ctx: rc.Ctx, video: str, out_dir: str) -> dict:
    tool = os.path.join(ctx.repo, "tools", "analyze_refs.py")
    if not os.path.isfile(tool):
        tool = os.path.join(rc.REPO, "tools", "analyze_refs.py")
    cmd = [sys.executable, tool, video, "--out", out_dir, "--strips", "0"]
    # a later review round writes into the same folder: the analyzer's ffmpeg calls have no -y, so a still left from
    # the previous round made ffmpeg wait for "Overwrite? [y/N]" until the stage timed out (found in M12). The old
    # results go first, and the analyzer gets no stdin, so no prompt can ever block it.
    shutil.rmtree(os.path.join(out_dir, "v01"), ignore_errors=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                          timeout=int(ctx.c("timeouts.style_seconds", 1200)))
    summary = rc.load_json(os.path.join(out_dir, "v01", "summary.json"), None)
    if not summary:
        raise RuntimeError(f"analyze_refs.py produced no summary ({(proc.stderr or proc.stdout or '')[-300:]})")
    return summary


def reference_ranges(ctx: rc.Ctx) -> dict:
    refs = []
    for f in sorted(glob.glob(os.path.join(ctx.analysis_dir, "v*", "summary.json"))):
        d = rc.load_json(f, None)
        if d and d.get("cadence", {}).get("middle"):
            refs.append(d)
    if refs:
        mids = [d["cadence"]["middle"] for d in refs]
        return {"source": f"{len(refs)} reference videos in {ctx.analysis_dir}", "n": len(refs),
                "gap_median_s": [min(m["gap_median_s"] for m in mids), max(m["gap_median_s"] for m in mids)],
                "gap_max_s": [min(m["gap_max_s"] for m in mids), max(m["gap_max_s"] for m in mids)],
                "per_10s": [min(m["per_10s"] for m in mids), max(m["per_10s"] for m in mids)]}
    pacing = ctx.toks.get("pacing") or {}
    return {"source": "tokens.json pacing (no reference analysis found)", "n": 0,
            "gap_median_s": [float(pacing.get("gap_median_s", 0.9)) * 0.5, float(pacing.get("gap_median_s", 0.9)) * 1.5],
            "gap_max_s": [0.0, float(pacing.get("gap_max_s", 6.5))], "per_10s": [float(pacing.get("changes_per_10s_median", 6.4)) * 0.6, float(pacing.get("changes_per_10s_median", 6.4)) * 1.4]}


def frames_rgb(video: str, w: int, h: int, fps: float = 1.0, timeout: int = 600) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", video, "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg could not read the draft: " + proc.stderr.decode("utf-8", "replace")[-200:])
    raw = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = len(raw) // (w * h * 3)
    return raw[: n * w * h * 3].reshape(n, h, w, 3)


def lab_of(rgb: np.ndarray) -> np.ndarray:
    """sRGB (0..255, shape (..., 3)) to CIE Lab (D65), vectorized."""
    c = rgb.astype(np.float32) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    x = (lin[..., 0] * 0.4124 + lin[..., 1] * 0.3576 + lin[..., 2] * 0.1805) / 0.95047
    y = (lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722)
    zc = (lin[..., 0] * 0.0193 + lin[..., 1] * 0.1192 + lin[..., 2] * 0.9505) / 1.08883
    f = lambda t: np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16.0 / 116.0)  # noqa: E731
    fx, fy, fz = f(x), f(y), f(zc)
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=-1)


def palette_rgb(toks: dict) -> np.ndarray:
    colors = dict(toks.get("colors") or {})
    pts = [rc.hex_rgb(v) for v in colors.values()]
    pts.append((255, 255, 255))

    def grad(a: str, b: str, n: int):
        if a in colors and b in colors:
            ca, cb = np.array(rc.hex_rgb(colors[a]), float), np.array(rc.hex_rgb(colors[b]), float)
            for i in range(1, n):
                pts.append(tuple((ca + (cb - ca) * i / n).round()))
    grad("paper", "glow-warm", 6)
    grad("paper", "glow-lower", 4)
    grad("paper", "corner", 4)
    grad("paper", "shadow-dark", 8)
    grad("surface", "shadow-dark", 6)
    grad("surface", "card-edge", 3)
    return np.array(pts, dtype=np.float32)


def mask_for(boxes: list, scale: float, w: int, h: int, kinds: tuple) -> np.ndarray:
    m = np.zeros((h, w), dtype=bool)
    for b in boxes or []:
        if len(b) >= 5 and b[4] not in kinds:
            continue
        x0, y0 = max(0, int(b[0] * scale)), max(0, int(b[1] * scale))
        x1, y1 = min(w, int((b[0] + b[2]) * scale) + 1), min(h, int((b[1] + b[3]) * scale) + 1)
        if x1 > x0 and y1 > y0:
            m[y0:y1, x0:x1] = True
    return m


def measure_audio(ctx: rc.Ctx, video: str) -> dict:
    """The mixed draft's loudness (ffmpeg loudnorm) and the check against the targets."""
    sys.path.insert(0, os.path.join(rc.LIB, "sfx"))
    from audioio import measure_loudness
    target_i, target_tp = float(ctx.c("voice.loudness_lufs", -14)), float(ctx.c("voice.true_peak_dbtp", -1.5))
    aac_tol = float(ctx.c("review.aac_peak_tolerance_db", 0.5))
    m = measure_loudness(video, target_i, target_tp)
    lufs, tp = m.get("lufs"), m.get("true_peak_dbtp")
    return {"lufs": lufs, "true_peak_dbtp": tp, "target": [target_i, target_tp], "ok": lufs is not None and abs(lufs - target_i) <= 1.0 and (tp is None or tp <= target_tp + aac_tol)}


def refresh_loudness(ctx: rc.Ctx, rep: dict) -> dict:
    """A cached visual result with the loudness of the current mix (the sound pass changes it, the picture does not)."""
    video = ctx.draft_mixed if os.path.isfile(ctx.draft_mixed) else ctx.draft
    loud = measure_audio(ctx, video)
    rep = dict(rep)
    rep["loudness"] = loud
    issues = [i for i in rep.get("issues", []) if i.get("kind") != "loudness"]
    if not loud["ok"]:
        issues.append(rc.issue("sfx", "loudness", f"the mixed draft measures {loud['lufs']} LUFS, {loud['true_peak_dbtp']} dBTP (target {loud['target'][0]} plus or minus 1, at most {loud['target'][1]} dBTP)"))
    rep["issues"] = issues
    rep["pass"] = not issues
    rep["cached_visual"] = True
    return rep


def run(ctx: rc.Ctx, mech: dict | None, out_path: str) -> dict:
    video = ctx.draft_mixed if os.path.isfile(ctx.draft_mixed) else ctx.draft
    out_dir = os.path.join(ctx.stage_dir, "analysis")
    summary = run_analyzer(ctx, video, out_dir)
    issues: list[dict] = []
    tol = float(ctx.c("review.cadence_tolerance_pct", 20)) / 100.0
    refs = reference_ranges(ctx)
    mid = (summary.get("cadence") or {}).get("middle") or {}
    cadence = {"draft": mid, "reference": refs, "checks": {}}
    for key, upper_only in (("gap_median_s", False), ("gap_max_s", True)):
        lo, hi = refs[key]
        allowed = [0.0 if upper_only else round(lo * (1 - tol), 2), round(hi * (1 + tol), 2)]
        val = float(mid.get(key, 0) or 0)
        ok = allowed[0] <= val <= allowed[1]
        cadence["checks"][key] = {"value": val, "allowed": allowed, "ok": ok}
        if not ok:
            what = "median gap between visual changes" if key == "gap_median_s" else "longest gap between visual changes"
            issues.append(rc.issue("animation", "cadence", f"the {what} in the hero zone is {val:.2f} s; the references run {allowed[0]:.2f} to {allowed[1]:.2f} s (the range plus or minus {int(tol * 100)} percent)"))
    per10 = float(mid.get("per_10s", 0) or 0)
    cadence["checks"]["per_10s"] = {"value": per10, "reference": refs["per_10s"], "ok": True, "note": "informational"}
    # the frames of the draft, 1 fps, at the draft's own size
    vinfo = summary
    w, h = int(vinfo.get("width", 540)), int(vinfo.get("height", 960))
    scale = w / rc.CANVAS_W
    frames = frames_rgb(video, w, h, 1.0, int(ctx.c("timeouts.style_seconds", 1200)))
    pal = palette_rgb(ctx.toks)
    pal_lab = lab_of(pal)
    de_max = float(ctx.c("review.palette_delta_e", 5))
    min_share = float(ctx.c("review.palette_min_share_pct", 90))
    images_by_time = (mech or {}).get("images_by_time") or {}
    shares = []
    accent_shares = []
    acc_max = float((ctx.toks.get("limits") or {}).get("accent_share_max_pct", 5))
    for i, fr in enumerate(frames):
        T = 500 + i * 1000
        boxes = images_by_time.get(str(T)) or images_by_time.get(str(min((int(k) for k in images_by_time), key=lambda k: abs(k - T)))) if images_by_time else []
        img_mask = mask_for(boxes, scale, w, h, ("image", "logo"))
        logo_mask = mask_for(boxes, scale, w, h, ("logo",))
        lab = lab_of(fr.reshape(-1, 3)).reshape(h, w, 3)
        # the nearest palette color per pixel, in chunks of rows
        d_min = np.full((h, w), 1e9, dtype=np.float32)
        for p in pal_lab:
            d = np.sqrt(((lab - p) ** 2).sum(axis=-1))
            d_min = np.minimum(d_min, d)
        keep = ~img_mask
        n = int(keep.sum())
        shares.append(100.0 * float((d_min[keep] <= de_max).sum()) / max(1, n))
        # the accent share: hue 8..30 deg, sat > 0.55, val > 0.7
        f = fr.astype(np.float32) / 255.0
        mx, mn = f.max(axis=-1), f.min(axis=-1)
        sat = (mx - mn) / (mx + 1e-9)
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        hue = np.zeros_like(mx)
        is_r = (mx == r)
        hue = np.where(is_r, ((g - b) / (mx - mn + 1e-9)) % 6.0, hue)
        hue = np.where(mx == g, ((b - r) / (mx - mn + 1e-9)) + 2.0, hue)
        hue = np.where(mx == b, ((r - g) / (mx - mn + 1e-9)) + 4.0, hue)
        hue_deg = (hue * 60.0) % 360.0
        acc = (hue_deg >= 8) & (hue_deg <= 30) & (sat > 0.55) & (mx > 0.70) & ~logo_mask
        accent_shares.append(100.0 * float(acc.sum()) / max(1, int((~logo_mask).sum())))
    palette = {"frames": len(frames), "share_within_delta_e_pct": round(float(np.mean(shares)), 2) if shares else None, "min_frame_share_pct": round(float(np.min(shares)), 2) if shares else None,
               "delta_e": de_max, "min_share_pct": min_share, "palette_colors": int(len(pal)), "ok": bool(shares) and float(np.mean(shares)) >= min_share}
    if not palette["ok"]:
        issues.append(rc.issue("animation", "palette", f"only {palette['share_within_delta_e_pct']} percent of the non-image pixels sit within delta E {de_max:g} of a token color ({min_share:g} needed): colors outside the look"))
    accent = {"max_frame_share_pct": round(float(np.max(accent_shares)), 2) if accent_shares else None, "median_frame_share_pct": round(float(np.median(accent_shares)), 2) if accent_shares else None,
              "max_allowed_pct": acc_max, "ok": bool(accent_shares) and float(np.max(accent_shares)) <= acc_max}
    if accent_shares and not accent["ok"]:
        worst = int(np.argmax(accent_shares))
        issues.append(rc.issue("animation", "accent_share", f"the accent covers {accent['max_frame_share_pct']} percent of the frame at {worst + 0.5:.1f} s (tweaks.md: under {acc_max:g} percent)"))
    loud = measure_audio(ctx, video)
    if not loud["ok"]:
        issues.append(rc.issue("sfx", "loudness", f"the mixed draft measures {loud['lufs']} LUFS, {loud['true_peak_dbtp']} dBTP (target {loud['target'][0]} plus or minus 1, at most {loud['target'][1]} dBTP)"))
    report = {"written_by": "12-review", "pass": not issues, "issues": issues, "video": os.path.relpath(video, ctx.run_dir).replace("\\", "/"), "size": [w, h],
              "cadence": cadence, "palette": palette, "accent": accent, "loudness": loud, "analyzer": {"duration": summary.get("duration"), "palette": summary.get("palette"), "accent": summary.get("accent"), "accent_share_pct": summary.get("accent_share_pct")}}
    rc.write_json(out_path, report)
    return report
