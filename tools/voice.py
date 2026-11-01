#!/usr/bin/env python3
"""
voice.py - text in, audio out, with automatic silence tightening.

  python tools/voice.py say "Your text here" --out test.wav                 af_bella (Kokoro), tightened
  python tools/voice.py say --file script.txt --out test.wav                 a blank line after the first
                                                                             paragraph leaves a breath there
  python tools/voice.py say --file script.txt --kokoro-voice am_puck --out puck.wav
  python tools/voice.py say --file script.txt --no-tighten --out raw.wav     keep the natural pauses
  python tools/voice.py tighten in.wav out.wav                               tighten any recording (yours too)
  python tools/voice.py words test.wav            word timestamps (faster-whisper), writes test.words.json
  python tools/voice.py blindtest a.wav b.wav c.wav   shuffles files into blindtest/A.wav, B.wav ... + key.txt

Silence tightening (like Audacity's Truncate Silence): every pause of --min-pause seconds or longer, below
--threshold-db, is shortened to --keep seconds. Shorter pauses (commas, the tiny stops inside words) stay.
After the first paragraph the gap is --breath seconds instead, so the reel has time to breathe after the hook.

Engines:
  kokoro      Kokoro: stock voices (af_bella, am_puck, ...), very fast on CPU, deterministic
  turbo       Chatterbox-Turbo: clones from a reference wav
  chatterbox  Chatterbox original: clones, tunable (exaggeration, cfg)
  qwen        Qwen3-TTS 1.7B Base: clones, GPU only in practice
"""

import argparse
import json
import random
import re
import shutil
import sys
from pathlib import Path

DEFAULT_REF = Path("library/voice/reference.wav")


def sentences(text, max_len=250):
    """Split into sentences; split very long ones at commas so each chunk stays natural."""
    text = re.sub(r"\s+", " ", text.replace(chr(0x2014), ", ")).strip()   # em dash -> comma pause
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    out = []
    for p in parts:
        while len(p) > max_len and "," in p[:max_len]:
            cut = p[:max_len].rfind(",") + 1
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            out.append(p)
    return out


def paragraphs(text):
    """Blank lines separate paragraphs; each paragraph becomes a list of sentences."""
    blocks = [b for b in re.split(r"\n\s*\n", text.replace("\r\n", "\n")) if b.strip()]
    return [sentences(b) for b in blocks]


