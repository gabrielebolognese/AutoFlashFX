#!/usr/bin/env python
"""A fake transcriber for the tests (pipeline/tests/test-m7.sh): the same job contract as
pipeline/lib/tts/whisper_worker.py, run with the project's python (REELS_WHISPER_PYTHON=python
REELS_WHISPER_WORKER=pipeline/tests/fakes/whisper_worker.py). It "hears" the text the job carries for each file,
with evenly spaced word timestamps over the file's duration, unless a garble rule applies.

Environment:
  FAKE_WHISPER_MODE=ok|crash          crash: exit 1 with a traceback
  FAKE_WHISPER_GARBLE=<rule>[;<rule>] rule = <id>:<target>:<attempts>; target is a word (matched without case
                                      or punctuation), "#k" (the k-th word, 1-based) or "n=<count>" (every
                                      second word, count of them); attempts is how many transcriptions of that
                                      id are garbled (an integer, or * for every one). A garbled word is heard
                                      as "xx".
  FAKE_WHISPER_STATE=<dir>            the per-id transcription counters (default: next to the job file)
"""
import json
import os
import re
import sys
import traceback
import wave


def norm(tok: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", tok.lower())


def counter(state_dir: str, key: str) -> int:
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".n")
    n = 0
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            n = int((f.read().strip() or "0"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(n + 1))
    return n + 1


def rules():
    out = []
    for rule in (os.environ.get("FAKE_WHISPER_GARBLE") or "").split(";"):
        parts = rule.strip().split(":")
        if len(parts) == 3 and parts[0]:
            out.append((parts[0], parts[1], parts[2]))
    return out


def main() -> int:
    with open(sys.argv[1], encoding="utf-8-sig") as f:
        job = json.load(f)
    if os.environ.get("FAKE_WHISPER_MODE", "ok") == "crash":
        try:
            raise RuntimeError("fake whisper crash: cannot load the model")
        except RuntimeError:
            traceback.print_exc()
        return 1
    state_dir = os.environ.get("FAKE_WHISPER_STATE") or os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "fake-whisper-state")
    print("whisper ready (fake)", flush=True)
    items = []
    for i, item in enumerate(job["items"], 1):
        text = re.sub(r"\[([^\]]+)\]\(/[^)]*/\)", r"\1", str(item.get("text", "")))
        tokens = [t for t in text.split() if re.search(r"[A-Za-z0-9]", t)]
        n_try = counter(state_dir, item["id"])
        for rid, target, attempts in rules():
            if rid != item["id"]:
                continue
            if attempts != "*" and n_try > int(attempts):
                continue
            if target.startswith("#"):
                k = int(target[1:]) - 1
                if 0 <= k < len(tokens):
                    tokens[k] = "xx"
            elif target.startswith("n="):
                count = int(target[2:])
                done = 0
                for k in range(1, len(tokens), 2):
                    if done >= count:
                        break
                    tokens[k] = "xx"
                    done += 1
            else:
                for k, tok in enumerate(tokens):
                    if norm(tok) == norm(target):
                        tokens[k] = "xx"
        try:
            with wave.open(item["wav"], "rb") as w:
                duration = w.getnframes() / float(w.getframerate())
        except (OSError, wave.Error):
            duration = 0.4 * max(1, len(tokens))
        step = duration / max(1, len(tokens))
        words = [{"word": tok, "start": round(k * step, 3), "end": round((k + 1) * step - min(0.02, step / 4), 3)} for k, tok in enumerate(tokens)]
        items.append({"id": item["id"], "duration": round(duration, 3), "text": " ".join(tokens), "words": words, "took_s": 0.01})
        print(f"FILE {i}/{len(job['items'])} {item['id']} 0.0", flush=True)
    with open(job["result"], "w", encoding="utf-8", newline="\n") as f:
        json.dump({"model": "fake", "items": items, "timing": {"import_s": 0.0, "load_s": 0.0, "transcribe_s": 0.0, "total_s": 0.0}}, f, ensure_ascii=False, indent=1)
    print(f"done (fake): {len(items)} files", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
