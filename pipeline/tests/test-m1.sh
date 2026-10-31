#!/usr/bin/env bash
# test-m1.sh: acceptance test for M1 (Skeleton). No model calls; runs in under a minute.
#   bash pipeline/tests/test-m1.sh
#
# Covers: parser fixtures (multi-line, CRLF with BOM, Italian accents, notes outside braces, two blocks on one
# line, a restarted block, an empty file), stable ids, removal (exact id, an idea edited meanwhile at similarity
# 0.9 or more, an unrelated edit left alone), 20 concurrent add-idea.sh against a removal, stale and live locks,
# add-idea.sh output, validate-json, the run.sh banner, and a preflight failure that writes STOPPED.md.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"

IDEAS_PY="$REPO_DIR/pipeline/lib/ideas.py"
ADD_IDEA="$REPO_DIR/pipeline/bin/add-idea.sh"
FX="$FIXTURES/ideas"
SPEC_IDEA="Claude Code's frontend-design skill: it makes websites built with AI stop looking AI-generated. Show what it does and how to install it."

ipy() { python "$IDEAS_PY" "$@"; }
nlines() { printf '%s' "$1" | grep -c . || true; }
text_of() { printf '%s\n' "$1" | sed -n "${2}p" | cut -f2-; }
id_of() { printf '%s\n' "$1" | sed -n "${2}p" | cut -f1; }
hide_from_path() {  # print PATH without every directory that holds $1
  local tool="$1" p="$PATH" found dir i=0
  while [ $i -lt 6 ]; do
    found="$(PATH="$p" bash -c "command -v '$tool'" 2>/dev/null)" || break
    [ -n "$found" ] || break
    dir="$(dirname "$found")"
    p="$(printf '%s' "$p" | tr ':' '\n' | grep -v -F -x -- "$dir" | paste -sd: -)"
    i=$((i + 1))
  done
  printf '%s' "$p"
}

sandbox_init
Q="$SANDBOX_M/ideas.txt"

section "1. parser fixtures"
out="$(ipy list --file "$FX/multiline.txt" --plain)"
assert_eq "$(nlines "$out")" "2" "multiline.txt: 2 ideas"
assert_eq "$(text_of "$out" 1)" "$SPEC_IDEA" "multiline.txt: a multi-line idea becomes one line"
assert_eq "$(text_of "$out" 2)" "Second idea: 3 terminal tools that replaced my whole dev setup" "multiline.txt: second idea exact"

assert_true "crlf.txt fixture really has CRLF bytes and a BOM" python -c \
  'import sys; d = open(sys.argv[1], "rb").read(); sys.exit(0 if (b"\r\n" in d and d[:3] == b"\xef\xbb\xbf") else 1)' "$FX/crlf.txt"
out="$(ipy list --file "$FX/crlf.txt" --plain)"
assert_eq "$(nlines "$out")" "2" "crlf.txt: 2 ideas"
assert_eq "$(text_of "$out" 1)" "Idea with CRLF endings: ffmpeg in 60 seconds, the three flags that matter" "crlf.txt: CRLF normalized, BOM ignored"
assert_eq "$(text_of "$out" 2)" "Another CRLF idea about the gh CLI" "crlf.txt: second idea exact"
assert_false "crlf.txt: no carriage return in the parsed text" grep -q $'\r' <<<"$out"

out="$(ipy list --file "$FX/italian.txt" --plain)"
assert_eq "$(nlines "$out")" "2" "italian.txt: 2 ideas, the note outside braces ignored"
assert_eq "$(text_of "$out" 1)" "Perché il tuo sito fatto con l'AI sembra finto: 5 dettagli da sistemare, città, più, così" "italian.txt: accents intact"
assert_eq "$(text_of "$out" 2)" 'Un'"'"'idea con emoji 🚀 e virgolette "curve" e l'"'"'apostrofo tipografico ’' "italian.txt: emoji and typographic quotes intact"

out="$(ipy list --file "$FX/notes.txt" --plain 2>"$SANDBOX/notes.err")"
assert_eq "$(nlines "$out")" "1" "notes.txt: 1 idea among notes, a stray } and an unclosed {"
assert_eq "$(text_of "$out" 1)" "The only real idea in this file: Playwright screenshots in a reel" "notes.txt: idea exact"
assert_grep "unclosed brace" "$SANDBOX/notes.err" "notes.txt: the unclosed brace is reported on stderr"

