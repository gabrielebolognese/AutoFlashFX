# pipeline/lib/review.sh: the review and fix loop (BUILD_SPEC.md 4.2). Source common.sh, log.sh, config.sh,
# state.sh, status.sh and ai.sh first.
#
# A code error in a stage (a non-zero exit, an exception, an output still invalid after the stage's schema retry)
# goes: error file -> reviewer -> fix file -> fixer -> verify -> commit -> restart the stage. Caps per stage per
# idea: caps.error_review_cycles (3) cycles with the Opus reviewer; when the same error signature appears
# errors.repeated_signature_skip (2) times in a row the remaining Opus cycles are skipped; then one escalation
# cycle with the Fable reviewer (caps.escalation_cycles); then the idea is blocked. A reviewer verdict with
# auto_apply no blocks the idea at once with what the user must do. The runner keeps the counters in state.json
# under errors.<stage> (cycles, escalated, repeats, last_signature, failures, last_outcome).
#
# Runner side (pipeline/lib/runner.sh calls these):
#   review_note_failure RUN_DIR STAGE SIGNATURE   count a stage failure: repeats of the same signature in a row
#   review_decide RUN_DIR STAGE                   -> REVIEW_KIND (opus | fable | block), REVIEW_CYCLE (1-based),
#                                                 REVIEW_CAP, REVIEW_DONE (Opus cycles so far), REVIEW_N (the number
#                                                 of the next E file), REVIEW_REASON (when block)
#   review_record RUN_DIR STAGE KIND N OUTCOME    count the cycle after it ran
#   review_restart_note RUN_DIR STAGE "MSG" N "SUMMARY" "COMMIT"   write <stage>/restart-note.md for the restart
# Child side (pipeline/bin/review-cycle, a background child of the runner so the heartbeat keeps printing):
#   review_error_file RUN_DIR STAGE N RC "MSG" "CMD"     errors/E<n>.md: the stage, command and exit code, the last
#                                                 errors.log_tail_lines of stage.log, the input files, CONTRACT.md,
#                                                 the git diff since the last successful run (logs/.last-good-sha),
#                                                 the previous E and F files of this stage
#   review_cycle RUN_DIR STAGE LABEL N KIND CYCLE CAP RC "MSG" "CMD"   the whole cycle; writes fixes/F<n>.md (rendered
#                                                 from the reviewer's structured output, fixes/F<n>.json),
#                                                 fixes/F<n>.fixer.json, fixes/F<n>.verify.log and
#                                                 fixes/F<n>.result.json {outcome: fixed | no_auto | failed | error,
#                                                 summary, commit, reason, class, root_cause, user_action, fatal}
#   review_write_result FILE key=value...         write a result JSON
#
# The fixer may edit only the paths in config review.fixer_paths (pipeline, motion-lib/candidates): its tools are
# pre-approved on those paths only, the protected files are denied (ai.sh), and pipeline/lib/treeguard.py puts back
# anything it changed elsewhere without touching the user's own uncommitted files. The fixer does not commit: this
# script runs the verify command again, appends the known-issues line and commits `autofix(<stage>): <summary>`.

REVIEW_KIND=""; REVIEW_CYCLE=0; REVIEW_CAP=0; REVIEW_DONE=0; REVIEW_N=1; REVIEW_REASON=""; REVIEW_REPEATS=0

review_known_issues_file() { printf '%s/%s' "$REELS_REPO" "$(cfg paths.known_issues pipeline/knowledge/known-issues.md)"; }

review_fixer_paths() { cfg review.fixer_paths '["pipeline","motion-lib/candidates"]' | tr -d '[]"' | tr ',' ' '; }

# ------------------------------------------------------------------ runner side

