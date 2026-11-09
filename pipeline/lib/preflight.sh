# pipeline/lib/preflight.sh: the startup checks (BUILD_SPEC.md section 3), table-driven by preflight.require in
# config.json, for one channel (REELS_CHANNEL; channel.json is validated first, 14.4). Source common.sh, log.sh and
# config.sh first.
#
#   preflight_run     returns 0 when every hard check passes. On a hard failure it writes the channel's logs/STOPPED.md
#                     with the diagnosis and the exact fix, prints a STOP line and returns 3 (a systemic failure).
#                     "{channel}" in a fix text is the channel id.
#
# Entry fields in preflight.require:
#   check: command | python_module | file | disk | shell | voice | brand
#                 voice (M7): pipeline/lib/voiceover.py engine-check, the voice config of library/voice/engine.txt:
#                 its interpreter exists and imports kokoro, one interpreter imports faster_whisper; the check's
#                 notes (a missing engine.txt, another engine named, missing lines) are warnings
#                 brand (M10): library/brand/brand.json of the channel parses and every asset it lists exists with
#                 its use_on, width and height (BUILD_SPEC.md 2.7)
#   name          command or module name
#   min_version   command: the first X.Y[.Z] of "<name> --version" must be at least this
#   path          file: relative to the repo, or to the channel folder when in_channel is true
#   min_free_gb   disk: free space under the state root
#   cmd           shell: a command that must exit 0
#   level         hard (default) or warn
#   fix           what to do, printed in STOPPED.md

preflight_version_of() {
  "$1" --version 2>/dev/null </dev/null | head -n 1 | grep -o -E '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n 1
}

preflight_version_ok() {  # $1 found, $2 minimum
  [ -z "$2" ] && return 0
  [ -z "$1" ] && return 1
  [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n 1)" = "$2" ]
}

preflight_free_gb() {
  df -kP "$1" 2>/dev/null | awk 'NR == 2 { printf "%d", $4 / 1048576 }'
}

preflight_write_stopped() {  # args: "problem|fix" ...
  mkdir -p "$REELS_LOGS"
  {
    echo "# Runner stopped: preflight failed"
    echo
    echo "Written $(date '+%Y-%m-%d %H:%M') by run.sh. The runner checks its hard dependencies at startup and does not"
    echo "start until every item below is fixed. This file is removed at the next successful start."
    echo
    echo "## Diagnosis"
    local f
    for f in "$@"; do echo "- ${f%%|*}"; done
    echo
    echo "## Fix"
    local i=1
    for f in "$@"; do echo "$i. ${f#*|}"; i=$((i + 1)); done
    echo
    echo "Then start the runner again: bash run.sh --channel $REELS_CHANNEL"
  } > "$REELS_LOGS/STOPPED.md"
}

preflight_run() {
  local failures=() warnings=() modules=() module_levels=() module_fixes=()
  local n_tools=0 n_files=0 free_gb=""
  local check name path in_channel min_version min_free_gb cmd level fix problem have full vout vrc vline
  local sep=$'\x1f'
  local cj_problems
  cj_problems="$("$REELS_PY" "$REELS_PIPELINE/lib/config.py" validate 2>&1 </dev/null)" \
    || failures+=("channel.json is not valid: $(printf '%s' "$cj_problems" | head -n 1)|fix channels/$REELS_CHANNEL/channel.json (schema: pipeline/schemas/channel.schema.json)")
  while IFS="$sep" read -r check name path in_channel min_version min_free_gb cmd level fix; do
    [ -z "$check" ] && continue
    level="${level:-hard}"
    fix="${fix//\{channel\}/$REELS_CHANNEL}"
    problem=""
    case "$check" in
      command)
        if ! command -v "$name" >/dev/null 2>&1; then
          problem="$name is not on PATH"
        elif [ -n "$min_version" ]; then
          have="$(preflight_version_of "$name")"
          preflight_version_ok "$have" "$min_version" \
            || problem="$name is version ${have:-unknown}, need $min_version or newer"
        fi
        [ -z "$problem" ] && n_tools=$((n_tools + 1))
        ;;
      python_module)
        modules+=("$name"); module_levels+=("$level"); module_fixes+=("$fix")
        continue
        ;;
      file)
        if [ "$in_channel" = "true" ]; then full="$(chpath "$path")"; else full="$REELS_REPO/$path"; fi
        if [ -e "$full" ]; then n_files=$((n_files + 1)); else problem="$path is missing ($full)"; fi
        ;;
      fill_in)  # M19: a file that still says [FILL IN] is a template the user has not written yet (pipeline/bin/new-channel)
        local fi_list=() fi_f
        IFS=, read -r -a fi_list <<<"$name"
        for fi_f in "${fi_list[@]}"; do
          full="$(chpath "$fi_f")"
          if [ -f "$full" ] && grep -q -F '[FILL IN]' "$full" 2>/dev/null; then problem="${problem:+$problem, }$fi_f still says [FILL IN]"; fi
        done
        # a channel that is switched on has been through its owner's hands: the markers that stay in it are a warning; a channel
        # still disabled (new-channel makes it so) is incomplete: a hard failure that lists them
        [ "$(cfg_channel_enabled)" = true ] && level="warn"
        ;;
      disk)
        free_gb="$(preflight_free_gb "$REELS_ROOT")"
        if [ -n "$free_gb" ] && [ "$free_gb" -lt "${min_free_gb:-0}" ]; then
          problem="only ${free_gb} GB free under $REELS_ROOT, need ${min_free_gb} GB"
        fi
        ;;
      shell)
        (eval "$cmd") >/dev/null 2>&1 </dev/null || problem="'$cmd' failed"
        ;;
      brand)
        # M10 (BUILD_SPEC.md 2.7): library/brand/brand.json under the repo parses and every asset it lists exists
        vout="$("$REELS_PY" - "$REELS_CHANNEL_ROOT" "$REELS_LIBRARY" 2>&1 <<'PYEOF'
