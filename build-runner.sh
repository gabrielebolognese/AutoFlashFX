#!/usr/bin/env bash
# build-runner.sh: builds the reels autopilot (BUILD_SPEC.md) milestone by milestone, unattended.
#
# Each milestone is a fresh Claude Code session:
#   build batch -> review 1 -> (if rejected) fix batch -> review 2 -> (if rejected) fix batch -> next milestone.
# At most 2 lenient reviews per milestone: after the second one the build moves on whatever the verdict, and
# anything left open is written to build/open-issues.md for the later batches.
# Coding (build and fix batches) runs on Fable. When Fable hits a usage limit, coding switches to Opus by itself
# until Fable's limit resets. The runner stops only when Claude Code itself cannot run, or a batch says it needs you.
#
# Usage (Git Bash, from the instagramReels folder):
#   bash build-runner.sh                 start, or resume where it stopped
#   bash build-runner.sh --from M5       restart from a milestone
#   bash build-runner.sh --review-plan   pause after M0 so you can read PLAN.md
#   bash build-runner.sh --status        print the latest status line and exit
#   bash build-runner.sh --check         check that Claude Code runs with these settings, then exit
#
# What you see: every step is printed with the time and a tag. While Claude works, a live feed shows what
# it is doing (DOING lines: files it reads and edits, commands it runs; NOTE lines: what it says), and a
# status line comes every 2 minutes. Options (environment variables, all optional):
#   ACTIVITY=tools    actions only, no notes        ACTIVITY=off   no live feed
#   STATUS_EVERY=60   status line every minute      STREAM=0       old single-result output, no live feed

set -u

# ---------------------------------------------------------------- settings
SPEC="BUILD_SPEC.md"
BUILD_MODEL="${BUILD_MODEL:-fable}";            BUILD_EFFORT="${BUILD_EFFORT:-max}"
FIX_MODEL="${FIX_MODEL:-fable}";                FIX_EFFORT="${FIX_EFFORT:-max}"
REVIEW_MODEL="${REVIEW_MODEL:-opus}";           REVIEW_EFFORT="${REVIEW_EFFORT:-medium}"
LIMIT_MODEL="${LIMIT_MODEL:-opus}";             LIMIT_EFFORT="${LIMIT_EFFORT:-high}"   # coding while Fable is at its limit
FALLBACK="${FALLBACK:-1}"                       # 1: Fable batches pass --fallback-model $LIMIT_MODEL, so Claude Code
                                                #    itself switches to Opus inside the session when Fable is unavailable
PROBE_MODEL="${PROBE_MODEL:-haiku}"
MAX_REVIEWS="${MAX_REVIEWS:-2}"                 # reviews per milestone; after the last one the build moves on
FINAL_FIX="${FINAL_FIX:-1}"                     # 1: a fix batch after the last rejected review, 0: move on at once
STATUS_EVERY="${STATUS_EVERY:-120}"             # status line every 2 minutes
ACTIVITY="${ACTIVITY:-full}"                    # live feed while Claude works: full, tools or off
STREAM="${STREAM:-1}"                           # 1: stream-json (live feed), 0: single json result
LIMIT_MARGIN="${LIMIT_MARGIN:-120}"             # wait 2 minutes past a limit reset
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
# Unattended permissions. If your Claude Code rejects these flags, run with:
#   PERM_FLAGS='--permission-mode acceptEdits --allowedTools Bash Read Write Edit Glob Grep WebSearch WebFetch' bash build-runner.sh
read -r -a PERM_FLAGS <<< "${PERM_FLAGS:---permission-mode auto --permission-prompts none}"
SLEEP_SCALE="${SLEEP_SCALE:-1}"                 # tests only: 0.001 makes every wait near instant

MS_IDS=(M0 M1 M2 M3 M4 M5 M6 M7 M8 M9 M10 M11 M12 M13)
MS_TITLES=("Plan" "Skeleton" "Runner core and terminal output" "Error system"
           "Research, expansion, gate, angle" "Profile and hooks" "Script" "Voiceover"
           "Sound effects memory map" "Motion library" "Visual stages"
           "Sound effects pass and review loop" "Final render, caption, export, end to end" "Hardening")

BUILD_DIR="build"; STATE="$BUILD_DIR/state.env"; STATUS_FILE="$BUILD_DIR/.status"
LOG="$BUILD_DIR/build.log"; STATUS_TXT="$BUILD_DIR/status.txt"; TODO="$BUILD_DIR/HUMAN_TODO.md"

cd "$(dirname "$0")" || exit 1
mkdir -p "$BUILD_DIR"

# ---------------------------------------------------------------- output
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_G=$'\e[32m'; C_R=$'\e[31m'; C_Y=$'\e[33m'; C_C=$'\e[36m'; C_D=$'\e[90m'; C_0=$'\e[0m'
else
  C_G=""; C_R=""; C_Y=""; C_C=""; C_D=""; C_0=""
fi

say() {  # say TAG message...
  local tag="$1"; shift
  local col="$C_C"
  case "$tag" in
    PASS|DONE) col="$C_G" ;; REJECT|STOP|ERROR) col="$C_R" ;;
    LIMIT|RETRY|ESCAL|HUMAN|WAIT|WARN|MOVEON) col="$C_Y" ;; STATUS|NOTE|USAGE) col="$C_D" ;;
  esac
  printf '%s[%s] %-6s%s %s\n' "$col" "$(date +%H:%M)" "$tag" "$C_0" "$*"
  printf '[%s] %-6s %s\n' "$(date '+%F %H:%M')" "$tag" "$*" >> "$LOG"
}

fmt_dur() {  # seconds -> 5h41m / 12m / 40s
  local s=$1
  [ "$s" -lt 0 ] && s=0
  if [ "$s" -ge 3600 ]; then printf '%dh%02dm' $((s/3600)) $(((s%3600)/60))
  elif [ "$s" -ge 60 ]; then printf '%dm' $((s/60))
  else printf '%ds' "$s"; fi
}

# ---------------------------------------------------------------- time (virtual in tests)
VOFF=0
now_epoch() { echo $(( $(date +%s) + VOFF )); }
scaled_sleep() {
  local s=$1
  if [ "$SLEEP_SCALE" = "1" ]; then sleep "$s"
  else sleep "$(awk -v s="$s" -v k="$SLEEP_SCALE" 'BEGIN{printf "%.3f", s*k}')"; VOFF=$((VOFF + s)); fi
}
wait_until() {  # sleep in 60 s chunks so a sleeping PC doesn't break the wait
  local t=$1 left
  while [ "$(now_epoch)" -lt "$t" ]; do
    left=$(( t - $(now_epoch) )); [ "$left" -gt 60 ] && left=60
    scaled_sleep "$left"
  done
}

# ---------------------------------------------------------------- python helper
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
    PY="$c"; break
  fi
done

parse_json() {  # parse_json OUT.json -> prints session id, then is_error; writes OUT.txt with the result text
  "$PY" - "$1" <<'EOF'
import json, sys
path = sys.argv[1]
raw = open(path, encoding="utf-8", errors="replace").read()
obj = None
candidates = [raw] + [l for l in reversed(raw.splitlines()) if l.strip().startswith("{")]
for cand in candidates:
    try:
        obj = json.loads(cand)
        break
    except Exception:
        pass
if not isinstance(obj, dict):
    obj = {}
with open(path[:-5] + ".txt", "w", encoding="utf-8") as f:
    f.write(str(obj.get("result") or ""))
print(obj.get("session_id") or "")
print("true" if obj.get("is_error") else "false")
EOF
}

