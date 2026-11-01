# 01-research: Research (S1)

Built in M4 (the folder, this contract, schema.json and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S1.

## Purpose
Get the facts right as of today (not virality: the user validated the idea before writing it). Session A with the
research model; tools WebSearch, WebFetch, Read and Bash restricted to `gh ...` and `bash pipeline/bin/screenshot`
(config research.tools and research.allowed). The model answers with one JSON object (model.schema.json) and
pipeline/lib/research.py writes the files below from it, so their format never depends on the model.

## Inputs
- the idea text (<run>/idea.txt, state.json idea.text)
- library/profile/account.md (topics in and out); when it is missing the stage continues with default audience
  assumptions and records a NEEDS REVIEW flag (BUILD_SPEC.md 2.3)
- today's date (the "checked" date of every claim)
- the restart note <stage>/restart-note.md when the runner restarts the stage after an automatic fix (read and
  removed by stage_begin, passed to the model as a note)

## Outputs (in runs/<id>/01-research/)
- research.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). It holds idea_id, checked, core_claim {text, status verified |
  false | unverified, note}, claims (numbered n, claim, url, tier primary | vendor | press | forum, status, checked,
  note, added_by), numbers (keyed by name: value, unit, url, checked), pitfalls, one_true_thing candidates,
  unverified, assets, summary, sources and counts.
- facts.md: rendered from research.json: the core claim and its status, then every claim as
  `n. <claim> [tier, status]: <url> (checked YYYY-MM-DD)`, verified before unverified before false and primary
  sources first within a status, then numbers, pitfalls, the one specific true thing candidates, the unverified
  list, the assets and the research summary. Pointers such as facts.md#3 (used by the expansion and the gate)
  are these numbers; later additions (the angle stage) continue the numbering and never renumber.
- numbers.json: the numbers object of research.json.
- assets/ plus assets.json: screenshots of the real pages taken by the model with pipeline/bin/screenshot
  (Playwright, headless Chromium, 1080 px wide; NN-name.png with a NN-name.json sidecar holding url, final_url,
  title, status, captured). assets.json lists the screenshots whose file exists (at most research.max_assets),
  each with its URL, capture date and the model's one-line caption.
- prompt-research.md: the rendered prompt; calls/: every model call's files (ai.sh).
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block); this stage never does either: a false
  core claim is recorded in research.json and the gate drops the idea.

## Invariants
- never invent anything; a key fact that cannot be verified is listed as unverified, a contradicted one as false
- primary sources first: official repo and docs, then the vendor's blog, then press, forums last
- no getting around sites that block automated access: pipeline/bin/screenshot reports a block and saves nothing,
  and the prompt forbids workarounds
- the model never writes files itself: it may only run gh and the screenshot tool (which writes only inside the
  runs folder); ai() denies and guards the protected files (ideas.txt, library/, styles/, exports/)
- no em dash in any output file (research.py cleans every text)
- the session id of session A is stored in state.json (sessions.A) for S2, S4 and S5; when the session no longer
  exists on a later resume, session_call starts a new one seeded with facts.md, expansion.md and the latest gate
  feedback (pipeline/lib/session.sh)

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea
(reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the
review and fix loop (BUILD_SPEC.md 4.2). A failed model call (a schema still invalid after the one retry, a fatal
CLI error) is reported in <stage>/error.json by ai() and the stage exits 1.

## Model and session
Session A (shared with S2, S4 and S5, resumed with --resume). Model: config models.research. Timeout
config timeouts.research_seconds.

## dummy.sh
`bash pipeline/stages/01-research/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
