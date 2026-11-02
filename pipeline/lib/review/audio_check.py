"""pipeline/lib/review/audio_check.py: the audio checks of S12 (BUILD_SPEC.md S12, M11).

  sfx         S11's own verification passed (11-sfx/cues.json verification.pass): every sound within a frame of its
              event, the 8 dB rule, the mix's loudness                                                       [sfx]
  intelligible the voice in the mixed draft is understood: the draft's audio is transcribed with faster-whisper (the
              same worker and interpreter resolution as S8: REELS_WHISPER_WORKER and REELS_WHISPER_PYTHON first, then
              config tts.whisper_python, the kokoro venv, .venv-tts, python) and compared with the words S8 aligned
              (08-voiceover/words.json) with the voiceover's word error rate; under review.wer_max_pct (5)   [voice]

  run(ctx, out_path) -> the report dict (also written as JSON)
"""
from __future__ import annotations

import os
import subprocess
import sys

from review import common as rc

sys.path.insert(0, rc.LIB)
import voiceover  # noqa: E402  (pipeline/lib/voiceover.py: import_ok, wer_report, strip_markup)


def whisper_interpreter(ctx: rc.Ctx) -> tuple[str, str, list[str]]:
    """(python, worker, tried): the first interpreter that imports faster_whisper, and the worker script."""
    worker_env = os.environ.get("REELS_WHISPER_WORKER")
    if worker_env:
        return (os.environ.get("REELS_WHISPER_PYTHON") or "python"), worker_env, []
    worker = os.path.join(ctx.repo, "pipeline", "lib", "tts", "whisper_worker.py")
    if not os.path.isfile(worker):
        worker = os.path.join(rc.REPO, "pipeline", "lib", "tts", "whisper_worker.py")
    venv = str(ctx.c("paths.venv_python", ".venv-tts/Scripts/python.exe") or "")
    if venv and not os.path.isabs(venv) and not venv[1:2] == ":":
        venv = os.path.join(ctx.repo, venv)
    cands = []
    for p in (os.environ.get("REELS_WHISPER_PYTHON", ""), str(ctx.c("tts.whisper_python", "") or ""), str(ctx.c("paths.kokoro_python", "") or ""), venv, "python"):
        p = (p or "").replace("\\", "/").strip()
        if p and p not in cands:
            cands.append(p)
    tried = []
    for cand in cands:
        if cand != "python" and not voiceover.exe_exists(cand):
            tried.append(f"{cand}: does not exist")
            continue
        ok, why = voiceover.import_ok(cand, "faster_whisper")
        if ok:
            return cand, worker, tried
        tried.append(why)
    return "", worker, tried


def transcribe(ctx: rc.Ctx, wav: str, ref_text: str) -> dict:
    py, worker, tried = whisper_interpreter(ctx)
    if not py:
        raise RuntimeError("no interpreter imports faster_whisper for the intelligibility check (" + "; ".join(tried)[:300] + ")")
    work = os.path.join(ctx.stage_dir, "transcribe")
    os.makedirs(work, exist_ok=True)
    job = {"model": str(ctx.c("tts.whisper_model", "small")), "language": "en", "pad_s": float(ctx.c("tts.whisper_pad_s", 0.5)), "compute_type": "int8", "device": "cpu",
           "items": [{"id": "mix", "wav": rc.mixed(wav), "text": ref_text}], "result": rc.mixed(os.path.join(work, "whisper.result.json")),
           "hotwords": voiceover.hotwords([ref_text])}  # the reel's names, as S8 transcribes them (DECISIONS.md 283)
    job_path = os.path.join(work, "whisper.json")
    rc.write_json(job_path, job)
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env.pop("REELS_SAY_FD", None)
    proc = subprocess.run([voiceover.winpath(py), voiceover.winpath(worker), rc.mixed(job_path)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=int(ctx.c("timeouts.transcribe_seconds", 1800)), env=env, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        raise RuntimeError(f"the transcription failed (whisper_worker.py exit {proc.returncode}): {(proc.stderr or proc.stdout or '')[-300:]}")
    res = rc.load_json(job["result"], None)
    if not res or not res.get("items"):
        raise RuntimeError("the transcription wrote no result")
    item = res["items"][0]
    heard = (item.get("text") or "").strip() or " ".join(w.get("word", "") for w in item.get("words", []))
    return {"python": py, "worker": worker, "model": res.get("model"), "heard": heard, "timing": res.get("timing")}


def run(ctx: rc.Ctx, out_path: str) -> dict:
    issues: list[dict] = []
    ver = (ctx.cues or {}).get("verification") or {}
    sfx = {"pass": bool(ver.get("pass")), "voice_only": bool(ctx.cues.get("voice_only")), "passes": ver.get("passes"),
           "max_error_ms": (ver.get("accuracy") or {}).get("max_error_ms"), "lufs": (ver.get("loudness") or {}).get("lufs"), "true_peak_dbtp": (ver.get("loudness") or {}).get("true_peak_dbtp"),
           "sounds": len(ctx.cues.get("cues") or [])}
    if not ctx.cues:
        issues.append(rc.issue("sfx", "sfx_missing", "11-sfx/cues.json is missing: the sound stage did not run"))
    elif not sfx["pass"]:
        issues.append(rc.issue("sfx", "sfx_verification", f"the sound pass did not verify: sync max error {sfx['max_error_ms']} ms, mix {sfx['lufs']} LUFS, {sfx['true_peak_dbtp']} dBTP"))
    # the voice in the mix
    words = [w.get("word", "") for w in (ctx.words.get("words") or [])]
    ref = voiceover.strip_markup(" ".join(words))
    src = ctx.draft_mixed if os.path.isfile(ctx.draft_mixed) else os.path.join(ctx.run_dir, "11-sfx", "mix.wav")
    work = os.path.join(ctx.stage_dir, "transcribe")
    os.makedirs(work, exist_ok=True)
    wav16 = os.path.join(work, "mix16.wav")
    proc = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav16], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if proc.returncode != 0 or not os.path.isfile(wav16):
        raise RuntimeError("ffmpeg could not extract the mixed draft's audio: " + (proc.stderr or "")[-200:])
    tr = transcribe(ctx, wav16, ref)
    rep = voiceover.wer_report(ref, tr["heard"])
    wer_max = float(ctx.c("review.wer_max_pct", 5))
    intelligible = {"wer_pct": rep["wer_pct"], "max_pct": wer_max, "errors": rep["errors"], "words": rep["n"], "misheard": rep["misheard"][:20], "heard": rep["heard"][:20],
                    "model": tr.get("model"), "python": tr.get("python"), "ok": float(rep["wer_pct"]) < wer_max}
    if not intelligible["ok"]:
        issues.append(rc.issue("voice", "intelligibility", f"the voice is hard to follow in the mix: word error rate {rep['wer_pct']} percent (misheard: {', '.join(rep['misheard'][:6])})"))
    report = {"written_by": "12-review", "pass": not issues, "issues": issues, "sfx": sfx, "intelligible": intelligible, "source": os.path.relpath(src, ctx.run_dir).replace("\\", "/")}
    rc.write_json(out_path, report)
    return report
