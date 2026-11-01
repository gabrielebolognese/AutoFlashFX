# M6 review 1 (Script, S7)

Verdict: APPROVED

## Acceptance test
`bash pipeline/tests/test-m6.sh` ran once (log: build/M6/review1-logs/test-m6.log): `161 passed, 0 failed`, exit 0.
- Section 1 (units) and section 2 (S7 through run.sh with the fake claude: the normal, rewrite, block and soft
  paths, plus the one-line rewrite) passed.
- Section 3 (real models): S7 finished in 2 rounds, then the dummy stages ran through to `DONE exported #1`. script.json
  validates against the schema. It has 11 beats, 37.23 s and 113 words. Tone insider, draft a picked (seeded order
  b,a, with a reason). Draft a was cut 21.6% (125 to 98 words) and draft b 12.9%. detect.py scored 83.1 (lowest check:
  VOICE 69.2). 13 claims checked, 0 bad. The stake lasts 4.0 s and the loop word is "identical". No spoken track holds
  a digit, there is no em dash, draft a opened session D, draft b resumed it, and the pick ran fresh.
- The report says 162 checks. This run counted 161, a small difference that does not matter here.

## Required fixes
None.

## What I checked
- M7's interface: `pipeline/tests/fixtures/runs/test-idea/07-script/script.json` exists and carries beats with
  id, type, display, spoken, emphasis, card, card_words, facts and seconds, plus hook2, ask, flags, pronunciations and an
  empty `rewrites` list. `run.sh <run_dir> --rewrite-line <beat> --reason "<why>"` is implemented (exit 0, 4 or 1)
  and covered by section 2.
- Shared code M6 touched: `write_retry_prompt` in stage.sh takes an optional 6th argument, so existing callers
  are unaffected. The fake claude looks up the `# Task:` fixtures first and otherwise behaves as before. The report shows
  M2, M3, M4 and M5 regression runs passing after these changes.

## Suggestions (not blocking)
1. Some cards are code tokens rather than words: `rgba(0,0,0,.1)` (b3) and
   `/plugin install frontend-design@claude-plugins-official` (b10). They count as 1 to 3 words, so they pass
   the 6-word rule, but the second one is very long on a 1080 px card. The visual stages (M8 on) should wrap
   or shrink long tokens, or S7 could add a character cap on top of the word cap.
2. Round 1 failed on detect.py burstiness for draft a again (55 on that check). The prescribed rhythm rule
   makes round 2 pass, but other ideas may often end with a soft flag. Watch how often the flag appears on real runs.
3. The payoff beat b10 is a bare command line. That is fine for this idea, but the payoff check could ask for a
   sentence and not only a command.
4. Hook 2's spoken line is not timed by beats.py (known gap in the report). Running a simple duration check on it
   would cost almost nothing.
