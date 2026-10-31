#!/usr/bin/env python3
"""
analyze_refs.py - turn reference videos into things Claude can look at and measure.

Claude cannot watch video. This script extracts what it needs instead:
  - contact sheets: 1 frame per second, timestamps labeled
  - filmstrips: 10 fps strips of the hook and of the biggest visual changes (motion)
  - full-resolution frames for pixel measurements
  - numbers: palette, accent color, visual-change cadence per screen band, loudness

Usage
  python analyze_refs.py VIDEO_OR_FOLDER [VIDEO_OR_FOLDER ...] --out analysis
  python analyze_refs.py refs/look refs/motion --out analysis --strips 8

Needs ffmpeg and ffprobe on PATH, and Python with numpy and pillow.
Videos are never renamed: each gets a nickname (v01, v02, ...) in alphabetical order.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


def sh(cmd):
    """Run a command, return (stdout bytes, stderr text)."""
    p = subprocess.run(cmd, capture_output=True)
    return p.stdout, p.stderr.decode("utf-8", "replace")


def ts(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def probe(path):
    out, _ = sh(["ffprobe", "-v", "error", "-show_entries",
                 "stream=codec_type,width,height,r_frame_rate:format=duration",
                 "-of", "json", str(path)])
    d = json.loads(out or b"{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise RuntimeError("no video stream")
    num, den = (v.get("r_frame_rate") or "30/1").split("/")
    return {
        "width": int(v["width"]), "height": int(v["height"]),
        "fps": round(float(num) / float(den or 1), 3),
        "duration": round(float(d.get("format", {}).get("duration", 0)), 2),
        "has_audio": any(s.get("codec_type") == "audio" for s in d.get("streams", [])),
    }


def contact_sheets(frames, out_prefix, cols, per, t0, step):
    paths = []
    for si in range(0, len(frames), per):
        chunk = frames[si:si + per]
        w, h = Image.open(chunk[0]).size
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * w, rows * (h + 18)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, f in enumerate(chunk):
            x, y = (i % cols) * w, (i // cols) * (h + 18)
            sheet.paste(Image.open(f).convert("RGB"), (x, y + 18))
            draw.text((x + 4, y + 3), ts(t0 + (si + i) * step), fill="black")
        p = Path(f"{out_prefix}_{si // per:02d}.png")
        sheet.save(p)
        paths.append(p.name)
    return paths


def kmeans_once(px, k, iters, seed):
    rng = np.random.default_rng(seed)
    centers = [px[rng.integers(len(px))].astype(float)]          # k-means++ init
    for _ in range(k - 1):
        d = np.min(((px[:, None, :] - np.array(centers)[None]) ** 2).sum(-1), axis=1)
        centers.append(px[rng.choice(len(px), p=d / d.sum())].astype(float))
    centers = np.array(centers)
    for _ in range(iters):
        d = ((px[:, None, :] - centers[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            if (lab == j).any():
                centers[j] = px[lab == j].mean(0)
    inertia = float(d[np.arange(len(px)), lab].sum())
    return centers, lab, inertia


def kmeans(px, k=8, iters=25, tries=4):
    """Best of several k-means runs (lowest inertia), returned as (hex, share %) sorted by share."""
    centers, lab, _ = min((kmeans_once(px, k, iters, s) for s in range(tries)), key=lambda r: r[2])
    cnt = np.bincount(lab, minlength=k)
    order = np.argsort(-cnt)
    return [("#%02X%02X%02X" % tuple(centers[j].round().astype(int)), round(100 * cnt[j] / cnt.sum(), 1))
            for j in order]


def palette_and_accent(frames):
    px = np.concatenate([np.asarray(Image.open(f).convert("RGB")).reshape(-1, 3) for f in frames])
    rng = np.random.default_rng(0)
    sample = px[rng.choice(len(px), min(len(px), 120000), replace=False)].astype(float)
    pal = kmeans(sample)
    # flat colors: exact surface colors (paper vs white card) that k-means tends to merge
    q = np.clip((px.astype(np.int64) + 2) // 4 * 4, 0, 252)
    keys, counts = np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2], return_counts=True)
    top = np.argsort(-counts)[:8]
    flat = [("#%02X%02X%02X" % ((keys[i] >> 16) & 255, (keys[i] >> 8) & 255, keys[i] & 255),
             round(100 * counts[i] / len(px), 1)) for i in top]
    mx, mn = px.max(1).astype(float), px.min(1).astype(float)
    sat = (mx - mn) / (mx + 1e-9)
    acc = px[(sat > 0.45) & (mx > 120)]
    share = round(100 * len(acc) / len(px), 2)
    accent = "#%02X%02X%02X" % tuple(np.median(acc, axis=0).astype(int)) if share >= 0.3 else None
    return pal, flat, accent, share


def cadence(path, fps):
    """Per-frame visual change, overall and per screen third (top/middle/bottom)."""
    w, h = 90, 160
    raw, _ = sh(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h},format=gray",
                 "-f", "rawvideo", "-"])
    fr = np.frombuffer(raw, dtype=np.uint8)
    n = len(fr) // (w * h)
    fr = fr[:n * w * h].reshape(n, h, w).astype(np.float32)
    diff = np.abs(np.diff(fr, axis=0))
    t = np.arange(1, n) / fps
    bands = {"overall": diff.mean((1, 2)),
             "top": diff[:, :h // 3].mean((1, 2)),
             "middle": diff[:, h // 3:2 * h // 3].mean((1, 2)),
             "bottom": diff[:, 2 * h // 3:].mean((1, 2))}
    res = {}
    for name, d in bands.items():
        thr = max(1.0, float(np.percentile(d, 90)))
        ev = []
        for i in np.where(d > thr)[0]:
            if not ev or t[i] - ev[-1] > 0.3:
                ev.append(float(t[i]))
        gaps = np.diff(ev) if len(ev) > 1 else np.array([0.0])
        res[name] = {"events": len(ev),
                     "per_10s": round(10 * len(ev) / max(t[-1], 1e-9), 1),
                     "gap_median_s": round(float(np.median(gaps)), 2),
                     "gap_p90_s": round(float(np.percentile(gaps, 90)), 2),
                     "gap_max_s": round(float(gaps.max()), 2),
                     "first_event_s": round(ev[0], 2) if ev else None}
    return res, bands["overall"], t


def top_events(d, t, k, min_sep=2.0, skip_before=1.6):
    picks = []
    for i in np.argsort(-d):
        if t[i] < skip_before or t[i] > t[-1] - 0.5:
            continue
        if all(abs(t[i] - p) >= min_sep for p in picks):
            picks.append(float(t[i]))
        if len(picks) == k:
            break
    return sorted(picks)


def filmstrip(path, start, out_prefix, tmp):
    d = Path(tmp) / f"strip_{start:.2f}"
    d.mkdir(parents=True, exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-ss", f"{start:.2f}", "-t", "1.6", "-i", str(path),
        "-vf", "fps=10,scale=200:-1", str(d / "%03d.png")])
    frames = sorted(d.glob("*.png"))
    if not frames:
        return None
    made = Path(out_prefix.parent) / contact_sheets(frames, out_prefix, 8, 16, start, 0.1)[0]
    final = Path(f"{out_prefix}.png")
    made.replace(final)
    return final.name


def audio_stats(path):
    _, err = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                 "-af", "loudnorm=print_format=summary", "-f", "null", "-"])
    lufs = re.search(r"Input Integrated:\s*(-?[\d.]+)", err)
    peak = re.search(r"Input True Peak:\s*([-+]?[\d.]+)", err)
    raw, _ = sh(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000",
                 "-f", "s16le", "-"])
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    win = 800
    n = len(a) // win
    silence = None
    if n:
        rms = np.sqrt((a[:n * win].reshape(n, win) ** 2).mean(1)) + 1e-9
        silence = round(100 * float((20 * np.log10(rms) < -45).mean()), 1)
    return {"integrated_lufs": float(lufs.group(1)) if lufs else None,
            "true_peak_dbtp": float(peak.group(1)) if peak else None,
            "silence_share_pct": silence,
            "music_bed_likely": (silence is not None and silence < 2.0)}


def analyze(path, nick, out_root, n_strips):
    out = out_root / nick
    out.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    scale = round(1080 / info["width"], 3)
    with tempfile.TemporaryDirectory() as tmp:
        sh(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "fps=1,scale=240:-1",
            str(Path(tmp) / "s_%04d.png")])
        thumbs = sorted(Path(tmp).glob("s_*.png"))
        sheets = contact_sheets(thumbs, out / "sheet", 6, 18, 0.5, 1.0)
        pal, flat, accent, accent_share = palette_and_accent(thumbs)
        cad, overall, t = cadence(path, info["fps"])
        events = top_events(overall, t, n_strips)
        strips = [filmstrip(path, 0.0, out / "strip_hook", tmp)]
        for i, e in enumerate(events, 1):
            strips.append(filmstrip(path, max(0.0, e - 0.3), out / f"strip_{i:02d}", tmp))
    fulls = []
    for tt in [0.5] + [e + 0.8 for e in events]:
        if tt < info["duration"]:
            name = f"full_{tt:06.2f}.png"
            sh(["ffmpeg", "-v", "error", "-ss", f"{tt:.2f}", "-i", str(path), "-frames:v", "1",
                str(out / name)])
            fulls.append(name)
    audio = audio_stats(path) if info["has_audio"] else None

    summary = {"nickname": nick, "file": path.name, **info, "scale_to_1080": scale,
               "palette": pal, "flat_colors": flat, "accent": accent, "accent_share_pct": accent_share,
               "cadence": cad, "strip_events_s": [round(e, 2) for e in events],
               "audio": audio, "sheets": sheets, "strips": [s for s in strips if s], "full_frames": fulls}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [f"# {nick}: {path.name}", "",
          f"- {info['width']}x{info['height']}, {info['fps']} fps, {info['duration']}s. "
          f"Multiply pixel values by {scale} to convert to 1080 wide.", "",
          "## Palette (share of screen, 1 fps frames)"]
    md += [f"- `{hexc}` {share}%" for hexc, share in pal]
    md += ["", "## Flat colors (most common exact colors, rounded to 4: backgrounds, surfaces, ink)"]
    md += [f"- `{hexc}` {share}%" for hexc, share in flat]
    md += ["", f"Accent (median of saturated pixels): `{accent}` covering {accent_share}% of pixels"
           if accent else "Accent: none found (no saturated color above 0.3% of pixels)", "",
           "## Visual change cadence (frame differences; captions count too)",
           "| band | events | per 10s | gap median | gap p90 | gap max | first |",
           "|---|---|---|---|---|---|---|"]
    for band, c in cad.items():
        md.append(f"| {band} | {c['events']} | {c['per_10s']} | {c['gap_median_s']}s | {c['gap_p90_s']}s | "
                  f"{c['gap_max_s']}s | {c['first_event_s']}s |")
    md += ["", "A band with far more events than the others usually holds the captions.", "",
           "## Audio"]
    if audio:
        md += [f"- Integrated loudness {audio['integrated_lufs']} LUFS, true peak {audio['true_peak_dbtp']} dBTP",
               f"- True silence: {audio['silence_share_pct']}% of the track. "
               f"Music bed likely: {'yes' if audio['music_bed_likely'] else 'no'}"]
    else:
        md.append("- No audio stream")
    md += ["", "## Files",
           f"- Contact sheets: {', '.join(sheets)}",
           f"- Filmstrips (10 fps, 1.6s each): {', '.join(s for s in strips if s)} "
           f"(events at {', '.join(ts(e) for e in events)})",
           f"- Full-resolution frames: {', '.join(fulls)}"]
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser(description="Turn reference videos into sheets, strips and numbers.")
    ap.add_argument("inputs", nargs="+", help="video files or folders")
    ap.add_argument("--out", default="analysis")
    ap.add_argument("--strips", type=int, default=6, help="filmstrips per video besides the hook")
    args = ap.parse_args()

    vids = []
    for inp in args.inputs:
        p = Path(inp)
        if p.is_dir():
            vids += [f for f in p.rglob("*") if f.suffix.lower() in VIDEO_EXT]
        elif p.suffix.lower() in VIDEO_EXT:
            vids.append(p)
    vids = sorted(set(vids), key=lambda f: f.name.lower())
    if not vids:
        sys.exit("no videos found")

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    rows = ["| nickname | file | folder | duration | resolution | fps |", "|---|---|---|---|---|---|"]
    for i, v in enumerate(vids, 1):
        nick = f"v{i:02d}"
        print(f"[{nick}] {v.name} ...", flush=True)
        try:
            s = analyze(v, nick, out_root, args.strips)
            rows.append(f"| {nick} | {v.name} | {v.parent.name} | {s['duration']}s | "
                        f"{s['width']}x{s['height']} | {s['fps']} |")
        except Exception as e:  # keep going on a broken file
            print(f"   failed: {e}", flush=True)
            rows.append(f"| {nick} | {v.name} | {v.parent.name} | FAILED: {e} | | |")
    (out_root / "index.md").write_text("# Reference index\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"done: {out_root / 'index.md'}")


if __name__ == "__main__":
    main()