extract_result() {  # extract_result STREAM.jsonl OFFSET OUT.json: the final result event of this attempt, as one JSON
  "$PY" - "$1" "$2" "$3" <<'EOF'
import json, sys
path, off, outp = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with open(path, "rb") as f:
    f.seek(off)
    data = f.read().decode("utf-8", "replace")
result, plain, texts = None, [], []
for line in data.splitlines():
    s = line.strip()
    if not s:
        continue
    try:
        o = json.loads(s)
    except Exception:
        plain.append(line)
        continue
    if not isinstance(o, dict):
        continue
    if o.get("type") == "result":
        result = o
    elif o.get("type") == "assistant" and not o.get("parent_tool_use_id"):
        for c in (o.get("message") or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "text":
                texts.append(c.get("text") or "")
with open(outp, "w", encoding="utf-8") as f:
    if result is not None:
        json.dump(result, f)
    else:  # no result event (crash or CLI error): keep plain output and the last words, for the error checks
        f.write("\n".join(plain + texts[-2:]))
EOF
}

ACT_PID=""; ACT_STOP=""
start_activity() {  # start_activity STREAM.jsonl OFFSET: prints what Claude is doing, live, until stop_activity
  [ "$ACTIVITY" = "off" ] && return 0
  ACT_STOP="$1.stop"; rm -f "$ACT_STOP"
  (
    PYTHONIOENCODING=utf-8 "$PY" -u - "$1" "$2" "$ACT_STOP" "$ACTIVITY" <<'EOF' |
import json, os, re, sys, time
path, pos, stop, mode = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
cwd = os.getcwd().replace("\\", "/").rstrip("/")
bases = [cwd]
if len(cwd) > 2 and cwd[1] == ":":
    bases.append("/" + cwd[0].lower() + cwd[2:])
usage = {}
model_seen = [None, False]   # the session's model, and whether a model change was already reported

def short(m):  # claude-fable-5-1 -> fable
    return re.sub(r"^claude-|-[0-9][-0-9.]*$", "", str(m or "?"))

def out(tag, msg):
    msg = " ".join(str(msg).split())
    if len(msg) > 150:
        msg = msg[:147] + "..."
    if msg:
        print(tag + "\t" + msg, flush=True)

def rel(p):
    p = str(p or "").replace("\\", "/")
    for b in bases:
        if p.lower() == b.lower():
            return "the project folder"
        if p.lower().startswith(b.lower() + "/"):
            return p[len(b) + 1:]
    return p

def tool(name, i):
    i = i if isinstance(i, dict) else {}
    if name in ("Read", "Write", "Edit", "MultiEdit", "NotebookEdit"):
        verb = {"Read": "reading", "Write": "writing"}.get(name, "editing")
        return verb + " " + rel(i.get("file_path") or i.get("notebook_path"))
    if name in ("Bash", "PowerShell"):
        return "running: " + str(i.get("command") or i.get("description") or "")
    if name == "Grep":
        return "searching for '" + str(i.get("pattern", "")) + "'" + (" in " + rel(i["path"]) if i.get("path") else "")
    if name == "Glob":
        return "listing files " + str(i.get("pattern", "")) + (" in " + rel(i["path"]) if i.get("path") else "")
    if name == "WebSearch":
        return "web search: " + str(i.get("query", ""))
    if name == "WebFetch":
        return "fetching " + str(i.get("url", ""))
    if name in ("Task", "Agent"):
        return "starting a subagent: " + str(i.get("description") or i.get("prompt") or "")
    if name == "TodoWrite":
        todos = i.get("todos") or []
        done = sum(1 for t in todos if t.get("status") == "completed")
        now = [t.get("activeForm") or t.get("content") for t in todos if t.get("status") == "in_progress"]
        return "todo list: %d/%d done%s" % (done, len(todos), (", now: " + str(now[0])) if now else "")
    return name + " " + json.dumps(i, ensure_ascii=False)

def when(ts, weekly):
    try:
        return time.strftime("%a %H:%M" if weekly else "%H:%M", time.localtime(int(ts)))
    except Exception:
        return "?"

def handle(raw):
    line = raw.decode("utf-8", "replace").strip()
    if not line:
        return
    try:
        o = json.loads(line)
    except Exception:
        out("NOTE", line)
        return
    if not isinstance(o, dict):
        return
    t = o.get("type")
    sub = "(subagent) " if o.get("parent_tool_use_id") else ""
    if t == "system" and o.get("subtype") == "init":
        out("CLAUDE", "session started (%s, Claude Code %s)" % (o.get("model", "?"), o.get("claude_code_version", "?")))
        if o.get("model"):
            model_seen[0] = o.get("model")
    elif t == "assistant":
        m = (o.get("message") or {}).get("model")
        if m and m != "<synthetic>" and not o.get("parent_tool_use_id"):
            if model_seen[0] is None:
                model_seen[0] = m
            elif m != model_seen[0] and not model_seen[1]:
                model_seen[1] = True
                out("LIMIT", "%s not available: Claude Code switched this session to %s and carries on" % (short(model_seen[0]), short(m)))
        for c in (o.get("message") or {}).get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                out("DOING", sub + tool(c.get("name", "?"), c.get("input")))
            elif c.get("type") == "text" and mode == "full":
                first = next((l for l in str(c.get("text", "")).splitlines() if l.strip()), "")
                out("NOTE", sub + first)
    elif t == "rate_limit_event":
        info = o.get("rate_limit_info") or {}
        wins = info.get("unifiedWindows") or {}
        parts, show = [], info.get("status") not in (None, "allowed")
        # seven_day_overage_included shows up only in Fable sessions: it is Fable's own weekly limit
        for key, label in (("five_hour", "5-hour window"), ("seven_day", "weekly"),
                           ("seven_day_overage_included", "fable weekly")):
            w = wins.get(key)
            if not isinstance(w, dict) or w.get("utilization") is None:
                continue
            pct = int(round(float(w["utilization"]) * 100))
            if key not in usage or pct // 10 != usage[key] // 10 or w.get("status") not in ("allowed", "allowed_warning"):
                show = True
            usage[key] = pct
            parts.append("%s %d%% (resets %s)" % (label, pct, when(w.get("resetsAt"), key != "five_hour")))
        if show and parts:
            out("USAGE", ("LIMIT STATUS %s: " % info.get("status") if info.get("status") not in (None, "allowed") else "usage: ") + ", ".join(parts))
    elif t == "result":
        secs = int((o.get("duration_ms") or 0) / 1000)
        dur = "%dh%02dm" % (secs // 3600, secs % 3600 // 60) if secs >= 3600 else ("%dm" % (secs // 60) if secs >= 60 else "%ds" % secs)
        out("CLAUDE", "session finished: %s, %s turns, %s" % (o.get("subtype", "?"), o.get("num_turns", "?"), dur))

buf, idle = b"", time.time()
while True:
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if size > pos:
        with open(path, "rb") as fh:
            fh.seek(pos)
            data = fh.read(size - pos)
        pos += len(data)
        buf += data
        idle = time.time()
        *lines, buf = buf.split(b"\n")
        for raw in lines:
            handle(raw)
    elif os.path.exists(stop):
        if buf.strip():
            handle(buf)
        break
    elif time.time() - idle > 3 * 3600:
        break
    else:
        time.sleep(0.5)
EOF
    while IFS=$'\t' read -r tag msg; do say "$tag" "$msg"; done
  ) &
  ACT_PID=$!
}

stop_activity() {  # lets the feed print its last lines (at most about 5 s), then stops it
  [ -z "$ACT_PID" ] && return 0
  [ -n "$ACT_STOP" ] && : > "$ACT_STOP"
  local i=0
  while kill -0 "$ACT_PID" 2>/dev/null && [ "$i" -lt 50 ]; do sleep 0.1; i=$((i + 1)); done
  kill "$ACT_PID" 2>/dev/null
  wait "$ACT_PID" 2>/dev/null
  rm -f "$ACT_STOP"; ACT_PID=""; ACT_STOP=""
}

# ---------------------------------------------------------------- state
MS_INDEX=0; PHASE="build"; REVIEW_N=0; REV_DONE=0; FABLE_UNTIL=0
MS_START_SHA=""; MS_START_EPOCH=0; ISSUES_FOUND=0; ISSUES_FIXED=0; LAST_REJECT_COUNT=0
INTERRUPTED=0; STOPPED=0; TOTAL_START=0; BATCH_N=0

save_state() {
  local k
  { for k in MS_INDEX PHASE REVIEW_N REV_DONE FABLE_UNTIL MS_START_SHA MS_START_EPOCH \
             ISSUES_FOUND ISSUES_FIXED LAST_REJECT_COUNT INTERRUPTED STOPPED TOTAL_START BATCH_N; do
      printf '%s=%q\n' "$k" "${!k}"
    done; } > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"
}
load_state() { [ -f "$STATE" ] && source "$STATE"; return 0; }

S_VERB=""; S_DETAIL=""; S_WAIT_UNTIL=""; S_PHASE_START=0
set_phase() {  # set_phase VERB [DETAIL]
  S_VERB="$1"; S_DETAIL="${2:-}"; S_PHASE_START=$(now_epoch); S_WAIT_UNTIL=""; write_status
}
write_status() {
  { printf 'S_MS=%q\nS_TITLE=%q\nS_VERB=%q\nS_DETAIL=%q\nS_WAIT_UNTIL=%q\nS_PHASE_START=%q\n' \
      "${MS_IDS[$MS_INDEX]}" "${MS_TITLES[$MS_INDEX]}" "$S_VERB" "$S_DETAIL" "$S_WAIT_UNTIL" "$S_PHASE_START"
    printf 'S_MS_START=%q\nS_START_SHA=%q\nS_FOUND=%q\nS_FIXED=%q\nS_VOFF=%q\n' \
      "$MS_START_EPOCH" "$MS_START_SHA" "$ISSUES_FOUND" "$ISSUES_FIXED" "$VOFF"; } > "$STATUS_FILE.tmp" \
    && mv "$STATUS_FILE.tmp" "$STATUS_FILE"
}

status_line() {  # the heartbeat text, from the status file
  [ -f "$STATUS_FILE" ] || return 1
  # shellcheck disable=SC1090
  source "$STATUS_FILE"
  local now=$(( $(date +%s) + S_VOFF ))
  local minute=$(( (now - S_MS_START) / 60 ))
  local files commits detail="$S_DETAIL"
  files=$( { git diff --name-only "$S_START_SHA" 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } \
           | sort -u | grep -v "^$BUILD_DIR/" | grep -c . )
  commits=$(git rev-list --count "$S_START_SHA"..HEAD 2>/dev/null || echo 0)
  if [ -n "$S_WAIT_UNTIL" ]; then
    local left=$(( S_WAIT_UNTIL - now )); [ "$left" -lt 0 ] && left=0
    detail="$detail ($(fmt_dur "$left") left)"
  elif [ -n "$detail" ]; then
    detail="$detail, $(fmt_dur $(( now - S_PHASE_START ))) in this step"
  fi
  printf 'still %s milestone %s "%s" (minute %d)%s | files changed: %d | commits: %d | issues so far: %d (%d fixed)' \
    "$S_VERB" "$S_MS" "$S_TITLE" "$minute" "${detail:+ | $detail}" "$files" "$commits" "$S_FOUND" "$S_FIXED"
}

TICKER_PID=""
start_ticker() {
  (
    trap 'exit 0' TERM
    while true; do
      if [ "$SLEEP_SCALE" = "1" ]; then sleep "$STATUS_EVERY"
      else sleep "$(awk -v s="$STATUS_EVERY" -v k="$SLEEP_SCALE" 'BEGIN{printf "%.3f", s*k}')"; fi
      if line=$(status_line); then
        say STATUS "$line"
        printf '[%s] %s\n' "$(date +%H:%M)" "$line" > "$STATUS_TXT"
      fi
    done
  ) &
  TICKER_PID=$!
}
stop_ticker() { [ -n "$TICKER_PID" ] && kill "$TICKER_PID" 2>/dev/null; TICKER_PID=""; }

on_interrupt() {
  stop_activity; stop_ticker; save_state
  say STOP "interrupted by you. Run bash build-runner.sh again to resume at ${MS_IDS[$MS_INDEX]} ($PHASE)."
  exit 130
}
trap on_interrupt INT TERM
trap 'stop_activity; stop_ticker' EXIT

# ---------------------------------------------------------------- limits and errors
parse_reset_epoch() {  # $1 text -> prints epoch. returns 0 parsed, 2 limit but unparseable, 1 no limit
  local text="$1" line when tz e n
  line=$(printf '%s\n' "$text" | grep -iE "hit your .*limit|limit reached|usage limit|limit.*reset|out of extra usage|try again in [0-9]+ (hour|minute)" | tail -1)
  [ -z "$line" ] && return 1
  if [[ $line =~ \|([0-9]{10}) ]]; then echo "${BASH_REMATCH[1]}"; return 0; fi
  if [[ $line =~ try\ again\ in\ ([0-9]+)\ (hour|minute) ]]; then
    n=${BASH_REMATCH[1]}
    if [ "${BASH_REMATCH[2]}" = "hour" ]; then echo $(( $(date +%s) + n * 3600 )); else echo $(( $(date +%s) + n * 60 )); fi
    return 0
  fi
  when=$(printf '%s' "$line" | sed -nE 's/.*[Rr]esets?( at)? +(([A-Z][a-z]{2},? )?([A-Z][a-z]{2} [0-9]{1,2},? )?[0-9]{1,2}(:[0-9]{2})? ?[apAP][mM]).*/\2/p')
  [ -z "$when" ] && return 2
  when=${when//,/}
  tz=$(printf '%s' "$line" | sed -nE 's/.*\(([A-Za-z_]+\/[A-Za-z_]+|UTC)\).*/\1/p')
  e=""
  if [ -n "$tz" ] && [ -e "/usr/share/zoneinfo/$tz" ]; then e=$(TZ="$tz" date -d "$when" +%s 2>/dev/null); fi
  [ -z "$e" ] && e=$(date -d "$when" +%s 2>/dev/null)
  [ -z "$e" ] && return 2
  n=$(date +%s)
  if [ "$e" -le "$n" ]; then
    if printf '%s' "$when" | grep -qE '^[A-Z][a-z]{2} [0-9]{1,2} '; then e=$(( e + 365 * 86400 ))
    elif printf '%s' "$when" | grep -qE '^[A-Z][a-z]{2} '; then e=$(( e + 7 * 86400 ))
    else e=$(( e + 86400 )); fi
  fi
  echo "$e"
}

is_transient() { printf '%s' "$1" | grep -qiE 'overloaded|"?529"?|internal server error|server_error|ECONNRESET|ETIMEDOUT|EAI_AGAIN|socket hang up|network error|timed out|temporarily unavailable|rate_limit|502 |503 |504 '; }
is_fatal()     { printf '%s' "$1" | grep -qiE 'not logged in|run /login|authentication_failed|invalid api key|unknown option|error: unknown|billing_error|account_on_hold|oauth_org_not_allowed|model_not_found|command not found|is not recognized'; }

wait_limit() {  # wait_limit EPOCH TEXT
  local kind="session" target when prev_verb="$S_VERB" prev_detail="$S_DETAIL"
  printf '%s' "$2" | grep -qi weekly && kind="weekly"
  target=$(( $1 + LIMIT_MARGIN ))
  [ "$SLEEP_SCALE" != "1" ] && target=$(( target - $(date +%s) + $(now_epoch) ))
  when=$(date -d "@$(( target - VOFF ))" '+%a %H:%M' 2>/dev/null || echo "?")
  say LIMIT "$kind limit hit, waiting until $when (reset + $((LIMIT_MARGIN / 60)) min)"
  printf '%s %s limit, waiting until %s\n' "$(date '+%F %T')" "$kind" "$when" >> "$BUILD_DIR/limits.log"
  S_VERB="waiting for usage limit in"; S_DETAIL="$kind limit until $when"; S_WAIT_UNTIL="$target"; write_status
  wait_until "$target"
  say RESUME "limit reset, continuing ${MS_IDS[$MS_INDEX]} ($prev_verb)"
  set_phase "$prev_verb" "$prev_detail"
}

wait_unparsed_limit() {
  local prev_verb="$S_VERB" prev_detail="$S_DETAIL"
  say LIMIT "usage limit hit but no reset time found, checking every 30 minutes"
  S_VERB="waiting for usage limit in"; S_DETAIL="no reset time, probing every 30 min"; write_status
  while true; do
    scaled_sleep 1800
    if "$CLAUDE_BIN" -p "reply ok" --model "$PROBE_MODEL" --output-format json "${PERM_FLAGS[@]}" >/dev/null 2>&1; then break; fi
  done
  say RESUME "limit is over, continuing ${MS_IDS[$MS_INDEX]} ($prev_verb)"
  set_phase "$prev_verb" "$prev_detail"
}

CONTINUE_PROMPT="You were interrupted (usage limit or a temporary error). Continue exactly where you stopped: check git status and the files you were writing, finish the batch, and end with the required result line from the original instructions."

fable_limited() { [ "$(now_epoch)" -lt "${FABLE_UNTIL:-0}" ]; }  # true while Fable is at its usage limit

coding_model() {  # coding_model MODEL EFFORT -> prints "model effort": Opus stands in for Fable while Fable is limited
  if [ "$1" = "fable" ] && fable_limited; then echo "$LIMIT_MODEL $LIMIT_EFFORT"; else echo "$1 $2"; fi
}

# switch_from_fable EPOCH_OR_EMPTY [inside]: Fable hit its limit; remember until when, so coding uses Opus meanwhile.
# "inside": Claude Code already moved the running session to Opus (--fallback-model); only the next batches change.
switch_from_fable() {
  local until="$1" when
  [ -z "$until" ] && until=$(( $(now_epoch) + 3600 ))   # no reset time found: try Fable again in an hour
  FABLE_UNTIL=$(( until + LIMIT_MARGIN )); save_state
  when=$(date -d "@$(( FABLE_UNTIL - VOFF ))" '+%a %H:%M' 2>/dev/null || echo "?")
  if [ "${2:-}" = "inside" ]; then
    say LIMIT "fable unavailable: Claude Code finished this batch on $LIMIT_MODEL in the same session; the next batches code on $LIMIT_MODEL ($LIMIT_EFFORT effort) until $when, then back to fable"
  else
    say LIMIT "fable usage limit hit: switching to $LIMIT_MODEL ($LIMIT_EFFORT effort) for coding until $when, then back to fable"
  fi
  printf '%s fable limit, coding on %s until %s\n' "$(date '+%F %T')" "$LIMIT_MODEL" "$when" >> "$BUILD_DIR/limits.log"
}

CALL_SID=""; CALL_TXT=""; STOP_REASON=""
call_claude() {  # call_claude MODEL EFFORT PROMPT_FILE OUT_BASE -> 0 when the run completed, 1 when Claude Code cannot run
  local model="$1" effort="$2" pfile="$3" out="$4" sid="" prompt orig tries=0 unknown=0 rc all epoch lim delay
  prompt=$(cat "$pfile"); orig="$prompt"
  while true; do
    local args=(-p "$prompt" --model "$model" "${PERM_FLAGS[@]}")
    if [ "$STREAM" = "1" ]; then args+=(--output-format stream-json --verbose); else args+=(--output-format json); fi
    [ -n "$effort" ] && args+=(--effort "$effort")
    if [ "$FALLBACK" = "1" ] && [ "$model" = "fable" ] && [ -n "$LIMIT_MODEL" ] && [ "$LIMIT_MODEL" != "fable" ]; then
      args+=(--fallback-model "$LIMIT_MODEL")   # Claude Code moves the session to Opus when Fable is unavailable
    fi
    [ -n "$sid" ] && args+=(--resume "$sid")
    if [ "$STREAM" = "1" ]; then
      local off
      [ -f "$out.stream.jsonl" ] || : > "$out.stream.jsonl"
      off=$(wc -c < "$out.stream.jsonl"); off=${off//[!0-9]/}; off=${off:-0}
      start_activity "$out.stream.jsonl" "$off"
      "$CLAUDE_BIN" "${args[@]}" >> "$out.stream.jsonl" 2> "$out.err" < /dev/null
      rc=$?
      stop_activity
      extract_result "$out.stream.jsonl" "$off" "$out.json"
    else
      "$CLAUDE_BIN" "${args[@]}" > "$out.json" 2> "$out.err" < /dev/null
      rc=$?
    fi
    parse_json "$out.json" > "$out.meta"   # sequential: the result file is complete before we read it
    CALL_SID=$(sed -n '1p' "$out.meta"); local is_err; is_err=$(sed -n '2p' "$out.meta")
    CALL_TXT="$out.txt"
    # what this attempt's stream says: the main session's models, and a rejected usage limit with its reset time
    local seg_models="" rej="" rej_epoch=""
    if [ "$STREAM" = "1" ]; then
      seg_models=$(tail -c +"$((off + 1))" "$out.stream.jsonl" 2>/dev/null | grep -E '"type": ?"assistant"' \
        | grep -vE '"parent_tool_use_id": ?"' | grep -oE '"model": ?"claude-[a-z]+' | sed 's/.*claude-//' \
        | sort -u | tr '\n' ' ')
      rej=$(tail -c +"$((off + 1))" "$out.stream.jsonl" 2>/dev/null | grep -E '"type": ?"rate_limit_event"' \
        | grep -E '"status": ?"rejected"' | tail -1)
      [ -n "$rej" ] && rej_epoch=$(printf '%s' "$rej" | grep -oE '"resetsAt": ?[0-9]+' | head -1 | grep -oE '[0-9]+')
    fi
    # Claude Code moved a Fable session to Opus by itself (--fallback-model): the next batches start on Opus
    if [ "$model" = "fable" ] && [[ " $seg_models " == *" $LIMIT_MODEL "* ]] && ! fable_limited; then
      switch_from_fable "$rej_epoch" inside
    fi
    if [ "$rc" -eq 0 ] && [ "$is_err" != "true" ] && [ -s "$out.txt" ]; then
      # a short answer with no result line that reads like a usage limit is a limit, not a finished batch
      local short_lim=1
      if [ "$(wc -c < "$out.txt" | tr -d ' ')" -lt 400 ] \
         && ! grep -qE "MILESTONE_RESULT|REVIEW_VERDICT|FIX_RESULT|PLAN_RESULT" "$out.txt"; then
        parse_reset_epoch "$(cat "$out.txt")" >/dev/null; short_lim=$?
      fi
      [ "$short_lim" -eq 1 ] && return 0
    fi
    all="$(cat "$out.json" "$out.err" 2>/dev/null)"
    epoch=$(parse_reset_epoch "$all"); lim=$?
    if [ "$lim" -eq 1 ] && [ -n "$rej" ]; then   # the stream reported a rejected usage limit
      if [ -n "$rej_epoch" ]; then epoch="$rej_epoch"; lim=0; else lim=2; fi
    fi
    if [ "$lim" -eq 1 ] && [ "$model" = "fable" ] \
       && printf '%s' "$all" | grep -qiE 'reached your .*limit|rate_limit_error|\b429\b|not available|unavailable'; then
      lim=2   # on Fable, an unfamiliar limit message still means: carry on with Opus
    fi
    if [ "$lim" -ne 1 ] && [ "$model" = "fable" ] && [ -n "$LIMIT_MODEL" ] && [ "$LIMIT_MODEL" != "fable" ]; then
      # Fable is at its limit: carry on with Opus in a fresh session that picks up the work from the files
      if [ "$lim" -eq 0 ]; then switch_from_fable "$epoch"; else switch_from_fable ""; fi
      model="$LIMIT_MODEL"; effort="$LIMIT_EFFORT"; sid=""
      prompt="$orig

Note: a previous session on this batch was cut off by a usage limit. Check git status, git log and build/${MS_IDS[$MS_INDEX]}/ first, and continue that work instead of starting over."
      say RESUME "continuing this batch on $model in a new session"
      continue
    fi
    if [ "$lim" -eq 0 ]; then wait_limit "$epoch" "$all"
    elif [ "$lim" -eq 2 ]; then wait_unparsed_limit
    elif is_fatal "$all"; then
      STOP_REASON="Claude Code cannot run: $(printf '%s' "$all" | grep -iE 'error|not|unknown|invalid' | head -1 | cut -c1-200)"
      return 1
    elif is_transient "$all" && [ "$tries" -lt 3 ]; then
      tries=$((tries + 1)); delay=$(( 60 * 4 ** (tries - 1) ))
      say RETRY "temporary error ($(printf '%s' "$all" | grep -oiE 'overloaded|529|server_error|timed out|ECONNRESET|rate_limit|50[234]' | head -1)), retrying in $(fmt_dur "$delay") (try $tries/3)"
      local pv="$S_VERB" pd="$S_DETAIL"
      S_VERB="retrying"; S_DETAIL="temporary error, next try in $(fmt_dur "$delay")"; write_status
      scaled_sleep "$delay"; set_phase "$pv" "$pd"
    elif [ "$unknown" -lt 2 ]; then
      unknown=$((unknown + 1))
      say RETRY "the batch ended with an error, retrying (try $unknown/2): $(cat "$out.txt" "$out.err" 2>/dev/null | head -c 160 | tr '\n' ' ')"
      scaled_sleep 60
    else
      STOP_REASON="the batch keeps failing: $(cat "$out.err" "$out.txt" 2>/dev/null | head -c 300 | tr '\n' ' ')"
      return 1
    fi
    if [ -n "$CALL_SID" ]; then sid="$CALL_SID"; prompt="$CONTINUE_PROMPT"; say RESUME "continuing the same Claude session ($model)"; fi
  done
}

result_line() { grep -oE "$2: [A-Z]+.*" "$1" 2>/dev/null | tail -1; }  # result_line FILE KEY

# ---------------------------------------------------------------- prompts
common_rules() {
  cat <<EOF
Rules for every batch:
- Read $SPEC (the full spec), CLAUDE.md, PLAN.md, DECISIONS.md, build/progress.md, build/HUMAN_TODO.md,
  build/open-issues.md and pipeline/knowledge/known-issues.md when they exist. They are the memory between batches.
  build/open-issues.md lists review findings from earlier milestones that were never re-checked: fix one when it
  gets in the way of your work.
- Nobody is watching. Never wait for me and never ask questions. When something needs me, use the spec's default,
  keep going, and add a line to build/HUMAN_TODO.md: "- $1: what I need to do, where".
- Never write an em dash in any file.
EOF
  if [ "$INTERRUPTED" = "1" ]; then
    echo "- A previous attempt at this batch was interrupted. Check git status, git log and build/$1/ first, and continue that work instead of starting over."
  fi
}

prompt_build() {
  local id="$1" title="$2"
  cat <<EOF
You are building milestone $id ($title) of the Instagram reels autopilot described in $SPEC.
This is one batch of an automated build: build-runner.sh runs each milestone in a fresh session, then a reviewer checks it.

$(common_rules "$id")

Do:
1. Build only milestone $id as defined in $SPEC section 12 and in PLAN.md. Do not start later milestones.
   Touch earlier milestones only when $id depends on it, and say so in your report.
2. Run the acceptance test for $id until it passes. Run an earlier milestone's test (build/progress.md) only when
   you changed that milestone's code.
3. Commit your work with clear messages, for example: feat($id): ...
4. Write build/$id/report.md: what you built, the files, how to run the test, a short summary of the test output,
   known gaps, and the HUMAN_TODO items you added.
5. Update build/progress.md (one section per milestone, including the command that runs its test) and the build status in CLAUDE.md.

End your final message with exactly one of these lines:
MILESTONE_RESULT: DONE
MILESTONE_RESULT: BLOCKED <one-line reason>
Use BLOCKED only for something you truly cannot do without me.
EOF
}

prompt_plan() {
  cat <<EOF
You are starting the automated build of the Instagram reels autopilot described in $SPEC. This batch is milestone M0 (Plan).

$(common_rules M0)

Do:
1. Read $SPEC completely.
2. Write PLAN.md: for every milestone M1 to M13, the files it creates, its acceptance test (exact command), and what it depends on.
3. Write DECISIONS.md with the decisions you already made, and CLAUDE.md as described in $SPEC section 11.
4. Create build/progress.md with an empty section per milestone. Write no pipeline code.
5. Commit: docs(M0): plan.
6. Write build/M0/report.md.

End your final message with exactly one of these lines:
MILESTONE_RESULT: DONE
MILESTONE_RESULT: BLOCKED <one-line reason>
EOF
}

prompt_review() {
  local id="$1" title="$2" n="$3" sha="$4"
  cat <<EOF
You are the reviewer for milestone $id ($title) of the build described in $SPEC. This is review $n of at most
$MAX_REVIEWS. You did not write this code. Fresh session.

This is a lenient, quick review. After the last review the build moves on to the next milestone whatever you decide,
so the goal is to catch what would really hurt, not to polish. Speed matters: the whole build is waiting on you.

$(common_rules "$id")

Read: section 12 of $SPEC for $id (its scope and test), the PLAN.md section for $id, build/$id/report.md, the earlier
reviews and fix notes in build/$id/, and the changes since commit $sha (git log $sha..HEAD, git diff --stat, then
only the files that matter).

Run the acceptance test for $id once and summarize the output. Do not run run-all.sh or the earlier milestones'
tests, unless $id changed their code.

Reject only for these reasons:
1. The acceptance test for $id fails or cannot run.
2. A crash, lost data, or an earlier feature that no longer works.
3. Something a later milestone needs from $id is missing (a file, a command, an interface PLAN.md names).
Everything else (style, naming, extra edge cases, documentation, small spec gaps later milestones do not depend on,
tests you would like to add) goes under suggestions and never causes a rejection. List at most 3 required fixes, the
most important ones. When in doubt, approve.

Do not edit code. Write build/$id/review-$n.md with: the verdict; "Required fixes" as a numbered list (each with
file, problem, how to verify); then suggestions.
For M0, review PLAN.md against the spec instead of code.

End your final message with exactly one of these lines:
REVIEW_VERDICT: APPROVED
REVIEW_VERDICT: REJECTED <number of required fixes>
EOF
}

prompt_fix() {
  local id="$1" title="$2" n="$3"
  cat <<EOF
You are fixing milestone $id ($title) of the build described in $SPEC, after review $n rejected it. Fresh session.

$(common_rules "$id")

Read build/$id/report.md, build/$id/review-$n.md, and the earlier reviews and fix notes in build/$id/.
1. Apply every required fix in review-$n.md. No unrelated changes, and skip the suggestions.
2. Re-run the acceptance test for $id (an earlier milestone's test only if you changed its code).
3. Commit: fix($id): ...
4. Write build/$id/fixes-$n.md: each required fix, what you changed, how you verified it.

End your final message with exactly one of these lines:
FIX_RESULT: DONE
FIX_RESULT: BLOCKED <one-line reason>
EOF
}

# ---------------------------------------------------------------- batches
todo_count() { local n; n=$(grep -c '^- ' "$TODO" 2>/dev/null); echo "${n:-0}"; }

run_batch() {  # run_batch ROLE MODEL EFFORT PROMPT_TEXT -> sets BATCH_TXT
  local role="$1" model="$2" effort="$3" text="$4" id="${MS_IDS[$MS_INDEX]}" dir pfile before after
  [ "$role" != "review" ] && read -r model effort <<< "$(coding_model "$model" "$effort")"
  dir="$BUILD_DIR/$id/batches"; mkdir -p "$dir"
  BATCH_N=$((BATCH_N + 1)); save_state
  pfile="$dir/$(printf '%02d' "$BATCH_N")-$role.prompt.md"
  printf '%s\n' "$text" > "$pfile"
  before=$(todo_count)
  local t0; t0=$(now_epoch)
  say CLAUDE "$id batch $(printf '%02d' "$BATCH_N") ($role, $model${effort:+, $effort effort}) started. Prompt: $pfile"
  if [ "$STREAM" = "1" ]; then say CLAUDE "full transcript: ${pfile%.prompt.md}.stream.jsonl"; fi
  if ! call_claude "$model" "$effort" "$pfile" "${pfile%.prompt.md}"; then
    stop_build "$STOP_REASON"
  fi
  BATCH_TXT="$CALL_TXT"
  say CLAUDE "$id batch $(printf '%02d' "$BATCH_N") ($role) finished after $(fmt_dur $(( $(now_epoch) - t0 )))"
  after=$(todo_count)
  if [ "$after" -gt "$before" ]; then say HUMAN "$id added $((after - before)) item(s) to $TODO (total $after)"; fi
}

marked_batch() {  # like run_batch, but marks the batch as in progress so a restart knows it was interrupted
  INTERRUPTED=1; save_state
  run_batch "$@"
  INTERRUPTED=0; save_state
}

stop_build() {
  STOPPED=1; save_state; stop_ticker
  local id="${MS_IDS[$MS_INDEX]}"
  {
    echo "# Build stopped at $id (${MS_TITLES[$MS_INDEX]})"
    echo
    echo "When: $(date '+%F %H:%M')"
    echo "Phase: $PHASE (review $REVIEW_N; $REV_DONE of $MAX_REVIEWS reviews since the last start)"
    echo
    echo "Reason: $1"
    echo
    echo "Last files: build/$id/ (reports, reviews, fixes, batches)"
    echo
    echo "To continue: fix the problem (or edit $SPEC), then run: bash build-runner.sh"
    echo "It resumes at $id with fresh review counters."
  } > "$BUILD_DIR/STOPPED.md"
  say STOP "$id: $1"
  say STOP "see $BUILD_DIR/STOPPED.md. Run bash build-runner.sh again after fixing to resume at $id."
  exit 1
}

start_milestone() {
  PHASE="build"; REVIEW_N=0; REV_DONE=0; LAST_REJECT_COUNT=0
  ISSUES_FOUND=0; ISSUES_FIXED=0; INTERRUPTED=0
  MS_START_SHA=$(git rev-parse HEAD 2>/dev/null || echo ""); MS_START_EPOCH=$(now_epoch)
  save_state
}

latest_file() {  # latest_file DIR PREFIX: the highest-numbered DIR/PREFIX-N.md, or "none"
  local f; f=$(ls "$1/$2"-*.md 2>/dev/null | sort -V | tail -1); echo "${f:-none}"
}

note_open_issues() {  # note_open_issues WHAT: record the last review's unchecked fixes in build/open-issues.md
  local id="${MS_IDS[$MS_INDEX]}" f="$BUILD_DIR/open-issues.md"
  [ -f "$f" ] || printf '# Open issues\n\nReview findings that were never re-checked, because the build moves on after %s reviews.\nLater batches: fix one when it gets in the way of your work.\n\n' "$MAX_REVIEWS" > "$f"
  local rv; rv=$(latest_file "$BUILD_DIR/$id" review); [ "$rv" = "none" ] && rv="$BUILD_DIR/$id/review-$REVIEW_N.md"
  printf -- '- %s: %s required fix(es) in %s, %s\n' "$id" "$LAST_REJECT_COUNT" "$rv" "$1" >> "$f"
}

finish_milestone() {  # finish_milestone approved|moved: commit build/ and print the result
  local id="${MS_IDS[$MS_INDEX]}" elapsed files commits
  elapsed=$(( $(now_epoch) - MS_START_EPOCH ))
  files=$(git diff --name-only "$MS_START_SHA" 2>/dev/null | grep -vc "^$BUILD_DIR/")
  commits=$(git rev-list --count "$MS_START_SHA"..HEAD 2>/dev/null || echo 0)
  if [ "$1" = "approved" ]; then
    git add -A "$BUILD_DIR" >/dev/null 2>&1 && git commit -q -m "build($id): approved after $REVIEW_N review(s)" >/dev/null 2>&1
    say PASS "$id approved after $REVIEW_N review(s): $(fmt_dur "$elapsed"), $files files changed, $commits commits, $ISSUES_FOUND issues found and fixed"
  else
    git add -A "$BUILD_DIR" >/dev/null 2>&1 && git commit -q -m "build($id): moved on after $REVIEW_N review(s)" >/dev/null 2>&1
    say MOVEON "$id moved on after $REVIEW_N review(s) without approval (see $BUILD_DIR/open-issues.md): $(fmt_dur "$elapsed"), $files files changed, $commits commits, $ISSUES_FOUND issues found, $ISSUES_FIXED fixed"
  fi
}

run_milestone() {
  local id="${MS_IDS[$MS_INDEX]}" title="${MS_TITLES[$MS_INDEX]}" res verdict count model effort
  mkdir -p "$BUILD_DIR/$id"

  if [ "$PHASE" = "build" ]; then
    read -r model effort <<< "$(coding_model "$BUILD_MODEL" "$BUILD_EFFORT")"
    say BUILD "$id $title: building ($model, $effort effort)"
    set_phase "building"
    if [ "$id" = "M0" ]; then marked_batch build "$BUILD_MODEL" "$BUILD_EFFORT" "$(prompt_plan)"
    else marked_batch build "$BUILD_MODEL" "$BUILD_EFFORT" "$(prompt_build "$id" "$title")"; fi
    res=$(result_line "$BATCH_TXT" MILESTONE_RESULT)
    case "$res" in
      *BLOCKED*) stop_build "builder says it needs you: ${res#*BLOCKED}" ;;
      *DONE*) say STEP "$id build batch finished, sending to review" ;;
      *) say WARN "$id build batch ended without a result line, the review will check it" ;;
    esac
    PHASE="review"; save_state
  fi

  while true; do
    if [ "$PHASE" = "fix" ]; then
      read -r model effort <<< "$(coding_model "$FIX_MODEL" "$FIX_EFFORT")"
      say FIX "$id applying review $REVIEW_N fixes ($LAST_REJECT_COUNT required, $model)"
      set_phase "fixing" "review $REVIEW_N fixes, $model"
      marked_batch fix "$FIX_MODEL" "$FIX_EFFORT" "$(prompt_fix "$id" "$title" "$REVIEW_N")"
      res=$(result_line "$BATCH_TXT" FIX_RESULT)
      case "$res" in
        *BLOCKED*) stop_build "fixer says it needs you: ${res#*BLOCKED}" ;;
        *) ISSUES_FIXED=$((ISSUES_FIXED + LAST_REJECT_COUNT)) ;;
      esac
      PHASE="review"; save_state
    fi

    if [ "$REV_DONE" -ge "$MAX_REVIEWS" ]; then  # the last review's fixes are in: no more reviews, move on
      res=$(latest_file "$BUILD_DIR/$id" fixes); [ "$res" = "none" ] && res="the last fix batch"
      note_open_issues "fixed in $res without another review"
      finish_milestone moved
      return 0
    fi

    # a review interrupted by a kill or crash is redone under the same number
    if [ "$INTERRUPTED" != "1" ]; then REVIEW_N=$((REVIEW_N + 1)); fi
    say REVIEW "$id review $REVIEW_N ($REVIEW_MODEL, $((REV_DONE + 1))/$MAX_REVIEWS, lenient)"
    set_phase "reviewing" "review $REVIEW_N, $REVIEW_MODEL, $((REV_DONE + 1))/$MAX_REVIEWS"
    save_state
    marked_batch review "$REVIEW_MODEL" "$REVIEW_EFFORT" "$(prompt_review "$id" "$title" "$REVIEW_N" "$MS_START_SHA")"
    verdict=$(result_line "$BATCH_TXT" REVIEW_VERDICT)

    if [[ "$verdict" == *APPROVED* ]]; then
      finish_milestone approved
      return 0
    fi

    count=$(printf '%s' "$verdict" | grep -oE '[0-9]+' | head -1); count=${count:-1}
    [ -z "$verdict" ] && say WARN "$id review ended without a verdict line, counted as rejected"
    LAST_REJECT_COUNT=$count; ISSUES_FOUND=$((ISSUES_FOUND + count))
    say REJECT "$id review $REVIEW_N: $count required fix(es), see $BUILD_DIR/$id/review-$REVIEW_N.md"
    REV_DONE=$((REV_DONE + 1))
    if [ "$REV_DONE" -ge "$MAX_REVIEWS" ]; then
      if [ "$FINAL_FIX" != "1" ]; then
        note_open_issues "left open"
        finish_milestone moved
        return 0
      fi
      say NOTE "$id that was the last review: one fix batch for it, then the build moves on to the next milestone"
    fi
    PHASE="fix"; save_state
  done
}