review_note_failure() {  # RUN_DIR STAGE SIGNATURE
  local run_dir="$1" stage="$2" sig="$3" last repeats failures
  last="$(state_get "$run_dir" "errors.$stage.last_signature" "")"
  repeats="$(state_get "$run_dir" "errors.$stage.repeats" 0)"
  failures="$(state_get "$run_dir" "errors.$stage.failures" 0)"
  if [ -n "$sig" ] && [ "$sig" = "$last" ]; then repeats=$((repeats + 1)); else repeats=1; fi
  state_set "$run_dir" "errors.$stage.last_signature=\"$sig\"" "errors.$stage.repeats=$repeats" \
    "errors.$stage.failures=$((failures + 1))" >/dev/null 2>&1
  REVIEW_REPEATS="$repeats"
}

review_decide() {  # RUN_DIR STAGE
  local run_dir="$1" stage="$2" cycles escalated repeats cap skip esc
  cycles="$(state_get "$run_dir" "errors.$stage.cycles" 0)"
  escalated="$(state_get "$run_dir" "errors.$stage.escalated" false)"
  repeats="$(state_get "$run_dir" "errors.$stage.repeats" 1)"
  cap="$(cfg caps.error_review_cycles 3)"
  skip="$(cfg errors.repeated_signature_skip 2)"
  esc="$(cfg caps.escalation_cycles 1)"
  REVIEW_DONE="$cycles"; REVIEW_CAP="$cap"; REVIEW_CYCLE=$((cycles + 1)); REVIEW_REASON=""
  REVIEW_N=$(( $(ls "$run_dir/errors" 2>/dev/null | grep -c -E '^E[0-9]+\.md$') + 1 ))
  if [ "$escalated" = true ]; then
    REVIEW_KIND=block
    REVIEW_REASON="still failing after $cycles $(plural "$cycles" "review cycle") and the escalated review"
  elif [ "$cycles" -lt "$cap" ] && [ "$repeats" -lt "$skip" ]; then
    REVIEW_KIND=opus
  elif [ "$esc" -gt 0 ]; then
    REVIEW_KIND=fable
  else
    REVIEW_KIND=block
    REVIEW_REASON="still failing after $cycles $(plural "$cycles" "review cycle") (no escalation configured)"
  fi
}

review_record() {  # RUN_DIR STAGE KIND N OUTCOME
  local run_dir="$1" stage="$2" kind="$3" n="$4" outcome="$5" cycles
  cycles="$(state_get "$run_dir" "errors.$stage.cycles" 0)"
  if [ "$kind" = fable ]; then
    state_set "$run_dir" "errors.$stage.escalated=true" "errors.$stage.last_n=$n" "errors.$stage.last_outcome=\"$outcome\"" >/dev/null 2>&1
  else
    state_set "$run_dir" "errors.$stage.cycles=$((cycles + 1))" "errors.$stage.last_n=$n" "errors.$stage.last_outcome=\"$outcome\"" >/dev/null 2>&1
  fi
}

review_restart_note() {  # RUN_DIR STAGE "MSG" N "SUMMARY" "COMMIT"
  cat > "$1/$2/restart-note.md" <<EOF
# Restart note (written by the runner after an automatic fix)

The previous attempt of this stage failed: $3
Fix F$4 applied${6:+ (commit $6)}: $5
The outputs of the failed attempt may be incomplete: start again from the stage's inputs. If you resume a model
session, tell it in one line what failed and what was fixed.
EOF
}

# ------------------------------------------------------------------ child side

