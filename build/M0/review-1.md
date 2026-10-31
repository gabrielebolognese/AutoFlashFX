# M0 review 1 (Plan)

Reviewer: fresh session, did not write the plan. Date: 2026-10-31.

## Verdict
APPROVED. PLAN.md, DECISIONS.md and CLAUDE.md meet BUILD_SPEC.md section 12 for M0, the checks pass, and no code was
written. There are no required fixes; the suggestions below are optional.

## Acceptance test (run by the reviewer)
M0 has no test command (build/progress.md). The reviewer ran the checks from build/M0/report.md plus a few more:
- `grep -c '^## M' PLAN.md`: 13 (M1 to M13). `Depends on`: 13, `Creates:`: 13, and 13 acceptance test lines, each
  of the form `bash pipeline/tests/test-m<n>.sh`.
- Em dash scan (U+2014) over PLAN.md, DECISIONS.md, CLAUDE.md, build/progress.md, build/HUMAN_TODO.md,
  build/M0/report.md, .gitignore, .gitattributes and every tracked file except hooks.txt: no match. hooks.txt has
  em dashes on lines 43, 64, 73 and 80, and lines 53 and 54 lost their blank, exactly as DECISIONS.md item 4 and
  HUMAN_TODO say. It is the user's file and is correctly left alone.
- Line endings, checked with Python on bytes: every file M0 wrote is LF. `git ls-files --eol` shows LF in the index
  for every tracked file.
- No code: pipeline/, run.sh, config.json and ideas.txt do not exist yet. The only script in the M0 diff is
  tools/analyze_refs.py, which already existed (spec section 1) and is now tracked.
- Git: three commits (1c83195, 529f9d0, aee691b). The tracked files contain no media, refs, analysis frames or sound
  pack audio. .gitignore covers every path in spec section 1 (runs/, exports/, logs/, styles/*/refs/,
  styles/*/analysis/, sfx audio and .cache/, library/voice/, .env). .gitattributes forces LF for *.sh and for all
  text files.
- Facts the plan relies on, checked: vocabulary.md has 24 numbered components (M9 says "items 1 to 24"), and
  styles/sfx has 106 audio files (M8 says 106).

## Spec compliance
- Section 12, M0: PLAN.md covers every milestone, each with the files it creates, an exact acceptance test and its
  dependencies, plus a dependency graph and risks. DECISIONS.md and CLAUDE.md exist. No code.
- Each milestone's test in PLAN.md covers what section 12 requires for it, and goes further in several places:
  - M1: parser fixtures and concurrency.
  - M2: kill and resume, exports 1 and 2, heartbeat fields.
  - M3: every limit format, a planted bug fixed, an unfixable block, three blocks write STOPPED.md.
  - M4: facts, expansion length, gate.json, the false idea is dropped and its block removed.
  - M5: winner and runner-up. M6: every script check. M7: vo.wav and words.json checks.
  - M8: every file is mapped or excluded, the pools, the override survives a rebuild.
  - M9: tokens, components with sound events, gallery, frame match, golden reel, HUMAN_TODOs.
  - M10: plan validation, draft, events.json against the screen. M11: sound sync and loudness, edit review, the
    planted [text] issue routes to 9b.
  - M12: export files and ffprobe checks. M13: three ideas, a simulated limit, the logs tell the story.
- Section 1: every library file the spec names in pipeline/lib (ai, limits, review, state, ideas, status, log) and
  every script in pipeline/bin (add-idea.sh, index-hooks, build-sfx-map, mix-sfx, screenshot) is assigned to a
  milestone.
- Section 3: the permission flags were checked against `claude --help` and recorded (DECISIONS.md 11). `--bare` is
  excluded. Models come from config only. Protected paths are enforced twice (DECISIONS.md 13).
- Section 11: CLAUDE.md has the project summary, folder map, how to start the runner, the braces rule (with the "not
  yet" note until M1), the status question, the curated folders, how to read the logs, and the build status.
- Choices the spec left open are recorded with reasons, notably style v2 over the tracker examples (31) and the
  python/.venv-tts split (5, 6).

## Robustness (as planned)
- Windows: `python` rather than `python3`, a separate 3.11 venv for TTS, GNU date, LF through .gitattributes,
  retries for mv under OneDrive, the 8 KB Bash tool limit noted. No secrets anywhere. No em dashes.

## Earlier milestones
None. M0 is the first milestone, so there are no earlier tests to run.

## Required fixes
None.

## Repeated from earlier review
None (this is the first review of M0).

## Optional suggestions (never a reason to reject)
1. DECISIONS.md item 36 says every text file is LF in the working copy. Four user files are still CRLF there:
   hooks.txt, styles/paper-cards/style.md, tweaks.md and vocabulary.md (`git ls-files --eol` shows `i/lf w/crlf`).
   Their index copies are LF. They are curated files, so leave them alone. Instead, add a convention to PLAN.md
   section 0: every reader of a user-edited text file strips `\r`. That covers hooks.py, tokens.py, the
   deliverables, pronunciations and overrides readers, and ideas.py. Then correct item 36 with a dated note.
2. Spec 2.3 says that if a profile file is missing at runtime, the run continues with defaults and adds a NEEDS
   REVIEW flag to the export. No milestone names this. Suggest assigning it to M5 (where the profile is read) and
   asserting it in test-m12 or test-m13.
3. Some spec S5 and S7 inputs are not named in their milestones:
   - M5: the vendor hooks.json (26 formulas) as extra shapes for S5, and the script that writes new hook shapes to
     library/hooks.suggested.txt. A model call cannot write to library/, so a script has to.
   - M6: the style's beat map and the length rules from tweaks.md as S7 inputs.
4. Spec 2.6 step 3: low-confidence sound files stay out until the user approves them in overrides.txt, but the
   override syntax only has `ban:` and `pin:`. Pick the approval syntax in M8, for example `pin:` or a new `allow:`
   line, and record it in DECISIONS.md.
5. The NEW event line (an idea added from Claude Code) needs a way for the runner to notice it, for example
   add-idea.sh writing a marker or the runner comparing queue sizes. Name the mechanism in M1 or M2.
6. pipeline/tests/test-limits.sh (spec 4.1's parser unit test) does not match run-all.sh's `test-m*.sh` pattern. Have
   test-m3.sh call it, or add it to run-all.sh, so later reviews keep running it.
7. run-all.sh would rerun real-model tests (M3 to M7, M12 at 1 to 3 hours) on every later review. A `--quick` mode
   that only runs unit and fake-model parts would let reviewers check for regressions cheaply. The full tests can
   still run at the milestone's own review.
8. `pipeline/stages/09-plan/` (M9, schema only) is not one of the stage folders listed in PLAN.md section 0. Moving
   the shared plan schema to `pipeline/schemas/visual-plan.json` would keep `pipeline/stages/` one folder per stage.
9. M1 creates `library/voice/README.txt`, but library/voice/ is ignored by git, so the README will never be
   committed. That is harmless, but worth knowing.
