# M4 fixes 1: Research, expansion, gate, angle (S1 to S4)

Fixed 2026-11-01 after build/M4/review-1.md (REJECTED, 2 required fixes), in a fresh session. Read BUILD_SPEC.md
(sections 3, 4, 5 S1 to S4, 12), CLAUDE.md, PLAN.md (M4), DECISIONS.md (95 to 109), build/progress.md,
build/HUMAN_TODO.md, pipeline/knowledge/known-issues.md, build/M4/report.md and review-1.md (the first review of
M4; no earlier fix notes exist). Only the two required fixes were applied; the optional suggestions of the review
were left alone. The pre-existing uncommitted changes in the working tree (build-runner.sh, tools/voice.py) are not
part of this batch and were not touched.

## Required fix 1: the angle stage wrote the model's `change` text without the em dash cleaning

What changed (pipeline/stages/04-angle/run.sh, CONTRACT.md; DECISIONS.md 110):
- `reels_undash change` right after `change="$(json_file_field "$AI_OUT" change "")"`. json_field does not clean,
  and the Python heredoc at the end of the stage wrote the raw text into angle.json and angle-<n>.json; the other
  uses (the drop reason through stage_drop, the INFO line through say, the next round's "Earlier angle rounds"
  section through prompt.py) were already cleaned, so the two JSON files were the one path where a model's em dash
  reached a file. With the variable cleaned at the source, every use gets the comma form.
- The contract's invariant "no em dash in any output file" now says where the cleaning happens.

How verified (pipeline/tests/test-m4.sh section 2, the angle loop through run.sh with the fake claude):
- Before the first run, the test rewrites the sandbox copy of the 04-angle fixture so that `change` carries two em
  dashes (`chr(0x2014)` in the test, written into the sandbox file only, so the repo fixture stays clean):
  "...the three banned defaults" + em dash + "so it survives without the video " + em dash + " and the identity
  is narrower...". The INFO line, the DROP line and the prompts of the loop are composed from that text.
