# M5 review 1 (Profile and hooks, S5 and S6)

Verdict: APPROVED

## Acceptance test
`bash pipeline/tests/test-m5.sh` (all four sections, real models in 3 and 4): `test-m5.sh: 231 passed, 0 failed`,
exit 0, no ERROR line.
- Section 1 (units, no model): hooks.py, index cache, lint, shortlist, spoken cap, judge.py, voiceprofile.py,
  session_call --seed-if-new, all PASS.
- Section 2 (fake claude through run.sh): S5 seeded session A, 14 hooks, 14 of 14 through hookscore, judge.json
  with hook 1 and hook 2; the regeneration path (3 of 12 passed, S5 regenerated, 13 of 13, exported), all PASS.
- Section 3 (real indexer over library/hooks.txt): index built, lint lines found, second run makes no call.
- Section 4 (real models on the frozen M4 outputs): 15 hooks from all 6 families, spoken cap 8 words at 195 wpm,
  brief.md 2691 tokens with claim citations, brief resumed session A, hook 1 "Five AI tells. Number five is
  Anthropic's own." (on screen "5 TELLS. #5 IS ANTHROPIC'S").
The report says 232 checks, this run counted 231. The model's answers vary from run to run, so that is not a failure.

## Required fixes
None.

## What M6 needs from M5 (checked)
- runs/<id>/05-hooks/hooks.json and brief.md, runs/<id>/06-judge/judge.json (winner = hook 1, runner-up = hook 2),
  plus frozen copies under pipeline/tests/fixtures/runs/test-idea/ for M6 to start from: present.
- library/profile/voice.md and account.md (placeholder drafts, flagged NEEDS REVIEW), config voice.wpm: present.
- session A is resumable through session.sh. The --seed-if-new change only applies when a caller passes the flag.
  Without it, S1 to S4 run the same code path as before, and the fake M4 sections pass according to the report.

## Suggestions (not blocking)
1. library/.hooks.stats.json is untracked in git and still empty (the tests write stats only in their sandbox).
   That matches CLAUDE.md (commit it when a snapshot is wanted). No action needed.
2. hookscore.py lets only a third to a half of the hooks through in real runs (8 of 16 and 5 of 14 earlier). If a
   later idea often triggers the regeneration path, think about asking S5 for more hooks, or for hooks shaped
   for hookscore.
3. The brief's first draft went over 3000 tokens in both earlier real runs. Tightening the target in
   prompt-brief.md (for example, aim for 2400) would save a retry call per reel.
4. pipeline/bin/setup-venv was not built (DECISIONS.md 134 defers it to M7). M7 should either build it or remove
   it from PLAN.md.
5. The working tree has uncommitted changes to BUILD_SPEC.md and build-runner.sh and an untracked tools/voice.py.
   They are not part of the M5 commits, so I did not review them. Likely edits made by the user or the build runner.