out="$(ipy list --file "$FX/inline.txt" --plain)"
assert_eq "$(nlines "$out")" "2" "inline.txt: two blocks inside one note line"
assert_eq "$(text_of "$out" 1)" "Idea A about uv, the Python installer" "inline.txt: first block exact"
assert_eq "$(text_of "$out" 2)" "Idea B about the gh CLI" "inline.txt: second block exact"

out="$(ipy list --file "$FX/restart.txt" --plain 2>"$SANDBOX/restart.err")"
assert_eq "$(nlines "$out")" "1" "restart.txt: a second { restarts the block and {} is ignored"
assert_eq "$(text_of "$out" 1)" "The real idea after a restart" "restart.txt: idea exact"
assert_grep "a new block opens" "$SANDBOX/restart.err" "restart.txt: the restart is reported"
assert_grep "empty braces" "$SANDBOX/restart.err" "restart.txt: the empty braces are reported"

assert_eq "$(ipy count --file "$FX/empty.txt")" "0" "empty.txt: 0 ideas"
ipy first --file "$FX/empty.txt" >/dev/null 2>&1; assert_rc 3 $? "empty.txt: first exits 3"
assert_eq "$(ipy count --file "$SANDBOX_M/does-not-exist.txt")" "0" "a missing file counts as 0 ideas"
if ipy list --file "$FX/multiline.txt" | python -c '
import json, sys
rows = json.loads(sys.stdin.read())
assert len(rows) == 2 and all(k in rows[0] for k in ("n", "id", "text", "raw")), rows
assert "\n" in rows[0]["raw"] and "\n" not in rows[0]["text"], rows[0]
'; then pass "list without --plain is JSON with n, id, text and raw"; else fail "list JSON output"; fi

section "2. ids"
id_second="$(id_of "$(ipy list --file "$FX/multiline.txt" --plain)" 2)"
assert_true "an id is 12 hex characters" grep -q -E '^[0-9a-f]{12}$' <<<"$id_second"
cp "$FX/multiline.txt" "$SANDBOX/ideas.txt"
printf '{Third idea appended later}' | ipy append --file "$Q" --root "$SANDBOX_M" >/dev/null
first_id="$(id_of "$(ipy first --file "$Q" --plain)" 1)"
ipy remove --file "$Q" --root "$SANDBOX_M" --id "$first_id" >/dev/null 2>&1
assert_eq "$(id_of "$(ipy first --file "$Q" --plain)" 1)" "$id_second" "an id survives adding and removing other ideas"
id_crlf="$(id_of "$(ipy list --file "$FX/crlf.txt" --plain)" 1)"
id_lf="$(printf 'Idea with CRLF endings: ffmpeg in 60 seconds,\nthe three flags that matter' | ipy id)"
assert_eq "$id_crlf" "$id_lf" "the id is the same for the CRLF and LF versions of a text"
id_spaced="$(printf '  Idea   with CRLF endings:\n\nffmpeg in 60 seconds, the three flags that matter ' | ipy id)"
assert_eq "$id_spaced" "$id_lf" "whitespace differences do not change the id"
assert_eq "$(printf '{%s}' "$SPEC_IDEA" | ipy id)" "$(printf '%s' "$SPEC_IDEA" | ipy id)" "ideas.py id accepts the text with or without braces"

section "3. remove"
cp "$FX/notes.txt" "$SANDBOX/ideas.txt"
printf '{%s}\n{%s}' "$SPEC_IDEA" "Second idea: 3 terminal tools that replaced my whole dev setup" \
  | ipy append --file "$Q" --root "$SANDBOX_M" >/dev/null
assert_eq "$(ipy count --file "$Q")" "3" "three ideas before the removals"
spec_id="$(printf '%s' "$SPEC_IDEA" | ipy id)"
out="$(ipy remove --file "$Q" --root "$SANDBOX_M" --id "$spec_id" --plain 2>/dev/null)"; rc=$?
assert_rc 0 $rc "exact id: removed"
assert_eq "$out" "removed $spec_id (queue: 2)" "exact id: plain confirmation line"
assert_not_grep "frontend-design skill" "$SANDBOX/ideas.txt" "exact id: the block is gone"
assert_grep "post on Tuesdays" "$SANDBOX/ideas.txt" "notes outside braces survive a rewrite"
assert_grep "unclosed brace \{ that never closes" "$SANDBOX/ideas.txt" "the trailing note survives a rewrite"

