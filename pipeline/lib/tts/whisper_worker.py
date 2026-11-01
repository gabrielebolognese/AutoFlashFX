#!/usr/bin/env python
"""whisper_worker.py: transcribe the audio files of one job with faster-whisper on CPU (compute_type int8, no
CUDA libraries), word timestamps included. Runs under the interpreter that has faster-whisper (config
tts.whisper_python, the voice interpreter, .venv-tts or python, whichever imports it first).

  <whisper python> pipeline/lib/tts/whisper_worker.py job.json

job.json: {"model": "small", "language": "en", "pad_s": 0.5, "compute_type": "int8", "device": "cpu",
           "result": ".../whisper-2.result.json",
           "items": [{"id": "b1", "wav": ".../b1.a1.wav", "text": "<what the voice was asked to say, for the log>"}, ...]}

The model is loaded once: the configured name from the local cache first, then "small" from the cache, then the
configured name with a download. Every file is padded with pad_s of silence at both ends before transcription (a
line that starts at its first sample is heard better with a little room) and the timestamps are shifted back.
Progress on stdout: "FILE i/n id took_s". The result JSON: model, timing {import_s, load_s, transcribe_s} and
items [{id, duration, text, words: [{word, start, end}]}]. Exit 0, or 1 when the model cannot be loaded or a file
cannot be read (the stage treats that as a code error).
"""
import json
import sys
import time


def load_model(name: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel
    attempts = [(name, True)]
    if name != "small":
        attempts.append(("small", True))
    attempts.append((name, False))
    last = None
    for model_name, local_only in attempts:
        try:
            print(f"loading faster-whisper {model_name} on {device} ({compute_type}{', local cache only' if local_only else ', download allowed'}) ...", flush=True)
            return WhisperModel(model_name, device=device, compute_type=compute_type, local_files_only=local_only), model_name
        except Exception as exc:  # not in the cache, no network
            last = exc
            print(f"  not available: {str(exc)[:120]}", flush=True)
    raise RuntimeError(f"no whisper model could be loaded: {last}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: whisper_worker.py job.json", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8-sig") as f:
        job = json.load(f)
    t0 = time.time()
    import numpy as np
    from faster_whisper.audio import decode_audio
    t1 = time.time()
    model, used = load_model(str(job.get("model", "small")), str(job.get("device", "cpu")), str(job.get("compute_type", "int8")))
    t2 = time.time()
    print(f"whisper ready ({used}): import {t1 - t0:.1f} s, load {t2 - t1:.1f} s", flush=True)
    pad_s = float(job.get("pad_s", 0.5))
    language = job.get("language") or None
    items = job["items"]
    n = len(items)
    results = []
    for i, item in enumerate(items, 1):
        ta = time.time()
        audio = decode_audio(item["wav"], sampling_rate=16000)
        audio = np.asarray(audio, dtype="float32")
        duration = len(audio) / 16000.0
        pad = np.zeros(int(16000 * pad_s), dtype="float32")
        padded = np.concatenate([pad, audio, pad])
        kwargs = {"word_timestamps": True, "beam_size": 5, "condition_on_previous_text": False, "vad_filter": False}
        if language:
            kwargs["language"] = language
        segments, _info = model.transcribe(padded, **kwargs)
        words = []
        texts = []
        for seg in segments:
            texts.append(seg.text.strip())
            for w in seg.words or []:
                start = max(0.0, float(w.start) - pad_s)
                end = max(start, min(duration, float(w.end) - pad_s))
                if end <= 0.0 and start <= 0.0 and float(w.end) <= pad_s * 0.5:
                    continue  # a hallucinated token inside the leading padding
                words.append({"word": w.word.strip(), "start": round(start, 3), "end": round(end, 3)})
        took = time.time() - ta
        results.append({"id": item["id"], "duration": round(duration, 3), "text": " ".join(t for t in texts if t), "words": words,
                        "took_s": round(took, 2)})
        print(f"FILE {i}/{n} {item['id']} {took:.1f}", flush=True)
    t3 = time.time()
    result = {"model": used, "items": results,
              "timing": {"import_s": round(t1 - t0, 2), "load_s": round(t2 - t1, 2), "transcribe_s": round(t3 - t2, 2), "total_s": round(t3 - t0, 2)}}
    with open(job["result"], "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"done: {n} files in {t3 - t2:.1f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