review_write_result() {  # FILE key=value ...
  "$REELS_PY" - "$@" <<'EOF'
import json, sys
out = {}
for pair in sys.argv[2:]:
    k, _, v = pair.partition("=")
    out[k] = v
with open(sys.argv[1], "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
EOF
}

review_error_file() {  # RUN_DIR STAGE N RC "MSG" "CMD"
  local run_dir="$1" stage="$2" n="$3" rc="$4" msg="$5" cmd="$6"
  local file="$run_dir/errors/E$n.md" tail_n stage_log="$run_dir/$stage/stage.log"
  local contract="$REELS_PIPELINE/stages/$stage/CONTRACT.md" lastgood="" attempts call
  tail_n="$(cfg errors.log_tail_lines 200)"
  attempts="$(state_get "$run_dir" "stages.$stage.attempts" "?" 2>/dev/null)"
  [ -f "$REELS_LOGS/.last-good-sha" ] && { read -r lastgood < "$REELS_LOGS/.last-good-sha"; } 2>/dev/null
  mkdir -p "$run_dir/errors" "$run_dir/fixes"
  {
    echo "# E$n: error in $stage (run $(basename "$run_dir"))"
    echo
    echo "- stage: $stage"
    echo "- error: $msg"
    echo "- command: $cmd"
    echo "- exit code: $rc"
    echo "- attempt: $attempts"
    printf -- '- time: %(%Y-%m-%d %H:%M)T\n' -1
    echo "- run folder: $run_dir"
    echo "- repo root: $REELS_REPO"
    echo "- idea: $(state_get "$run_dir" idea.text "" 2>/dev/null)"
    echo
    if [ -f "$run_dir/$stage/error.json" ]; then
      echo "## Model call error ($stage/error.json)"; echo; echo '```json'; cat "$run_dir/$stage/error.json"; echo; echo '```'; echo
      call="$(json_field "$(cat "$run_dir/$stage/error.json")" call "" 2>/dev/null)"
      if [ -n "$call" ] && [ -s "${call%.json}.err" ]; then
        echo "### Last 60 lines of the call's stderr ($(basename "${call%.json}").err)"; echo; echo '```'
        tail -n 60 "${call%.json}.err" | tr -d '\r'; echo '```'; echo
      fi
    fi
    echo "## Last $tail_n lines of $stage/stage.log"; echo
    echo '```'
    if [ -f "$stage_log" ]; then tail -n "$tail_n" "$stage_log" | tr -d '\r'; else echo "(no stage.log)"; fi
    echo '```'; echo
    echo "## Input files (runs/$(basename "$run_dir"), relative paths with sizes in bytes)"; echo
    echo '```'
    ( cd "$run_dir" && find . -type f ! -path './*/calls/*' ! -path './errors/*' ! -path './fixes/*' ! -name 'state.lock' \
        -printf '%P\t%s\n' 2>/dev/null | sort | head -n 300 )
    echo '```'; echo
    echo "## CONTRACT.md of $stage"; echo
    if [ -f "$contract" ]; then cat "$contract"; else echo "(no CONTRACT.md for $stage)"; fi
    echo; echo "## Git diff since the last successful run"; echo
    if [ -n "$lastgood" ] && git -C "$REELS_REPO" cat-file -e "$lastgood^{commit}" 2>/dev/null; then
      echo "The last successful run (an export) was at commit $lastgood. Committed changes since then under pipeline/ and motion-lib/:"; echo
      echo '```'; git -C "$REELS_REPO" diff --stat "$lastgood" -- pipeline motion-lib 2>/dev/null | tail -n 40; echo '```'; echo
      echo '```diff'; git -C "$REELS_REPO" diff "$lastgood" -- pipeline motion-lib 2>/dev/null | head -n 400; echo '```'; echo
    else
      echo "No successful run is recorded yet (logs/.last-good-sha), so only the uncommitted changes follow."; echo
    fi
    echo "Uncommitted changes under pipeline/ and motion-lib/ (git status, then the diff):"; echo
    echo '```'; git -C "$REELS_REPO" status --porcelain -- pipeline motion-lib 2>/dev/null | head -n 60; echo '```'; echo
    echo '```diff'; git -C "$REELS_REPO" diff -- pipeline motion-lib 2>/dev/null | head -n 300; echo '```'; echo
    echo "## Previous error and fix files for this stage"; echo
    local prev=0 f k
    for f in "$run_dir"/errors/E*.md; do
      [ -f "$f" ] || continue
      k="$(basename "$f" .md)"; k="${k#E}"
      [ "$k" -lt "$n" ] 2>/dev/null || continue
      grep -q -x -- "- stage: $stage" "$f" || continue
      prev=$((prev + 1))
      echo "### E$k.md (the first 40 lines; the full file is errors/E$k.md)"; echo; echo '```'; head -n 40 "$f"; echo '```'; echo
      if [ -f "$run_dir/fixes/F$k.md" ]; then echo "### F$k.md"; echo; cat "$run_dir/fixes/F$k.md"; echo; fi
      if [ -f "$run_dir/fixes/F$k.result.json" ]; then echo "### F$k outcome"; echo; echo '```json'; cat "$run_dir/fixes/F$k.result.json"; echo; echo '```'; echo; fi
      if [ -f "$run_dir/fixes/F$k.verify.log" ]; then echo "### F$k verify log (last 40 lines)"; echo; echo '```'; tail -n 40 "$run_dir/fixes/F$k.verify.log" | tr -d '\r'; echo '```'; echo; fi
    done
    [ "$prev" = 0 ] && echo "(none: this is the first error of $stage in this run)"
  } > "$file"
}

review_render_fix() {  # RUN_DIR STAGE N KIND CYCLE CAP MODEL F.json F.md
  "$REELS_PY" - "$@" <<'EOF'
import json, sys, time
run_dir, stage, n, kind, cycle, cap, model, src, dest = sys.argv[1:10]
with open(src, encoding="utf-8-sig") as f:
    v = json.load(f)
who = f"{model} (escalation)" if kind == "fable" else f"{model} (cycle {cycle}/{cap})"
lines = [f"# F{n}: fix for E{n} (stage {stage})", "", f"- reviewer: {who}", f"- written: {time.strftime('%Y-%m-%d %H:%M')}",
         f"- run: {run_dir}", "", "## Root cause", "", str(v.get("root_cause", "")).strip(), "", "## Class", "",
         str(v.get("class", "")).strip(), "", "## Changes", ""]
changes = v.get("changes") or []
if not changes:
    lines.append("(no file changes)")
for c in changes:
    if isinstance(c, dict):
        lines.append(f"- `{c.get('file', '?')}`: {str(c.get('change', '')).strip()}")
    else:
        lines.append(f"- {c}")
lines += ["", "## Verify", "", "```bash", str(v.get("verify_command", "")).strip(), "```", "",
          f"## auto_apply: {str(v.get('auto_apply', 'no')).strip().lower()}", ""]
if str(v.get("auto_apply", "no")).strip().lower() != "yes":
    lines += [f"User action: {str(v.get('user_action', '')).strip() or '(none given)'}", ""]
lines += ["## Summary", "", str(v.get("summary", "")).strip(), ""]
text = "\n".join(lines).replace(chr(0x2014), ", ")
with open(dest, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
EOF
}

review_commit() {  # STAGE "SUMMARY" -> prints the short sha ("" when nothing to commit)
  local stage="$1" summary="$2" p known
  local -a ident=()
  known="$(cfg paths.known_issues pipeline/knowledge/known-issues.md)"
  if [ -z "$(git -C "$REELS_REPO" config user.email 2>/dev/null)" ]; then
    ident=(-c user.name="reels runner" -c user.email="runner@localhost")
  fi
  for p in $(review_fixer_paths) "$known"; do
    [ -e "$REELS_REPO/$p" ] && git -C "$REELS_REPO" add -A -- "$p" >/dev/null 2>&1
  done
  if git -C "$REELS_REPO" diff --cached --quiet 2>/dev/null; then printf ''; return 0; fi
  summary="$(printf '%s' "$summary" | tr -d '\r\n' | cut -c1-100)"
  if git -C "$REELS_REPO" "${ident[@]}" commit -q -m "autofix($stage): $summary" >/dev/null 2>&1; then
    git -C "$REELS_REPO" rev-parse --short HEAD 2>/dev/null
  else
    printf ''
    return 1
  fi
}

review_cycle() {  # RUN_DIR STAGE LABEL N KIND CYCLE CAP RC "MSG" "CMD"
  local run_dir="$1" stage="$2" label="$3" n="$4" kind="$5" cycle="$6" cap="$7" rc="$8" msg="$9" cmd="${10}"
  local errors="$run_dir/errors" fixes="$run_dir/fixes" result="$run_dir/fixes/F$n.result.json"
  local role model_name known prompt fprompt allowed p verify vrc sha line
  mkdir -p "$errors" "$fixes"
  review_error_file "$run_dir" "$stage" "$n" "$rc" "$msg" "$cmd"
  if [ "$kind" = fable ]; then role=reviewer_escalation; else role=reviewer; fi
  model_name="$(cfg "models.$role.model")"
  if [ "$kind" = fable ]; then set_activity "error in $label: escalated review ($model_name)"
  else set_activity "error in $label: reviewing (cycle $cycle/$cap, $model_name)"; fi
  known="$(review_known_issues_file)"
  prompt="$errors/E$n.prompt.md"
  {
    cat "$REELS_PIPELINE/stages/_prompts/reviewer.md"
    echo; echo "## Error report (runs/$(basename "$run_dir")/errors/E$n.md)"; echo
    cat "$errors/E$n.md"
    echo; echo "## Known issues (pipeline/knowledge/known-issues.md)"; echo
    if [ -f "$known" ]; then cat "$known"; else echo "(no known issues file yet)"; fi
    echo; echo "## Paths"; echo
    echo "- repo root (your working directory): $REELS_REPO"
    echo "- run folder: $run_dir"
    echo "- state root (ideas.txt, runs/, logs/): $REELS_ROOT"
    if [ "$kind" = fable ]; then
      echo; echo "## Escalation"; echo
      echo "You are the escalation reviewer: the earlier review cycles (their E and F files are in the report) did not fix this. Look for what they missed, question their root cause, and prefer a different fix."
    fi
  } > "$prompt"
  if ! ai "$role" "$errors" "$prompt" --schema "$REELS_PIPELINE/stages/_prompts/reviewer.schema.json" \
        --tools "$(cfg review.reviewer_tools 'Read Glob Grep WebSearch WebFetch')" --cwd "$REELS_REPO" \
        --timeout "$(cfg timeouts.reviewer_seconds 2400)" --name "E$n-review" --activity "$(get_activity)"; then
    review_write_result "$result" outcome=error reason="reviewer call failed: $AI_ERROR" fatal="$AI_FATAL" kind="$kind" n="$n"
    return 0
  fi
  cp "$AI_OUT" "$fixes/F$n.json"
  review_render_fix "$run_dir" "$stage" "$n" "$kind" "$cycle" "$cap" "$model_name" "$fixes/F$n.json" "$fixes/F$n.md"
  local auto_apply class root_cause user_action summary
  eval "$(json_eval "$(cat "$fixes/F$n.json")" auto_apply=auto_apply class=class root_cause=root_cause user_action=user_action summary=summary verify=verify_command)"
  if [ "$auto_apply" != yes ]; then
    review_write_result "$result" outcome=no_auto class="$class" root_cause="$root_cause" user_action="$user_action" summary="$summary" kind="$kind" n="$n"
    return 0
  fi
  # the fixer
  local fixer_model; fixer_model="$(cfg models.fixer.model)"
  set_activity "error in $label: applying fix F$n ($fixer_model)"
  fprompt="$fixes/F$n.prompt.md"
  {
    cat "$REELS_PIPELINE/stages/_prompts/fixer.md"
    echo; echo "## Fix file (runs/$(basename "$run_dir")/fixes/F$n.md)"; echo
    cat "$fixes/F$n.md"
    echo; echo "## Error"; echo
    echo "The stage $stage failed with: $msg"
    echo "The full report is $errors/E$n.md (read it when the fix file is not enough)."
    echo; echo "## Paths"; echo
    echo "- repo root (your working directory): $REELS_REPO"
    echo "- run folder: $run_dir"
  } > "$fprompt"
  allowed="Read Glob Grep Bash"
  local -a allow_flags=()
  for p in $(review_fixer_paths); do allowed="$allowed Edit($p/**) Write($p/**) MultiEdit($p/**)"; allow_flags+=(--allow "$p"); done
  allow_flags+=(--allow "$(cfg paths.known_issues pipeline/knowledge/known-issues.md)")
  "$REELS_PY" "$REELS_PIPELINE/lib/treeguard.py" snapshot --repo "$REELS_REPO" --dir "$fixes/.tree-$n" "${allow_flags[@]}" >/dev/null 2>&1 || true
  local fixer_ok=1
  ai fixer "$errors" "$fprompt" --schema "$REELS_PIPELINE/stages/_prompts/fixer.schema.json" \
    --tools "$(cfg review.fixer_tools 'Read Glob Grep Edit Write Bash')" --allowed "$allowed" --cwd "$REELS_REPO" \
    --timeout "$(cfg timeouts.fixer_seconds 2400)" --name "E$n-fix" --activity "$(get_activity)" || fixer_ok=0
  local guard
  guard="$("$REELS_PY" "$REELS_PIPELINE/lib/treeguard.py" check --repo "$REELS_REPO" --dir "$fixes/.tree-$n" --restore 2>/dev/null)" || true
  printf '%s\n' "$guard" > "$fixes/F$n.tree.json"
  rm -rf "$fixes/.tree-$n"
  local put_back left_alone folders
  put_back="$(json_field "$guard" restored '[]' 2>/dev/null)"; left_alone="$(json_field "$guard" left '[]' 2>/dev/null)"
  folders="$(printf '%s' "$(review_fixer_paths)" | tr -s ' ' ',')"
  if [ -n "$put_back" ] && [ "$put_back" != "[]" ]; then
    say WARN "$label: the fixer changed files outside $folders, put back: $put_back"
  fi
  if [ -n "$left_alone" ] && [ "$left_alone" != "[]" ]; then
    say INFO "$label: files outside $folders changed during the fix and were left alone: $left_alone"
  fi
  if [ "$fixer_ok" != 1 ]; then
    review_write_result "$result" outcome=failed reason="fixer call failed: $AI_ERROR" fatal="$AI_FATAL" kind="$kind" n="$n"
    return 0
  fi
  cp "$AI_OUT" "$fixes/F$n.fixer.json"
  local applied fix_summary known_issue files_changed
  eval "$(json_eval "$(cat "$fixes/F$n.fixer.json")" applied=applied fix_summary=summary known_issue=known_issue files_changed=files_changed)"
  if [ "$applied" != true ]; then
    review_write_result "$result" outcome=failed reason="the fixer did not apply the fix: $fix_summary" kind="$kind" n="$n"
    return 0
  fi
  # verify
  set_activity "error in $label: verifying fix F$n"
  ( cd "$REELS_REPO" && timeout -k 10 "$(cfg timeouts.verify_seconds 900)" bash -c "$verify" ) > "$fixes/F$n.verify.log" 2>&1; vrc=$?
  if [ "$vrc" -ne 0 ]; then
    review_write_result "$result" outcome=failed reason="verify command failed (exit $vrc): $(grep -v '^[[:space:]]*$' "$fixes/F$n.verify.log" | tail -n 1 | tr -d '\r' | cut -c1-160)" kind="$kind" n="$n" verify_exit="$vrc"
    return 0
  fi
  # the known-issues line and the commit (one autofix commit holds both)
  line="$(printf '%s' "${known_issue:-$msg -> $fix_summary}" | tr -d '\r\n' | cut -c1-220)"
  line="$("$REELS_PY" -c 'import sys; sys.stdout.reconfigure(newline="\n"); print(sys.argv[1].replace(chr(0x2014), ", "))' "$line")"
  printf -- '- %(%Y-%m-%d)T | %s | %s (F%s, runs/%s)\n' -1 "$stage" "$line" "$n" "$(basename "$run_dir")" >> "$known"
  sha="$(review_commit "$stage" "${summary:-$fix_summary}")"
  review_write_result "$result" outcome=fixed summary="${summary:-$fix_summary}" commit="$sha" files="$files_changed" known_issue="$line" kind="$kind" n="$n" verify_exit=0
}
