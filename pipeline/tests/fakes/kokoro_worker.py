#!/usr/bin/env python
"""A fake voice engine worker for the tests (pipeline/tests/test-m7.sh): the same job contract as
pipeline/lib/tts/kokoro_worker.py, run with the project's python (REELS_TTS_PYTHON=python
REELS_TTS_WORKER=pipeline/tests/fakes/kokoro_worker.py). No Kokoro: every word becomes a short tone burst, so the
silence tightener (the real tools/voice.py tighten) and the stage's timeline have something real to work on.

Environment:
  FAKE_TTS_MODE=ok|crash|hang|noaudio   crash: exit 1 with a traceback on stderr; hang: sleep until killed;
                                        noaudio: a zero-length line (the stage's "produced no audio" error)
  FAKE_TTS_SLOW=b9=1.5,b3=1.2           per line id: stretch that line's speech by the factor (the overrun check)
  FAKE_TTS_LOG=<path>                   append one line per call: the ids generated and their texts
A line lasts about its estimate_s (the job carries it): words of estimate_s / n seconds each, 72 percent tone and
28 percent silence, a 0.45 s pause after every sentence end (which the tightener cuts to keep_pause_s), 0.25 s of
leading and 0.5 s of trailing silence (which it removes).
"""
import json
import math
import os
import re
import sys
import time
import traceback
import wave
import zlib


def main() -> int:
    with open(sys.argv[1], encoding="utf-8-sig") as f:
        job = json.load(f)
    mode = os.environ.get("FAKE_TTS_MODE", "ok")
    if mode == "crash":
        print("loading kokoro (fake) ...", flush=True)
        try:
            raise RuntimeError("fake kokoro crash: the model file is corrupt")
        except RuntimeError:
            traceback.print_exc()
        return 1
    if mode == "hang":
        print("loading kokoro (fake) ... hanging on purpose", flush=True)
        time.sleep(3600)
        return 1
    sys.path.insert(0, job["tools_dir"])
    import numpy as np
    import voice
    slow = {}
    for item in (os.environ.get("FAKE_TTS_SLOW") or "").split(","):
        k, _, v = item.partition("=")
        if k.strip() and v.strip():
            slow[k.strip()] = float(v)
    s = job["settings"]
    sr = int(job.get("sr", 24000))
    min_pause, keep, threshold = float(s["min_pause_s"]), float(s["keep_pause_s"]), float(s["silence_threshold_db"])
    out_dir = job["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    print(f"kokoro ready (fake): voice {s.get('voice')} lang {s.get('lang')} speed {s.get('speed')}", flush=True)
    lines = job["lines"]
    n = len(lines)
    raw = []
    for i, line in enumerate(lines, 1):
        text = re.sub(r"\[([^\]]+)\]\(/[^)]*/\)", r"\1", str(line.get("text", "")))
        tokens = [t for t in text.split() if re.search(r"[A-Za-z0-9]", t)]
        if mode == "noaudio":
            tokens = []
        est = float(line.get("estimate_s", max(1, len(tokens)) * 0.35))
        word_s = est / max(1, len(tokens)) * slow.get(line["id"], 1.0)
        pieces = [np.zeros(int(sr * 0.25), dtype="float32")]
        for k, tok in enumerate(tokens):
            freq = 160 + (zlib.crc32(tok.lower().encode()) % 120)
            burst_n = int(sr * word_s * 0.72)
            t = np.arange(burst_n) / sr
            burst = (0.3 * np.sin(2 * math.pi * freq * t)).astype("float32")
            fade = min(int(sr * 0.005), max(1, burst_n // 4))
            ramp = np.linspace(0, 1, fade, dtype="float32")
            burst[:fade] *= ramp
            burst[-fade:] *= ramp[::-1]
            pieces.append(burst)
            pieces.append(np.zeros(int(sr * word_s * 0.28), dtype="float32"))
            if k < len(tokens) - 1 and re.search(r"[.!?]$", tok):
                pieces.append(np.zeros(int(sr * 0.45), dtype="float32"))
        pieces.append(np.zeros(int(sr * 0.5), dtype="float32"))
        audio = np.concatenate(pieces) if tokens else np.zeros(0, dtype="float32")
        raw.append((line, audio, 1))
        print(f"LINE {i}/{n} {line['id']} {len(audio) / sr:.2f}", flush=True)
    results = []
    ok = True
    for i, (line, audio, _) in enumerate(raw, 1):
        if audio.size:
            tight, st = voice.tighten(audio, sr, threshold_db=threshold, min_pause=min_pause, keep=keep, lead=0.0, tail=0.0)
        else:
            tight, st = audio, {"shortened": 0, "longest": 0.0, "removed": 0.0}
        path = os.path.join(out_dir, f"{line.get('name') or line['id']}.wav").replace("\\", "/")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(tight, -1, 1) * 32767).astype("<i2").tobytes())
        dur = len(tight) / sr
        if dur <= 0:
            ok = False
            print(f"no audio for line {line['id']}", file=sys.stderr, flush=True)
        results.append({"id": line["id"], "wav": path, "raw_s": round(len(audio) / sr, 3), "duration_s": round(dur, 3), "shortened": int(st["shortened"]),
                        "removed_s": round(float(st["removed"]), 3), "longest_pause_s": round(float(st["longest"]), 3), "sentences": 1})
        print(f"TIGHTEN {i}/{n} {line['id']} {dur:.2f} {int(st['shortened'])}", flush=True)
    result = {"sr": sr, "voice": s.get("voice"), "lang": s.get("lang"), "speed": s.get("speed"), "kokoro_version": "fake", "lines": results,
              "timing": {"import_s": 0.1, "load_s": 0.1, "synth_s": 0.2, "tighten_s": 0.05, "total_s": 0.45}}
    with open(job["result"], "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    log_path = os.environ.get("FAKE_TTS_LOG")
    if log_path:
        with open(log_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ids": [ln["id"] for ln in lines], "texts": {ln["id"]: ln.get("text", "") for ln in lines}}, ensure_ascii=False) + "\n")
    print(f"done (fake): {n} lines", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
