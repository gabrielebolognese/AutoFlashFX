#!/usr/bin/env bash
# test-m4.sh: acceptance test for M4 (Research, expansion, gate, angle: S1 to S4). Sections 3 and 4 make real model
# calls (the research, expansion and gate models on the test idea and on a deliberately false idea); everything
# else uses the fake claude in pipeline/tests/fakes.
#   bash pipeline/tests/test-m4.sh                   everything (15 to 30 minutes, dominated by the real research)
#   M4_SECTIONS="1 2" bash pipeline/tests/test-m4.sh  only those sections (1 and 2 use no model, seconds to a minute)
#   M4_FREEZE=1 bash pipeline/tests/test-m4.sh        also copy the test idea's real outputs into
#                                                    pipeline/tests/fixtures/runs/test-idea/ (the frozen fixtures
#                                                    later milestones start from)
#
# Covers (BUILD_SPEC.md section 12, M4, and PLAN.md M4):
#   1. units, no model: prompt.py rendering, the screenshot tool against a local web server (save, reuse, a bot
#      wall, a refused folder, a bad URL), research.py (facts.md lines with URL and date, ordering, assets),
#      expansion.py (the rules and the length window, an existing keyword), gate.py (every decision rule, the
#      suggestion file, the round count), state.py's reopen.txt, session_call's reseed after a lost session
#   2. the angle loop through the whole runner with the fake claude answering from fixtures: a gate that always
#      scores S1 makes S4 run, the round counter reaches 2 and the idea is dropped with the scores in the reason;
#      a gate that passes on round 2 continues to the export; an F failure of kind core drops at once; a
#      different-topic verdict drops and writes logs/suggested-ideas.txt; an F failure for wording with the core
#      claim verified is repaired by an angle round and passes (DECISIONS.md 112); session A is resumed by S2 and
#      S4, the gate is a fresh session
#   3. the test idea with the real models: facts.md with sources and dates, numbers.json and assets.json with
#      existing files, expansion.md of 500 to 1500 characters with its five parts, gate.json with scores 0 to 3
#      and quoted evidence, the run continues (dummy stages after S4) to an export
#   4. the false idea with the real models: dropped with a reason and the scores in the history line, its block
#      gone from ideas.txt, nothing else written to ideas.txt
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
fast_mode
export REELS_DUMMY_SECONDS=0.1
SECTIONS="${M4_SECTIONS:-1 2 3 4}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }

STATE_PY="$REPO_DIR/pipeline/lib/state.py"
FAKE_M4="$FIXTURES/fake/m4"
TEST_IDEA="Claude Code's frontend-design skill: it makes websites built with AI stop looking AI-generated. Show what it does and how to install it."
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
LATER_DUMMIES="$(dummy_after 04-angle)"

