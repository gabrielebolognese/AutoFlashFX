# 08-voiceover: Voiceover (S8)

Built in M7 (the folder, the first schema and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S8 and 2.5;
decisions in DECISIONS.md (M7). Scripts: run.sh (the stage), pipeline/lib/voiceover.py (the work),
pipeline/lib/tts/kokoro_worker.py (the engine, under the interpreter of library/voice/engine.txt),
pipeline/lib/tts/whisper_worker.py (faster-whisper, under the interpreter that has it).

## Purpose
Voice the script with the one engine and voice of library/voice/engine.txt (kokoro af_bella; the defaults of
BUILD_SPEC.md 2.5 when the file is missing or names another engine; never a fallback engine or voice), beat by
beat, with the silence tightening of tools/voice.py; check that every line transcribes back (word error rate);
align the words; normalize loudness; also voice hook 2 for the alternate clip. No model call of its own: the one
line rewrite of the ladder runs `pipeline/stages/07-script/run.sh <run_dir> --rewrite-line <beat> --reason ...`.

## Inputs
- 07-script/script.json: beats[].spoken (the TTS track), beats[].id and type (the hook beat gets the breath after
  it), hook2.spoken; the file is rewritten in place by S7's --rewrite-line when the ladder asks for it
- library/voice/engine.txt (engine, python, voice, lang, speed, silence_threshold_db, min_pause_s, keep_pause_s,
  breath_after_hook_s; REELS_ENGINE_FILE overrides the path in tests), library/profile/pronunciations.txt
- config: tts (whisper_model, whisper_python, whisper_pad_s, wer_fail_pct 3, wer_flag_max_pct 8, overrun_pct 15,
  overrun_min_s, lead_s 0.05, tail_s 0.2), voice (wpm: the reel voice's pace, loudness_lufs -14, true_peak_dbtp
  -1.5), timeouts (tts_seconds, align_seconds, loudness_seconds), paths (kokoro_python, venv_python)
- tools/voice.py (Engine, sentences, tighten), ffmpeg

## Outputs (in runs/<id>/08-voiceover/)
- words.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). engine, voice, sample_rate 48000, duration_ms, wpm (the pace
  measured on this reel after tightening), beats[] (id, type, start_ms, end_ms in vo.wav, words, wer_pct, status,
  estimate_s, seconds), breath (after which beat, start_ms, end_ms), loudness, words[] (word: the spoken track's
  word; start_ms, end_ms; beat; heard when the transcription differed), flags.
- vo.wav: the reel's voice, 48 kHz mono 16-bit PCM, -14 LUFS integrated (within 1 LU), true peak at most -1.5 dBTP.
  Layout: 0.05 s lead, the beats tightened (pauses of min_pause_s or longer below silence_threshold_db cut to
  keep_pause_s, shorter pauses kept), keep_pause_s between beats, breath_after_hook_s after the hook beat, 0.2 s
  tail. Nothing is tightened after the alignment: words.json's timestamps are the timestamps of this file.
- vo_hook2.wav and words_hook2.json: hook 2's line, same voice, same tightening and loudness, beat id "hook2".
- voiceover.json: the trail (the engine config in force and where it came from, the interpreters, every line
  with its attempts, transcriptions, word error rates, respellings and rewrites, the timeline, the timings, the
  measured speed and pace, the loudness passes, the flags, the verdict).
- lines/<beat>.a<attempt>.wav (24 kHz, tightened, one per attempt), work/ (jobs, results, the 24 kHz assemblies).
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 20 (block).

## Invariants
- One engine and one voice per reel, from engine.txt: no fallback engine, no other voice, ever. An engine crash or
  hang is a code error (exit 1, the review and fix loop of BUILD_SPEC.md 4.2, then a block), never a switch.
- Pronunciations first: pronunciations.txt (a respelling, or inline phonemes written between slashes, applied as
  Kokoro's `[word](/phonemes/)`) is applied to the spoken text before any generation; the file itself is never
  edited. This reel's own respellings (the ladder's step 1) live only in voiceover.json.
- The ladder, per line, in this order: word error rate over wer_fail_pct (3): the misheard words are respelled by
  rule (acronyms spelled out, camelCase split, digits written out, dots and slashes named) and the line is
  regenerated; still failing: one rewrite through S7 in simpler words and a regeneration; still failing: a NEEDS
  REVIEW flag at wer_flag_max_pct (8) or less, a block above it. Hook 2 stops after the respelling step (a flag,
  never a block). A rewrite of the ladder or of the overrun check happens at most once per line.
- A beat running more than overrun_pct (15) over its estimate (spoken words at config voice.wpm) and by more than
  overrun_min_s is rewritten once through S7, then flagged when it still runs over.
- The word error rate compares the transcription with the text the voice was given: lowercase, punctuation and
  apostrophes dropped, hyphens and slashes split, digits written out (the year reading when the line says it that
  way), and a run of words whose joined letters equal the other side's (plug in / plugin, F X / FX) is a match.
- Timestamps monotonic and inside vo.wav; every beat has a window; the breath is silence in the audio (S9 fills
  it with motion), never a frame of the voice.

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 20 block the idea
(reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2).
The stage never drops an idea (exit 10).

## Model and session
No model. Kokoro runs under engine.txt's interpreter (CPU), faster-whisper under config tts.whisper_python (or
the first interpreter that imports it: the engine's, .venv-tts, python), both through workers in
pipeline/lib/tts/. REELS_TTS_WORKER, REELS_TTS_PYTHON, REELS_WHISPER_WORKER and REELS_WHISPER_PYTHON replace them
in tests (pipeline/tests/fakes/).

## dummy.sh
`bash pipeline/stages/08-voiceover/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
