#!/usr/bin/env python
"""build/M11/patch-claude-md.py: the M11 build status in CLAUDE.md (a record)."""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
p = os.path.join(ROOT, "CLAUDE.md")
s = open(p, encoding="utf-8").read()

old_head = "- M10 Visual stages: done (2026-11-01). Next: M11 Sound effects pass and review loop (S11, S12). The build is driven by\n  `bash build-runner.sh`; its log is build/build.log and its per-milestone reports are in build/M<n>/."
new_head = "- M11 Sound effects pass and review loop: done (2026-11-01). Next: M12 Final render, caption, export, end to end (S13,\n  S14). The build is driven by `bash build-runner.sh`; its log is build/build.log and its per-milestone reports are in\n  build/M<n>/."
assert old_head in s, "head"
s = s.replace(old_head, new_head)

old_tail = """  mounted components and verified on screen), pipeline/bin/contact-sheet, the preflight check `brand` (brand.json and
  every file it lists). Run every test with `bash pipeline/tests/run-all.sh` (about 2 hours; test-m3 section 4,
  test-m4 sections 3 and 4, test-m5 sections 3 and 4, test-m6 section 3, test-m7 section 3 and test-m10 section 3
  make real model or engine calls, test-m8 and test-m9 make none, test-m9 takes about 8 minutes, test-m10 about 25
  minutes; `M7_SECTIONS="1 2" bash pipeline/tests/test-m7.sh` and `M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh`
  are the fake-only tests)."""
new_tail = """  mounted components and verified on screen), pipeline/bin/contact-sheet, the preflight check `brand` (brand.json and
  every file it lists), the sound pass of M11: S11 (pipeline/stages/11-sfx/run.sh over pipeline/lib/sfx/assign.py the
  cue rules, pick.py the pool rotation with logs/sfx-usage.json, place.py, level.py, render_stem.py, verify.py,
  audioio.py, mixsfx.py the orchestrator; pipeline/bin/mix-sfx runs it by hand), the review loop of M11: S12
  (pipeline/stages/12-review/run.sh, prompt.md and model.schema.json for the qa editor, over the package
  pipeline/lib/review/: `python pipeline/lib/review <command>`: mechanical (the built composition opened host by host in
  the Playwright harness: zones, the right rail, fonts, overlaps, contrast, emphasis timing, the branding rules), style
  (tools/analyze_refs.py on the mixed draft against styles/paper-cards/analysis: cadence, token colors, accent share,
  loudness), audio (S11's verification, the voice transcribed from the mix, WER under 5 percent), filmstrips, prompt,
  verdict and feedback (route.py: pass when every check passes and every score is at least 4, else each tagged issue
  back to its owner through reopen.txt, every later stage again, 3 opus rounds then 2 fable rounds, then the export with
  NEEDS REVIEW), the review notes the re-run passes read ({{REVIEW}} in the director prompts, S8's respelling of a quoted
  word, S11's fewer and softer sounds), pipeline/tests/materialize-project.py (the frozen project folders rebuilt from
  the plans). Run every test with `bash pipeline/tests/run-all.sh` (about 2.5 hours; test-m3 section 4, test-m4
  sections 3 and 4, test-m5 sections 3 and 4, test-m6 section 3, test-m7 section 3, test-m10 section 3 and test-m11
  section 4 make real model or engine calls, test-m8 and test-m9 make none, test-m9 takes about 8 minutes, test-m10
  about 25 minutes, test-m11 about 40 minutes; `M7_SECTIONS="1 2" bash pipeline/tests/test-m7.sh`,
  `M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh` and `M11_SECTIONS="1 2 3" bash pipeline/tests/test-m11.sh` are the
  fake-only tests)."""
assert old_tail in s, "tail"
s = s.replace(old_tail, new_tail)

old_stages = """- The stages S11 to S14 (run.sh in each stage folder) arrive from M11 on, so `bash run.sh` alone stops with
  logs/STOPPED.md at S11. `REELS_DUMMY=all bash run.sh --once` runs the whole loop with dummy stages;
  `REELS_DUMMY=11,12,13,14 bash run.sh --once` runs the real research, expansion, gate, hooks, judge, script,
  voiceover, visual plan and build with dummy stages after them. The visual stages (S9a, S9b, S9c) write"""
new_stages = """- The stages S13 and S14 (run.sh in each stage folder) arrive from M12 on, so `bash run.sh` alone stops with
  logs/STOPPED.md at S13. `REELS_DUMMY=all bash run.sh --once` runs the whole loop with dummy stages;
  `REELS_DUMMY=13,14 bash run.sh --once` runs the real research, expansion, gate, hooks, judge, script, voiceover,
  visual plan, build, sound pass and review with dummy render and export after them. The sound stage (S11) writes
  runs/<id>/11-sfx/cues.json (every sound: cue type, file, the event it sits on, placement, gains, the verification),
  sfx_stem.wav, mix.wav (the audio S13 muxes), draft_mixed.mp4 (for the review), sound-map.txt (one readable line per
  sound), and sfx_stem_hook2.wav, mix_hook2.wav for the alternate clip; it refreshes styles/sfx/sfx-map.json at its
  start and records its picks in logs/sfx-usage.json. The review stage (S12) writes runs/<id>/12-review/review.json
  (round, pass, verdict pass | fix | cap | flag, the scores, every tagged issue, the routing), mechanical.json,
  style.json, audio.json, edit-r<n>.json, filmstrips/, prompt-r<n>.md, notes.md and feedback.json (what the re-run
  stages read); state.json rounds.review counts the failed rounds. The visual stages (S9a, S9b, S9c) write"""
assert old_stages in s, "stages"
s = s.replace(old_stages, new_stages)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("CLAUDE.md patched")