# ---------------------------------------------------------------- setup
ensure_git() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git init -q
    say START "initialized a git repository"
  fi
  if [ ! -f .gitignore ]; then
    say START "no .gitignore yet, writing the runner's default one"
    cat > .gitignore <<'EOF'
runs/
exports/
logs/
.locks/
.env
node_modules/
__pycache__/
*.mp4
*.mov
library/voice/
styles/*/refs/
styles/*/analysis/
styles/sfx/**/*.wav
styles/sfx/**/*.mp3
styles/sfx/**/*.aif
styles/sfx/**/*.aiff
styles/sfx/**/*.ogg
styles/sfx/**/*.flac
styles/sfx/**/*.m4a
styles/sfx/.cache/
styles/sfx/previews/
build/state.env
build/.status
build/status.txt
build/*.log
build/*/batches/
build/check.*
EOF
  fi
  [ -f .gitattributes ] || printf '*.sh text eol=lf\n' > .gitattributes
  git config user.name >/dev/null 2>&1 || git config user.name "reels-autopilot"
  git config user.email >/dev/null 2>&1 || git config user.email "autopilot@localhost"
  if ! git rev-parse HEAD >/dev/null 2>&1; then
    say START "no commits yet, committing everything not ignored as the starting point"
    git add -A >/dev/null 2>&1 && git commit -q -m "chore: initial import before the automated build" >/dev/null 2>&1
  fi
  say CHECK "git: branch $(git branch --show-current 2>/dev/null || echo '?'), $(git rev-list --count HEAD 2>/dev/null || echo 0) commit(s), HEAD $(git rev-parse --short HEAD 2>/dev/null || echo none)"
  if ! grep -qxF 'build/state.env' .gitignore 2>/dev/null; then
    say WARN ".gitignore does not list the runner's own files (build/state.env, build/*.log, ...): approved milestones will commit them too"
  fi
}

