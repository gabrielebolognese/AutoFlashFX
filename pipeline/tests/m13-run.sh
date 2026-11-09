#!/usr/bin/env bash
# m13-run.sh: the unattended multi-idea run of the M13 acceptance test (PLAN.md M13). test-m13.sh calls it; it can also
# run alone, so its hours-long real run never depends on a test script that might be edited meanwhile.
#
#   bash pipeline/tests/m13-run.sh fake OUTDIR   the fake claude, real S1 to S4, dummy stages after S4, fast clocks
#                                                (about 2 minutes)
#   bash pipeline/tests/m13-run.sh real OUTDIR   the real models and engines on every stage (several hours)
#
# In a new sandbox (kept: its path goes to OUTDIR/sandbox.txt) with the three ideas of
# pipeline/tests/fixtures/ideas/three-ideas.txt:
#   run 1  bash run.sh --once with REELS_FAULT="limit:02-expansion@2,kill:03-gate@2": idea 1 runs to its end, the second
#          idea meets a simulated session limit at its first S2 call (the wait fast-forwarded: REELS_FAULT_WAIT=fast),
#          then the runner and the stage are killed at its first S3 call, as a crash would
#   run 2  bash run.sh --once again (the same REELS_FAULT: each fault fires once, logs/.faults/ remembers): it must
#          resume the second idea at S3 and finish the queue
#   run 3  bash run.sh (forever mode) with the empty queue, stopped with SIGTERM once its IDLE line is out: the
#          summary, the IDLE line and the stop line
# Meanwhile a sampler copies logs/status.txt every M13_SAMPLE_SECONDS (fake 0.5, real 20) into OUTDIR/samples.txt.
# OUTDIR gets run1.out, run2.out, run3.out (the terminal output), samples.txt, driver.log and result.env (the exit
# codes, whether the kill fired, whether the killed runner left its lock and its stage pid behind).
# M13_TIMEOUT: the time limit of runs 1 and 2 each (fake 900 s, real 43200 s).
set -u
MODE="${1:-}"; OUT="${2:-}"
case "$MODE" in fake|real) ;; *) echo "usage: bash pipeline/tests/m13-run.sh fake|real OUTDIR" >&2; exit 2 ;; esac
[ -n "$OUT" ] || { echo "usage: bash pipeline/tests/m13-run.sh fake|real OUTDIR" >&2; exit 2; }
export KEEP_SANDBOX=1
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
trap - EXIT   # the sandbox stays for the checks
cd "$REPO_DIR"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
rm -f "$OUT"/run[123].out "$OUT/samples.txt" "$OUT/driver.log" "$OUT/result.env" "$OUT/.stop-sampler"
log() { printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$OUT/driver.log"; }

FAULTS="limit:02-expansion@2,kill:03-gate@2"
if [ "$MODE" = fake ]; then
  sandbox_init --with-pipeline
  fast_mode
  export REELS_STATUS_EVERY=1          # a heartbeat every second, so each idea has some
  fake_claude_on
  mkdir -p "$SANDBOX/fixtures"
  FM12="$FIXTURES/fake/m12"
  cp "$FM12/01-research.json" "$FM12/02-expansion.json" "$FM12/04-angle.json" "$SANDBOX/fixtures/"
  # every idea: the gate fails H once (the forced FlashFX solution), S4 decides again, the gate passes
  for n in 1 3 5 7; do cp "$FM12/03-gate.1.json" "$SANDBOX/fixtures/03-gate.$n.json"; done
  for n in 2 4 6 8; do cp "$FM12/03-gate.2.json" "$SANDBOX/fixtures/03-gate.$n.json"; done
  export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
  export REELS_DUMMY="$(dummy_after 04-angle)"
  TO="${M13_TIMEOUT:-900}"; EVERY="${M13_SAMPLE_SECONDS:-0.5}"
else
  sandbox_init --with-review
  fake_claude_off
  export REELS_SFX_DIR="$(mixed "$REPO_DIR/channels/flashfx/styles/sfx")" REELS_SFX_NO_BUILD=1
  unset REELS_DUMMY
  TO="${M13_TIMEOUT:-43200}"; EVERY="${M13_SAMPLE_SECONDS:-20}"
fi
grep -v '^#' "$FIXTURES/ideas/three-ideas.txt" > "$SANDBOX/channels/flashfx/ideas.txt"
printf '%s\n' "$SANDBOX_M" > "$OUT/sandbox.txt"
log "m13-run $MODE: sandbox $SANDBOX_M, 3 ideas, faults $FAULTS, time limit ${TO}s per run"

STATUS="$SANDBOX/channels/flashfx/logs/status.txt"
(
  while [ ! -e "$OUT/.stop-sampler" ]; do
    # say() renames a new status.txt into place: a reader never sees it empty or half written, but may find it
    # missing for a moment during the swap, so a read is tried a few times (as runner-status and the doctor do)
    got=0
    if [ -e "$STATUS" ]; then
      for try in 1 2 3 4 5; do
        if c="$(cat "$STATUS" 2>/dev/null && printf x)"; then got=1; break; fi
        sleep 0.05
      done
    fi
    if [ "$got" = 1 ]; then
      c="${c%x}"; c="${c%$'\n'}"
      printf '%s\t%s\n' "$EPOCHSECONDS" "${c//$'\n'/<NL>}"
    else
      printf '%s\t<missing>\n' "$EPOCHSECONDS"
    fi >> "$OUT/samples.txt"
    sleep "$EVERY"
  done
) &
SAMPLER=$!

run_runner() {  # run_runner <n> <timeout> [run.sh args]
  local n="$1" to="$2"; shift 2
  ( cd "$SANDBOX" && env NO_COLOR=1 REELS_FAULT="$FAULTS" REELS_FAULT_WAIT=fast REELS_FAULT_MINUTES=3 \
      timeout "$to" bash "$SANDBOX/run.sh" "$@" ) > "$OUT/run$n.out" 2>&1
}

t0="$EPOCHSECONDS"
run_runner 1 "$TO" --once; rc1=$?
t1="$EPOCHSECONDS"
kill_fired=0; [ -e "$SANDBOX/channels/flashfx/logs/.faults/kill-03-gate@2" ] && kill_fired=1
limit_fired=0; [ -e "$SANDBOX/channels/flashfx/logs/.faults/limit-02-expansion@2" ] && limit_fired=1
lock_left=0; [ -d "$SANDBOX/channels/flashfx/.locks/runner" ] && lock_left=1
pid_left=0; ls "$SANDBOX"/channels/flashfx/runs/*/03-gate/.pid >/dev/null 2>&1 && pid_left=1
log "run 1 ended with exit $rc1 after $((t1 - t0))s (limit fired $limit_fired, kill fired $kill_fired, runner lock left $lock_left, stage pid left $pid_left)"

rc2=""; t2="$t1"
if [ "$kill_fired" = 1 ]; then
  log "restarting the runner (run 2)"
  run_runner 2 "$TO" --once; rc2=$?
  t2="$EPOCHSECONDS"
  log "run 2 ended with exit $rc2 after $((t2 - t1))s"
fi

# forever mode on the empty queue: the summary, the IDLE line, then SIGTERM (as Ctrl+C or a closed window would)
( cd "$SANDBOX" && NO_COLOR=1 REELS_POLL_SECONDS=2 exec bash "$SANDBOX/run.sh" ) > "$OUT/run3.out" 2>&1 &
R3=$!
for i in $(seq 1 600); do
  grep -q "IDLE   no ideas in ideas.txt" "$OUT/run3.out" 2>/dev/null && break
  kill -0 "$R3" 2>/dev/null || break
  sleep 0.5
done
kill -TERM "$R3" 2>/dev/null
wait "$R3"; rc3=$?
log "run 3 (forever mode on the empty queue, stopped with SIGTERM after its IDLE line) ended with exit $rc3"

: > "$OUT/.stop-sampler"
wait "$SAMPLER" 2>/dev/null
rm -f "$OUT/.stop-sampler"
cat > "$OUT/result.env" <<EOF
MODE=$MODE
SANDBOX_M=$SANDBOX_M
RC1=$rc1
RC2=$rc2
RC3=$rc3
LIMIT_FIRED=$limit_fired
KILL_FIRED=$kill_fired
LOCK_LEFT=$lock_left
PID_LEFT=$pid_left
T0=$t0
T1=$t1
T2=$t2
EOF
[ "$MODE" = fake ] && fake_claude_off
log "m13-run $MODE done: $(tr '\n' ' ' < "$OUT/result.env")"
exit 0