def tighten(wav, sr, threshold_db=-40.0, min_pause=0.3, keep=0.1, lead=0.05, tail=0.05):
    """Shorten every pause of min_pause seconds or longer to keep seconds (half kept on each side, so word
    endings and onsets stay intact). Leading and trailing silence become lead and tail seconds.
    Works on mono (n,) or multichannel (n, ch) arrays. Returns (audio, stats)."""
    import numpy as np
    wav = np.asarray(wav, dtype="float32")
    mono = wav if wav.ndim == 1 else wav.mean(axis=1)
    hop = max(1, int(sr * 0.01))                       # 10 ms frames
    n = len(mono) // hop
    stats = {"shortened": 0, "longest": 0.0, "removed": 0.0}
    if n == 0:
        return wav, stats
    rms = np.sqrt((mono[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-12
    silent = 20 * np.log10(rms) < threshold_db
    if silent.all():
        return wav, stats
    total = len(mono)
    keep_n, lead_n, tail_n, min_n = int(keep * sr), int(lead * sr), int(tail * sr), int(min_pause * sr)
    segments, pos, i = [], 0, 0                         # (start, end) sample ranges to keep
    while i < n:
        if not silent[i]:
            i += 1
            continue
        j = i
        while j < n and silent[j]:
            j += 1
        start, end = i * hop, (j * hop if j < n else total)
        length = end - start
        if start == 0:                                  # leading silence
            pos = max(0, end - lead_n)
        elif end == total:                              # trailing silence
            segments.append((pos, min(end, start + tail_n)))
            pos = total
        elif length >= min_n:                           # a long pause: shorten it
            half = keep_n // 2
            segments.append((pos, start + half))
            pos = end - (keep_n - half)
            stats["shortened"] += 1
            stats["longest"] = max(stats["longest"], length / sr)
        i = j
    if pos < total:
        segments.append((pos, total))
    fade = min(int(0.005 * sr), 64)                     # 5 ms fades at every cut, against clicks
    pieces = []
    for k, (a, b) in enumerate(segments):
        seg = wav[a:b].copy()
        if fade and len(seg) > 2 * fade:
            ramp = np.linspace(0.0, 1.0, fade, dtype="float32")
            if wav.ndim > 1:
                ramp = ramp[:, None]
            if k > 0:
                seg[:fade] *= ramp
            if k < len(segments) - 1:
                seg[-fade:] *= ramp[::-1]
        pieces.append(seg)
    out = np.concatenate(pieces) if pieces else wav[:0]
    stats["removed"] = (len(wav) - len(out)) / sr
    return out, stats


def pick_device():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def cpu_safe_loading():
    """Checkpoints saved on a GPU can fail to load on a CPU-only PC; force torch.load onto the CPU."""
    import torch
    if getattr(torch.load, "_cpu_safe", False):
        return
    original = torch.load

    def load(*a, **k):
        k.setdefault("map_location", "cpu")
        return original(*a, **k)
    load._cpu_safe = True
    torch.load = load


def to_mono_np(wav):
    import numpy as np
    try:
        import torch
        if isinstance(wav, torch.Tensor):
            wav = wav.detach().float().cpu().numpy()
    except ImportError:
        pass
    wav = np.asarray(wav, dtype="float32")
    if wav.ndim > 1:
        wav = wav.reshape(-1) if 1 in wav.shape else wav.mean(axis=0)
    return wav


def transcribe_words(path, model_size="small"):
    """Word timestamps with faster-whisper on CPU (no CUDA libraries needed)."""
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(path), word_timestamps=True)
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)})
    return words


class Engine:
    def __init__(self, name, ref, args):
        self.name, self.ref, self.args = name, ref, args
        self.sr = 24000
        if name in ("chatterbox", "turbo", "qwen") and not Path(ref).exists():
            sys.exit(f"reference voice not found: {ref} (record it first, or pass --ref)")
        if name in ("chatterbox", "turbo") and pick_device() == "cpu":
            cpu_safe_loading()
        if name == "chatterbox":
            from chatterbox.tts import ChatterboxTTS
            self.model = ChatterboxTTS.from_pretrained(device=pick_device())
            self.sr = self.model.sr
        elif name == "turbo":
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            self.model = ChatterboxTurboTTS.from_pretrained(device=pick_device())
            self.sr = self.model.sr
        elif name == "kokoro":
            from kokoro import KPipeline
            self.model = KPipeline(lang_code=args.kokoro_lang)
            self.sr = 24000
        elif name == "qwen":
            import torch
            from qwen_tts import Qwen3TTSModel
            dev = pick_device()
            self.model = Qwen3TTSModel.from_pretrained(
                args.qwen_model,
                device_map="cuda:0" if dev == "cuda" else "cpu",
                dtype=torch.bfloat16 if dev == "cuda" else torch.float32,
                attn_implementation="sdpa",   # flash-attn has no easy Windows install; sdpa works everywhere
            )
            self.ref_text = self._reference_text()
        else:
            sys.exit(f"unknown engine: {name}")

    def _reference_text(self):
        if self.args.ref_text:
            return self.args.ref_text
        txt = Path(self.ref).with_suffix(".txt")
        if txt.exists():
            return txt.read_text(encoding="utf-8").strip()
        print("transcribing the reference once for qwen (saved next to it as .txt) ...", flush=True)
        text = " ".join(w["word"] for w in transcribe_words(self.ref))
        txt.write_text(text, encoding="utf-8")
        return text

    def say(self, text):
        if self.args.seed is not None and self.name != "kokoro":
            import torch
            torch.manual_seed(self.args.seed)
        if self.name == "chatterbox":
            return to_mono_np(self.model.generate(text, audio_prompt_path=str(self.ref),
                                                  exaggeration=self.args.exaggeration,
                                                  cfg_weight=self.args.cfg))
        if self.name == "turbo":
            return to_mono_np(self.model.generate(text, audio_prompt_path=str(self.ref)))
        if self.name == "kokoro":
            import numpy as np
            chunks = [to_mono_np(audio) for _, _, audio in
                      self.model(text, voice=self.args.kokoro_voice, speed=self.args.speed)]
            return np.concatenate(chunks) if chunks else np.zeros(0, dtype="float32")
        if self.name == "qwen":
            wavs, sr = self.model.generate_voice_clone(text=text, language=self.args.qwen_language,
                                                       ref_audio=str(self.ref), ref_text=self.ref_text)
            self.sr = sr
            return to_mono_np(wavs[0])


