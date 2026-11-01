# M4 review 1: Research, expansion, gate, angle (S1 to S4)

Reviewer: fresh session, 2026-11-01. Read BUILD_SPEC.md (sections 3, 4, 5 S1 to S4, 7, 9, 12), PLAN.md (M4),
DECISIONS.md 95 to 109, build/progress.md, build/HUMAN_TODO.md, build/M4/report.md, and the diff
57c885e..HEAD (commits 0a17a91, 85b39fc, 0643ce7). No earlier review or fix file exists for M4.

## Verdict

REJECTED, 2 required fixes. The acceptance test passes and the stages are well built (the model scores, the code
decides; the angle loop is file driven and crash safe; the reseed works); the two fixes are a project rule (an em
dash can reach a composed file) and the research model's gh permission being wider than the spec's read-only list.

## 1. Acceptance test (run by me)

`bash pipeline/tests/test-m4.sh`: **210 passed, 0 failed, exit 0**, about 13 minutes.
- Section 1 (units, no model): prompt.py, the screenshot tool against a local page (PNG, sidecar, reuse, blocked
  page saves nothing, folder outside runs/ refused), research.py, expansion.py, gate.py decide/suggest, reopen.txt in
  state.py, the session reseed: all pass.
- Section 2 (fake claude, the angle loop through run.sh): ANGLE round 1/2, ANGLE round 2/2, then DROP "still
  failing after 2 angle rounds (P3 S1 C3 F ok)"; the pass on round 2 continues to the dummy export; the false core
  claim drops at once with F fail; the different-topic verdict drops and writes logs/suggested-ideas.txt.
- Section 3 (real models, test idea): run took 253 s; 14 claims, all with URL and checked date; 5 screenshots;
  core claim verified; expansion.md 1221 characters with every part; `GATE passed (P3 S3 C3 F ok)`; S2 resumed S1's
  session, S3 fresh; dummy stages exported #1; no em dash in the stage files.
- Section 4 (real models, false idea): run took 290 s; research found the core claim false (12 claims, 3
  screenshots); `DROP ... dropped: facts don't hold (P3 S3 C3 F fail): the idea's core claim is false (...)`;
  history line with the scores; the block gone from ideas.txt and nothing else written; state dropped.

## 2. Earlier milestones (run by me)

- `test-m1.sh`: 96 passed, 0 failed.
- `test-m2.sh`: 220 passed, 0 failed (section 7 now stops at the first stage without run.sh, 05-hooks).
- `test-m3.sh`: 424 passed, 0 failed (its section 4 called the real reviewer and fixer).
- `test-limits.sh`: 94 passed, 0 failed.
- `test-no-emdash.sh`: 1 passed, 0 failed.
- Changed files scanned on bytes: no CR, no em dash; no `python3` call.

## Required fixes

1. **pipeline/stages/04-angle/run.sh (angle.json and angle-<n>.json): the model's `change` text is written
   without the em dash cleaning.**
   - Problem: `change="$(json_file_field "$AI_OUT" change "")"` takes the model's raw words (json_field in
     state.sh does not clean them) and the Python heredoc near the end writes them verbatim into angle.json and
     angle-<n>.json. CLAUDE.md and DECISIONS.md 95 say every text composed from a model's words is cleaned at the
     source (reels_undash, undash or errors.undash) and that no file may hold an em dash. The prompt asks the model
     not to write one, but the gate model in this very review's section 4 and the research model in the frozen
     fixture (DECISIONS.md 107) show the models do write them. Everything else the stages compose (research.py,
     expansion.py, gate.py, prompt.py, stage_drop, say) is cleaned; this is the one path that is not. The same raw
     text then flows into the next gate prompt's history (cleaned there by prompt.py, so only the JSON files are
     affected).
   - Expected: `change` cleaned before it is written (for example `reels_undash change` right after it is read,
     or errors.undash inside the heredoc), so angle.json and angle-<n>.json never hold U+2014.
   - Verify: a fixture variant of pipeline/tests/fixtures/fake/m4/04-angle.json whose `change` contains an em
     dash (written by the test with `printf '\xe2\x80\x94'`, so the repo file itself stays clean), run through the
     test-m4 section 2 angle loop, then `no_emdash_in` on 04-angle/angle.json and angle-1.json passes;
     `M4_SECTIONS="1 2" bash pipeline/tests/test-m4.sh` green.

