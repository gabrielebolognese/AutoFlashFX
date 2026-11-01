"""measure.py: measure every audio file of the sound pack with ffmpeg and numpy (BUILD_SPEC.md 2.6, item 1).

For one file:
  probe    ffprobe: codec, channels, sample rate, bit depth, duration
  decode   ffmpeg -> 48 kHz float32 PCM (1 or 2 channels) in memory, the first audio stream only (cover art is
           skipped)
  analyze  numpy: duration, sample peak (dBFS), clipping (full-scale runs), the 5 ms RMS envelope -> onset (the
           first frame within 30 dB of the loudest frame and 10 dB over the quietest 5 percent of frames), peak
           time (the loudest frame), attack (onset to peak), tail (peak to the last frame within 40 dB of the
           peak), end, effective duration (onset to end), silence padding at both ends (frames under -60 dBFS),
           the noise floor (the median 20 ms frame level of the lead-in before the onset and of the last 50 ms
           after the sound ended; unknown when the sound fills the file) and its distance from the peak (snr_db),
           the spectral centroid (brightness)
  ebur128  ffmpeg: integrated loudness (LUFS) and true peak (dBTP); the file is padded with 2 s of silence so
           sounds shorter than the 400 ms gating block measure too (silence falls under the gate)
  cache    the normalized copy: gain = normalize_peak_dbfs - peak_dbfs, written from the decoded samples as 48 kHz
           16-bit PCM with the file's channel count (1 or 2) under <pack>/.cache/<id>-<slug>.wav. The originals are
           never modified.

  measure_file(pack_dir, entry, settings) -> the measurement dict; a file ffmpeg cannot decode gives the same dict
  with "decode_error" set and no numbers.
  measure_many(pack_dir, entries, settings, progress=None, workers=4) -> list of dicts, in the entries' order.

  python pipeline/lib/sfx/measure.py <pack dir> [--table] [--json]   measure a folder and print a table (debugging)
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (MEASURE_VERSION, clean, file_id, list_audio_files, round_or_none, setup_streams,  # noqa: E402
                    slug, winpath)

SR = 48000
DEFAULT_SETTINGS = {
    "normalize_peak_dbfs": -12.0,
    "clip_threshold": 0.985,      # |sample| at or over this counts as full scale
    "clip_run_samples": 3,        # a run of this many full-scale samples is one clipped run
    "onset_db_under_peak": 30.0,  # the onset: the first 5 ms frame within this of the loudest frame
    "tail_db_under_peak": 40.0,   # the tail ends at the last frame within this of the loudest frame
    "silence_dbfs": -60.0,        # frames under this are silence padding
    "ffmpeg_timeout_s": 120,
}


class DecodeError(Exception):
    pass


def to_db(x: float, floor: float = -120.0) -> float:
    if x <= 0:
        return floor
    return max(floor, float(20.0 * np.log10(x)))


def run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)


def ffprobe(path: str, timeout: int) -> dict:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
           "stream=codec_name,channels,sample_rate,bits_per_sample,duration:format=duration",
           "-of", "json", winpath(path)]
    try:
        r = run(cmd, timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DecodeError(f"ffprobe failed: {exc}")
    if r.returncode != 0:
        raise DecodeError("ffprobe: " + clean(r.stderr.decode("utf-8", "replace")[-200:] or f"exit {r.returncode}"))
    try:
        d = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    except ValueError:
        raise DecodeError("ffprobe printed no JSON")
    streams = d.get("streams") or []
    if not streams:
        raise DecodeError("no audio stream")
    s = streams[0]
    fmt = d.get("format") or {}

    def num(v, default=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    return {
        "codec": s.get("codec_name", ""),
        "channels": int(num(s.get("channels"), 1) or 1),
        "sample_rate": int(num(s.get("sample_rate"), 0)),
        "bits": int(num(s.get("bits_per_sample"), 0)),
        "duration_probe_s": num(s.get("duration"), 0.0) or num(fmt.get("duration"), 0.0),
    }


def decode(path: str, channels: int, timeout: int) -> np.ndarray:
    ch = 2 if channels >= 2 else 1
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", winpath(path), "-map", "0:a:0", "-vn",
           "-f", "f32le", "-acodec", "pcm_f32le", "-ar", str(SR), "-ac", str(ch), "-"]
    try:
        r = run(cmd, timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DecodeError(f"ffmpeg failed: {exc}")
    if r.returncode != 0:
        raise DecodeError("ffmpeg: " + clean(r.stderr.decode("utf-8", "replace")[-200:] or f"exit {r.returncode}"))
    data = r.stdout
    n = len(data) // (4 * ch)
    if n < 8:
        raise DecodeError("no audio samples" + (": " + clean(r.stderr.decode("utf-8", "replace")[-160:]) if r.stderr else ""))
    x = np.frombuffer(data[: n * 4 * ch], dtype="<f4").reshape(n, ch).astype(np.float32)
    if not np.isfinite(x).all():
        x = np.nan_to_num(x, nan=0.0, posinf=1.0, neginf=-1.0)
    return x


def ebur128(path: str, timeout: int) -> tuple[float | None, float | None]:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-nostdin", "-i", winpath(path), "-map", "0:a:0", "-vn",
           "-af", f"aresample={SR},apad=pad_dur=2,ebur128=peak=true", "-f", "null", "-"]
    try:
        r = run(cmd, timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    text = r.stderr.decode("utf-8", "replace")
    if "Summary:" in text:
        text = text[text.rfind("Summary:"):]
    lufs = tp = None
    m = re.search(r"\bI:\s+(-?[\d.]+|-inf|nan|inf)\s+LUFS", text)
    if m and m.group(1) not in ("-inf", "nan", "inf"):
        lufs = float(m.group(1))
    m = re.search(r"True peak:\s*\n\s*Peak:\s+(-?[\d.]+|-inf|nan|inf)\s+dBFS", text)
    if m and m.group(1) not in ("-inf", "nan", "inf"):
        tp = float(m.group(1))
    return lufs, tp


def frame_env_db(mono: np.ndarray, hop: int) -> np.ndarray:
    n = len(mono)
    nf = max(1, int(np.ceil(n / hop)))
    padded = np.zeros(nf * hop, dtype=np.float64)
    padded[:n] = mono
    rms = np.sqrt((padded.reshape(nf, hop) ** 2).mean(axis=1))
    with np.errstate(divide="ignore"):
        env = 20.0 * np.log10(rms + 1e-12)
    return np.maximum(env, -120.0)


def analyze(x: np.ndarray, settings: dict) -> dict:
    n, ch = x.shape
    duration = n / SR
    mono = x.mean(axis=1) if ch > 1 else x[:, 0].astype(np.float64)
    absmax = np.abs(x).max(axis=1)
    peak_lin = float(absmax.max()) if n else 0.0
    peak_dbfs = to_db(peak_lin)

    # clipping: runs of full-scale samples in any channel
    clip_mask = absmax >= float(settings["clip_threshold"])
    clipped_samples = int(clip_mask.sum())
    d = np.diff(np.concatenate(([0], clip_mask.astype(np.int8), [0])))
    lengths = np.where(d == -1)[0] - np.where(d == 1)[0]
    clip_runs = int((lengths >= int(settings["clip_run_samples"])).sum())

    hop = SR // 200  # 5 ms
    env = frame_env_db(mono, hop)
    peak_frame = int(np.argmax(env))
    env_max = float(env[peak_frame])
    peak_s = (peak_frame + 0.5) * hop / SR

    hop20 = hop * 4
    env20 = frame_env_db(mono, hop20)  # 20 ms frames for the floor
    floor_p5 = float(np.percentile(env20, 5)) if len(env20) >= 4 else float(env20.min())

    silence = float(settings["silence_dbfs"])
    onset_thr = max(env_max - float(settings["onset_db_under_peak"]), floor_p5 + 10.0, silence)
    active = np.where(env >= onset_thr)[0]
    onset_frame = int(active[0]) if len(active) else peak_frame
    onset_s = onset_frame * hop / SR
    end_thr = max(env_max - float(settings["tail_db_under_peak"]), silence - 10.0)
    above = np.where(env >= end_thr)[0]
    end_frame = int(above[-1]) if len(above) else peak_frame
    end_s = (end_frame + 1) * hop / SR
    audible = np.where(env > silence)[0]
    if len(audible):
        pad_start = int(audible[0]) * hop / SR
        pad_end = max(0.0, duration - (int(audible[-1]) + 1) * hop / SR)
    else:
        pad_start, pad_end = duration, 0.0
    attack = max(0.0, peak_s - onset_s)
    tail = max(0.0, end_s - peak_s)
    effective = max(0.0, end_s - onset_s)
    rise = max(0.0, peak_s - pad_start)

    # the noise floor: what the file holds where there is no sound, the lead-in before the onset (at least two
    # 20 ms frames) and the last 50 ms when the sound ended 100 ms or more before the end of the file; unknown
    # (None) when the sound fills the file, so a long fade or a trimmed tone never counts as noise
    lead_frames = int(onset_s * SR) // hop20
    floor_frames = list(env20[:lead_frames]) if lead_frames >= 2 else []
    if end_s <= duration - 0.1 and len(env20) >= 3:
        floor_frames += list(env20[-max(2, int(0.05 * SR) // hop20):])
    noise_floor = float(np.median(floor_frames)) if floor_frames else None
    snr = (peak_dbfs - noise_floor) if noise_floor is not None else None

    # brightness: the spectral centroid of the active region (at most 30 s of it)
    a = onset_frame * hop
    b = min(n, (end_frame + 1) * hop, a + 30 * SR)
    seg = mono[a:b]
    centroid = None
    if len(seg) >= 64:
        win = np.hanning(len(seg))
        spec = np.abs(np.fft.rfft(seg * win))
        freqs = np.fft.rfftfreq(len(seg), 1.0 / SR)
        total = float(spec.sum())
        if total > 0:
            centroid = float((freqs * spec).sum() / total)

    return {
        "duration_s": round_or_none(duration),
        "peak_dbfs": round_or_none(peak_dbfs, 2),
        "noise_floor_db": round_or_none(noise_floor, 1),
        "snr_db": round_or_none(snr, 1),
        "floor_p5_db": round_or_none(floor_p5, 1),
        "onset_s": round_or_none(onset_s),
        "peak_s": round_or_none(peak_s),
        "attack_s": round_or_none(attack),
        "tail_s": round_or_none(tail),
        "end_s": round_or_none(end_s),
        "effective_s": round_or_none(effective),
        "rise_s": round_or_none(rise),
        "pad_start_s": round_or_none(pad_start),
        "pad_end_s": round_or_none(pad_end),
        "centroid_hz": round_or_none(centroid, 0),
        "clipped_samples": clipped_samples,
        "clip_runs": clip_runs,
        "_peak_lin": peak_lin,
    }


def write_cache(path: str, x: np.ndarray, gain_db: float) -> None:
    g = float(10.0 ** (gain_db / 20.0))
    y = np.clip(np.round(x.astype(np.float64) * g * 32767.0), -32768, 32767).astype("<i2")
    path = winpath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(y.reshape(-1).tobytes())
    os.replace(tmp, path)


def measure_file(pack_dir: str, entry: dict, settings: dict | None = None) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update(settings or {})
    rel = entry["path"]
    full = os.path.join(winpath(pack_dir), rel)
    fid = file_id(rel)
    base = os.path.splitext(os.path.basename(rel))[0]
    out = {
        "id": fid, "path": rel, "folder": os.path.dirname(rel), "name": os.path.basename(rel),
        "ext": os.path.splitext(rel)[1].lower().lstrip("."), "size": entry.get("size"), "mtime": entry.get("mtime"),
        "measure_version": MEASURE_VERSION, "decode_error": None,
        "cache": f".cache/{fid}-{slug(base)}.wav",
    }
    timeout = int(s["ffmpeg_timeout_s"])
    try:
        info = ffprobe(full, timeout)
        x = decode(full, info["channels"], timeout)
    except DecodeError as exc:
        out.update({"decode_error": clean(str(exc))[:300], "cache": None})
        return out
    out.update({"codec": info["codec"], "channels": int(x.shape[1]), "source_channels": info["channels"],
                "sample_rate": info["sample_rate"], "bits": info["bits"]})
    a = analyze(x, s)
    peak_lin = a.pop("_peak_lin")
    out.update(a)
    lufs, tp = ebur128(full, timeout)
    out["lufs"] = round_or_none(lufs, 1)
    out["true_peak_dbtp"] = round_or_none(tp, 1)
    gain = float(s["normalize_peak_dbfs"]) - out["peak_dbfs"] if peak_lin > 1e-6 else 0.0
    out["gain_db"] = round(gain, 2)
    try:
        write_cache(os.path.join(winpath(pack_dir), out["cache"]), x, gain)
    except OSError as exc:
        out["cache"] = None
        out["cache_error"] = clean(str(exc))[:200]
    return out


def measure_many(pack_dir: str, entries: list[dict], settings: dict | None = None, progress=None,
                 workers: int = 4) -> list[dict]:
    results: list[dict | None] = [None] * len(entries)
    if not entries:
        return []
    workers = max(1, min(workers, len(entries)))
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(measure_file, pack_dir, e, settings): i for i, e in enumerate(entries)}
        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as exc:  # a bug in the analysis must not lose the whole build: the file is excluded
                results[i] = {"id": file_id(entries[i]["path"]), "path": entries[i]["path"],
                              "folder": os.path.dirname(entries[i]["path"]), "name": os.path.basename(entries[i]["path"]),
                              "ext": os.path.splitext(entries[i]["path"])[1].lower().lstrip("."),
                              "size": entries[i].get("size"), "mtime": entries[i].get("mtime"),
                              "measure_version": MEASURE_VERSION, "cache": None,
                              "decode_error": clean(f"measurement failed: {type(exc).__name__}: {exc}")[:300]}
            done += 1
            if progress:
                progress(done, len(entries), results[i])
    return [r for r in results if r is not None]


def table(rows: list[dict]) -> str:
    cols = [("path", 46), ("dur", 6), ("eff", 6), ("onset", 6), ("peak_s", 6), ("att", 6), ("rise", 6), ("tail", 6),
            ("pk", 6), ("tp", 6), ("lufs", 6), ("floor", 6), ("snr", 5), ("cent", 6), ("clip", 5), ("ch", 2)]
    out = [" ".join(f"{c:<{w}}" if c == "path" else f"{c:>{w}}" for c, w in cols)]
    for r in rows:
        if r.get("decode_error"):
            out.append(f"{r['path'][:46]:<46} DECODE ERROR: {r['decode_error'][:60]}")
            continue

        def f(key, w, digits=2):
            v = r.get(key)
            return f"{v:>{w}.{digits}f}" if isinstance(v, (int, float)) else f"{'-':>{w}}"
        out.append(" ".join([f"{r['path'][:46]:<46}", f("duration_s", 6), f("effective_s", 6), f("onset_s", 6),
                             f("peak_s", 6), f("attack_s", 6), f("rise_s", 6), f("tail_s", 6), f("peak_dbfs", 6, 1),
                             f("true_peak_dbtp", 6, 1), f("lufs", 6, 1), f("noise_floor_db", 6, 1), f("snr_db", 5, 0),
                             f("centroid_hz", 6, 0), f"{r.get('clip_runs', 0):>5}", f"{r.get('channels', 0):>2}"]))
    return "\n".join(out)


def main(argv=None) -> int:
    setup_streams()
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    pack = argv[0]
    entries = list_audio_files(pack)
    rows = measure_many(pack, entries, progress=lambda d, n, r: print(f"measured {d}/{n} {r['path']}", file=sys.stderr))
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print(table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
