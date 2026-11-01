# M7 report: Voiceover (S8)

Built 2026-11-01 in one build batch. Spec: BUILD_SPEC.md section 5 (S8), 2.5 and section 12 (M7); plan: PLAN.md M7;
decisions: DECISIONS.md 161 to 177.

## What was built

- **The voice config.** `pipeline/lib/voiceover.py engine` reads library/voice/engine.txt (`key = value`) and
  fills every missing line from the block of BUILD_SPEC.md 2.5. A missing file means the whole block; a file that
  names another engine (the user's file still says `engine = turbo` with the chatterbox venv, written before the
  spec moved to Kokoro) means the block too, with a WARN at every start and a HUMAN_TODO, because this pipeline
  voices every reel with Kokoro af_bella and nothing else. The default interpreter path is config
  paths.kokoro_python (C:/Users/there/venvs/kokoro/Scripts/python.exe, which exists and imports kokoro 0.9.4).
- **The preflight check `voice`** (`voiceover.py engine-check`): the voice interpreter exists and imports kokoro
  (a real one-line import), one interpreter imports faster_whisper (config tts.whisper_python, the chatterbox venv;
  else the voice interpreter, .venv-tts, python). A failure is a systemic stop with the exact problem and the
  spec's fix in logs/STOPPED.md; the notes above are warnings. The runner banner now reads "voice: kokoro
  af_bella".
- **The stage** `pipeline/stages/08-voiceover/run.sh` runs `voiceover.py run` and relays its lines to the runner
  (activities for the heartbeat, say lines, flags, the error message), then maps the exit code (0 done, 20 block,
  else a code error for the review and fix loop). The Python:
  1. pronunciations.txt applied to the spoken track (a respelling, or `/phonemes/` as Kokoro's `[word](/.../)`),
  2. every line (11 beats plus hook 2) generated in one call of `pipeline/lib/tts/kokoro_worker.py` under
     engine.txt's interpreter, through tools/voice.py's Engine, sentences and tighten: sentences joined with
     min_pause_s + 0.05 s, the line tightened (pauses of min_pause_s or longer below silence_threshold_db cut to
     keep_pause_s, edges removed), written as 24 kHz PCM,
  3. every line transcribed in one call of `pipeline/lib/tts/whisper_worker.py` (faster-whisper small, CPU
     int8, 0.5 s of padding) and compared with what the voice was told, with a normalizer that treats split or
     joined words, digits, years, British spellings and a plural or possessive s as the same word,
  4. the ladder per line: over 3 percent WER, the misheard words respelled by rule and the line regenerated;
     still failing, one rewrite through `07-script/run.sh --rewrite-line` and a regeneration; still failing, a
     NEEDS REVIEW flag at 8 percent or under, a block above (hook 2 flags only),
  5. the overrun check: a beat more than 15 percent (and 0.4 s) over its estimate (syllable-spread, at config
     voice.wpm) is rewritten once, then flagged,
  6. the assembly: 0.05 s lead, 0.1 s between beats, the 1.0 s breath after the hook beat, 0.2 s tail,
  7. loudness: gain plus a light limiter, re-measured until -14 LUFS (within 0.4) and at most -1.5 dBTP, 48 kHz
     mono 16-bit; the same for hook 2,
  8. words.json from the per-line transcriptions offset by the timeline (nothing is tightened after the
     alignment), words_hook2.json, voiceover.json (the whole trail: attempts, transcriptions, rates, respellings,
     rewrites, timings, pace, loudness passes, verdict).
- **Config:** tts shrank to the stage's knobs (device, whisper_model, whisper_python, whisper_pad_s, wer_fail_pct 3,
  wer_flag_max_pct 8, overrun_pct 15, overrun_min_s 0.4, lead_s 0.05, tail_s 0.2); the chatterbox, turbo and qwen
  settings, gap_ms and voice.reference are gone; voice.wpm is 176 (measured); timeouts tts_seconds 1800,
  align_seconds 1800, loudness_seconds 300; paths.kokoro_python; the preflight `voice` entry.
