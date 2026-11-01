# M4 report: Research, expansion, gate, angle (S1 to S4)

Built 2026-11-01 from BUILD_SPEC.md section 5 (S1 to S4), section 3 (session A) and section 12 (M4), and PLAN.md
(M4). Acceptance test green (numbers in "Test output summary" below); the M1, M2 and M3 tests, the limits unit test
and the em dash scan pass with it. Two sections of the M4 test make real model calls (the research, expansion and
gate models on the test idea and on a deliberately false idea); everything else runs against the fake claude.

## What this batch built
- **S1 Research** (pipeline/stages/01-research/run.sh, prompt.md, model.schema.json, schema.json): session A with the
  research model, tools WebSearch, WebFetch, Read and Bash restricted to `gh ...` and `bash pipeline/bin/screenshot`
  (config research.allowed, through the new repeatable `--allow RULE` option of ai()). The model answers with one
  JSON object (the core claim and its status, claims with URL, tier and status, numbers, pitfalls, the one specific
  true thing candidates, the screenshots it took, what it could not verify); pipeline/lib/research.py renders
  research.json (the primary output), facts.md (every claim numbered, `n. <claim> [tier, status]: <url> (checked
  YYYY-MM-DD)`, verified before unverified before false, primary sources first), numbers.json and assets.json (the
  screenshots whose files exist, with the model's captions). A missing library/profile/account.md is a NEEDS REVIEW
  flag (once per run), not an error.
- **The screenshot tool** (pipeline/bin/screenshot over pipeline/lib/screenshot.py): Playwright, headless Chromium,
  a 1080x1920 viewport (or --full-page capped at 4 screens), NN-name.png plus a JSON sidecar with url, final_url,
  title, status and the capture date; the same URL is reused; it writes only inside the runs folder of the state
  root; a 401, 403, 429 or 503 or a bot-check page is reported as blocked and nothing is saved, with no user agent
  spoofing and no workaround (spec S1). setup-python installs playwright and its Chromium; the preflight warns when
  the package is missing.
- **S2 Expansion** (pipeline/stages/02-expansion/): session A resumed, no tools. The model answers with the five
  parts as fields; pipeline/lib/expansion.py checks the rules (one first-person problem sentence, a named identity,
  a keyword in capitals, a NEW deliverable described concretely unless the keyword is in deliverables.txt, 2 to 6
  evidence pointers to verified claims of facts.md) and composes expansion.md in one fixed layout of 500 to 1500
  characters; a broken rule or a length outside the window is asked again in the same session with the exact
  problems (3 tries, then written with a NEEDS REVIEW flag).
- **S3 Idea gate** (pipeline/stages/03-gate/): a fresh session B with the gate model every round, no tools. The
  model scores P, S and C 0 to 3 with quoted evidence and gives its F verdict, an angle hint and (rarely) a
  different-topic suggestion; pipeline/lib/gate.py decides: F fails whatever the model said when the research found
  the core claim false or unverified (drop at once), pass when P, S and C are at least 2 and F ok, a different-topic
  verdict drops and writes logs/suggested-ideas.txt, otherwise an angle round while caps.angle_rounds allows it,
  else a drop. Lines: `GATE   passed (P3 S2 C3 F ok)` (plus "after N angle round(s)"), `ANGLE  gate failed (S1):
  finding a better angle, round 1/2`; drop reasons carry the scores ("facts don't hold (P2 S2 C2 F fail): ...",
  "still failing after 2 angle rounds (P3 S1 C3 F ok): ...").
- **S4 Angle research** (pipeline/stages/04-angle/): session A resumed with the research tools again, the gate's
  verdict and the earlier rounds in the prompt; the model answers with a new expansion, what it changed, whether
  the core topic is kept and any new claims it researched. New claims are appended to facts.md and research.json
  (numbering continues, nothing is renumbered), the expansion is checked and composed as in S2 (the previous one
  kept as expansion-r<n-1>.md), angle.json and angle-<n>.json are written, and the gate runs again. A model that
  says no angle keeps the core topic drops the idea and writes the suggestion.
- **The angle loop's handover** goes through `<stage>/reopen.txt`: the gate names 04-angle, the angle stage names
  03-gate, and state.py stage-done reopens the named stages in the same write that marks the stage done (a
  reopened stage restarts its attempts at 0); stage-start removes a stale file. The rounds are derived from the
  gate-*.json and angle-*.json files, so a stage run again after a crash or a fix computes the same round.
- **Session A** (pipeline/lib/session.sh): `session_call` wraps ai() with `--session A`; when the stored session no
  longer exists it starts a new one seeded with the idea, facts.md, expansion.md and the latest gate verdict, then
  the task (the reseed fallback of spec section 3).
- **The shared stage library** (pipeline/lib/stage.sh: stage_begin, stage_drop, stage_block, stage_fail,
  stage_ai_failed, flag_once, profile_file, render_prompt, write_retry_prompt, cfg_list) and pipeline/lib/prompt.py
  (`{{KEY}}` templates, inlined files cleaned of em dashes and CR characters, a missing placeholder is an error).
- **Config:** `research` (tools, allowed, max_assets, screenshot size, expansion_chars, expansion_tries), the
  timeouts research_seconds, angle_seconds, expansion_seconds, gate_seconds and screenshot_seconds, the warn-level
  playwright preflight item; requirements.txt adds playwright.
- **Tests:** pipeline/tests/test-m4.sh (four sections, see below), pipeline/tests/session-driver.sh, the fake
  claude's FAKE_CLAUDE_FIXTURES mode (answers by the prompt's "# Stage: <key>" line), the fixtures
  pipeline/tests/fixtures/fake/m4/ (model-shaped answers for the loop) and pipeline/tests/fixtures/ideas/false-idea.txt,
  and the frozen outputs of the test idea under pipeline/tests/fixtures/runs/test-idea/ (research, expansion, gate,
  the model's structured answers under calls/, the screenshots), which M5 starts from.

## Files
- New: pipeline/lib/{stage.sh, session.sh, prompt.py, research.py, expansion.py, gate.py, screenshot.py},
  pipeline/bin/screenshot, pipeline/stages/{01-research,02-expansion,03-gate,04-angle}/{run.sh, prompt.md,
  model.schema.json}, pipeline/tests/{test-m4.sh, session-driver.sh}, pipeline/tests/fixtures/fake/m4/*,
  pipeline/tests/fixtures/ideas/false-idea.txt, pipeline/tests/fixtures/runs/test-idea/**, build/M4/report.md.
- Changed: the four stages' CONTRACT.md and schema.json (refined for the real files), the dummies of 01-research and
  03-gate (the refined schemas), pipeline/lib/state.py (reopen.txt in stage-done, stage-start cleanup, reopen
  resets attempts), pipeline/lib/ai.sh (`--allow RULE`, no wholesale pre-approval of the tools list when rules are
  given), pipeline/tests/fakes/claude.py (FAKE_CLAUDE_FIXTURES), pipeline/tests/lib.sh (profile .md files copied,
  dummy_after), config.json, pipeline/bin/setup-python, requirements.txt, .gitignore (runs/, exports/, logs/ and
  .locks/ anchored to the root so the fixtures folder is tracked), run.sh (build status), CLAUDE.md, DECISIONS.md
  (items 95 to 109), build/progress.md, build/HUMAN_TODO.md.
- Earlier milestones touched, because M4 depends on them: M2's state.py (the reopen handover) and the two dummies,
  M3's ai.sh (rules with spaces) and fake claude, M1's config.json, setup-python, requirements.txt and tests/lib.sh,
  M0's .gitignore. One earlier test changed because M4 changed its premise: test-m2 section 7 ("a stage that is not
  built yet") expected the runner to stop at S1 with no REELS_DUMMY; with the real S1 in place that run started a
  real research call and timed out. The section now finds the first stage without a run.sh (05-hooks today), runs
  the built stages as dummies and expects the stop there; it skips itself once every stage exists. M1 to M3 keep
  passing (see below).

## How to run the test
```
bash pipeline/tests/test-m4.sh                      # everything: 1 and 2 with the fake claude, 3 and 4 with the real models
M4_SECTIONS="1 2" bash pipeline/tests/test-m4.sh    # the units and the angle loop, no model calls (about a minute)
M4_SECTIONS="3 4" M4_FREEZE=1 bash pipeline/tests/test-m4.sh   # the real sections, and rewrite the frozen fixtures
bash pipeline/tests/run-all.sh                      # M1 to M4, limits and the em dash scan (about 50 minutes)
```
KEEP_SANDBOX=1 keeps the temporary roots. The tests never touch the real ideas.txt, runs/, exports/ or logs/; the
real sections run in a sandbox copy of the repo, so a fixer (none was needed) would commit there.

## Test output summary
`bash pipeline/tests/test-m4.sh`: `test-m4.sh: 210 passed, 0 failed`, exit 0, about 11 minutes on this PC (the
fake sections take about a minute; the test idea's real run took 4 min 40 s, the false idea's 4 min 06 s). The
sections, in the order of the test:

1. Units, no model (116 checks): prompt.py (a missing placeholder is an error, inlined files cleaned of em dashes
   and CR); the screenshot tool against a local `python -m http.server` page (a 1080 px PNG with its sidecar
   holding title, status, URL and the capture date; the same URL reused; a "Just a moment..." page reported as
   blocked with nothing saved; a folder outside runs/ refused; a non-http URL refused); research.py on the fixture
   (7 claims, every numbered line with its URL and checked date, verified before unverified before false, primary
   before vendor, numbers parsed, the captured asset with the model's caption, research.json valid); expansion.py
   (the fixture passes, 1002 characters; a bad answer collects every rule error with exact numbers; a keyword from
   deliverables.txt is existing with the file's link); gate.py (angle, the cap, the model's F fail, a false or
   unverified core claim forcing F, pass, the different-topic drop, suggested-ideas.txt, the round count); state.py
   (reopen.txt applied by stage-done, an unknown key ignored, a stale file removed by stage-start); session_call
   (a lost session is reseeded: the WARN line, the first attempt resumed, the second a new session whose prompt
   keeps the Role and Stage header first and carries facts.md, expansion.md and the latest gate verdict).
2. The angle loop through run.sh with the fake claude (47 checks): the gate fixture scores S1 every round, so the
   event lines are STEP, STEP, ANGLE (round 1/2), STEP, STEP, ANGLE (round 2/2), STEP, STEP, DROP with
   "still failing after 2 angle rounds (P3 S1 C3 F ok): ..." in the DROP line and the history line; rounds.angle
   is 2, gate.json is round 3 with gate-1 to gate-3 and angle-1 and angle-2 kept, the expansion rewritten by
   "04-angle round 2" with the earlier versions kept as expansion-r0.md and expansion-r1.md, the angle's new claim
   appended once as facts.md#8 and cited; the fake's log shows S1, S2, S3, S4, S3, S4, S3 with S2 and S4 resuming
   S1's session and every gate round a fresh session with the gate model, the research tools and the Bash rules
   for gh and the screenshot tool only, no tools for S2 and S3, the protected files denied; one FLAG for the
   missing account.md. Then a gate that passes on round 2 (GATE "passed (P3 S3 C3 F ok) after 1 angle round",
   the run continues through the 12 dummy stages to DONE exported #1), a research that found the core claim false
   (DROP at once with "facts don't hold (P3 S3 C3 F fail)" although the gate model scored it well, 04-angle still
   skipped) and a different-topic verdict (DROP, the suggestion in braces in logs/suggested-ideas.txt, nothing in
   ideas.txt).
3. The test idea with the real models (36 checks): S1 in 3 min 02 s (one call of 32 turns): 14 claims, all
   verified, 10 numbers, 5 screenshots (the plugin folder on GitHub, the Claude marketplace page, SKILL.md, the
   Anthropic article, the install docs), the core claim verified; S2 in 53 s: expansion.md of 1343 characters
   (1372 in the frozen run, where the first answer was 1645 characters and the retry cut it), keyword DESIGN
   (TELLS in the frozen run), NEW deliverable, 5 evidence lines; S3 in 24 s: `GATE   passed (P3 S3 C3 F ok)` with
   quoted evidence for P, S, C and F; S2 resumed S1's session and S3 ran fresh; the dummy stages after S4 exported
   #1; no em dash in any file. The frozen fixtures were written by the first run (M4_FREEZE=1).
4. The false idea with the real models (12 checks): S1 found the core claim false (11 claims, all verified, about
   what ffmpeg 8 really has; 4 screenshots), S2 still wrote an expansion, and the gate dropped the idea at once:
   `DROP ... dropped: facts don't hold (P2 S3 C3 F fail): the idea's core claim is false (...). Removed from
   ideas.txt`, the same reason with the scores in the history line, ideas.txt without the block and with nothing
   else written, state.json dropped, no ERROR or BLOCK line.

Earlier milestones: `test-m1.sh: 96 passed, 0 failed`, `test-limits.sh: 94 passed, 0 failed`,
`test-no-emdash.sh: 1 passed, 0 failed` (run alongside the M4 test). `test-m2.sh: 220 passed, 0 failed` (after its section 7 was updated as described above),
`test-m3.sh: 424 passed, 0 failed` (its section 4 called the real Opus reviewer and Sonnet fixer). One housekeeping
step came out of the scan: the frozen model answer calls/001-research.out.json held an em dash the model wrote
(the stages clean what they render, not the raw answers); the frozen copy was cleaned and the freeze step now cleans
every frozen file (DECISIONS.md 107).

## Known gaps
- The research quality depends on the model and the sites it reaches: a site that blocks headless Chromium gives no
  screenshot (the tool reports it, the stage warns when none was saved); the number of claims and screenshots
  varies between runs. The acceptance test asserts the shape (sources and dates on every claim, at least three
  claims, at least one screenshot) and the gate's pass on the test idea, not fixed numbers.
- library/profile/account.md does not exist yet (M5 drafts it), so every run carries the "account.md is missing"
  flag and the research assumes a generic developer-tools audience; library/profile/deliverables.txt is empty, so
  every keyword is NEW (HUMAN_TODO M1 and M4).
- The research call has no turn cap (a max-turns stop would be an error, not a result); the 45-minute timeout and
  the prompt's budget bound it. A long call is a transient timeout with its three retries, then a code error.
- The angle stage reseeds a lost session with facts.md and the latest gate verdict, but not with the screenshots the
  earlier session took (they are on disk and listed in facts.md's Assets section).
- Auto mode's classifier may approve harmless commands beyond gh and the screenshot tool (DECISIONS.md 104); the
  prompt forbids them and the protected files stay denied and guarded, but the fence is the prompt plus the guard,
  not the permission rules alone.

## HUMAN_TODO items added
- M4: run `bash pipeline/bin/setup-python` once after a Python reinstall or a move of the repo (Playwright and its
  Chromium, about 150 MB).
- M4: library/profile/account.md is missing until M5 (or until you write it); every reel carries the flag until then.
- M4: logs/suggested-ideas.txt holds the ideas the gate suggested instead of a dropped one; skim it now and then.
