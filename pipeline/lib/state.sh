# pipeline/lib/state.sh: bash access to the run state (wraps state.py). Source common.sh first.
#
#   state_py <args...>                         run state.py
#   state_stages                               the stage table (key, label, activity, output, initial), tab separated
#   state_new <idea_id> "<raw text>"           create a run; prints JSON {run_dir, run_id, idea_id}
#   state_unfinished                           JSON list of unfinished runs, oldest first (exit 3 when none)
#   state_pickup <run_dir>                     session accounting at start or resume; prints the summary JSON
#   state_next <run_dir>                       JSON {phase: stage|export|finalize|finished, stage, activity, ...}
#   state_stage_start <run_dir> <stage> [pid]  mark the stage running (attempt + 1)
#   state_stage_done <run_dir> <stage> [exit]  validate the output against pipeline/stages/<stage>/schema.json,
#                                              write .done; exit 5 and JSON errors when invalid
#   state_stage_fail <run_dir> <stage> <exit> "<reason>"
#   state_reopen <run_dir> <stage>...          back to pending (the gate and review loops)
#   state_flag <run_dir> <stage> "<text>"      record a NEEDS REVIEW flag (the FLAG line is printed by run_flag)
#   state_get <run_dir> <key> [default]        state_set <run_dir> key=json ...
#   state_finish <run_dir> exported|dropped|blocked "<reason>" [stage] [number]
#   json_field '<json>' <key> [default]        read one field of a JSON object (dotted keys allowed)
#   eval "$(json_eval '<json>' VAR=key ...)"  read several fields in one call (missing keys give "")
#   run_flag <run_dir> <stage> "<text>"        record the flag and print the FLAG line (needs log.sh)

state_py() { "$REELS_PY" "$REELS_PIPELINE/lib/state.py" "$@"; }

state_stages()      { state_py stages; }
state_new()         { printf '%s' "$2" | state_py new --runs "${REELS_RUNS:-$REELS_ROOT/runs}" --id "$1"; }
state_unfinished()  { state_py unfinished --runs "${REELS_RUNS:-$REELS_ROOT/runs}"; }
state_pickup()      { state_py pickup "$1"; }
state_summary()     { state_py summary "$1"; }
state_next()        { state_py next "$1"; }
state_stage_start() { if [ -n "${3:-}" ]; then state_py stage-start "$1" "$2" --pid "$3"; else state_py stage-start "$1" "$2"; fi; }
state_stage_done()  { state_py stage-done "$1" "$2" --schemas "$REELS_PIPELINE/stages" --exit "${3:-0}"; }
state_stage_fail()  { state_py stage-fail "$1" "$2" --exit "$3" --reason "${4:-}"; }
state_reopen()      { state_py reopen "$@"; }
state_flag()        { state_py flag "$1" "$2" "$3"; }
state_get()         { state_py get "$@"; }
state_set()         { state_py set "$@"; }
state_touch()       { state_py touch "$1"; }
state_finish() {
  local run_dir="$1" kind="$2" reason="$3" stage="${4:-}" number="${5:-}"
  state_py finish "$run_dir" "$kind" --reason "$reason" ${stage:+--stage "$stage"} ${number:+--number "$number"}
}

json_field() {
  "$REELS_PY" -c 'import json, sys
sys.stdout.reconfigure(newline="\n")
try:
    cur = json.loads(sys.argv[1])
    for part in sys.argv[2].split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
except (KeyError, IndexError, TypeError, ValueError):
    if len(sys.argv) > 3:
        print(sys.argv[3]); sys.exit(0)
    sys.exit(3)
if isinstance(cur, bool): print("true" if cur else "false")
elif cur is None: print("")
elif isinstance(cur, (dict, list)): print(json.dumps(cur, ensure_ascii=False))
else: print(cur)' "$@"
}

run_flag() {
  state_flag "$1" "$2" "$3" >/dev/null
  say FLAG "needs review: $3"
}

json_eval() {  # eval "$(json_eval '<json>' VAR=key ...)": several fields in one Python call; a missing key gives ""
  "$REELS_PY" -c 'import json, shlex, sys
sys.stdout.reconfigure(newline="\n")
try:
    obj = json.loads(sys.argv[1])
except ValueError:
    obj = {}
for spec in sys.argv[2:]:
    name, _, key = spec.partition("=")
    cur = obj
    try:
        for part in key.split("."):
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    except (KeyError, IndexError, TypeError, ValueError):
        cur = ""
    if isinstance(cur, bool):
        cur = "true" if cur else "false"
    elif cur is None:
        cur = ""
    elif isinstance(cur, (dict, list)):
        cur = json.dumps(cur, ensure_ascii=False)
    print(name + "=" + shlex.quote(str(cur)))' "$@"
}
