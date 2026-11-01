# M4 review 2: Research, expansion, gate, angle (S1 to S4)

Reviewer: fresh session, 2026-11-01. Read BUILD_SPEC.md (sections 3, 4, 5 S1 to S4, 7, 12), CLAUDE.md, PLAN.md
(M4), DECISIONS.md 95 to 111, build/progress.md, build/HUMAN_TODO.md, pipeline/knowledge/known-issues.md,
build/M4/report.md, review-1.md, fixes-1.md, and the diff 57c885e..HEAD (commits 0a17a91, 85b39fc, 0643ce7,
2f61db1, 290d8d1).

## Verdict

REJECTED, 1 required fix. Both fixes of review 1 are applied correctly and tested (details below). But the
acceptance test failed in my run: the real gate model dropped the true test idea at once with "F fail". It blamed
two wording slips in the expansion that the pipeline itself wrote, while the research had verified the core claim.
The code follows the letter of "F failing: drop immediately". The result is that a valid idea is deleted from
ideas.txt over a statement the pipeline could have removed, and the acceptance test passes or fails by chance.

## 1. Acceptance test (run by me)

`bash pipeline/tests/run-all.sh`, exit 1: "6 test files, 1 failed: test-m4.sh".
`test-m4.sh: 210 passed, 4 failed`.
- Section 1 (units) and section 2 (the angle loop with the fake claude): all pass, including the 3 checks of fix 1
  (the model's em dashes in `change` become commas in angle-1.json; angle.json, angle-1.json, angle-2.json and
  prompt-angle-r2.md hold no em dash) and the 2 checks of fix 2 (the S1 and both S4 calls carry only the read-only
  gh allow rules and carry the deny rules).
- Section 3 (the test idea, real models; run took 225 s). S1 found 14 claims (all verified), 10 numbers and 5
  screenshots, and the core claim verified. The permission system refused no Bash call
  (permission_denials empty), and 7 numbers come from github.com, so the narrowed gh rules still get the stars and
  the dates. S2 wrote 1254 characters, keyword DESIGN, every rule held. Then S3:
  `DROP idea "Claude Code's frontend-design skill: it ..." dropped: facts don't hold (P3 S3 C3 F fail): The pain,
  sharer and deliverable are all sharp, ... Facts fail because "serif" is not in the research (Inter is
  sans-serif), and "one command adds" skips the scope-picking step the docs describe.. Removed from ideas.txt`.
  4 checks failed: `GATE passed`, `DONE exported #1`, `gate.json: pass` (got false), and `history: exported`.
  Everything else in the section passed (facts.md with URL and date on every line, expansion 500 to 1500 characters,
  gate.json valid, sessions, no em dash).
- Section 4 (the false idea, real models; run took 367 s): S1 found the core claim false (11 claims, 3
  screenshots). The run printed `DROP ... dropped: facts don't hold (P2 S2 C3 F fail): the idea's core claim is
  false (...)`, the block left ideas.txt and the history line carries the scores. All pass.

## 2. Earlier milestones (run by me, same run-all)

- `test-m1.sh: 96 passed, 0 failed`
- `test-m2.sh: 220 passed, 0 failed`
- `test-m3.sh: 424 passed, 0 failed` (section 4 called the real reviewer and fixer)
- `test-limits.sh: 94 passed, 0 failed`
- `test-no-emdash.sh: 1 passed, 0 failed`
- Every file changed since 57c885e, plus build-runner.sh, tools/voice.py and review-1.md, scanned on bytes: no CR
  (only in the binary PNG fixtures) and no em dash. No `python3` call. `bash -n` passes on the changed scripts and
  config.json parses.

## Review 1 fixes, checked

- Fix 1: `reels_undash change` comes right after the field is read in pipeline/stages/04-angle/run.sh, so
  angle.json, angle-<n>.json, the drop reason and the INFO line are all cleaned. The suggestion goes through
  gate.py suggest, which cleans it.
- Fix 2: research_call_args (pipeline/lib/stage.sh) is shared by S1 and S4. The allow list holds only the read-only
  forms. The deny list covers auth, gist, clone, download, the writing verbs and the mutating `gh api` flags in any
  position. ai() gained `--deny RULE`. The probe script, DECISIONS.md 111 and both CONTRACT.md files are updated.
  session_call passes every option through, so a reseeded session keeps the rules.

