# 02-expansion: Expansion (S2)

Built in M4 (the folder, this contract, schema.json and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S2.

## Purpose
Turn the researched idea into the viewer's problem and the solution, the share driver, the comment keyword with its
deliverable, the one specific true thing and the evidence lines (BUILD_SPEC.md S2). Session A resumed, so the
research is in context; no tools. The model answers with the parts as fields (model.schema.json);
pipeline/lib/expansion.py checks the rules and composes expansion.md in one fixed layout.

## Inputs
- 01-research/facts.md and research.json (the claims, their numbers and statuses)
- library/profile/deliverables.txt (KEYWORD | what they get | link, or "to create"); an empty or missing file means
  every deliverable is NEW
- library/profile/account.md (a NEEDS REVIEW flag when missing, as in S1)
- config research.expansion_chars ([500, 1500]) and research.expansion_tries (3)
- the restart note after an automatic fix (passed to the model)

## Outputs (in runs/<id>/02-expansion/)
- expansion.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). Fields: problem, solution, share_identity, takeaway, keyword,
  deliverable, deliverable_status (existing or new), deliverable_link, one_true_thing, evidence (lines
  "facts.md#n: note"), evidence_refs, chars, round (0 here, the angle round number when 04-angle rewrote it),
  written_by, checked, rule_errors (empty unless the last try was written by force).
- expansion.md: the same as prose, 500 to 1500 characters, in this layout: a title line, "Problem:", "Solution:",
  "Share driver: <identity>. Takeaway worth forwarding: <takeaway>", "Comment keyword: <KEYWORD>. Deliverable
  (existing): ... (link)" or "Deliverable (NEW, to create): ...", "One specific true thing:", and "Evidence:" with
  one "- facts.md#n: note" line per pointer.
- expansion.candidate.md: the last composed text, whether or not it passed the checks.
- prompt-expansion.md and prompt-expansion-fixN.md: the rendered prompts; calls/: the model calls (ai.sh).
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block); this stage never does either.

## Invariants (checked by expansion.py, asked again on failure, flagged when still broken on the last try)
- the problem is one first-person sentence (I, my, me) and a single sentence
- the share driver names a specific identity (at least two words)
- the keyword is one word of 3 to 20 letters or digits, written in capitals
- a keyword that is not in deliverables.txt is NEW whatever the model said, and a NEW deliverable is described
  concretely; a keyword that is in the file is existing, with the file's link
- 2 to 6 evidence pointers, each naming a claim of facts.md that is marked verified
- expansion.md is between research.expansion_chars (500 and 1500 characters)
- the core topic of the idea is kept (a rule of the prompt; the gate checks the result)
- no em dash in any output file

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea
(reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the
review and fix loop (BUILD_SPEC.md 4.2).

## Model and session
Session A resumed (session_call reseeds a lost session with facts.md and the idea). Model: config models.research.
Timeout config timeouts.expansion_seconds.

## dummy.sh
`bash pipeline/stages/02-expansion/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