printf '{%s}\n' "$SPEC_IDEA" | ipy append --file "$Q" --root "$SANDBOX_M" >/dev/null
python - "$Q" <<'EOF'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
s = s.replace("Show what it does and how to install it.", "Show what it does, then how to install it.")
open(p, "w", encoding="utf-8", newline="\n").write(s)
EOF
out="$(printf '%s' "$SPEC_IDEA" | ipy remove --file "$Q" --root "$SANDBOX_M" --id "$spec_id" --text-stdin 2>"$SANDBOX/fuzzy.err")"; rc=$?
assert_rc 0 $rc "edited idea: the closest match at similarity 0.9 or more is removed"
assert_true "edited idea: the result reports the similarity" grep -q -E '"similarity": 0\.9[0-9]*' <<<"$out"
assert_not_grep "frontend-design skill" "$SANDBOX/ideas.txt" "edited idea: the edited block is gone"
assert_grep "edited meanwhile" "$SANDBOX/logs/runner.log" "edited idea: the fuzzy removal is logged"
assert_eq "$(ipy count --file "$Q")" "2" "edited idea: count back to 2"

cp "$SANDBOX/ideas.txt" "$SANDBOX/ideas.before"
out="$(printf '%s' "$SPEC_IDEA" | ipy remove --file "$Q" --root "$SANDBOX_M" --id "$spec_id" --text-stdin 2>"$SANDBOX/unrelated.err")"; rc=$?
assert_rc 3 $rc "unrelated content: nothing removed, exit 3"
assert_true "unrelated content: the file is untouched" cmp -s "$SANDBOX/ideas.txt" "$SANDBOX/ideas.before"
assert_grep "file left alone" "$SANDBOX/logs/runner.log" "unrelated content: logged"
assert_eq "$(ipy count --file "$Q")" "2" "unrelated content: count unchanged"

cp "$FX/crlf.txt" "$SANDBOX/ideas.txt"
crlf_first="$(id_of "$(ipy first --file "$Q" --plain)" 1)"
ipy remove --file "$Q" --root "$SANDBOX_M" --id "$crlf_first" >/dev/null 2>&1
assert_true "a CRLF file is written back with CRLF" python -c \
  'import sys; d = open(sys.argv[1], "rb").read(); sys.exit(0 if (b"\r\n" in d and b"Another CRLF idea" in d) else 1)' "$Q"
assert_eq "$(ipy count --file "$Q")" "1" "CRLF file: one idea left after the removal"

section "4. add-idea.sh"
: > "$SANDBOX/ideas.txt"
rm -f "$SANDBOX/logs/.new-ideas"
out="$(bash "$ADD_IDEA" "{Idea one via add-idea} some note {Idea two via add-idea}")"; rc=$?
assert_rc 0 $rc "add-idea.sh exits 0"
assert_eq "$out" "added 2 ideas to ideas.txt (queue: 2)" "add-idea.sh: two blocks in one argument, one confirmation line"
out="$(bash "$ADD_IDEA" "an idea without braces, città")"
assert_eq "$out" "added 1 idea to ideas.txt (queue: 3)" "add-idea.sh: text without braces becomes one idea"
out="$(printf '{Idea from stdin\nacross two lines}' | bash "$ADD_IDEA")"
assert_eq "$out" "added 1 idea to ideas.txt (queue: 4)" "add-idea.sh: reads stdin"
assert_eq "$(text_of "$(ipy list --file "$Q" --plain)" 4)" "Idea from stdin across two lines" "add-idea.sh: a multi-line idea is stored and parsed back"
assert_grep "^\{an idea without braces, città\}$" "$SANDBOX/ideas.txt" "add-idea.sh: accents written as UTF-8"
assert_eq "$(grep -c . "$SANDBOX/logs/.new-ideas")" "4" "each addition is recorded in logs/.new-ideas for the NEW line"
bash "$ADD_IDEA" "   " >/dev/null 2>&1; assert_rc 1 $? "add-idea.sh: blank input is refused"
bash "$ADD_IDEA" "{}" >/dev/null 2>&1; assert_rc 1 $? "add-idea.sh: empty braces are refused"