fallback_start_sha() {  # the start point of the current milestone when the saved state lost it
  local sha="" prev
  if [ "$MS_INDEX" -gt 0 ]; then
    prev="${MS_IDS[$((MS_INDEX - 1))]}"
    sha=$(git log --format=%H -1 --grep="^build($prev): approved" 2>/dev/null)
  fi
  [ -z "$sha" ] && sha=$(git rev-list --max-parents=0 HEAD 2>/dev/null | tail -1)
  echo "$sha"
}

preflight() {
  local ok=1 v
  say CHECK "checking the tools the build needs"
  if command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
    v=$("$CLAUDE_BIN" --version 2>/dev/null | head -1)
    say CHECK "claude: ${v:-found} ($(command -v "$CLAUDE_BIN"))"
  else say ERROR "claude is not on PATH in Git Bash"; ok=0; fi
  if command -v git >/dev/null 2>&1; then say CHECK "git: $(git --version 2>/dev/null | sed 's/^git version //')"
  else say ERROR "git is not installed"; ok=0; fi
  if [ -n "$PY" ]; then say CHECK "python: $PY $("$PY" -c 'import sys; print(sys.version.split()[0])' 2>/dev/null)"
  else say ERROR "Python 3.8+ not found (tried python3, python, py)"; ok=0; fi
  if [ -f "$SPEC" ]; then say CHECK "spec: $SPEC ($(wc -l < "$SPEC" | tr -d ' ') lines)"
  else say ERROR "$SPEC not found in $(pwd)"; ok=0; fi
  if date -d "Mon 12:00am" +%s >/dev/null 2>&1; then say CHECK "GNU date: ok"
  else say ERROR "GNU date is missing (run this from Git Bash)"; ok=0; fi
  [ "$ok" = "1" ] || { say STOP "fix the problems above, then run bash build-runner.sh again"; exit 1; }
}