def cmd_say(args):
    import time
    import numpy as np
    import soundfile as sf
    text = Path(args.file).read_text(encoding="utf-8") if args.file else " ".join(args.text)
    if not text.strip():
        sys.exit("no text: pass it in quotes, or use --file")
    paras = paragraphs(text)
    count = sum(len(p) for p in paras)
    print(f"loading {args.engine} (first run downloads the model) ...", flush=True)
    eng = Engine(args.engine, args.ref, args)
    sr = eng.sr
    t0 = time.time()
    tight = not args.no_tighten
    # when tightening, sentences are joined with at least --min-pause of silence, so every sentence boundary
    # is caught by the tightener and ends up exactly --keep long
    join_s = max(args.gap_ms / 1000, args.min_pause + 0.05) if tight else args.gap_ms / 1000
    totals = {"shortened": 0, "longest": 0.0, "removed": 0.0}
    para_audio, done = [], 0
    for para in paras:
        chunks = []
        for sent in para:
            done += 1
            print(f"  [{done}/{count}] {sent}", flush=True)
            chunks.append(eng.say(sent))
            chunks.append(np.zeros(int(sr * join_s), dtype="float32"))
        audio = np.concatenate(chunks[:-1]) if chunks else np.zeros(0, dtype="float32")
        if tight:
            audio, st = tighten(audio, sr, args.threshold_db, args.min_pause, args.keep,
                                lead=args.keep / 2, tail=args.keep / 2)
            totals["shortened"] += st["shortened"]
            totals["removed"] += st["removed"]
            totals["longest"] = max(totals["longest"], st["longest"])
        para_audio.append(audio)
    pieces = []
    for k, audio in enumerate(para_audio):
        pieces.append(audio)
        if k < len(para_audio) - 1:
            if k == 0:
                gap = max(0.0, args.breath - (args.keep if tight else 0))     # the breath after the hook
            else:
                gap = 0.0 if tight else args.gap_ms / 1000
            pieces.append(np.zeros(int(sr * gap), dtype="float32"))
    pieces.append(np.zeros(int(sr * 0.2), dtype="float32"))                   # short tail
    wav = np.concatenate(pieces)
    peak = float(np.abs(wav).max()) if wav.size else 0.0
    if peak > 0:
        wav = wav * (0.89 / peak)   # peak at about -1 dB; the pipeline does proper loudness later
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), wav, sr)
    took = time.time() - t0
    secs = len(wav) / sr if sr else 0
    print(f"wrote {out} ({secs:.1f}s of audio, {sr} Hz)")
    if tight:
        print(f"tightened: {totals['shortened']} pauses shortened to {args.keep}s "
              f"(longest was {totals['longest']:.2f}s), {totals['removed']:.1f}s removed"
              + (f", {args.breath}s breath after the first paragraph" if len(paras) > 1 else ""))
    if secs:
        print(f"generation took {took:.0f}s: {took / secs:.1f}x the audio length "
              f"(a 35s voiceover would take about {35 * took / secs:.0f}s on this PC)")
    if args.words:
        cmd_words(argparse.Namespace(audio=str(out), model=args.whisper_model))


def cmd_tighten(args):
    import soundfile as sf
    wav, sr = sf.read(args.input, dtype="float32", always_2d=False)
    out, st = tighten(wav, sr, args.threshold_db, args.min_pause, args.keep, lead=args.lead, tail=args.tail)
    sf.write(args.output, out, sr)
    print(f"wrote {args.output}: {len(wav) / sr:.1f}s -> {len(out) / sr:.1f}s, {st['shortened']} pauses shortened "
          f"to {args.keep}s (longest was {st['longest']:.2f}s)")