section "5. concurrency and locks"
printf '{%s}\n' "$SPEC_IDEA" > "$SANDBOX/ideas.txt"
pids=()
for i in $(seq 1 20); do
  bash "$ADD_IDEA" "{Concurrent idea number $i: tool-$i with accent è}" >"$SANDBOX/add-$i.out" 2>"$SANDBOX/add-$i.err" &
  pids+=($!)
done
ipy remove --file "$Q" --root "$SANDBOX_M" --id "$spec_id" >/dev/null 2>"$SANDBOX/remove.err"; rc=$?
wait "${pids[@]}"
assert_rc 0 $rc "a removal during 20 concurrent additions succeeds"
assert_eq "$(ipy count --file "$Q")" "20" "20 additions and 1 removal in parallel leave exactly 20 ideas"
missing=0
for i in $(seq 1 20); do
  grep -q -F "{Concurrent idea number $i: tool-$i with accent è}" "$SANDBOX/ideas.txt" || missing=$((missing + 1))
done
assert_eq "$missing" "0" "every concurrently added idea is intact"
assert_not_grep "frontend-design" "$SANDBOX/ideas.txt" "the removed idea is gone"
assert_no_file "$SANDBOX/.locks/ideas" "the lock directory is gone afterwards"
errs="$(cat "$SANDBOX"/add-*.err "$SANDBOX/remove.err" | grep -c -E "Traceback|lock stayed busy" || true)"
assert_eq "$errs" "0" "no process hit a traceback or a lock timeout"
assert_eq "$(ls "$SANDBOX"/ideas.txt.tmp.* 2>/dev/null | wc -l | tr -d ' ')" "0" "no temp file left behind"

mkdir -p "$SANDBOX/.locks/ideas"
echo "424242 0" > "$SANDBOX/.locks/ideas/pid"
touch -d '-120 seconds' "$SANDBOX/.locks/ideas"
start=$(date +%s)
bash "$ADD_IDEA" "{After the stale lock}" >/dev/null 2>"$SANDBOX/stale.err"; rc=$?
took=$(( $(date +%s) - start ))
assert_rc 0 $rc "a stale lock (older than 60 s) does not block a writer"
assert_true "the stale lock was broken within a few seconds (took ${took}s)" [ "$took" -lt 10 ]
assert_grep "removed a stale ideas lock" "$SANDBOX/logs/runner.log" "the stale lock removal is logged"
assert_eq "$(ipy count --file "$Q")" "21" "the idea after the stale lock was added"

mkdir "$SANDBOX/.locks/ideas"
( bash "$ADD_IDEA" "{After the live lock}" >/dev/null 2>&1; echo $? > "$SANDBOX/live.rc" ) &
sleep 1.5
assert_eq "$(ipy count --file "$Q")" "21" "a writer waits while a fresh lock is held"
rmdir "$SANDBOX/.locks/ideas"
wait
assert_eq "$(cat "$SANDBOX/live.rc")" "0" "the writer proceeds once the lock is released"
assert_eq "$(ipy count --file "$Q")" "22" "the idea after the live lock was added"

section "6. validate-json"
printf '%s' '{"type":"object","required":["id"],"properties":{"id":{"type":"string"}}}' > "$SANDBOX/schema.json"
printf '%s' '{"id":"abc"}' > "$SANDBOX/good.json"
printf '%s' '{"id":5}' > "$SANDBOX/bad.json"
python "$REPO_DIR/pipeline/bin/validate-json" "$SANDBOX_M/schema.json" "$SANDBOX_M/good.json" >/dev/null; assert_rc 0 $? "a valid file passes"
out="$(python "$REPO_DIR/pipeline/bin/validate-json" "$SANDBOX_M/schema.json" "$SANDBOX_M/bad.json")"; rc=$?
assert_rc 1 $rc "an invalid file fails with exit 1"
assert_true "the error line names the path and the problem" grep -q "bad.json: id: 5 is not of type 'string'" <<<"$out"
python "$REPO_DIR/pipeline/bin/validate-json" "$SANDBOX_M/schema.json" "$SANDBOX_M/missing.json" >/dev/null; assert_rc 2 $? "an unreadable file exits 2"