check_claude() {  # one tiny call with the same flags the batches use
  local out="$BUILD_DIR/check"
  local t0
  printf 'Reply with the single word: ok\n' > "$out.prompt.md"
  say CHECK "testing Claude Code with one tiny call ($PROBE_MODEL, flags: ${PERM_FLAGS[*]}), usually 10 to 30 s"
  set_phase "checking Claude Code for"
  t0=$(now_epoch)
  if call_claude "$PROBE_MODEL" "" "$out.prompt.md" "$out"; then
    say START "Claude Code check passed in $(fmt_dur $(( $(now_epoch) - t0 ))) ($PROBE_MODEL, flags: ${PERM_FLAGS[*]})"
    return 0
  fi
  say ERROR "Claude Code check failed: $STOP_REASON"
  say ERROR "if the permission flags are the problem, see PERM_FLAGS at the top of build-runner.sh"
  exit 1
}

# ---------------------------------------------------------------- main
[ "${BUILD_RUNNER_LIB_ONLY:-0}" = "1" ] && return 0 2>/dev/null
FROM=""; REVIEW_PLAN=0; CHECK_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift ;;
    --review-plan) REVIEW_PLAN=1 ;;
    --status) if [ -f "$STATUS_TXT" ]; then cat "$STATUS_TXT"; elif line=$(status_line); then echo "$line"; else echo "not started"; fi; exit 0 ;;
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,/^$/p' "$0"; exit 0 ;;
    *) echo "unknown option: $1"; exit 2 ;;
  esac
  shift