2. **config.json research.allowed (and the fallback list in pipeline/stages/01-research/run.sh and
   04-angle/run.sh): `Bash(gh *)` and `Bash(gh:*)` pre-approve every gh subcommand for an unattended model that
   reads untrusted web pages.**
   - Problem: spec S1 gives the research model "Bash for the gh CLI (repo view, README, releases, stars, last
     commit)", that is read-only GitHub data. The rules approve any gh command with the user's logged-in GitHub
     account, without the auto mode classifier looking at it (an explicit allow rule skips it): `gh gist create`,
     `gh issue create`, `gh repo create`, `gh api -X POST/DELETE ...`, `gh release download -D <dir>`, `gh repo
     clone`, `gh auth token`. The research call runs WebFetch on arbitrary pages, so a prompt injected in a fetched
     page is enough to make the model act on the user's GitHub account (publishing a gist is an outward, hard to
     undo action). The prompt's "never run any other command" is the only fence today; protect.py guards the local
     protected files but not GitHub. DECISIONS.md 104 notes the classifier lets harmless commands through, which is
     fine for commands outside the rules; the problem is the rules themselves granting the mutating gh commands.
   - Expected: the allow rules list only the read-only forms the spec names, for example `Bash(gh repo view *)`,
     `Bash(gh release list *)`, `Bash(gh release view *)`, `Bash(gh api repos/*)` (and their colon forms if the
     CLI needs them), plus deny rules (through ai()'s `--disallow` or a config list) for the mutating forms of
     `gh api` (`-X`, `--method`, `-f`, `-F`, `--field`, `--raw-field`, `--input`) and for `gh auth *`, `gh gist *`,
     `gh * create *`, `gh * delete *`, `gh repo clone *`, `gh release download *`. Probe the rule syntax with the
     probe model as DECISIONS.md 104 did and record the result there; update the prompt's gh examples to the
     allowed forms (they already are) and the CONTRACT.md of 01-research and 04-angle.
   - Verify: test-m4 section 2 asserts from the fake claude's log that the research and angle calls' allowedTools
     contain no `Bash(gh *)` or `Bash(gh:*)` and that their disallowedTools contain the gh mutating rules; a probe
     (haiku, sandbox) shows `gh repo view cli/cli --json stargazerCount` runs without a prompt and `gh gist create`
     is refused; section 3 still gets the gh data (the test idea's numbers.json still has the stars or the last
     commit from gh).

## Repeated from earlier review

None (this is the first review of M4).

## Optional suggestions (no rejection)

- The core claim's note is cut at exactly 160 characters inside a word in the drop reason ("... 9:16 mode. The f)"),
  and a model reason ending in a period gives "assumes.." before ". Removed from ideas.txt". Cut at a word boundary
  with an ellipsis, and strip a trailing period from the reason before the runner appends its own.
- The STEP line into S4 reads "-> finding a better angle" (the state table's default) and the first heartbeat of S4
  too, while the spec's activity is "finding a better angle (round 1/2)". The round is known from the gate's
  decision when the gate finishes; state.py could take the activity from the reopening stage.
- 04-angle drops with "...; suggestion written to logs/suggested-ideas.txt" even when the model gave no suggestion
  (keeps_core_topic false with an empty suggested_idea). Say so only when a suggestion was written.
- Screenshots the research model takes during an angle round land in 01-research/assets/ but are not added to
  assets.json (append-claims rewrites assets.json unchanged). Run collect_assets in append-claims too.
- The research call has no turn cap and a 45 minute timeout, so a stuck call costs 45 minutes plus three retries.
  Logging the turn count from the call's JSON in the S1 INFO line would make drift visible.