import json, os, sys
repo = sys.argv[1]  # the channel folder: brand.json lists its assets relative to it
library = sys.argv[2]
path = os.path.join(library, "brand", "brand.json")
if not os.path.isfile(path):
    print("library/brand/brand.json is missing"); sys.exit(1)
try:
    data = json.load(open(path, encoding="utf-8-sig"))
except ValueError as exc:
    print(f"library/brand/brand.json is not valid JSON ({exc})"); sys.exit(1)
assets = data.get("assets") or []
if not assets:
    print("library/brand/brand.json lists no assets"); sys.exit(1)
missing = [a.get("path", "?") for a in assets if not os.path.isfile(os.path.join(repo, a.get("path", "")))]
bad = [a.get("path", "?") for a in assets if a.get("use_on") not in ("light", "dark", "both") or not a.get("width") or not a.get("height")]
if missing:
    print("brand.json lists files that do not exist: " + ", ".join(missing[:5])); sys.exit(1)
if bad:
    print("brand.json entries without use_on, width or height: " + ", ".join(bad[:5])); sys.exit(1)
print(f"ok: {len(assets)} brand assets")
PYEOF
)"; vrc=$?
        if [ "$vrc" != 0 ]; then
          problem="$(printf '%s\n' "$vout" | head -n 1)"
          [ -n "$problem" ] || problem="the brand kit check failed (exit $vrc)"
        else
          n_files=$((n_files + 1))
        fi
        ;;
      voice)
        vout="$("$REELS_PY" "$REELS_PIPELINE/lib/voiceover.py" engine-check 2>&1 </dev/null)"; vrc=$?
        while IFS= read -r vline; do
          case "$vline" in "WARN: "*) warnings+=("${vline#WARN: }") ;; esac
        done <<<"$vout"
        if [ "$vrc" != 0 ]; then
          problem="$(printf '%s\n' "$vout" | grep -v -E '^(WARN: |ok: )' | head -n 1)"
          [ -n "$problem" ] || problem="the voice engine check failed (exit $vrc)"
        else
          n_tools=$((n_tools + 1))
        fi
        ;;
      *)
        problem="unknown preflight check type '$check' in config.json"
        ;;
    esac
    if [ -n "$problem" ]; then
      if [ "$level" = "warn" ]; then warnings+=("$problem (fix: $fix)"); else failures+=("$problem|$fix"); fi
    fi
  done < <(cfg_rows preflight.require check name path in_channel min_version min_free_gb cmd level fix)

  local n_modules=${#modules[@]} missing i m
  if [ "$n_modules" -gt 0 ]; then
    missing="$("$REELS_PY" -c 'import importlib.util, sys
print(" ".join(m for m in sys.argv[1:] if importlib.util.find_spec(m) is None))' "${modules[@]}" 2>/dev/null </dev/null)"
    for m in $missing; do
      i=0
      while [ $i -lt "$n_modules" ]; do
        if [ "${modules[$i]}" = "$m" ]; then
          problem="python package $m is not installed"
          if [ "${module_levels[$i]}" = "warn" ]; then warnings+=("$problem (fix: ${module_fixes[$i]})")
          else failures+=("$problem|${module_fixes[$i]}"); fi
        fi
        i=$((i + 1))
      done
      n_modules=$((n_modules - 1))
    done
  fi

  local w
  for w in "${warnings[@]}"; do say WARN "preflight: $w"; done
  if [ ${#failures[@]} -gt 0 ]; then
    preflight_write_stopped "${failures[@]}"
    local first="${failures[0]%%|*}" more=""
    [ ${#failures[@]} -gt 1 ] && more=" and $(( ${#failures[@]} - 1 )) more"
    say STOP "systemic failure: preflight failed: ${first}${more}. See logs/STOPPED.md"
    return 3
  fi
  if [ -f "$REELS_LOGS/STOPPED.md" ]; then
    rm -f "$REELS_LOGS/STOPPED.md"
    say INFO "removed logs/STOPPED.md left by the previous stop"
  fi
  say READY "preflight ok: $n_tools tools, $n_modules python packages, $n_files files${free_gb:+, ${free_gb} GB free}"
  return 0
}
