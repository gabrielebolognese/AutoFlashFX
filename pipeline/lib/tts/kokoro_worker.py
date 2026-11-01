#!/usr/bin/env python
"""kokoro_worker.py: generate the voice lines of one job with Kokoro, through tools/voice.py (its Engine class,
sentences() and tighten()), under the interpreter named in library/voice/engine.txt (Python 3.11, CPU only).

  <engine python> pipeline/lib/tts/kokoro_worker.py job.json

job.json: {"tools_dir": ".../tools", "sr": 24000, "out_dir": ".../lines", "result": ".../tts-1.result.json",
           "settings": {"voice": "af_bella", "lang": "a", "speed": 1.0, "silence_threshold_db": -40, "min_pause_s": 0.3,
                        "keep_pause_s": 0.1},
           "lines": [{"id": "b1", "name": "b1.a1", "text": "Why your Claude Code cards all look identical."}, ...]}

Per line: the text is split into sentences (voice.py sentences), each sentence is generated, the sentences are
joined with min_pause_s + 0.05 s of silence (so every sentence boundary is a pause the tightener catches), then
the line is tightened (pauses of min_pause_s or longer below silence_threshold_db become keep_pause_s, the leading
and trailing silence is removed: the stage inserts the exact gaps, the breath, the lead and the tail when it joins
the lines) and written as 16-bit PCM mono at 24 kHz to out_dir/<name>.wav.

Progress on stdout: "LINE i/n id raw_s" after each generated line, "TIGHTEN i/n id tight_s shortened" after each
tightened line. The result JSON lists every line (id, wav, raw_s, duration_s, shortened, removed_s, longest_pause_s,
sentences) and the timing (import_s, load_s, synth_s, tighten_s). Exit 0 when every line has audio, 1 otherwise
(the stage treats that as a code error). Kokoro is deterministic: no seed, no retry changes the result.
"""
import json
import os
import sys
import time
import types


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: kokoro_worker.py job.json", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8-sig") as f:
        job = json.load(f)
    tools_dir = job["tools_dir"]
    sys.path.insert(0, tools_dir)
    t0 = time.time()
    import numpy as np
    import soundfile as sf
    import voice  # tools/voice.py
    t1 = time.time()
    s = job["settings"]
    sr = int(job.get("sr", 24000))
    ns = types.SimpleNamespace(kokoro_lang=str(s.get("lang", "a")), kokoro_voice=str(s.get("voice", "af_bella")),
                               speed=float(s.get("speed", 1.0)), seed=None)
    print(f"loading kokoro ({ns.kokoro_voice}, lang {ns.kokoro_lang}, speed {ns.speed:g}) on CPU ...", flush=True)
    eng = voice.Engine("kokoro", "", ns)
    sr = int(eng.sr or sr)
    t2 = time.time()
    print(f"kokoro ready: import {t1 - t0:.1f} s, load {t2 - t1:.1f} s", flush=True)
    min_pause = float(s.get("min_pause_s", 0.3))
    keep = float(s.get("keep_pause_s", 0.1))
    threshold = float(s.get("silence_threshold_db", -40.0))
    join_s = min_pause + 0.05
    out_dir = job["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    lines = job["lines"]
    n = len(lines)
    raw_audio = []
    synth_s = 0.0
    for i, line in enumerate(lines, 1):
        text = str(line.get("text", "")).strip()
        sents = voice.sentences(text) if text else []
        chunks = []
        ta = time.time()
        for sent in sents:
            audio = eng.say(sent)
            audio = np.asarray(audio, dtype="float32")
            if audio.size:
                chunks.append(audio)
                chunks.append(np.zeros(int(sr * join_s), dtype="float32"))
        audio = np.concatenate(chunks[:-1]) if chunks else np.zeros(0, dtype="float32")
        synth_s += time.time() - ta
        raw_audio.append((line, audio, len(sents)))
        print(f"LINE {i}/{n} {line['id']} {len(audio) / sr:.2f}", flush=True)
    results = []
    t3 = time.time()
    ok = True
    for i, (line, audio, n_sent) in enumerate(raw_audio, 1):
        raw_s = len(audio) / sr
        if audio.size:
            tight, st = voice.tighten(audio, sr, threshold_db=threshold, min_pause=min_pause, keep=keep, lead=0.0, tail=0.0)
        else:
            tight, st = audio, {"shortened": 0, "longest": 0.0, "removed": 0.0}
        name = line.get("name") or line["id"]
        path = os.path.join(out_dir, f"{name}.wav").replace("\\", "/")
        sf.write(path, tight, sr, subtype="PCM_16")
        dur = len(tight) / sr
        if dur <= 0.0:
            ok = False
            print(f"no audio for line {line['id']} ({text!r})", file=sys.stderr, flush=True)
        results.append({"id": line["id"], "wav": path, "raw_s": round(raw_s, 3), "duration_s": round(dur, 3), "shortened": int(st["shortened"]),
                        "removed_s": round(float(st["removed"]), 3), "longest_pause_s": round(float(st["longest"]), 3), "sentences": n_sent})
        print(f"TIGHTEN {i}/{n} {line['id']} {dur:.2f} {int(st['shortened'])}", flush=True)
    t4 = time.time()
    try:
        import kokoro
        kv = getattr(kokoro, "__version__", "?")
    except Exception:
        kv = "?"
    result = {"sr": sr, "voice": ns.kokoro_voice, "lang": ns.kokoro_lang, "speed": ns.speed, "kokoro_version": kv, "lines": results,
              "timing": {"import_s": round(t1 - t0, 2), "load_s": round(t2 - t1, 2), "synth_s": round(synth_s, 2), "tighten_s": round(t4 - t3, 2),
                         "total_s": round(t4 - t0, 2)}}
    with open(job["result"], "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    total_audio = sum(r["raw_s"] for r in results)
    print(f"done: {n} lines, {total_audio:.1f} s of raw voice in {synth_s:.1f} s ({synth_s / max(total_audio, 0.01):.2f}x real time), "
          f"tightened in {t4 - t3:.1f} s", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
