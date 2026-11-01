# M7 review 2: Voiceover (S8)

Verdict: APPROVED

## Acceptance test

`bash pipeline/tests/test-m7.sh` (full run, with real Kokoro and faster-whisper in section 3): `test-m7.sh: 140 passed,
0 failed`, exit 0. Full log: build/M7/review-2-test.log.

- Section 1 (units) and section 2 (fake engine and transcriber through the runner): all pass.
- Section 3 (real): speed 0.434x real time (TTS 42.5 s, alignment 39.7 s, loudness 7.6 s, total 90.5 s); pace 176 wpm
  after tightening (matches config voice.wpm); vo.wav -14.38 LUFS / -1.56 dBTP in 8 passes.
- The new fixture check passes: the frozen vo.wav (41460 ms) and vo_hook2.wav (2680 ms) match the durations in their
  words.json files. The fixtures were already there, so this run did not copy anything, and `git status` shows no
  change under pipeline/tests/fixtures. (The count is 140, not the 141 in fixes-1, because the freeze step only runs
  and passes when the wavs are missing.)

## Review 1 fix 1 (frozen wavs): fixed

pipeline/tests/fixtures/runs/test-idea/08-voiceover/ holds vo.wav and vo_hook2.wav. They are ignored by git through
`*.wav` and come from the same run as the tracked words.json, words_hook2.json and voiceover.json. test-m7 recreates
them when they are missing (all five files together when the timestamps differ) and checks them on every full run.
M9 and M10 have the audio they depend on.

## Required fixes

None.

## Suggestions (not blocking)

- Loudness still takes 8 passes to land at about -14.4 LUFS (within 1 LU). A final gain correction after the limiter
  would land in fewer passes and closer to -14.
- When the frozen wavs are missing, the test refreshes the tracked JSON fixtures and only prints a NOTE asking for a
  commit. On a fresh clone this changes tracked files without anyone noticing. Consider failing loudly instead, or
  documenting `M7_FREEZE=1` as the one way to refresh them.
- The review 1 suggestions still apply: the PLAN.md module names (engine.py and the others) against voiceover.py,
  `setup-venv --whisper/--kokoro` untested, library/voice/engine.txt still names turbo (HUMAN_TODO covers it).
