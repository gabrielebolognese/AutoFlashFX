#!/usr/bin/env bash
# test-limits.sh: unit tests of the usage limit parser (pipeline/lib/limits.py, BUILD_SPEC.md 4.1) and of the error
# classifier and signature (pipeline/lib/errors.py). No model calls, no sandbox, a few seconds.
#   bash pipeline/tests/test-limits.sh
#
# Every format of the spec with a fixed clock (Saturday 2026-10-31 14:31 Europe/Rome) and a fixed default zone, so
# the expected epochs are computed independently here (explicit datetimes in Python) and do not depend on the PC's
# clock or zone: time only, weekday and time, date and time, a timezone in parentheses, an epoch after a |, plus the
# rollovers (+1 day, +7 days, next year), a DST change inside the wait, the weekly kind, an unparseable limit and
# text without a limit.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
LIMITS="$REPO_DIR/pipeline/lib/limits.py"
ERRORS="$REPO_DIR/pipeline/lib/errors.py"
TZ_NAME="Europe/Rome"

epoch_of() {  # epoch_of "YYYY-MM-DD HH:MM" [zone]: an aware datetime built directly, independent of limits.py
  python -c '
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
d = datetime.strptime(sys.argv[1], "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(sys.argv[2]))
print(int(d.timestamp()))' "$1" "${2:-$TZ_NAME}"
}
NOW="$(epoch_of "2026-10-31 14:31")"   # a Saturday, CET (DST ended on Oct 25)

parse() {  # parse "<phrase>" -> "parsed reset kind" (reset as epoch), PARSE_RC set
  local out
  out="$(python "$LIMITS" parse-when --tz "$TZ_NAME" --now "$NOW" "$1")"; PARSE_RC=$?
  python -c 'import json, sys; d = json.loads(sys.argv[1]); print(d.get("parsed"), d.get("reset"), d.get("kind"))' "$out"
}

check_when() {  # check_when "<phrase>" <expected how> "<expected local time>" [zone] "<name>"
  local phrase="$1" how="$2" when="$3" zone="$4" name="$5" got exp
  got="$(parse "$phrase")"
  exp="$how $(epoch_of "$when" "$zone")"
  assert_eq "${got% *}" "$exp" "$name: $phrase"
}

section "1. every reset-time format, with the clock at Sat 2026-10-31 14:31 Europe/Rome"
check_when "resets 3:45pm" time "2026-10-31 15:45" "$TZ_NAME" "time only"
check_when "resets 3pm" time "2026-10-31 15:00" "$TZ_NAME" "time only, no minutes"
check_when "resets 15:45" time "2026-10-31 15:45" "$TZ_NAME" "time only, 24h"
check_when "resets at 11:59pm" time "2026-10-31 23:59" "$TZ_NAME" "time only with 'at'"
check_when "resets 1pm" time "2026-11-01 13:00" "$TZ_NAME" "a past time rolls to tomorrow (+1 day)"
check_when "resets 2:30pm" time "2026-11-01 14:30" "$TZ_NAME" "a time one minute past rolls to tomorrow"
check_when "resets Mon 12:00am" weekday "2026-11-02 00:00" "$TZ_NAME" "weekday and time"
check_when "resets Monday 9am" weekday "2026-11-02 09:00" "$TZ_NAME" "full weekday name"
check_when "resets Sat 2:00pm" weekday "2026-11-07 14:00" "$TZ_NAME" "today's weekday, past time: +7 days"
check_when "resets Sat 6pm" weekday "2026-10-31 18:00" "$TZ_NAME" "today's weekday, time still ahead: today"
check_when "resets Nov 3, 10am" date "2026-11-03 10:00" "$TZ_NAME" "date and time"
check_when "resets November 3 10:30am" date "2026-11-03 10:30" "$TZ_NAME" "full month name, no comma"
check_when "resets Oct 30, 10am" date "2027-10-30 10:00" "$TZ_NAME" "a past date rolls to next year"
check_when "resets 3pm (Europe/Rome)" time "2026-10-31 15:00" "Europe/Rome" "zone in parentheses, same zone"
check_when "resets 3pm (America/New_York)" time "2026-10-31 15:00" "America/New_York" "zone in parentheses, another zone"
check_when "resets 3pm (UTC)" time "2026-10-31 15:00" "UTC" "UTC in parentheses"
check_when "resets 3pm (PST)" time "2026-10-31 15:00" "America/Los_Angeles" "an abbreviation maps to its zone"
check_when "resets Mon 12:00am (America/New_York)" weekday "2026-11-02 00:00" "America/New_York" "weekday in a zone whose DST ends inside the wait (Nov 1)"
check_when "resets Nov 3, 10am (UTC)" date "2026-11-03 10:00" "UTC" "date in UTC"
check_when "resets 3pm (Mars/Olympus)" time "2026-10-31 15:00" "$TZ_NAME" "an unknown zone falls back to the default zone"
got="$(parse "Claude AI usage limit reached|1793696400")"
assert_eq "${got% *}" "epoch 1793696400" "an epoch after a |"
got="$(parse "limit reached | 1793696400000")"
assert_eq "${got% *}" "epoch 1793696400" "a 13-digit epoch is milliseconds"
got="$(parse "try again in 2 hours")"
assert_eq "${got% *}" "relative $((NOW + 7200))" "a relative time (extra)"

section "2. kinds, detection, the unparseable case and no limit"
got="$(parse "You've hit your weekly limit · resets Mon 12:00am")"
assert_eq "${got##* }" "weekly" "weekly kind"
got="$(parse "You've hit your session limit · resets 3:45pm")"
assert_eq "${got##* }" "session" "session kind"
got="$(parse "Claude AI usage limit reached|1793696400")"
assert_eq "${got##* }" "usage" "usage kind"
python "$LIMITS" detect --tz "$TZ_NAME" --now "$NOW" "You've hit your usage limit. Try again later." >/dev/null; rc=$?
assert_rc 2 $rc "a limit with no reset time exits 2"
python "$LIMITS" detect --tz "$TZ_NAME" --now "$NOW" "the function's limit is 3, resets nothing" >/dev/null; rc=$?
assert_rc 1 $rc "text without a limit exits 1"
python "$LIMITS" detect --tz "$TZ_NAME" --now "$NOW" "all fine" >/dev/null; rc=$?
assert_rc 1 $rc "plain text exits 1"
out="$(printf 'noise\nError: You have hit your session limit\nresets 3:45pm (Europe/Rome)\n' | python "$LIMITS" detect --stdin --tz "$TZ_NAME" --now "$NOW")"; rc=$?
assert_rc 0 $rc "a limit split over stdin lines parses"
assert_eq "$(python -c 'import json,sys; d=json.loads(sys.argv[1]); print(d["reset"], d["target"], d["kind"])' "$out")" \
  "$(epoch_of "2026-10-31 15:45") $(( $(epoch_of "2026-10-31 15:45") + 120 )) session" "the target is the reset plus the 120 s margin"
out="$(python "$LIMITS" detect --tz "$TZ_NAME" --now "$NOW" --margin 300 "hit your limit · resets 3:45pm")"
assert_eq "$(python -c 'import json,sys; print(json.loads(sys.argv[1])["target"])' "$out")" "$(( $(epoch_of "2026-10-31 15:45") + 300 ))" "the margin is a parameter"
assert_eq "$(python "$LIMITS" left $((NOW + 20460)) --now "$NOW")" "5h41m" "left: hours and minutes"
assert_eq "$(python "$LIMITS" left $((NOW + 720)) --now "$NOW")" "12m" "left: minutes"

section "3. the error signature and the classifier"
s1="$(python "$ERRORS" signature "exit 1: KeyError: 'beatz' at C:/Users/x/pipeline/stages/10-build/helper.py line 14 (2026-10-31 15:58)")"
s2="$(python "$ERRORS" signature "exit 1: KeyError: 'beatz' at D:/other/helper.py line 99 (2026-11-02 09:01)")"
s3="$(python "$ERRORS" signature "exit 1: KeyError: 'beats'")"
assert_eq "$s1" "$s2" "the signature ignores paths, numbers and timestamps"
assert_ne "$s1" "$s3" "a different message gives a different signature"
assert_true "the signature is 12 hex characters" grep -q -E '^[0-9a-f]{12}$' <<<"$s1"
tmp="$(mktemp -d)"
printf '{"type":"result","is_error":true,"result":"API Error: 529 overloaded_error","api_error_status":529,"session_id":"abc"}' > "$tmp/529.json"
cls() { python "$ERRORS" classify --rc "$1" --stdout "$2" --stderr "${3:-$tmp/none}" --tz "$TZ_NAME" --now "$NOW" | python -c 'import json,sys; d=json.load(sys.stdin); print(d["class"], d["detail"], d["fatal"], d["resume_failed"])'; }
assert_eq "$(cls 1 "$tmp/529.json")" "transient overloaded False False" "529 is transient (overloaded)"
printf 'TypeError: fetch failed\n    cause: Error: read ECONNRESET\n' > "$tmp/reset.txt"; : > "$tmp/empty.json"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/reset.txt")" "transient connection reset False False" "ECONNRESET on stderr is transient"
assert_eq "$(cls 124 "$tmp/empty.json")" "transient timeout False False" "exit 124 (timeout) is transient"
printf '{"type":"result","is_error":true,"result":"You have hit your weekly limit \\u00b7 resets Mon 12:00am","session_id":"abc"}' > "$tmp/limit.json"
assert_eq "$(cls 1 "$tmp/limit.json")" "limit weekly limit False False" "a limit in the JSON result"
printf 'No conversation found with session ID: 123\n' > "$tmp/resume.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/resume.txt")" "error resume failed False True" "a missing session is resume_failed"
printf 'Not logged in · Please run /login\n' > "$tmp/login.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/login.txt")" "error fatal True False" "not logged in is fatal"
printf 'Traceback (most recent call last):\n  File "x.py", line 3\nKeyError: beatz\n' > "$tmp/trace.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/trace.txt")" "error  False False" "a traceback is a code error"
assert_eq "$(python "$ERRORS" classify --rc 1 --stdout "$tmp/empty.json" --stderr "$tmp/trace.txt" | python -c 'import json,sys; print(json.load(sys.stdin)["message"])')" "KeyError: beatz" "the message is the last stderr line"
printf '{"type":"result","is_error":false,"result":"ok","session_id":"s1","structured_output":{"a":1}}' > "$tmp/ok.json"
assert_eq "$(python "$ERRORS" classify --rc 0 --stdout "$tmp/ok.json" | python -c 'import json,sys; d=json.load(sys.stdin); print(d["class"], d["session_id"], d["structured"])')" "ok s1 True" "a good result is ok with its session id and structured flag"
printf 'rate limited, retry-after: 30\n' > "$tmp/ra.txt"
assert_eq "$(python "$ERRORS" classify --rc 1 --stdout "$tmp/empty.json" --stderr "$tmp/ra.txt" | python -c 'import json,sys; d=json.load(sys.stdin); print(d["class"], d["retry_after"])')" "transient 30" "retry-after is read"
# the same patterns run on the tail of a failed stage's log (runner_stage_failed), so common log text must not
# look transient: error codes are word-bounded, a status number needs its context, "temporary" alone is nothing
printf 'FileNotFoundError: library/keys/service.key is missing: this stage needs the API key file\n' > "$tmp/fnf.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/fnf.txt")" "error  False False" "FileNotFoundError is a code error (ENOTFOUND does not match inside it)"
printf 'wrote 503 bytes to events.json\nKeyError: beats\n' > "$tmp/bytes.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/bytes.txt")" "error  False False" "a bare number 503 in a log is not an HTTP status"
printf 'removed the temporary file plan.tmp\nValueError: no beats\n' > "$tmp/tmpfile.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/tmpfile.txt")" "error  False False" "a temporary file is not a temporary error"
printf 'API Error: 503 {"type":"error","error":{"type":"api_error","message":"Service unavailable"}}\n' > "$tmp/503.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/503.txt")" "transient server error False False" "an API error 503 is transient"
printf 'Error: getaddrinfo ENOTFOUND api.anthropic.com\n' > "$tmp/dns.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/dns.txt")" "transient network error False False" "a DNS failure is transient"
printf 'curl: (7) Failed to connect: connection refused\n' > "$tmp/refused.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/refused.txt")" "transient connection refused False False" "a refused connection is transient"
printf 'Temporary failure in name resolution\n' > "$tmp/tempfail.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/tempfail.txt")" "transient temporary error False False" "a temporary failure is transient"
printf "stage: fetching the clip\nYou've hit your session limit · resets 3pm\n" > "$tmp/stagelimit.txt"
assert_eq "$(cls 1 "$tmp/empty.json" "$tmp/stagelimit.txt")" "limit session limit False False" "a limit printed by a stage script is a limit"
rm -rf "$tmp"

test_summary