section "7. run.sh banner and preflight"
printf '{%s}\n' "$SPEC_IDEA" > "$SANDBOX/ideas.txt"
rm -f "$SANDBOX/logs/runner.log" "$SANDBOX/logs/status.txt"
( cd "$SANDBOX" && NO_COLOR=1 bash "$REPO_DIR/run.sh" --once ) > "$SANDBOX/run.out" 2>&1; rc=$?
assert_rc 0 $rc "bash run.sh --once exits 0"
assert_grep '^\[[0-9]{2}:[0-9]{2}\] READY  preflight ok: [0-9]+ tools, [0-9]+ python packages, [0-9]+ files' "$SANDBOX/run.out" "preflight line"
assert_grep '^\[[0-9]{2}:[0-9]{2}\] START  reels autopilot v[0-9]+\.[0-9]+\.[0-9]+.* \| queue: 1 idea \| style: paper-cards \| voice: chatterbox \(fallback kokoro\) \| sfx map: not built$' "$SANDBOX/run.out" "banner: version, queue, style, voice engine, sfx map"
assert_grep '^\[[0-9]{2}:[0-9]{2}\] QUEUE  1\. Claude Code' "$SANDBOX/run.out" "the queue is listed"
assert_not_grep $'\x1b' "$SANDBOX/run.out" "NO_COLOR output has no escape codes"
assert_file "$SANDBOX/logs/runner.log" "logs/runner.log written"
assert_file "$SANDBOX/logs/status.txt" "logs/status.txt written"
assert_eq "$(cat "$SANDBOX/logs/status.txt")" "$(tail -n 1 "$SANDBOX/run.out")" "status.txt holds the latest line"
assert_true "runs/, exports/ and .locks/ are created at startup" [ -d "$SANDBOX/runs" ]
assert_true "exports/ created" [ -d "$SANDBOX/exports" ]
assert_true ".locks/ created" [ -d "$SANDBOX/.locks" ]
bash "$REPO_DIR/run.sh" --bogus >/dev/null 2>&1; assert_rc 1 $? "an unknown option exits 1"
( cd "$SANDBOX" && bash "$REPO_DIR/pipeline/bin/preflight" ) >/dev/null 2>&1; assert_rc 0 $? "pipeline/bin/preflight exits 0 on this machine"

hidden_path="$(hide_from_path ffmpeg)"
if PATH="$hidden_path" bash -c 'command -v ffmpeg' >/dev/null 2>&1; then
  fail "could not hide ffmpeg from PATH for the preflight failure test"
else
  ( cd "$SANDBOX" && PATH="$hidden_path" NO_COLOR=1 bash "$REPO_DIR/run.sh" --once ) > "$SANDBOX/run-fail.out" 2>&1; rc=$?
  assert_rc 3 $rc "run.sh exits 3 when ffmpeg is hidden from PATH"
  assert_file "$SANDBOX/logs/STOPPED.md" "logs/STOPPED.md written"
  assert_grep "ffmpeg is not on PATH" "$SANDBOX/logs/STOPPED.md" "STOPPED.md names the missing tool"
  assert_grep "winget install Gyan.FFmpeg" "$SANDBOX/logs/STOPPED.md" "STOPPED.md gives the exact fix"
  assert_grep '^\[[0-9]{2}:[0-9]{2}\] STOP   systemic failure: preflight failed: ffmpeg is not on PATH' "$SANDBOX/run-fail.out" "STOP line printed"
  assert_not_grep 'START  reels autopilot' "$SANDBOX/run-fail.out" "no banner after a failed preflight"
  assert_grep 'STOP   systemic failure' "$SANDBOX/logs/status.txt" "status.txt holds the STOP line"
  ( cd "$SANDBOX" && NO_COLOR=1 bash "$REPO_DIR/run.sh" --once ) > "$SANDBOX/run-ok.out" 2>&1
  assert_no_file "$SANDBOX/logs/STOPPED.md" "the next successful start removes STOPPED.md"
  assert_grep "removed logs/STOPPED.md" "$SANDBOX/run-ok.out" "the removal is announced"
fi

test_summary