done

say START "build runner starting in $(pwd) (log: $LOG)"
if [ "$CHECK_ONLY" = "1" ]; then
  preflight; check_claude
  say DONE "check finished: the runner is ready. Start it with: bash build-runner.sh"
  exit 0
fi
preflight
ensure_git
[ -f "$TODO" ] || printf '# Things the build needs from you\n\nEach line: milestone, what to do, where.\n\n' > "$TODO"
load_state

if [ -n "$FROM" ]; then
  idx=-1
  for i in "${!MS_IDS[@]}"; do [ "${MS_IDS[$i]}" = "$FROM" ] && idx=$i; done
  [ "$idx" -lt 0 ] && { echo "unknown milestone: $FROM (use M0 to M13)"; exit 2; }
  MS_INDEX=$idx; STOPPED=0; start_milestone
  say START "restarting from $FROM ${MS_TITLES[$MS_INDEX]}, as you asked"
elif [ ! -f "$STATE" ]; then
  MS_INDEX=0; TOTAL_START=$(now_epoch); start_milestone
  say START "no saved state: starting a fresh build at M0 ${MS_TITLES[0]}"
elif [ "$STOPPED" = "1" ]; then
  STOPPED=0; REV_DONE=0
  [ "$PHASE" = "fix" ] && PHASE="review"
  save_state
  say START "resuming after a stop: ${MS_IDS[$MS_INDEX]} with fresh review counters"
