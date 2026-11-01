# 07-script: Script (S7)

Built in M6 (the folder, the first schema and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S7.

## Purpose
Fresh session D with the script model. pipeline/lib/script_checks.py reads the inputs once (setup: the pace from
voice.md, the length range from the Length line of tweaks.md with config lengths as the fallback, the video type
and the two tones from the brief's header, else from hook 1's family, hook 1 and hook 2 from judge.json, the
keyword and the identity from expansion.json, the pronunciations, the style's beat map). Round 1 writes two drafts
in two tones (draft B resumes session D so it differs from draft A), cuts each with the cut model (about 20 percent
fewer words, no number or name lost), runs humanize.py and every scripted check, and has the checks model map every
claim to facts.md. The judge model picks the draft the creator would say out loud (the voice excerpts as reference).
Rounds 2 and on rewrite the picked draft in session D with the failing checks as feedback. The code decides
everything: the model writes, cuts, maps and picks.

## Inputs
- 05-hooks/brief.md, 06-judge/judge.json (winner = hook 1, runner_up = hook 2), 01-research/facts.md,
  02-expansion/expansion.json (keyword, deliverable, identity, problem, solution)
- library/profile/voice.md (the pace wins over config voice.wpm; the verbatim excerpts feed the pick) and
  pronunciations.txt (applied to the spoken track); a missing or draft voice.md is the same flag S5 records
- styles/paper-cards/style.md (the Beat map section) and tweaks.md (the Length line in force)
- pipeline/vendor/ig-agent-skill/{beats.py, humanize.py, detect.py, slop.json}, imported as modules, unchanged
- config: script.*, caps.script_rounds, lengths, voice.wpm, timeouts.script_seconds, cut_seconds, checks_seconds,
  pick_seconds, models.script, models.cut, models.checks, models.judge

## Outputs (in runs/<id>/07-script/)
- script.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). The model answers are validated by ai()'s one schema retry
  against model.schema.json (a draft or a rewrite), cut.schema.json, claims.schema.json, pick.schema.json and
  rewrite-line.schema.json.
- script.json: tone, tones, picked, pick (order, winner, reason), drafts (both, with their cut), video_type,
  length_s, target_seconds, estimated_seconds, wpm, words, hook (hook 1), hook2 (display, spoken, card for the
  alternate clip), beats[] (id b1.., type, display, spoken, emphasis of at most 3 words, card of 1 to 6 words,
  card_words, facts, seconds), ask (keyword, line, loop_word, deliverable), cut (before, after, removed_pct, ok),
  checks (ok, hard, soft, info, summary, detail: beats, structure, stake, ask, requirements, length, cards, hook,
  detect, humanize, claims), rounds, rounds_log, flags, pronunciations, spoken_changes, rewrites (S8's one-line
  rewrites, empty at first)
- plan.json, draft-<a|b>.r<n>.json (the written drafts), draft-<a|b>.r1.cut<k>.json and .cut.json (the cut
  attempts and the one kept), checks-<a|b>-r<n>.json (the reports), pick-data.json, pick.json, rounds.json,
  prompt-*.md, calls/ (every model call)
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 20 (block).

## Invariants
- The structure: beat 1 is the hook with hook 1's spoken line as display (word for word, forced by the code) and
  its on-screen line as card; a stake right after it (seconds 2 to 7, at most script.stake_max_s, naming the share
  identity); at least script.min_body_beats body beats with a type each (number, tool, step, comparison, proof,
  mechanism, before-after, pain-payoff); a payoff; the ask last, one ask only, with the expansion's keyword and one
  word repeated from the hook (the loop).
- Two tracks per beat: display (digits, names, exact commands) and spoken (numbers written out and pronunciations
  applied; the code applies both after the model), plus the card (6 words or fewer) and the emphasis words (present
  in the display line).
- Length 25 to 40 s, or 45 to 75 s for list and explainer videos (tweaks.md); words = seconds x wpm / 60, measured
  on the longer of the two tracks; the hook 3 s or less; no beat over 4 s; no 3 beats in a row without a number
  or a name; humanize.py then detect.py PASS (overall 70 or more, no check under 55); zero placeholders; every
  claim supported by a verified claim of facts.md in the same strength.
- Hard failures (facts, placeholders, a missing requirement: stake, identity, keyword, hook line; a second ask; the
  structure; the length off by more than script.length_tolerance_pct) left after caps.script_rounds rounds block the
  idea (exit 20), unless the other draft passed every hard check in round 1 (it is used, with a NEEDS REVIEW flag).
  Soft failures (detect.py, the beats timing, the stake timing, the length within the tolerance, the cards, a cut
  outside 10 to 30 percent) continue with one NEEDS REVIEW flag per check.
- No em dash anywhere: every model text is cleaned when it is read; humanize.py also turns one into a comma.
- The stage writes only under runs/<id>/07-script/ (and the flags in state.json).

## S8's one-line rewrite
`bash pipeline/stages/07-script/run.sh <run_dir> --rewrite-line <beat id> [--reason "<why>"]`: the beat's spoken
track rewritten in simpler words by the script model (session D resumed when it still exists), the pronunciations
and numbers applied again, the display track updated where a word changed, the change appended to script.json
"rewrites". Exit 0 rewritten, 4 when the model gave no usable line in two tries (script.json unchanged), 1 on a
code error. The caller re-validates nothing: the line keeps its length or gets shorter.

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea
(reason in result.json; not used by this stage), 20 block the idea (hard failures after every round), anything
else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2).

## Model and session
Session D (fresh for this stage; the two drafts and the rewrites share it, a lost session gets the self-contained
prompt again). Models: config models.script (drafts, rewrites, the one-line rewrite), models.cut (the cut pass,
fresh session, a retry resumes it), models.checks (the claims check, fresh), models.judge (the pick, fresh). No
tools on any call. Happy path: 7 calls (2 drafts, 2 cuts, 2 claims checks, 1 pick); each rewrite round adds 2.

## dummy.sh
`bash pipeline/stages/07-script/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