- **S5 and S7 time with config voice.wpm first** (the reel voice), voice.md's Pace line only as a fallback.
- **pipeline/bin/setup-venv:** `--check` (reports both interpreters), `--whisper` (.venv-tts with faster-whisper
  through uv) and `--kokoro` (the default kokoro venv, CPU torch) for the day something is missing; only `--check`
  ran in this build.

## Files

- New: pipeline/lib/voiceover.py, pipeline/lib/tts/kokoro_worker.py, pipeline/lib/tts/whisper_worker.py,
  pipeline/stages/08-voiceover/run.sh, pipeline/bin/setup-venv, pipeline/tests/test-m7.sh,
  pipeline/tests/fakes/kokoro_worker.py, pipeline/tests/fakes/whisper_worker.py,
  pipeline/tests/fixtures/fake/m7/07-script.rewrite-line.json, pipeline/tests/fixtures/runs/test-idea/08-voiceover/
  (words.json, words_hook2.json, voiceover.json; the wavs are not tracked), build/M7/report.md.
- Changed: config.json, pipeline/lib/preflight.sh (the `voice` check), pipeline/lib/status.sh (the banner),
  pipeline/stages/08-voiceover/{CONTRACT.md,schema.json,dummy.sh}, pipeline/stages/05-hooks/run.sh and
  pipeline/stages/07-script/run.sh (the pace source), pipeline/lib/script_checks.py (apply_pronunciations: the
  slash rule and the double-wrap guard), pipeline/tests/lib.sh (tools/ copied into the sandbox, SANDBOX_WPM),
  pipeline/tests/test-m1.sh and test-m2.sh (the banner text), test-m5.sh and test-m6.sh (SANDBOX_WPM=195),
  DECISIONS.md, build/progress.md, build/HUMAN_TODO.md, CLAUDE.md.

## How to run the test

```
bash pipeline/tests/test-m7.sh                    # everything, 5 to 15 minutes
M7_SECTIONS="1 2" bash pipeline/tests/test-m7.sh  # no engine, no model: units and the fake paths
M7_FREEZE=1 bash pipeline/tests/test-m7.sh        # also refresh the frozen 08-voiceover JSON fixtures
bash pipeline/bin/setup-venv --check              # which interpreter voices, which one transcribes
```

## Test output, in short

`bash pipeline/tests/test-m7.sh`: `test-m7.sh: 139 passed, 0 failed` in about 12 minutes (section 1: 48 checks in
under a minute; section 2: 68 checks in about 6 minutes, six runner runs with the fakes; section 3: 23 checks, the
real S8 in 1 min 47 s inside a 2 min 11 s runner pass).