state_get() { python "$STATE_PY" get "$@"; }
run_dirs() { ls -d "$SANDBOX"/runs/*/ 2>/dev/null | sed 's|/$||'; }
first_run() { run_dirs | head -n 1; }
run_of() { printf '%s/%s' "$SANDBOX" "$(grep -o -E -m1 'runs/[^[:space:]]+' "$1")"; }  # the run folder named by a run's START line (ls sorts "<id>-2" before "<id>" here)

run_once() {  # run_once <outfile> [env...]: the sandbox's own run.sh (REELS_REPO is the sandbox copy of the repo)
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 3600 bash "$SANDBOX/run.sh" --once ) > "$out" 2>&1
}

event_tags() {  # the event lines' tags in order, comma separated (no REEL, INFO, QUEUE, READY, WARN, FLAG, START, NEXT)
  grep -E "$ts_regex" "$1" | awk '{print $2}' | grep -v -E '^(REEL|INFO|QUEUE|READY|WARN|IDLE|FLAG|START|NEXT)$' | paste -sd,
}

fake_calls_json() {  # every logged fake call as a JSON list
  python -c 'import json, sys; print(json.dumps([json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]))' "$FAKE_CLAUDE_LOG"
}

fake_field() {  # fake_field <call n> <key>
  python -c 'import json, sys
calls = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
v = calls[int(sys.argv[2]) - 1].get(sys.argv[3])
print(json.dumps(v) if isinstance(v, (list, dict, bool)) else ("" if v is None else v))' "$FAKE_CLAUDE_LOG" "$1" "$2"
}

no_emdash_in() {  # no_emdash_in <name> <file>...: a byte scan
  local name="$1"; shift
  if python -c 'import sys
bad = [p for p in sys.argv[1:] if open(p, "rb").read().find(bytes([0xE2, 0x80, 0x94])) >= 0]
sys.exit(1 if bad else 0)' "$@"; then pass "$name"; else fail "$name (an em dash in one of: $*)"; fi
}

json_get() {  # json_get <file> <dotted key> [default]
  python -c 'import json, sys
try:
    cur = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    for part in sys.argv[2].split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
except (OSError, ValueError, KeyError, IndexError, TypeError):
    print(sys.argv[3] if len(sys.argv) > 3 else ""); sys.exit(0)
if isinstance(cur, bool): print("true" if cur else "false")
elif isinstance(cur, (dict, list)): print(json.dumps(cur, ensure_ascii=False))
else: print(cur)' "$@"
}

claim_lines_ok() {  # claim_lines_ok <facts.md>: every numbered claim line has a URL and a checked date; prints the count
  python -c 'import re, sys
lines = [l.rstrip("\n") for l in open(sys.argv[1], encoding="utf-8")]
claims = [l for l in lines if re.match(r"^\d+\. ", l)]
bad = [l for l in claims if not (re.search(r"https?://\S+", l) and re.search(r"\(checked \d{4}-\d{2}-\d{2}\)$", l))]
print(len(claims))
sys.exit(1 if (bad or not claims) else 0)' "$1"
}

# ----------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. units: prompt.py, the screenshot tool, research.py, expansion.py, gate.py, reopen.txt, the reseed"
sandbox_init
fake_claude_on
export REELS_SLEEP_SCALE=0
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/ideas.txt"
created="$(printf '%s' "$TEST_IDEA" | python "$STATE_PY" new --runs "$SANDBOX_M/runs" --id m4unit01)"
RD="$(python -c 'import json, sys; print(json.loads(sys.argv[1])["run_dir"])' "$created")"

# prompt.py
printf '# Role: x\nIdea: {{IDEA}}\nFacts:\n{{FACTS}}\nTail {{MISSING}}\n' > "$SANDBOX/tpl.md"
printf 'claim one \xe2\x80\x94 with a dash\r\nline two\n' > "$SANDBOX/facts-in.md"
out="$(python pipeline/lib/prompt.py render "$SANDBOX_M/tpl.md" --set "IDEA=an idea" --file "FACTS=$SANDBOX_M/facts-in.md" 2>&1)"; rc=$?
assert_rc 1 $rc "prompt.py: a placeholder without a value is an error"
assert_true "prompt.py: the error names the placeholder" grep -q "no value for MISSING" <<<"$out"
python pipeline/lib/prompt.py render "$SANDBOX_M/tpl.md" --set "IDEA=an idea" --file "FACTS=$SANDBOX_M/facts-in.md" --allow-missing --out "$SANDBOX_M/rendered.md"
assert_grep "^Idea: an idea$" "$SANDBOX/rendered.md" "prompt.py: --set value rendered"
assert_grep "^claim one, with a dash$" "$SANDBOX/rendered.md" "prompt.py: an inlined file is cleaned of em dashes"
assert_true "prompt.py: CR characters are removed" python -c 'import sys; sys.exit(1 if b"\r" in open(sys.argv[1], "rb").read() else 0)' "$SANDBOX_M/rendered.md"
assert_grep "^Tail $" "$SANDBOX/rendered.md" "prompt.py: --allow-missing leaves the placeholder empty"

# the screenshot tool against a local server (no network)
WEB="$SANDBOX/web"; mkdir -p "$WEB"
printf '<html><head><title>Demo page</title></head><body style="font:40px sans-serif"><h1>Local test page</h1><p>%s</p></body></html>' "$(printf 'lorem ipsum %.0s' $(seq 1 300))" > "$WEB/index.html"
printf '<html><head><title>Just a moment...</title></head><body><h1>Verify you are human</h1></body></html>' > "$WEB/wall.html"
PORT=$(( 8700 + RANDOM % 200 ))
( cd "$WEB" && exec python -m http.server "$PORT" ) >/dev/null 2>&1 &
WEB_PID=$!
sleep 1.5
ASSETS="$RD/01-research/assets"
out="$(REELS_ASSETS_DIR="$ASSETS" bash pipeline/bin/screenshot "http://127.0.0.1:$PORT/index.html" repo)"; rc=$?
assert_rc 0 $rc "screenshot: a page is captured (exit 0)"
assert_eq "$(python -c 'import json, sys; print(json.loads(sys.argv[1])["file"])' "$out")" "01-repo.png" "screenshot: the file is NN-name.png"
assert_file "$ASSETS/01-repo.png" "screenshot: the PNG exists"
assert_file "$ASSETS/01-repo.json" "screenshot: the sidecar exists"
assert_eq "$(json_get "$ASSETS/01-repo.json" title)" "Demo page" "screenshot: the sidecar has the page title"
assert_eq "$(json_get "$ASSETS/01-repo.json" status)" "200" "screenshot: the sidecar has the HTTP status"
assert_true "screenshot: the sidecar has the URL and the capture date" grep -q "\"captured\": \"20[0-9-]* [0-9:]*\"" "$ASSETS/01-repo.json"
assert_eq "$(python -c 'import struct, sys; d = open(sys.argv[1], "rb").read(24); print(struct.unpack(">II", d[16:24])[0])' "$ASSETS/01-repo.png")" "1080" "screenshot: 1080 px wide"
out="$(REELS_ASSETS_DIR="$ASSETS" bash pipeline/bin/screenshot "http://127.0.0.1:$PORT/index.html" again)"; rc=$?
assert_rc 0 $rc "screenshot: the same URL again is reused"
assert_true "screenshot: reused is true and the first file is returned" grep -q '"reused": true, "file": "01-repo.png"' <<<"$out"
assert_eq "$(ls "$ASSETS"/*.png | wc -l | tr -d ' ')" "1" "screenshot: no second file for the same URL"
out="$(REELS_ASSETS_DIR="$ASSETS" bash pipeline/bin/screenshot "http://127.0.0.1:$PORT/wall.html" wall)"; rc=$?
assert_rc 2 $rc "screenshot: a bot wall is reported as blocked (exit 2)"
assert_true "screenshot: blocked true in the result" grep -q '"blocked": true' <<<"$out"
assert_eq "$(ls "$ASSETS"/*.png | wc -l | tr -d ' ')" "1" "screenshot: nothing saved for a blocked page"
out="$(bash pipeline/bin/screenshot "http://127.0.0.1:$PORT/index.html" x --out-dir "$SANDBOX_M/library")"; rc=$?
assert_rc 1 $rc "screenshot: a folder outside runs/ is refused"
assert_no_file "$SANDBOX/library/01-x.png" "screenshot: nothing written outside runs/"
out="$(REELS_ASSETS_DIR="$ASSETS" bash pipeline/bin/screenshot "ftp://example.com/x" y)"; rc=$?
assert_rc 1 $rc "screenshot: a non-http URL is refused"
kill "$WEB_PID" 2>/dev/null; wait "$WEB_PID" 2>/dev/null

# research.py finish on the fixture (plus the asset captured above)
summary="$(python pipeline/lib/research.py finish --run-dir "$RD" --model-out "$FAKE_M4/01-research.json" --today 2026-11-01 --idea-id m4unit01 --idea "$TEST_IDEA" --max-assets 6)"
assert_true "research.py: the summary counts" grep -q '"claims": 7, "verified": 5, "false": 1, "numbers": 2, "assets": 1' <<<"$summary"
assert_true "research.json validates against schema.json" python pipeline/bin/validate-json pipeline/stages/01-research/schema.json "$RD/01-research/research.json"
n="$(claim_lines_ok "$RD/01-research/facts.md")"; rc=$?
assert_rc 0 $rc "facts.md: every claim line has a URL and a checked date"
assert_eq "$n" "7" "facts.md: seven numbered claims"
assert_grep "^1\. .*\[primary, verified\]" "$RD/01-research/facts.md" "facts.md: primary verified claims first"
assert_grep "^5\. .*\[vendor, verified\]" "$RD/01-research/facts.md" "facts.md: the vendor source after the primary ones"
assert_grep "^6\. .*\[forum, unverified\]" "$RD/01-research/facts.md" "facts.md: unverified after verified"
assert_grep "^7\. .*\[press, false\]" "$RD/01-research/facts.md" "facts.md: false claims last"
assert_grep "^Status: verified\." "$RD/01-research/facts.md" "facts.md: the core claim status"
assert_grep "^- skills_repo_stars: 12345 stars \(https://github.com/anthropics/skills, checked 2026-11-01" "$RD/01-research/facts.md" "facts.md: numbers with source and date"
assert_grep "^- 01-repo.png: the anthropics/skills repository page \(http://127.0.0.1" "$RD/01-research/facts.md" "facts.md: the asset with the model's caption"
assert_eq "$(json_get "$RD/01-research/numbers.json" skills_repo_stars.value)" "12345" "numbers.json: 12,345 parsed as a number"
assert_eq "$(json_get "$RD/01-research/assets.json" 0.file)" "assets/01-repo.png" "assets.json: the captured file"
assert_file "$RD/01-research/$(json_get "$RD/01-research/assets.json" 0.file)" "assets.json: the file exists"
no_emdash_in "research.py: no em dash in the files" "$RD/01-research/facts.md" "$RD/01-research/research.json"

# expansion.py
printf '# keywords\nGUIDE | the one-page setup checklist (PDF) | https://example.com/guide\nTEMPLATE | the Notion template | to create\n' > "$SANDBOX/deliv.txt"
assert_eq "$(python pipeline/lib/expansion.py deliverables --file "$SANDBOX_M/deliv.txt" | head -n 1)" "- GUIDE: the one-page setup checklist (PDF) (https://example.com/guide)" "deliverables: an existing keyword with its link"
assert_true "deliverables: a missing file means every deliverable is NEW" grep -q "none yet" <<<"$(python pipeline/lib/expansion.py deliverables --file /nonexistent)"
res="$(python pipeline/lib/expansion.py compose --run-dir "$RD" --model-out "$FAKE_M4/02-expansion.json" --deliverables "$SANDBOX_M/deliv.txt" --written-by 02-expansion --round 0)"
assert_true "expansion.py: the fixture passes every rule" grep -q '"ok": true' <<<"$res"
chars="$(wc -c < "$RD/02-expansion/expansion.md" | tr -d ' ')"
assert_true "expansion.md is between 500 and 1500 characters ($chars)" test "$chars" -ge 500 -a "$chars" -le 1500
assert_true "expansion.json validates against schema.json" python pipeline/bin/validate-json pipeline/stages/02-expansion/schema.json "$RD/02-expansion/expansion.json"
assert_grep "^Problem: I build landing pages" "$RD/02-expansion/expansion.md" "expansion.md: the problem line"
assert_grep "^Comment keyword: LINK\. Deliverable \(existing\): the link to .*\(https://github.com/anthropics/skills\)$" "$RD/02-expansion/expansion.md" "expansion.md: an external solution takes the keyword LINK with its link (M12)"
assert_grep "^Solution decision: external \(the frontend-design skill \(anthropics/skills\), https://github.com/anthropics/skills\): " "$RD/02-expansion/expansion.md" "expansion.md: the solution decision line (M12)"
assert_eq "$(json_get "$RD/02-expansion/solution.json" type)/$(json_get "$RD/02-expansion/solution.json" keyword)" "external/LINK" "solution.json: the type and the keyword (M12)"
assert_grep "^- facts.md#1: " "$RD/02-expansion/expansion.md" "expansion.md: evidence lines point to facts.md"
python - "$FAKE_M4/02-expansion.json" "$SANDBOX_M/bad.json" "$SANDBOX_M/guide.json" <<'EOF'
import json, sys
base = json.load(open(sys.argv[1], encoding="utf-8"))
bad = dict(base); bad["problem"] = "Landing pages look generic. They all use the same font."; bad["keyword"] = "two words"
bad["evidence"] = [{"fact": 6, "note": "x"}, {"fact": 99, "note": "y"}]; bad["share_identity"] = "everyone"
bad["deliverable_status"] = "existing"; bad["solution"] = base["solution"] * 5
json.dump(bad, open(sys.argv[2], "w", encoding="utf-8"))
good = dict(base); good["keyword"] = "guide"; good["deliverable_status"] = "new"
good["solution_decision"] = {"type": "method", "name": "copy the skill folder by hand", "url": "", "reason": "fixture: a method keeps the keyword the model chose (M12)"}
json.dump(good, open(sys.argv[3], "w", encoding="utf-8"))
EOF
res="$(python pipeline/lib/expansion.py compose --run-dir "$RD" --model-out "$SANDBOX_M/bad.json" --deliverables "$SANDBOX_M/deliv.txt" --written-by 02-expansion --round 0)"
assert_true "expansion.py: a bad answer is refused" grep -q '"ok": false' <<<"$res"
assert_true "expansion.py: the problem must be first person" grep -q "first-person sentence" <<<"$res"
assert_true "expansion.py: the identity must name someone" grep -q "share identity must name" <<<"$res"
assert_true "expansion.py: the keyword must be one word" grep -q "keyword must be one word" <<<"$res"
assert_true "expansion.py: an unverified claim cannot be cited" grep -q "facts.md#6 is marked unverified" <<<"$res"
assert_true "expansion.py: a pointer past the last claim is refused" grep -q "facts.md#99 does not exist (facts.md has 7 claims)" <<<"$res"
assert_true "expansion.py: the length limit with the exact numbers" grep -q -E "would be [0-9]+ characters, the limit is 1500: cut about [0-9]+ characters" <<<"$res"
assert_true "expansion.py: expansion.md is not overwritten by a refused answer" grep -q "^Problem: I build landing pages" "$RD/02-expansion/expansion.md"
res="$(python pipeline/lib/expansion.py compose --run-dir "$RD" --model-out "$SANDBOX_M/guide.json" --deliverables "$SANDBOX_M/deliv.txt" --written-by 02-expansion --round 0)"
assert_true "expansion.py: a keyword from deliverables.txt is existing, in capitals" grep -q '"keyword": "GUIDE", "deliverable_status": "existing"' <<<"$res"
assert_grep "^Comment keyword: GUIDE\. Deliverable \(existing\): .*\(https://example.com/guide\)$" "$RD/02-expansion/expansion.md" "expansion.md: the existing deliverable carries the file's link"

# gate.py
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/03-gate.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: S1 with rounds left is an angle" grep -q '"decision": "angle", "scores_text": "P3 S1 C3 F ok H ok", "failing_text": "S1"' <<<"$res"
assert_true "gate.json validates against schema.json" python pipeline/bin/validate-json pipeline/stages/03-gate/schema.json "$RD/03-gate/gate.json"
assert_file "$RD/03-gate/gate-1.json" "gate: a copy per round"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/03-gate.json" --round 3 --angles-done 2 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: no round left is a drop with the scores" grep -q '"decision": "drop", .*"reason": "still failing after 2 angle rounds (P3 S1 C3 F ok H ok): ' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.false.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: the model's F fail of kind core drops at once" grep -q '"decision": "drop", .*"reason": "facts don.t hold (P2 S2 C2 F fail H ok): ' <<<"$res"
assert_eq "$(json_get "$RD/03-gate/gate.json" F_kind)" "core" "gate.json: F_kind core"
# an F fail of kind wording (a statement of the expansion that facts.md does not back, the core claim verified) is
# repaired by an angle round, not a drop (M4 review 2, DECISIONS.md 112)
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.wording.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: an F fail of kind wording with the core verified is an angle round, not a drop" grep -q '"decision": "angle", "scores_text": "P3 S3 C3 F fail H ok", "failing_text": "F wording"' <<<"$res"
assert_eq "$(json_get "$RD/03-gate/gate.json" F_kind)" "wording" "gate.json: F_kind wording"
assert_eq "$(json_get "$RD/03-gate/gate.json" failing)" '["F"]' "gate.json: failing lists F"
assert_eq "$(json_get "$RD/03-gate/gate.json" decision)" "angle" "gate.json: decision angle"
assert_true "gate.json with F_kind validates against schema.json" python pipeline/bin/validate-json pipeline/stages/03-gate/schema.json "$RD/03-gate/gate.json"
assert_true "gate: the wording fail keeps the model's angle hint (the statements to reword)" grep -q '"angle_hint": "Fixture gate hint: reword the install sentence' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.wording.json" --round 3 --angles-done 2 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: a wording fail with no round left drops with the scores" grep -q '"decision": "drop", .*"reason": "still failing after 2 angle rounds (P3 S3 C3 F fail H ok): Fixture gate: ' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.wording.json" --round 1 --angles-done 0 --cap 2 --core-status false --today 2026-11-01)"
assert_true "gate: a false core claim drops at once whatever kind the model gave" grep -q '"decision": "drop", "scores_text": "P3 S3 C3 F fail H ok", .*core claim is false.*"F_kind": "core"' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.wording.json" --round 1 --angles-done 0 --cap 2 --core-status unverified --today 2026-11-01)"
assert_true "gate: an unverified core claim drops at once whatever kind the model gave" grep -q '"decision": "drop", "scores_text": "P3 S3 C3 F fail H ok", .*core claim is unverified.*"F_kind": "core"' <<<"$res"
python - "$FAKE_M4/variants/03-gate.wording.json" "$SANDBOX_M/w-nokind.json" "$SANDBOX_M/w-s1.json" "$SANDBOX_M/w-nohint.json" <<'EOF'
import json, sys
w = json.load(open(sys.argv[1], encoding="utf-8"))
nokind = dict(w); del nokind["F_kind"]
json.dump(nokind, open(sys.argv[2], "w", encoding="utf-8"))
s1 = dict(w); s1["scores"] = {"P": 3, "S": 1, "C": 3}
json.dump(s1, open(sys.argv[3], "w", encoding="utf-8"))
nohint = dict(w); nohint["angle_hint"] = ""
json.dump(nohint, open(sys.argv[4], "w", encoding="utf-8"))
EOF
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$SANDBOX_M/w-nokind.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: an F fail without a kind is read as core (the strict default) and drops" grep -q '"decision": "drop", .*"reason": "facts don.t hold (P3 S3 C3 F fail H ok): ' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$SANDBOX_M/w-s1.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: S1 plus a wording fail is one angle round naming both" grep -q '"decision": "angle", "scores_text": "P3 S1 C3 F fail H ok", "failing_text": "S1 F wording"' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$SANDBOX_M/w-nohint.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: a wording fail without an angle hint gets one built from the F evidence" grep -q '"angle_hint": "remove or reword the statements of the expansion that facts.md does not back: \\"one folder in' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.pass.json" --round 1 --angles-done 0 --cap 2 --core-status false --today 2026-11-01)"
assert_true "gate: a false core claim fails F whatever the model said" grep -q '"decision": "drop", "scores_text": "P3 S3 C3 F fail H ok", .*core claim is false' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.pass.json" --round 1 --angles-done 0 --cap 2 --core-status unverified --today 2026-11-01)"
assert_true "gate: an unverified core claim fails F too" grep -q '"decision": "drop", "scores_text": "P3 S3 C3 F fail H ok"' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.pass.json" --round 2 --angles-done 1 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: P, S, C at least 2 and F ok passes" grep -q '"decision": "pass", "scores_text": "P3 S3 C3 F ok H ok"' <<<"$res"
python - "$FAKE_M4/03-gate.json" "$SANDBOX_M/dt.json" <<'EOF'
import json, sys
g = json.load(open(sys.argv[1], encoding="utf-8")); g["different_topic"] = True; g["suggested_idea"] = "A reel about {something else} entirely"
json.dump(g, open(sys.argv[2], "w", encoding="utf-8"))
EOF
res="$(python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$SANDBOX_M/dt.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: a different-topic verdict drops with the suggestion" grep -q '"decision": "drop", .*no angle keeps the core topic (P3 S1 C3 F ok H ok)' <<<"$res"
python pipeline/lib/gate.py suggest --logs "$SANDBOX_M/logs" --idea "$TEST_IDEA" --suggestion "A reel about {something else} entirely" --source 03-gate >/dev/null
assert_grep "^# 20[0-9-]+ [0-9:]+ \| from 03-gate \| the idea was: Claude Code" "$SANDBOX/logs/suggested-ideas.txt" "suggested-ideas.txt: the comment line"
assert_grep "^\{A reel about \(something else\) entirely\}$" "$SANDBOX/logs/suggested-ideas.txt" "suggested-ideas.txt: the suggestion in braces, inner braces replaced"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "1" "suggested-ideas.txt: ideas.txt untouched"
rm -f "$RD/03-gate/gate-"*.json
python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/03-gate.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01 >/dev/null
python pipeline/lib/gate.py decide --run-dir "$RD" --model-out "$FAKE_M4/variants/03-gate.pass.json" --round 2 --angles-done 1 --cap 2 --core-status verified --today 2026-11-01 >/dev/null
assert_eq "$(python pipeline/lib/gate.py angle-rounds --run-dir "$RD")" "1" "gate.py angle-rounds counts the rounds that decided angle"
no_emdash_in "gate.py: no em dash in gate.json" "$RD/03-gate/gate.json"

# state.py: reopen.txt is applied by stage-done in the same write
python "$STATE_PY" stage-start "$RD" 03-gate >/dev/null
printf '04-angle\n' > "$RD/03-gate/reopen.txt"
res="$(python "$STATE_PY" stage-done "$RD" 03-gate --schemas pipeline/stages)"
assert_true "state.py: stage-done reports the reopened stage" grep -q '"reopened": \["04-angle"\]' <<<"$res"
assert_eq "$(state_get "$RD" stages.04-angle.status)" "pending" "state.py: 04-angle went from skipped to pending"
assert_eq "$(state_get "$RD" stages.03-gate.status)" "done" "state.py: 03-gate is done"
assert_no_file "$RD/03-gate/reopen.txt" "state.py: reopen.txt is consumed"
python "$STATE_PY" stage-start "$RD" 04-angle >/dev/null
printf '03-gate\nnot-a-stage\n' > "$RD/04-angle/reopen.txt"
bash pipeline/stages/04-angle/dummy.sh "$RD" >/dev/null 2>&1
res="$(python "$STATE_PY" stage-done "$RD" 04-angle --schemas pipeline/stages 2>/dev/null)"
assert_true "state.py: the angle stage reopens the gate (an unknown key is ignored)" grep -q '"reopened": \["03-gate"\]' <<<"$res"
assert_eq "$(state_get "$RD" stages.03-gate.status)" "pending" "state.py: 03-gate is pending again"
assert_no_file "$RD/03-gate/.done" "state.py: the gate's .done marker is removed"
python "$STATE_PY" stage-start "$RD" 03-gate >/dev/null
assert_no_file "$RD/04-angle/reopen.txt" "state.py: no stale reopen.txt left behind"
printf 'stale\n' > "$RD/03-gate/reopen.txt"
python "$STATE_PY" stage-start "$RD" 03-gate >/dev/null
assert_no_file "$RD/03-gate/reopen.txt" "state.py: stage-start removes a reopen.txt left by an earlier attempt"

# session_call: the reseed after a lost session
printf '# Role: research\n# Stage: 02-expansion\n\nTask: write the expansion.\n' > "$RD/p.md"
FAKE_CLAUDE_MODE=ok bash pipeline/tests/session-driver.sh A research "$RD/02-expansion" "$RD/p.md" --tools "" >/dev/null
sidA="$(state_get "$RD" sessions.A "")"
assert_true "session_call: the first call stores session A" grep -q '^fake-' <<<"$sidA"
printf 'resume-missing\nok\n' > "$SANDBOX/script.txt"
fake_claude_reset
out="$(FAKE_CLAUDE_SCRIPT="$SANDBOX_M/script.txt" bash pipeline/tests/session-driver.sh A research "$RD/02-expansion" "$RD/p.md" --tools "" 2>&1)"; rc=$?
assert_rc 0 $rc "session_call: a lost session is reseeded and the call succeeds"
assert_true "session_call: the WARN line names the reseed" grep -q "WARN   session A no longer exists .*starting a new one seeded with facts.md" <<<"$out"
assert_eq "$(fake_field 1 resume)" "$sidA" "session_call: the first attempt resumed the stored session"
assert_eq "$(fake_field 2 resume)" "" "session_call: the second attempt is a new session"
assert_true "session_call: the new prompt keeps the Role and Stage header first" grep -q '^# Role: research' <<<"$(fake_field 2 prompt_head)"
seed="$(ls "$RD"/02-expansion/calls/*-reseed.prompt.md | tail -n 1)"
assert_grep "^## facts.md" "$seed" "session_call: the seed carries facts.md"
assert_grep "^## expansion.md" "$seed" "session_call: the seed carries expansion.md"
assert_grep "^## The latest gate verdict" "$seed" "session_call: the seed carries the latest gate feedback"
assert_grep "^Task: write the expansion\.$" "$seed" "session_call: the original task follows the seed"
assert_ne "$(state_get "$RD" sessions.A "")" "$sidA" "session_call: the new session id replaces the lost one"
unset REELS_SLEEP_SCALE
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. the angle loop with the fake claude: S4 runs, the round counter reaches 2, then the idea is dropped"
sandbox_init --with-pipeline
rm -f "$SANDBOX/library/profile/account.md"   # M5 drafted the file; this section tests the flag for a missing one
fake_claude_on
mkdir -p "$SANDBOX/fixtures"
cp "$FAKE_M4"/*.json "$SANDBOX/fixtures/"
export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
# the angle fixture's "change" gets two em dashes in the sandbox copy (never in the repo file): the stage must clean
# the model's words before they reach angle.json, angle-<n>.json, the drop reason and the next round's prompt
python - "$SANDBOX_M/fixtures/04-angle.json" <<'EOF'
import json, sys
path = sys.argv[1]
a = json.load(open(path, encoding="utf-8"))
em = chr(0x2014)
a["change"] = ("The share line now names the three banned defaults" + em + "so it survives without the video " + em
               + " and the identity is narrower: freelancers who ship client landing pages.")
json.dump(a, open(path, "w", encoding="utf-8"), ensure_ascii=False)
EOF
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/drop.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/drop.out"; RD="$(first_run)"
assert_rc 0 $rc "the runner exits 0 after the drop"
assert_grep "${ts_regex}STEP   researching facts done \([0-9ms]+\) -> expanding idea$" "$OUT" "STEP after S1"
assert_grep "${ts_regex}STEP   expanding idea done \([0-9ms]+\) -> checking idea \(gate\)$" "$OUT" "STEP after S2"
assert_grep "${ts_regex}ANGLE  gate failed \(S1\): finding a better angle, round 1/2$" "$OUT" "ANGLE line, round 1/2"
assert_grep "${ts_regex}STEP   checking idea \(gate\) done \([0-9ms]+\) -> finding a better angle$" "$OUT" "STEP: the gate hands over to the angle stage"
assert_grep "${ts_regex}STEP   finding a better angle done \([0-9ms]+\) -> checking idea \(gate\)$" "$OUT" "STEP: the angle stage hands back to the gate"
assert_grep "${ts_regex}ANGLE  gate failed \(S1\): finding a better angle, round 2/2$" "$OUT" "ANGLE line, round 2/2"
assert_grep "${ts_regex}DROP   idea \"Claude Code's frontend-design skill: it ...\" dropped: still failing after 2 angle rounds \(P3 S1 C3 F ok H ok\): Fixture gate: the share driver is too weak to be forwarded on its own\.\. Removed from ideas.txt$" "$OUT" "DROP line with the scores and the reason"
assert_eq "$(event_tags "$OUT")" "STEP,STEP,ANGLE,STEP,STEP,ANGLE,STEP,STEP,DROP" "the event lines in order: two angle rounds, then the drop"
assert_grep "${ts_regex}FLAG   needs review: library/profile/account.md is missing: the research and the expansion used default audience assumptions$" "$OUT" "FLAG: a missing account.md is a NEEDS REVIEW flag, not an error"
assert_eq "$(grep -c "FLAG   needs review: library/profile/account.md" "$OUT")" "1" "the missing account.md is flagged once, although S1, S2 and S4 all noticed it"
assert_not_grep "GATE   passed" "$OUT" "no GATE passed line"
assert_not_grep "${ts_regex}ERROR" "$OUT" "no ERROR line"
assert_grep "^20[0-9-]+ [0-9:]+ \| $TEST_IDEA \| external \| dropped: still failing after 2 angle rounds \(P3 S1 C3 F ok H ok\): " "$SANDBOX/logs/history.txt" "history: the drop with the scores"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "ideas.txt: the idea is gone"
assert_eq "$(state_get "$RD" rounds.angle)" "2" "state.json: rounds.angle reached 2"
assert_eq "$(state_get "$RD" status)" "dropped" "state.json: dropped"
assert_eq "$(state_get "$RD" stages.04-angle.status)" "done" "state.json: 04-angle ran"
assert_eq "$(json_get "$RD/03-gate/gate.json" round)" "3" "gate.json: round 3 (two angle rounds before it)"
assert_eq "$(json_get "$RD/03-gate/gate.json" decision)" "drop" "gate.json: decision drop"
assert_eq "$(json_get "$RD/03-gate/gate.json" angles_done)" "2" "gate.json: angles_done 2"
assert_file "$RD/03-gate/gate-1.json" "gate-1.json kept"
assert_file "$RD/03-gate/gate-3.json" "gate-3.json kept"
assert_file "$RD/04-angle/angle-1.json" "angle-1.json kept"
assert_file "$RD/04-angle/angle-2.json" "angle-2.json kept"
assert_eq "$(json_get "$RD/04-angle/angle.json" round)" "2" "angle.json: round 2"
assert_eq "$(json_get "$RD/04-angle/angle.json" previous_scores.S)" "1" "angle.json: the previous scores"
assert_eq "$(json_get "$RD/02-expansion/expansion.json" written_by)" "04-angle round 2" "expansion.json: rewritten by the second angle round"
assert_file "$RD/02-expansion/expansion-r0.md" "the original expansion is kept as expansion-r0.md"
assert_file "$RD/02-expansion/expansion-r1.md" "the first rewrite is kept as expansion-r1.md"
assert_grep "^Share driver: if you are a freelancer" "$RD/02-expansion/expansion.md" "expansion.md: the angle's new share line"
assert_eq "$(grep -c '^8\. The skill.s SKILL.md tells Claude Code' "$RD/01-research/facts.md")" "1" "facts.md: the angle's new claim appended once as #8 (the second round did not duplicate it)"
assert_grep "^   Added by 04-angle round 1\.$" "$RD/01-research/facts.md" "facts.md: the new claim says who added it"
assert_eq "$(json_get "$RD/01-research/research.json" counts.claims)" "8" "research.json: 8 claims"
assert_grep "^- facts.md#8: " "$RD/02-expansion/expansion.md" "expansion.md: the new claim is cited"
assert_grep "^\[[0-9:]+\] INFO   S4: angle round 2/2, 0 new claims" "$SANDBOX/logs/runner.log" "INFO: the second angle round added nothing new"
assert_grep "^\[[0-9:]+\] INFO   S4: angle round 1/2, 1 new claim, solution external \(.*\), expansion [0-9]+ chars: The share line now names" "$SANDBOX/logs/runner.log" "INFO: the first angle round added the new claim (and names the solution, M12)"
assert_eq "$(json_get "$RD/04-angle/angle-1.json" change)" "The share line now names the three banned defaults, so it survives without the video, and the identity is narrower: freelancers who ship client landing pages." "angle-1.json: the em dashes the model wrote in \"change\" became commas before the file was written"
no_emdash_in "angle.json, angle-1.json, angle-2.json and the second round's prompt hold no em dash" "$RD/04-angle/angle.json" "$RD/04-angle/angle-1.json" "$RD/04-angle/angle-2.json" "$RD/04-angle/prompt-angle-r2.md"
# the model calls: S1, S2, S3, S4, S3, S4, S3; session A for the research model, a fresh session for every gate
calls="$(fake_calls_json)"
assert_eq "$(python -c 'import json, sys; print(",".join(c["stage"] for c in json.loads(sys.argv[1])))' "$calls")" "01-research,02-expansion,03-gate,04-angle,03-gate,04-angle,03-gate" "the fake answered the stages in order"
sidA="$(python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig"))["session_id"])' "$RD/01-research/calls/001-research.json")"
assert_eq "$(fake_field 2 resume)" "$sidA" "S2 resumes session A"
assert_eq "$(fake_field 4 resume)" "$sidA" "S4 resumes session A"
assert_eq "$(fake_field 6 resume)" "$sidA" "the second angle round resumes session A"
assert_eq "$(fake_field 3 resume)$(fake_field 5 resume)$(fake_field 7 resume)" "" "every gate round is a fresh session"
assert_eq "$(fake_field 3 model)" "$(python -c 'import json; print(json.load(open("config.json"))["models"]["gate"]["model"])')" "the gate uses the gate model from config"
assert_eq "$(fake_field 1 model)" "$(python -c 'import json; print(json.load(open("config.json"))["models"]["research"]["model"])')" "the research uses the research model from config"
assert_eq "$(fake_field 1 tools)" '["WebSearch,WebFetch,Read,Bash"]' "S1: the research tools"
assert_true "S1 and S4: Bash is approved only for the read-only gh forms and the screenshot tool, never for every gh command" python -c 'import json, sys
calls = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
ok = True
for n in (1, 4, 6):
    allowed = calls[n - 1]["allowed"]
    ok = ok and all(r in allowed for r in ("Bash(gh repo view *)", "Bash(gh release list *)", "Bash(gh release view *)", "Bash(gh api repos/*)", "Bash(bash pipeline/bin/screenshot *)"))
    ok = ok and "Bash" not in allowed and not any(r.startswith(("Bash(gh *", "Bash(gh:*", "Bash(gh*")) for r in allowed)
sys.exit(0 if ok else 1)' "$FAKE_CLAUDE_LOG"
assert_true "S1 and S4: the gh forms that write are denied (auth, gist, clone, download, the writing verbs, gh api with a method or field flag)" python -c 'import json, sys
calls = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
need = {"Bash(gh auth *)", "Bash(gh gist *)", "Bash(gh repo clone *)", "Bash(gh release download *)", "Bash(gh * create *)",
        "Bash(gh * delete *)", "Bash(gh * comment *)", "Bash(gh api* -X*)", "Bash(gh api* --method*)", "Bash(gh api* -f*)",
        "Bash(gh api* -F*)", "Bash(gh api* --field*)", "Bash(gh api* --raw-field*)", "Bash(gh api* --input*)"}
sys.exit(0 if all(need <= set(calls[n - 1]["disallowed"]) for n in (1, 4, 6)) else 1)' "$FAKE_CLAUDE_LOG"
assert_eq "$(fake_field 3 tools)" '[""]' "S3: the gate has no tools"
assert_eq "$(fake_field 2 tools)" '[""]' "S2: the expansion has no tools"
assert_true "S1: the protected files are denied" grep -q 'Edit(ideas.txt)' <<<"$(fake_field 1 disallowed)"
assert_eq "$(fake_field 1 schema)" "true" "S1: a JSON schema is passed"
assert_true "every call is saved under calls/" test -f "$RD/03-gate/calls/003-gate-r3.json" -a -f "$RD/04-angle/calls/002-angle-r2-try1.json"
assert_eq "$(state_get "$RD" sessions.A)" "$sidA" "state.json: sessions.A holds the session id"
no_emdash_in "no em dash in the stage files" "$RD/01-research/facts.md" "$RD/02-expansion/expansion.md" "$RD/03-gate/gate.json" "$RD/04-angle/angle.json" "$SANDBOX/logs/history.txt"

# the gate passes on round 2: the loop ends and the run continues to the export
fake_claude_reset
cp "$FAKE_M4/variants/03-gate.pass.json" "$SANDBOX/fixtures/03-gate.2.json"
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/pass.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/pass.out"; RD="$(run_dirs | sed -n 2p)"
assert_rc 0 $rc "pass on round 2: the runner exits 0"
assert_grep "${ts_regex}ANGLE  gate failed \(S1\): finding a better angle, round 1/2$" "$OUT" "pass on round 2: one ANGLE line"
assert_grep "${ts_regex}GATE   passed \(P3 S3 C3 F ok H ok\) after 1 angle round$" "$OUT" "pass on round 2: the GATE line names the angle round"
assert_grep "${ts_regex}STEP   checking idea \(gate\) done \([0-9ms]+\) -> picking hooks$" "$OUT" "pass on round 2: the gate hands over to S5"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "pass on round 2: the run continues to the export (dummy stages)"
assert_eq "$(event_tags "$OUT")" "STEP,STEP,ANGLE,STEP,STEP,GATE,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,DONE" "pass on round 2: the event lines (the gate's own STEP, then the 12 dummy stages)"
assert_eq "$(state_get "$RD" rounds.angle)" "1" "pass on round 2: rounds.angle is 1"
assert_eq "$(json_get "$RD/03-gate/gate.json" pass)" "true" "pass on round 2: gate.json pass true"
assert_eq "$(json_get "$RD/03-gate/gate.json" round)" "2" "pass on round 2: gate round 2"
assert_no_file "$RD/04-angle/angle-2.json" "pass on round 2: no second angle round"
rm -f "$SANDBOX/fixtures/03-gate.2.json"

# the research found the core claim false: F fails and the idea is dropped at once, no angle round
fake_claude_reset
python - "$FAKE_M4/01-research.json" "$SANDBOX_M/fixtures/01-research.json" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
r["core_claim"] = {"text": "ffmpeg 8 has a --make-reel flag", "status": "false", "note": "the ffmpeg 8 documentation lists no such option"}
json.dump(r, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF
cp "$FAKE_M4/variants/03-gate.pass.json" "$SANDBOX/fixtures/03-gate.json"
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/false.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/false.out"; RD="$(run_dirs | sed -n 3p)"
assert_rc 0 $rc "false core claim: the runner exits 0"
assert_grep "${ts_regex}DROP   idea \".*\" dropped: facts don't hold \(P3 S3 C3 F fail H ok\): the idea's core claim is false \(the ffmpeg 8 documentation lists no such option\)" "$OUT" "false core claim: DROP at once with F fail, whatever the gate model scored"
assert_not_grep "${ts_regex}ANGLE" "$OUT" "false core claim: no angle round"
assert_eq "$(state_get "$RD" stages.04-angle.status)" "skipped" "false core claim: 04-angle stayed skipped"
assert_eq "$(json_get "$RD/03-gate/gate.json" F)" "fail" "false core claim: gate.json F fail"
assert_grep "dropped: facts don't hold \(P3 S3 C3 F fail H ok\)" "$SANDBOX/logs/history.txt" "false core claim: the history line"

# the gate says only a different topic works: drop, and the suggestion goes to logs/suggested-ideas.txt
fake_claude_reset
cp "$FAKE_M4/01-research.json" "$SANDBOX/fixtures/01-research.json"
python - "$FAKE_M4/03-gate.json" "$SANDBOX_M/fixtures/03-gate.json" <<'EOF'
import json, sys
g = json.load(open(sys.argv[1], encoding="utf-8")); g["different_topic"] = True
g["suggested_idea"] = "A reel about the three defaults every AI page shares, with the skill as one fix among others"
json.dump(g, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/topic.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/topic.out"
assert_grep "${ts_regex}DROP   idea \".*\" dropped: no angle keeps the core topic \(P3 S1 C3 F ok H ok\): .*suggestion written to logs/suggested-ideas.txt\. Removed from ideas.txt$" "$OUT" "different topic: DROP with the reason"
assert_grep "^\{A reel about the three defaults every AI page shares, with the skill as one fix among others\}$" "$SANDBOX/logs/suggested-ideas.txt" "different topic: the suggestion in logs/suggested-ideas.txt"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "different topic: nothing added to ideas.txt"
assert_not_grep "${ts_regex}ANGLE" "$OUT" "different topic: no angle round"

# the gate fails F for wording on round 1 (the core claim verified, a statement of the expansion not in facts.md):
# no drop; the angle stage repairs the expansion, the gate passes on round 2 and the run continues to the export
# (M4 review 2, DECISIONS.md 112)
fake_claude_reset
cp "$FAKE_M4/01-research.json" "$SANDBOX/fixtures/01-research.json"
cp "$FAKE_M4/variants/03-gate.wording.json" "$SANDBOX/fixtures/03-gate.json"
cp "$FAKE_M4/variants/03-gate.pass.json" "$SANDBOX/fixtures/03-gate.2.json"
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/ideas.txt"
run_once "$SANDBOX/wording.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/wording.out"; RD="$(run_of "$OUT")"
assert_rc 0 $rc "wording repair: the runner exits 0"
assert_grep "${ts_regex}ANGLE  gate failed \(F wording\): finding a better angle, round 1/2$" "$OUT" "wording repair: the ANGLE line names the F wording failure"
assert_not_grep "${ts_regex}DROP" "$OUT" "wording repair: a wording slip with the core verified does not drop the idea"
assert_grep "${ts_regex}GATE   passed \(P3 S3 C3 F ok H ok\) after 1 angle round$" "$OUT" "wording repair: the gate passes on round 2"
assert_grep "${ts_regex}DONE   exported #[0-9]+ -> exports/" "$OUT" "wording repair: the run continues to the export"
assert_eq "$(event_tags "$OUT")" "STEP,STEP,ANGLE,STEP,STEP,GATE,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,DONE" "wording repair: the event lines (one angle round, the pass, the dummy stages)"
assert_eq "$(json_get "$RD/03-gate/gate-1.json" decision)" "angle" "wording repair: gate-1.json decided angle"
assert_eq "$(json_get "$RD/03-gate/gate-1.json" F)/$(json_get "$RD/03-gate/gate-1.json" F_kind)" "fail/wording" "wording repair: gate-1.json F fail of kind wording"
assert_eq "$(json_get "$RD/03-gate/gate-1.json" failing)" '["F"]' "wording repair: gate-1.json failing lists F"
assert_eq "$(json_get "$RD/03-gate/gate.json" pass)" "true" "wording repair: gate.json (round 2) pass"
assert_eq "$(json_get "$RD/04-angle/angle-1.json" previous_F_kind)" "wording" "wording repair: angle-1.json records the F kind it repaired"
assert_true "angle.json with previous_F_kind validates against schema.json" python pipeline/bin/validate-json pipeline/stages/04-angle/schema.json "$RD/04-angle/angle.json"
assert_grep "^## F failed for wording: fix this first$" "$RD/04-angle/prompt-angle-r1.md" "wording repair: the angle prompt asks for the repair first"
assert_grep "^Scores: P3 S3 C3 F fail H ok\. Failing: F \(wording\)\.$" "$RD/04-angle/prompt-angle-r1.md" "wording repair: the angle prompt names the failing criterion"
assert_grep "one folder in ~/.claude/skills\" says more than claim 3" "$RD/04-angle/prompt-angle-r1.md" "wording repair: the angle prompt quotes the gate's F evidence (the statement to fix)"
assert_grep "^Hint for a better angle: Fixture gate hint: reword the install sentence" "$RD/04-angle/prompt-angle-r1.md" "wording repair: the angle prompt carries the gate's hint"
assert_grep "gate round 1: P3 S3 C3 F fail \(wording\) H ok, decision angle" "$RD/03-gate/prompt-gate-r2.md" "wording repair: the second gate round sees the first round's F kind"
assert_eq "$(json_get "$RD/02-expansion/expansion.json" written_by)" "04-angle round 1" "wording repair: the expansion was rewritten by the angle round"
assert_eq "$(grep -c '| exported [0-9]*$' "$SANDBOX/logs/history.txt")" "2" "wording repair: the history line says exported (the second export of this section)"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "wording repair: the idea left ideas.txt after the export, not after a drop"
no_emdash_in "wording repair: no em dash in the gate and angle files" "$RD/03-gate/gate-1.json" "$RD/03-gate/gate.json" "$RD/04-angle/angle-1.json" "$RD/04-angle/prompt-angle-r1.md"
unset FAKE_CLAUDE_FIXTURES
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. the test idea with the real models: research, expansion, gate (several minutes)"
sandbox_init --with-pipeline
fake_claude_off
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/ideas.txt"
started="$EPOCHSECONDS"
run_once "$SANDBOX/real.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/real.out"; RD="$(first_run)"
printf 'real run took %ss, kept at %s\n' "$((EPOCHSECONDS - started))" "$RD"
grep -E "$ts_regex(STEP|GATE|ANGLE|DROP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0"
assert_grep "${ts_regex}STEP   researching facts done \([0-9hms]+\) -> expanding idea$" "$OUT" "S1 done"
assert_grep "${ts_regex}STEP   expanding idea done \([0-9hms]+\) -> checking idea \(gate\)$" "$OUT" "S2 done"
assert_grep "${ts_regex}GATE   passed \(P[2-3] S[2-3] C[2-3] F ok H ok\)" "$OUT" "GATE passed (directly or after an angle round)"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the run continued past the gate to the (dummy) export"
assert_not_grep "${ts_regex}ERROR" "$OUT" "no ERROR line"
assert_not_grep "${ts_regex}BLOCK" "$OUT" "no BLOCK line"
R="$RD/01-research"
assert_file "$R/facts.md" "facts.md exists"
n="$(claim_lines_ok "$R/facts.md")"; rc=$?
assert_rc 0 $rc "facts.md: every claim line carries a URL and a checked date ($n claims)"
assert_true "facts.md: at least 3 claims" test "${n:-0}" -ge 3
assert_true "research.json validates against schema.json" python pipeline/bin/validate-json pipeline/stages/01-research/schema.json "$R/research.json"
assert_true "research.json: at least one verified claim" test "$(json_get "$R/research.json" counts.verified 0)" -ge 1
assert_eq "$(json_get "$R/research.json" core_claim.status)" "verified" "research.json: the core claim of the test idea is verified"
assert_true "numbers.json is valid JSON with at least one number" python -c 'import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8-sig")); sys.exit(0 if isinstance(d, dict) and len(d) >= 1 and all("url" in v and "checked" in v for v in d.values()) else 1)' "$R/numbers.json"
assert_true "assets.json is valid JSON and every asset file exists" python -c 'import json, os, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig")); base = os.path.dirname(sys.argv[1])
sys.exit(0 if isinstance(d, list) and all(os.path.isfile(os.path.join(base, a["file"])) and a.get("url") and a.get("captured") for a in d) else 1)' "$R/assets.json"
n_assets="$(python -c 'import json, sys; print(len(json.load(open(sys.argv[1], encoding="utf-8-sig"))))' "$R/assets.json")"
assert_true "assets.json: at least one screenshot of a real page ($n_assets)" test "${n_assets:-0}" -ge 1
assert_true "research.json: one specific true thing candidates" test "$(json_get "$R/research.json" one_true_thing '[]' | python -c 'import json, sys; print(len(json.load(sys.stdin)))')" -ge 1
E="$RD/02-expansion"
chars="$(wc -c < "$E/expansion.md" | tr -d ' ')"
assert_true "expansion.md is between 500 and 1500 characters ($chars)" test "${chars:-0}" -ge 500 -a "${chars:-0}" -le 1500
assert_true "expansion.json validates against schema.json" python pipeline/bin/validate-json pipeline/stages/02-expansion/schema.json "$E/expansion.json"
assert_grep "^Problem: .*\b(I|I'm|my|me)\b" "$E/expansion.md" "expansion.md: the problem sentence in the first person"
assert_grep "^Solution: ." "$E/expansion.md" "expansion.md: the solution"
assert_grep "^Share driver: .+\. Takeaway worth forwarding: ." "$E/expansion.md" "expansion.md: the share identity and the takeaway"
assert_grep "^Comment keyword: [A-Z0-9]+\. Deliverable \((existing|NEW, to create)\): ." "$E/expansion.md" "expansion.md: the keyword with its deliverable"
assert_grep "^One specific true thing: ." "$E/expansion.md" "expansion.md: the one specific true thing"
assert_true "expansion.md: at least two evidence lines pointing to facts.md" test "$(grep -c '^- facts.md#[0-9]*: ' "$E/expansion.md")" -ge 2
assert_eq "$(json_get "$E/expansion.json" rule_errors '[]')" "[]" "expansion.json: every rule held (no forced write)"
G="$RD/03-gate"
assert_true "gate.json validates against schema.json" python pipeline/bin/validate-json pipeline/stages/03-gate/schema.json "$G/gate.json"
assert_eq "$(json_get "$G/gate.json" pass)" "true" "gate.json: pass"
assert_true "gate.json: scores 0 to 3 and quoted evidence for P, S, C and F" python -c 'import json, sys
g = json.load(open(sys.argv[1], encoding="utf-8-sig")); s = g["scores"]
ok = all(isinstance(s[k], int) and 0 <= s[k] <= 3 for k in "PSC") and all(len(g["evidence"][k].strip()) > 10 for k in "PSCF")
sys.exit(0 if ok else 1)' "$G/gate.json"
assert_true "state.json: sessions.A is stored" test -n "$(state_get "$RD" sessions.A "")"
sid1="$(python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig")).get("session_id", ""))' "$R/calls/001-research.json")"
assert_grep "^resume: $sid1$" "$E/calls/001-expansion-1.meta" "S2 resumed S1's session (session A)"
assert_grep "^resume: $" "$G/calls/001-gate-r1.meta" "S3 ran in a fresh session"
# the narrowed gh rules (DECISIONS.md 111) must not refuse a read-only gh command: the CLI's result lists every
# Bash call the permission system refused (permission_denials)
printf '    Bash calls the permission system refused in S1: %s\n' "$(python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig"))
print(json.dumps([str((x.get("tool_input") or {}).get("command", "")) for x in (d.get("permission_denials") or []) if x.get("tool_name") == "Bash"]))' "$R/calls/001-research.json")"
printf '    numbers whose source is on github.com: %s\n' "$(python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig")); print(", ".join(k for k, v in d.items() if "github.com" in str(v.get("url", ""))) or "none")' "$R/numbers.json")"
assert_true "S1: the permission rules refused no read-only gh command" python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig"))
cmds = [str((x.get("tool_input") or {}).get("command", "")) for x in (d.get("permission_denials") or []) if x.get("tool_name") == "Bash"]
mutating = (" -X", " --method", " -f", " -F", " --field", " --raw-field", " --input")
bad = [c for c in cmds if c.startswith(("gh repo view", "gh release list", "gh release view", "gh api repos/")) and not any(m in c for m in mutating)]
sys.exit(1 if bad else 0)' "$R/calls/001-research.json"
no_emdash_in "no em dash in the stage files" "$R/facts.md" "$R/research.json" "$E/expansion.md" "$E/expansion.json" "$G/gate.json" "$SANDBOX/logs/runner.log" "$SANDBOX/logs/history.txt"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "ideas.txt: the idea is gone after the export"
assert_grep "exported 1$" "$SANDBOX/logs/history.txt" "history: exported"
if [ -n "${M4_FREEZE:-}" ] && [ "$rc" = 0 ] && [ "$(json_get "$G/gate.json" pass)" = true ]; then
  FR="$FIXTURES/runs/test-idea"
  rm -rf "$FR"; mkdir -p "$FR"
  for st in 01-research 02-expansion 03-gate 04-angle; do
    [ -d "$RD/$st" ] || continue
    mkdir -p "$FR/$st"
    ( cd "$RD/$st" && find . -type f \( -name '*.json' -o -name '*.md' -o -name '*.png' \) ! -path './calls/*' ! -name 'prompt-*' ! -name 'error.json' ! -name 'result.json' -exec cp --parents {} "$FR/$st/" \; )
    mkdir -p "$FR/$st/calls"
    cp "$RD/$st"/calls/*.out.json "$FR/$st/calls/" 2>/dev/null || true
  done
  # the model's raw answers may hold em dashes (the rendered files are cleaned by the stages, the raw answers are
  # not): no file of this repo may hold one, so the frozen copies are cleaned the same way
  python - "$FR" <<'PYEOF'
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "pipeline", "lib"))  # the test runs from the repo root
from errors import undash
def clean(x):
    if isinstance(x, str): return undash(x)
    if isinstance(x, list): return [clean(v) for v in x]
    if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
    return x
em = bytes([0xE2, 0x80, 0x94])
for dp, _, names in os.walk(sys.argv[1]):
    for name in names:
        path = os.path.join(dp, name)
        data = open(path, "rb").read()
        if em not in data:
            continue
        if name.endswith(".json"):
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(clean(json.loads(data.decode("utf-8-sig"))), fh, ensure_ascii=False, indent=1)
                fh.write("\n")
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(undash(data.decode("utf-8-sig")))
PYEOF
  cp "$RD/idea.txt" "$FR/idea.txt"
  python "$STATE_PY" summary "$RD" > "$FR/state.summary.json" 2>/dev/null || true
  rm -rf "$FR/04-angle" 2>/dev/null && [ -f "$RD/04-angle/angle.json" ] && { mkdir -p "$FR/04-angle"; cp "$RD/04-angle/angle"*.json "$FR/04-angle/"; }
  printf 'frozen outputs of the test idea, written by M4_FREEZE=1 bash pipeline/tests/test-m4.sh on %s from %s\n' "$(date '+%Y-%m-%d %H:%M')" "$(basename "$RD")" > "$FR/README.txt"
  pass "frozen: the test idea's outputs copied to pipeline/tests/fixtures/runs/test-idea/"
fi
fi

# ----------------------------------------------------------------------------------------------------------------
if want 4; then
section "4. a deliberately false idea with the real models: dropped with a reason, its block gone from ideas.txt"
sandbox_init --with-pipeline
fake_claude_off
cp "$FIXTURES/ideas/false-idea.txt" "$SANDBOX/ideas.txt"
FALSE_IDEA="$(python pipeline/lib/ideas.py first --file "$SANDBOX_M/ideas.txt" | python -c 'import json, sys; print(json.load(sys.stdin)["text"])')"
started="$EPOCHSECONDS"
run_once "$SANDBOX/false-real.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/false-real.out"; RD="$(first_run)"
printf 'false idea run took %ss, kept at %s\n' "$((EPOCHSECONDS - started))" "$RD"
grep -E "$ts_regex(STEP|GATE|ANGLE|DROP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0 after the drop"
assert_grep "${ts_regex}DROP   idea \"ffmpeg 8 added a \"--make-reel\" flag: one...\" dropped: (facts don't hold|still failing after [0-9] angle rounds?|no angle keeps the core topic) \(P[0-3] S[0-3] C[0-3] F (ok|fail)\): .+\. Removed from ideas.txt$" "$OUT" "DROP line with the scores and a reason"
assert_grep "${ts_regex}DROP   .* dropped: facts don't hold \(P[0-3] S[0-3] C[0-3] F fail H (ok|fail)\): " "$OUT" "the drop is an F failure (the tool does not do what the idea assumes)"
assert_not_grep "${ts_regex}(ERROR|BLOCK|DONE)" "$OUT" "no ERROR, BLOCK or DONE line"
assert_grep "^20[0-9-]+ [0-9:]+ \| $(printf '%s' "$FALSE_IDEA" | sed 's/[][\.*^$()+?{}|]/\\&/g') \| (-|flashfx|external|method) \| dropped: .*\(P[0-3] S[0-3] C[0-3] F (ok|fail) H (ok|fail)\): " "$SANDBOX/logs/history.txt" "history: the drop line with the scores and the reason"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "ideas.txt: the false idea's block is gone"
assert_true "ideas.txt: nothing else was written (only the fixture's note text remains)" python -c 'import sys
left = open(sys.argv[1], encoding="utf-8-sig").read()
sys.exit(0 if "{" not in left and "}" not in left and "make-reel" not in left.split("A deliberately false idea", 1)[-1].replace("so the research must find the core claim false and the gate must drop the idea with the reason.", "") else 1)' "$SANDBOX_M/ideas.txt"
assert_not_grep "protected files" "$SANDBOX/logs/runner.log" "the model touched no protected file"
assert_eq "$(state_get "$RD" status)" "dropped" "state.json: dropped"
assert_ne "$(json_get "$RD/01-research/research.json" core_claim.status)" "verified" "research.json: the core claim is not verified (status: $(json_get "$RD/01-research/research.json" core_claim.status))"
assert_true "gate.json: F fail" test "$(json_get "$RD/03-gate/gate.json" F)" = fail
no_emdash_in "no em dash in the files" "$RD/01-research/facts.md" "$RD/02-expansion/expansion.md" "$RD/03-gate/gate.json" "$SANDBOX/logs/history.txt" "$SANDBOX/logs/runner.log"
fi

test_summary