else
  if [ "$INTERRUPTED" = "1" ]; then
    say START "resuming ${MS_IDS[$MS_INDEX]} ${MS_TITLES[$MS_INDEX]} at the $PHASE step: the last batch was interrupted, the next one continues its work"
  else
    say START "resuming ${MS_IDS[$MS_INDEX]} ${MS_TITLES[$MS_INDEX]} at the $PHASE step"
  fi
fi
if [ "${MS_START_EPOCH:-0}" = "0" ] || [ -z "$MS_START_SHA" ]; then  # e.g. a Ctrl+C during the startup checks saved an empty state
  MS_START_SHA=$(fallback_start_sha); [ "${MS_START_EPOCH:-0}" = "0" ] && MS_START_EPOCH=$(now_epoch)
  save_state
  say NOTE "the saved state had no start point for ${MS_IDS[$MS_INDEX]}; using commit ${MS_START_SHA:0:7}"
fi
[ "$TOTAL_START" = "0" ] && TOTAL_START=$(now_epoch)

check_claude
say START "build runner: ${#MS_IDS[@]} batches (M0 to M13), now at ${MS_IDS[$MS_INDEX]} ${MS_TITLES[$MS_INDEX]} ($PHASE). Status every $(fmt_dur "$STATUS_EVERY"), live feed: $([ "$STREAM" = "1" ] && echo "$ACTIVITY" || echo off)."
say START "coding: $BUILD_MODEL ($BUILD_EFFORT), $LIMIT_MODEL ($LIMIT_EFFORT) while $BUILD_MODEL is at its limit. Reviews: $REVIEW_MODEL ($REVIEW_EFFORT), lenient, at most $MAX_REVIEWS per milestone, then it moves on. Log: $LOG"
[ "$FALLBACK" = "1" ] && say START "fable batches run with --fallback-model $LIMIT_MODEL: when fable runs out mid-batch, Claude Code carries on with $LIMIT_MODEL in the same session"
fable_limited && say NOTE "fable is still at its usage limit until $(date -d "@$(( FABLE_UNTIL - VOFF ))" '+%a %H:%M' 2>/dev/null): coding on $LIMIT_MODEL until then"
start_ticker

while [ "$MS_INDEX" -lt "${#MS_IDS[@]}" ]; do
  run_milestone
  if [ "${MS_IDS[$MS_INDEX]}" = "M0" ] && [ "$REVIEW_PLAN" = "1" ] && [ -t 0 ]; then
    say WAIT "PLAN.md is approved by the reviewer. Read it now; press Enter to start building (Ctrl+C to stop)"
    read -r _
  fi
  MS_INDEX=$((MS_INDEX + 1))
  if [ "$MS_INDEX" -lt "${#MS_IDS[@]}" ]; then
    start_milestone
    say NEXT "${MS_IDS[$MS_INDEX]} ${MS_TITLES[$MS_INDEX]}"
  fi
done

stop_ticker
save_state
say DONE "all ${#MS_IDS[@]} batches complete in $(fmt_dur $(( $(now_epoch) - TOTAL_START ))). $(todo_count) item(s) in $TODO"
[ "$(todo_count)" -gt 0 ] && grep '^- ' "$TODO" | sed 's/^/        /'
exit 0