- New checks: `angle-1.json: the em dashes the model wrote in "change" became commas before the file was written`
  (the field equals "The share line now names the three banned defaults, so it survives without the video, and
  the identity is narrower: freelancers who ship client landing pages.") and `angle.json, angle-1.json,
  angle-2.json and the second round's prompt hold no em dash` (a byte scan for U+2014, which also covers
  prompt-angle-r2.md, where the first round's change is quoted back to the model).
- Without the fix the same test fails on both checks (the raw text reaches angle-1.json). With it:
  `M4_SECTIONS="1 2" bash pipeline/tests/test-m4.sh`: 166 passed, 0 failed (163 before, plus the 3 checks of this
  batch; the loop's event lines, the DROP line and the history line are unchanged).

## Required fix 2: `Bash(gh *)` pre-approved every gh subcommand for a model that reads untrusted pages

What changed (config.json, pipeline/lib/stage.sh, pipeline/lib/ai.sh, pipeline/stages/01-research/run.sh,
prompt.md and CONTRACT.md, pipeline/stages/04-angle/run.sh, prompt.md and CONTRACT.md, pipeline/tests/test-m4.sh,
pipeline/tests/probe-gh-rules.sh; DECISIONS.md 111 and a pointer in 104):
- config research.allowed now lists only the read-only forms spec S1 names: `Bash(gh repo view *)` (the README too,
  without --json), `Bash(gh release list *)`, `Bash(gh release view *)`, `Bash(gh api repos/*)`, plus WebSearch,
  WebFetch, Read and `Bash(bash pipeline/bin/screenshot *)`. The colon forms were dropped: the Claude Code
  permissions reference states that `:*` is the same as a trailing ` *` (confirmed by the probe below).
- The new config research.denied lists the gh forms that act on the account or the disk: `Bash(gh auth *)`,
  `Bash(gh gist *)`, `Bash(gh repo clone *)`, `Bash(gh release download *)`, the writing verbs as
  `Bash(gh * <verb> *)` (create, delete, edit, comment, merge, close, reopen, review, fork, sync, transfer, lock,
  upload, run, rerun, cancel, set, add, archive, rename) and the `gh api` mutating flags in any position as
  `Bash(gh api* -X*)`, `Bash(gh api* --method*)`, `Bash(gh api* -f*)`, `Bash(gh api* -F*)`,
  `Bash(gh api* --field*)`, `Bash(gh api* --raw-field*)`, `Bash(gh api* --input*)`. A deny rule resolves before the
  classifier in every permission mode and applies to every subcommand of a compound command, which is why the
  deny list exists although the allow list is narrow (a command outside the allow rules goes to auto mode's
  classifier, a judgement; the deny rules are a hard fence). The patterns keep a space before the flag and after
  the verb, so a repository named foo-Xbar or `--json createdAt` is not caught.
- `research_call_args` (pipeline/lib/stage.sh) fills RESEARCH_CALL_ARGS with `--tools`, one `--allow` per rule of
  research.allowed and one `--deny` per rule of research.denied, with the same lists as defaults when a key is
  missing or empty; 01-research/run.sh and 04-angle/run.sh call it instead of each building its own allow list
  (their old fallback lists held `Bash(gh *)`).
- ai() has the repeatable `--deny RULE` option (verbatim, like `--allow`), because the space-separated `--disallow`
  string cannot carry a rule with spaces; the rules land in `--disallowedTools` after the protected-file rules.
- The research prompt names the four allowed forms with examples that match the rules (`gh api
  repos/owner/name/commits?per_page=1 --jq ...` with the endpoint unquoted, see the probe) and says that every other
  gh command, and `gh api` with a method or field flag, is refused; the angle prompt points to the same forms. Both
  CONTRACT.md files describe the allowed and denied forms and why.

How verified:
- Probe with the real probe model (haiku), `bash pipeline/tests/probe-gh-rules.sh both` (new, not part of
  run-all.sh; real calls, needs the gh login). It asks the model to run 16 fixed commands one per Bash call and to
  report each as ran or refused; every command is harmless even if a rule failed (a missing file, a missing
  endpoint, a repository that does not exist); the script also prints the Bash calls listed in the result's
  permission_denials.
  - Auto mode through ai(), the production path (17 turns): the six read-only forms ran (`gh repo view cli/cli
    --json stargazerCount` printed 46828 stars; `gh release list -R cli/cli --limit 2`; `gh release view -R cli/cli
    --json tagName`; `gh api repos/cli/cli --jq .stargazers_count`; `gh api repos/cli/cli/commits?per_page=1 --jq
    ".[0].sha"` quoted and unquoted) and the ten writing forms were refused by the permission system, each with
    "Permission to use Bash with command ... has been denied" and all ten in permission_denials: `gh gist create
    /nonexistent/probe.txt`, `gh api -X POST repos/cli/cli/nonexistent-probe`, `gh api repos/cli/cli/nonexistent-probe
    -f title=probe`, `gh api repos/cli/cli/nonexistent-probe --method DELETE`, `gh auth status`, `gh label create
    probe-label -R nonexistent-owner-probe/nonexistent-repo`, `gh repo clone nonexistent-owner-probe/nonexistent-repo`,
    `gh release download -R nonexistent-owner-probe/nonexistent-repo`, `gh workflow run probe.yml -R
    nonexistent-owner-probe/nonexistent-repo` and the compound `gh repo view cli/cli --json stargazerCount && gh gist
    create /nonexistent/probe.txt`.
  - Manual mode with the same rules (`claude -p --permission-mode manual --permission-prompts none`, so anything
    outside the allow rules is refused: this shows what the rules alone approve): the same ten refused, the
    read-only forms ran, except the quoted endpoint `gh api "repos/cli/cli/commits?per_page=1"`, which
    `Bash(gh api repos/*)` does not match because the quote comes before repos/ (auto mode's classifier had let it
    through). Hence the prompt's unquoted example and its note.
  - No warning on stderr from the CLI for either run (the `*` before the verb is in deny rules only; the reference
    warns for allow rules).
- pipeline/tests/test-m4.sh section 2 (fake claude): `S1 and S4: Bash is approved only for the read-only gh forms
  and the screenshot tool, never for every gh command` checks the research call and both angle calls for the five
  allow rules and for the absence of `Bash(gh *)`, `Bash(gh:*)`, `Bash(gh*` and a bare Bash; `S1 and S4: the gh
  forms that write are denied (...)` checks that the three calls carry the deny rules (auth, gist, clone, download,
  create, delete, comment and the seven gh api flag rules). Both pass; the old `S1: Bash is approved only for gh and
  the screenshot tool` check was replaced.
- pipeline/tests/test-m4.sh section 3 (the test idea with the real models): a new check `S1: the permission rules
  refused no read-only gh command` reads permission_denials from the research call's raw result and fails when a
  `gh repo view`, `gh release list`, `gh release view` or `gh api repos/` command without a mutating flag was
  refused; the section also prints the refused Bash calls and the numbers whose source is on github.com (the gh
  data of the review's verify step). The results of the real run are in "Test results" below.

## Test results

`bash pipeline/tests/run-all.sh` on 2026-11-01 after the fixes, on a quiet machine (about 55 minutes), exit 0,
"6 test files, all passed":
- `test-m1.sh: 96 passed, 0 failed`.
- `test-m2.sh: 220 passed, 0 failed` (its heartbeat-timing section included).
- `test-m3.sh: 424 passed, 0 failed` (section 4 called the real Opus reviewer and Sonnet fixer).
- `test-m4.sh: 214 passed, 0 failed`: the 210 checks of the review's run plus the 3 checks of fix 1 (section 2) and
  the 1 check of fix 2 (section 3). Section 3, the test idea with the real models: the run took 260 s; S1 in 2m44s
  with 14 claims (all verified), 9 numbers, 5 screenshots and the core claim verified; the permission system
  refused no Bash call at all in S1 (permission_denials empty), and six of the nine numbers have their source on
  github.com (plugin_version, anthropics_skills_stars, anthropics_claude_plugins_official_stars,
  last_skill_update, skill_md_size, ai_default_cream_background), so the research still gets the stars and the
  last update with the narrowed rules; S2 asked once more (a two-sentence problem) and wrote 1362 characters with
  the keyword TELLS; `GATE   passed (P3 S3 C3 F ok)`; the dummy stages exported #1; no em dash in the stage files.
  Section 4, the false idea with the real models: S1 found the core claim false (10 claims, all verified, 9
  numbers, 3 screenshots); `DROP ... dropped: facts don't hold (P2 S2 C3 F fail): the idea's core claim is false
  (No such flag exists. The official FFmpeg Changelog ...)`; the block gone from ideas.txt.
- `test-limits.sh: 94 passed, 0 failed`; `test-no-emdash.sh: 1 passed, 0 failed` (the scan covers the new probe
  script, this file and every changed file).
- Earlier in the batch: `M4_SECTIONS="1 2" bash pipeline/tests/test-m4.sh`: 166 passed, 0 failed; the probe
  `bash pipeline/tests/probe-gh-rules.sh both`: exit 0, its output quoted under fix 2.
- The changed files scanned on bytes: no CR, no em dash; `bash -n` on every changed script; config.json parses.

Commits: `2f61db1 fix(M4): the angle stage cleans the model's change text; the research model's gh rules are
read-only, the writing forms denied` (the code, config, prompts, contracts, the test, the probe script, DECISIONS.md
110 and 111 plus the pointer in 104, build/progress.md) and `docs(M4): fixes 1 notes` (this file). The
pre-existing uncommitted changes (build-runner.sh, tools/voice.py) and build/M4/review-1.md were left as they were.
Nothing was added to build/HUMAN_TODO.md: nothing needs the user (the gh login stays as it is; the rules make the
research model's use of it read-only).