The real run on the frozen script (11 beats plus hook 2, 118 spoken words):
- Kokoro af_bella through the defaults (engine.txt names turbo): 12 lines generated in 43 s, synthesis at 0.45x
  real time for 66.7 s of raw voice (0.40x on the quiet probe run), 12 s to import and load; the lines tightened
  from 66.7 s to 41.7 s (14 pauses shortened); vo.wav 41.5 s with the 0.05 s lead, the 0.1 s gaps, the 1.0 s
  breath and the 0.2 s tail, 2 percent under the 42.5 s expected at 176 wpm (the script's own estimate was 36.3 s
  at the user's 195 wpm).
- faster-whisper small (CPU int8): 12 lines aligned in 41 s (about 3 s per line); every line at 0.0 percent word
  error rate with the normalizer, so no respelling, no rewrite and no model call; the first probe run, before the
  normalizer learned spelling variants and possessives, had one line at 16.7 percent (grey/gray, Anthropic's/
  Anthropic) and went to the rewrite.
- vo.wav at -14.35 LUFS and -1.6 dBTP (5 passes, gain 13.7 dB), vo_hook2.wav 2.7 s at -14.2 LUFS and -1.7 dBTP.
- words.json: 118 words, 11 beats, monotonic and inside their beats; the 5 spot-checked first words (b1, b3, b6, b9,
  b11) start exactly at their beat's audio, speech at -9 to -13 dB in the window, digital silence in the gap before.
- Silences: one run of 0.3 s or longer, the 1.0 s breath after the hook; 4 natural pauses between 0.15 and 0.3 s
  kept inside lines (the spec's own rule: shorter pauses stay).
- Pace after tightening: 176 wpm counting the gaps, 180 on speech alone (config voice.wpm = 176).

The fake paths (section 2): the happy path with the exact timeline and no model call; the ladder with b5 fixed by
respelling AI as A I (no model call), b9 fixed by S7's rewrite (one call), b7 at 37 percent over its estimate
rewritten then flagged (one call); the flag path at 7.1 percent after the rewrite; the block path at 14.3 percent
("blocked at S8: voice: line b9 cannot be said clearly by af_bella (WER 14.3%: ...) after no respelling rule,
rewritten by S7: ..."); the engine crash as a code error through the review loop to a block; the engine hang
killed after 4 s, classified as a timeout, retried three times (fast-forwarded) and blocked. Never another voice or
engine anywhere.

## Earlier milestones touched

config.json (M1); the preflight's check types (M1); the banner and its assertions in test-m1 and test-m2 (M2);
S5's and S7's pace source (M5, M6) and SANDBOX_WPM in their tests; script_checks.apply_pronunciations (M6);
tests/lib.sh (tools/ in the sandbox); the 08-voiceover schema, dummy and contract (M2). Regression runs after
these changes: `bash pipeline/tests/test-m1.sh` 96 passed, 0 failed; `M5_SECTIONS="1 2" bash
pipeline/tests/test-m5.sh` 198 passed, 0 failed; `M6_SECTIONS="1 2" bash pipeline/tests/test-m6.sh` 147 passed, 0
failed; `bash pipeline/tests/test-limits.sh` 94 passed, 0 failed; `bash pipeline/tests/test-no-emdash.sh` 1 passed;
`bash pipeline/tests/test-m2.sh` (alone on a quiet machine, its heartbeat-schedule check is CPU sensitive) 220
passed, 0 failed.
test-m2's section 7 now stops at 09a-animations, the first stage without a run.sh.

## Known gaps

- library/voice/engine.txt names turbo: the stage runs on the spec's kokoro defaults until the user rewrites it
  (HUMAN_TODO). The defaults are the exact block of BUILD_SPEC.md 2.5 and the interpreter exists, so the voice is
  the one the spec asks for; only the file is stale.
- The transcriber is faster-whisper "small" (what is cached; small.en is not) from the chatterbox venv. The word
  error rate check measures whisper's agreement, not a listener's: the normalizer removes the known transcription
  artifacts (split words, spelling variants, possessives), but a tool name whisper spells differently will still
  count as misheard, go through the respelling (no rule for a plain word) and the rewrite, and end as a flag or a
  block. pronunciations.txt is the user's lever (HUMAN_TODO).
- The respelling step has rules only for words with capitals, digits or symbols (acronyms, camelCase, file
  names, commands); a plain English word the voice says oddly goes straight to the rewrite. Kokoro's own
  phonemes for such a word are what it would produce anyway, so a scripted "fix" without a dictionary would change
  nothing.
- The per-line overrun estimate is syllable-spread at config voice.wpm with a 0.4 s floor; the spec's words-based
  reading would flag long-word lines of a reel that is on pace overall (b4 of the test script: 19 percent over at
  words, on time at syllables). The total length check is unchanged.
- setup-venv's install branches (`--whisper`, `--kokoro`) are plain uv commands but were not run: nothing was
  missing on this PC.
- The hang path is classified by the runner from the stage's message ("the voice engine hung: ... did not finish
  in N s (killed)"): a code error straight to the review loop; the spec's wording ("retries and the review and fix
  path") is met by the review loop's own restarts.
- Hook 2 never blocks an idea (a flag at most) and is not rewritten: it has no beat for S7's rewrite and the
  alternate clip is secondary.

## HUMAN_TODO items added

- M7: rewrite library/voice/engine.txt with the kokoro block (it still names turbo).
- M7: transcription runs from the chatterbox venv (config tts.whisper_python); what to do if that venv goes away.
- M7: config voice.wpm is 176 (af_bella measured); how to re-measure after a speed change.
- M7: how to read a voice flag or a voice block, and that pronunciations.txt is the fix.