def cmd_words(args):
    words = transcribe_words(args.audio, args.model)
    out = Path(args.audio).with_suffix(".words.json")
    out.write_text(json.dumps(words, indent=1, ensure_ascii=False), encoding="utf-8")
    for w in words:
        print(f"{w['start']:7.2f} -> {w['end']:6.2f}  {w['word']}")
    print(f"wrote {out} ({len(words)} words)")


def cmd_blindtest(args):
    files = [Path(f) for f in args.files]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        sys.exit("not found: " + ", ".join(missing))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    order = files[:]
    random.shuffle(order)
    key = []
    for letter, f in zip("ABCDEFGH", order):
        shutil.copy(f, out / f"{letter}{f.suffix}")
        key.append(f"{letter} = {f.name}")
    (out / "key.txt").write_text("\n".join(key) + "\n", encoding="utf-8")
    print(f"copied {len(order)} files to {out}/ as " + ", ".join(f"{l}{order[0].suffix}" for l in "ABCDEFGH"[:len(order)]))
    print(f"listen on your phone, pick a winner, then open {out}/key.txt")


def add_tighten_args(p):
    p.add_argument("--threshold-db", type=float, default=-40.0, help="below this level counts as silence")
    p.add_argument("--min-pause", type=float, default=0.3, help="pauses at least this long get shortened")
    p.add_argument("--keep", type=float, default=0.1, help="seconds each long pause is shortened to")


def main():
    ap = argparse.ArgumentParser(description="Text in, audio out, with automatic silence tightening.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("say", help="generate speech")
    s.add_argument("text", nargs="*", help="the text, in quotes")
    s.add_argument("--file", help="read the text from a file instead")
    s.add_argument("--out", default="test.wav")
    s.add_argument("--engine", default="kokoro", choices=["kokoro", "turbo", "chatterbox", "qwen"])
    s.add_argument("--ref", default=str(DEFAULT_REF), help="reference voice wav")
    s.add_argument("--ref-text", help="qwen only: transcript of the reference (else made automatically)")
    s.add_argument("--exaggeration", type=float, default=0.5, help="chatterbox: energy/emotion, 0.25 to 1.0")
    s.add_argument("--cfg", type=float, default=0.5, help="chatterbox: pacing/adherence, try 0.3 for faster speech")
    s.add_argument("--seed", type=int, default=None, help="same seed = same result")
    s.add_argument("--gap-ms", type=int, default=150, help="silence between sentences when not tightening")
    s.add_argument("--no-tighten", action="store_true", help="keep the natural pauses")
    s.add_argument("--breath", type=float, default=1.0, help="seconds of silence after the first paragraph")
    s.add_argument("--speed", type=float, default=1.0, help="kokoro: speaking speed, e.g. 1.1")
    s.add_argument("--kokoro-voice", default="af_bella")
    s.add_argument("--kokoro-lang", default="a", help="a = American English, b = British, i = Italian")
    s.add_argument("--qwen-model", default="Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    s.add_argument("--qwen-language", default="English")
    s.add_argument("--words", action="store_true", help="also write word timestamps")
    s.add_argument("--whisper-model", default="small")
    add_tighten_args(s)
    s.set_defaults(func=cmd_say)

    t = sub.add_parser("tighten", help="shorten long pauses in any wav")
    t.add_argument("input")
    t.add_argument("output")
    add_tighten_args(t)
    t.add_argument("--lead", type=float, default=0.05, help="seconds of silence kept at the start")
    t.add_argument("--tail", type=float, default=0.2, help="seconds of silence kept at the end")
    t.set_defaults(func=cmd_tighten)

    w = sub.add_parser("words", help="word timestamps for an audio file")
    w.add_argument("audio")
    w.add_argument("--model", default="small")
    w.set_defaults(func=cmd_words)

    b = sub.add_parser("blindtest", help="shuffle finished files for a blind listening test")
    b.add_argument("files", nargs="+")
    b.add_argument("--out-dir", default="blindtest")
    b.set_defaults(func=cmd_blindtest)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