## Required fixes

1. **pipeline/lib/gate.py, pipeline/stages/03-gate/prompt.md and model.schema.json (with 02-expansion's prompt as
   needed): an F fail caused only by the expansion's wording drops a true idea at once.**
   - Problem: gate.py lets the model's F verdict decide alone: `f_verdict = model_f if core_status == "verified"
     else "fail"`, and any F fail ends in decision drop. The F criterion in the prompt fails "when any statement is
     not in facts.md". The expansion is written by the pipeline's own S2 (or S4), so one slip of the writing model
     (here "serif", and "one command adds" without the scope step) kills an idea whose core claim the research
     verified. The idea is deleted from ideas.txt, and the only trace is a history line. Spec S3 gives the reasons
     F fails as "the tool does not do what the idea assumes, it is deprecated, or the claims cannot be verified".
     Those are faults of the idea. A sentence that can simply be dropped from the expansion is not one. Spec S4
     exists to rewrite expansion.md. The verdict is also unstable between runs: the frozen fixture's expansion
     (pipeline/tests/fixtures/runs/test-idea/02-expansion/expansion.md) says "One command installs ..." and passed
     with F ok, while today the same kind of sentence failed. So M4's acceptance test (the test idea must reach and
     pass the gate) passes or fails by chance. It failed in this review after passing in the report, in review 1
     and in fixes 1.
   - Expected: tell apart an F fail of the idea from an F fail of the wording.
     - The gate model also says what kind of F fail it found, for example `F_kind: "core" | "wording"` in
       model.schema.json and the prompt. "core" means the tool does not do what the idea assumes, it is deprecated,
       or the core cannot be verified. "wording" means a statement in the expansion that is not in facts.md, while
       the idea still holds without it.
     - gate.py drops at once in these cases, exactly as today: the core status is false or unverified (code-forced,
       unchanged), or the model's F_kind is "core".
     - An F fail of kind "wording" with a verified core claim becomes a repair. Either a decision angle (S4 rewrites
       the expansion with the quoted statements as the hint, counted against caps.angle_rounds), or a dedicated
       single repair of the expansion in session A followed by one more gate round. Drop only when F still fails
       after it, with the scores and the reason as today.
     - Record the choice in DECISIONS.md as the reading of spec S3 ("drop immediately" applies to the idea's facts,
       not to a wording slip the pipeline can fix).
     - Tighten the S2 and S4 prompts so the expansion keeps the core claim's exact wording from facts.md (for
       example the install steps as the docs give them).
   - Verify:
     - Unit tests in test-m4 section 1 for gate.py decide: F fail of kind wording with core verified gives a repair
       or angle decision, not a drop. F fail of kind core gives a drop. Core false or unverified gives a drop
       whatever the kind.
     - A section 2 fixture run: the gate fails F (wording) on round 1 and passes on round 2. Expect the repair or
       ANGLE line, then `GATE passed ... after 1 ...`, then DONE exported #1.
     - The existing false-core and different-topic cases unchanged.
     - `bash pipeline/tests/test-m4.sh` green, with section 3 run at least twice in a row (for example
       `M4_SECTIONS=3` twice) and the test idea reaching `GATE passed` both times.

## Repeated from earlier review

None. Review 1's two required fixes are applied and verified above; this fix is new.

## Optional suggestions (no rejection)

- Still open from review 1: the drop reason doubles the period ("the docs describe.. Removed from ideas.txt",
  visible again in this run). Strip a trailing period from the model's reason before the runner appends its own.
  The core note is also cut at 160 characters in mid word ("... and no automatic reel,)").
- "kept at /tmp/tmp.../runs/..." is printed for the real runs, but the sandbox is removed at the end unless
  KEEP_SANDBOX=1. When a real section fails, keep the sandbox (or copy the run folder to build/ or /tmp) so the
  gate.json and expansion.md of a failed model run can be read afterwards.
- A deny rule such as `Bash(gh * create *)` needs text after the verb. A bare `gh repo fork` or `gh issue create`
  with no arguments falls to auto mode's classifier rather than the deny list. Most of these fail without a TTY
  anyway, but adding the bare forms (`Bash(gh * fork)`, and so on) would close the gap.
- Review 1's other suggestions (the STEP activity round number, the "suggestion written" text when there is none,
  assets.json in append-claims, the turn count in the S1 INFO line) are still open.
