#!/usr/bin/env python
"""build/M11/patch-progress.py: the M11 section of build/progress.md (a record). Run once; the test summary is filled in
by a second run with the summary text in build/M11/test-summary.txt."""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
p = os.path.join(ROOT, "build", "progress.md")
s = open(p, encoding="utf-8").read()
stub = """## M11 Sound effects pass and review loop (S11, S12)
- Status: not started
- Test command: `bash pipeline/tests/test-m11.sh` (planned)
- Notes:
"""
section = """## M11 Sound effects pass and review loop (S11, S12)
- Status: done (2026-11-01). @@TEST_SUMMARY@@
- Test command: `bash pipeline/tests/test-m11.sh` (`M11_SECTIONS="1 2 3"` for the fake-only sections; `M11_FREEZE=1` also
  copies the real 11-sfx and 12-review JSON outputs into pipeline/tests/fixtures/runs/test-idea/); `bash
  pipeline/tests/run-all.sh` runs M1 to M11, limits and the em dash scan (about 2.5 hours).
- Notes: S11 is pipeline/stages/11-sfx/run.sh over pipeline/lib/sfx/{assign,pick,place,level,render_stem,verify,audioio,
  mixsfx}.py (pipeline/bin/mix-sfx by hand): the cue rules of the spec on 10-build/events.json with the density read of
  DECISIONS.md 235 (typing beds are not hits, a checklist's ticks count once, a hero on the scene change pops at its
  landing), seeded per reel; the pools in rotation with logs/sfx-usage.json; whooshes by their measured peak, the rest by
  their onset, typing trimmed, tails cut 50 ms before the next sound; gains from the map's normalization plus config
  sfx.base_gain_db, capped 8 dB under the voice's local peak (floor: the overall peak minus 12 dB); the stem and the mix
  in numpy, verified on the rendered files (33 ms, the whoosh plateau rule, the strongest-rise onset over a bed, no
  unplanned sound, the 8 dB rule, -14 LUFS plus or minus 1, -1.5 dBTP) and corrected up to 3 passes; cues.json,
  sfx_stem.wav, mix.wav, draft_mixed.mp4, sound-map.txt, the hook 2 clip's sounds; voice only plus a flag without a map;
  the review's [sfx] notes change the next pass. S12 is pipeline/stages/12-review/run.sh over pipeline/lib/review/
  (`python pipeline/lib/review mechanical|style|audio|filmstrips|prompt|verdict|feedback|strip`): the mechanical checks in
  the Playwright harness host by host from the project's index.html (zones with the caption band exception, the right
  rail, fonts and sizes, overlaps, off-canvas, contrast 4.5:1 and 2.7:1 for the style's accent words from the pixels
  behind the glyphs, emphasis within 80 ms from the caption line's events, the branding rules with the surface measured
  behind the hidden logo), the style check with tools/analyze_refs.py (cadence against the references, delta E 5 palette
  share, accent share, loudness), the audio check (S11's verification, the mix transcribed, WER under 5), the editor
  (config models.qa, a fresh session, Read and Glob on the contact sheet, the filmstrips, three reference stills, the
  scene table and sound-map.txt; eight scores, branding_natural, tagged issues), the verdict and routing (pass at every
  check and every score 4 or more; else the earliest owner and everything after it reopened through reopen.txt, S12
  included; 3 opus rounds then 2 fable; then the export with NEEDS REVIEW; [voice] routes only with a quoted word), the
  feedback to the re-run passes ({{REVIEW}} in the director prompts, S8's respelling, S11's adaptation), a result cache
  for the unchanged checks. Earlier milestones touched: caption-line.html (M9: every chunk was scaled to 60 percent, found
  by the new check; the drafts and the contact sheet of the frozen test idea were rendered again), card.html (a logo keeps
  its aspect ratio), state.py (self reopen), visual.sh and the three director prompts, voiceover.py, config.json (sfx.*,
  review.*, timeouts, models.visual_director_escalation), tests/lib.sh (--with-review). Fixtures: the fake editor's
  answers pipeline/tests/fixtures/fake/{m11,m11-text,m11-sfx}/; the frozen projects are rebuilt from the plans by
  pipeline/tests/materialize-project.py. Hooks for M12: 11-sfx/mix.wav and mix_hook2.wav are the audio S13 muxes (48 kHz
  mono, -14 LUFS), 12-review/review.json and notes.md the review's verdict and notes (state.json flags carry the NEEDS
  REVIEW text for the captions file), 10-build/project and hook2 the compositions to render at 1080x1920. DECISIONS.md
  234 to 260. Report: build/M11/report.md.
"""
summary_path = os.path.join(ROOT, "build", "M11", "test-summary.txt")
if stub in s:
    s = s.replace(stub, section)
    print("progress.md: section written")
if "@@TEST_SUMMARY@@" in s and os.path.isfile(summary_path):
    s = s.replace("@@TEST_SUMMARY@@", open(summary_path, encoding="utf-8").read().strip())
    print("progress.md: summary filled")
open(p, "w", encoding="utf-8", newline="\n").write(s)
