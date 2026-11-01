#!/usr/bin/env bash
# test-m5.sh: acceptance test for M5 (Profile and hooks: S5, S6). Sections 3 and 4 make real model calls (the
# indexer model over library/hooks.txt, then the research and judge models on the frozen M4 outputs of the test
# idea); everything else uses the fake claude in pipeline/tests/fakes.
#   bash pipeline/tests/test-m5.sh                    everything (10 to 20 minutes, dominated by the real S5 and S6)
#   M5_SECTIONS="1 2" bash pipeline/tests/test-m5.sh  only those sections (1 and 2 use no model, about two minutes)
#   M5_FREEZE=1 bash pipeline/tests/test-m5.sh        also copy the real 05-hooks and 06-judge outputs into
#                                                    pipeline/tests/fixtures/runs/test-idea/ (the frozen fixtures
#                                                    later milestones start from)
#
# Covers (BUILD_SPEC.md section 12, M5, and PLAN.md M5):
#   1. units, no model: hooks.py (parsing, stable ids, the index cache and the lint, the vendor formulas, the
#      shortlist, the spoken-word cap, the hook checks, the brief measure, the stats), index-hooks with the fake
#      indexer (one call, then none), judge.py (hookscore filter, candidates, labels and shuffles, lenient ranking
#      parse, Borda, pairwise, tally, judge.json), voiceprofile.py (measure, the template draft, set-wpm,
#      build-voice-profile in the sandbox), session_call --seed-if-new
#   2. S5 and S6 through the whole runner with the fake claude answering from fixtures, starting from the frozen M4
#      outputs: the seeded session, hooks.json, brief.md, judge.json, the stats; then the regeneration path (too few
#      hooks pass hookscore, S5 regenerates once, the judge continues)
#   3. index-hooks over the real library/hooks.txt with the real indexer model: one entry per hook line with id,
#      family, fit and blanks; the lint names the broken-blank and em-dash lines; a second run makes no model call
#   4. S5 and S6 on the frozen M4 outputs with the real models: hooks.json (12 to 20 hooks, 3 families or more,
#      every rule), brief.md in the token range, judge.json with a winner and a runner-up, the stats updated
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
export SANDBOX_WPM="${SANDBOX_WPM:-195}"  # the frozen fixtures and the asserted numbers were made at 195 wpm (M7 made config voice.wpm the reel voice's pace)
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
HOOKS_PY="$REPO_DIR/pipeline/lib/hooks.py"
JUDGE_PY="$REPO_DIR/pipeline/lib/judge.py"
VP_PY="$REPO_DIR/pipeline/lib/voiceprofile.py"
VENDOR="$REPO_DIR/pipeline/vendor/ig-agent-skill"
SECTIONS="${M5_SECTIONS:-1 2 3 4}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
FAKE_M5="$FIXTURES/fake/m5"
FAKE_M5_REGEN="$FIXTURES/fake/m5-regen"
FROZEN="$FIXTURES/runs/test-idea"
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
LATER_DUMMIES="$(dummy_after 06-judge)"
FAMILIES_RE='^(tools-listicle|how-to-system|mistake-warning|myth-contrarian|story-confession|transformation)$'

state_get() { python "$STATE_PY" get "$@"; }
run_dirs() { ls -d "$SANDBOX"/runs/*/ 2>/dev/null | sed 's|/$||'; }
first_run() { run_dirs | head -n 1; }
run_once() {  # run_once <outfile> [env...]: the sandbox's own run.sh (REELS_REPO is the sandbox copy of the repo)
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 3600 bash "$SANDBOX/run.sh" --once ) > "$out" 2>&1
}
fake_field() {  # fake_field <call n> <key>
  python -c 'import json, sys
calls = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
v = calls[int(sys.argv[2]) - 1].get(sys.argv[3])
print(json.dumps(v) if isinstance(v, (list, dict, bool)) else ("" if v is None else v))' "$FAKE_CLAUDE_LOG" "$1" "$2"
}
fake_calls() { python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG"; }
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
json_len() { json_get "$1" "$2" '[]' | python -c 'import json, sys; v = json.load(sys.stdin); print(len(v) if isinstance(v, (list, dict)) else 0)'; }
jf() { python -c 'import json, sys; d = json.loads(sys.argv[1]); print(d.get(sys.argv[2], ""))' "$1" "$2"; }
hooks_rules_ok() {  # hooks_rules_ok <hooks.json> <min> <max words>: the rules of spec S5 on the written file; prints a summary
  python - "$1" "$2" "$3" <<'EOF'
import json, re, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig")); lo = int(sys.argv[2]); cap = int(sys.argv[3])
hooks = d["hooks"]; fams = sorted({h["family"] for h in hooks})
WORD = re.compile(r"[A-Za-z0-9$%'’-]+")
def words(t): return WORD.findall(re.sub(r"(?<=\d),(?=\d)", "", t))
bad = []
for h in hooks:
    sp, os_ = h["spoken"], h["on_screen"]
    if len(words(sp)) > cap or len(words(sp)) > 8: bad.append(f'{h["id"]}: spoken {len(words(sp))} words')
    if float(h.get("spoken_seconds", 0)) >= 3: bad.append(f'{h["id"]}: {h.get("spoken_seconds")} s')
    if len([w for w in words(os_) if re.search(r"[A-Za-z0-9]", w)]) > 6: bad.append(f'{h["id"]}: on-screen too long')
    if not h.get("marker") or h["marker"].lower() not in sp.lower(): bad.append(f'{h["id"]}: marker not in spoken')
    if chr(0x2014) in sp or chr(0x2014) in os_: bad.append(f'{h["id"]}: em dash')
    if h["id"] != f"h{hooks.index(h) + 1:02d}": bad.append(f'{h["id"]}: id order')
print(f"{len(hooks)} hooks, families {', '.join(fams)}" + (f"; problems: {bad}" if bad else ""))
sys.exit(1 if (bad or len(hooks) < lo or len(hooks) > 20 or len(fams) < 3) else 0)
EOF
}

seed_run() {  # a run in the sandbox with S1 to S3 done from the frozen M4 outputs (04-angle stays skipped); prints the run dir
  local raw id created rd st
  raw="$(tr -d '\r' < "$FROZEN/idea.txt")"
  printf '{%s}\n' "$raw" > "$SANDBOX/ideas.txt"
  id="$(printf '%s' "$raw" | python pipeline/lib/ideas.py id)"
  created="$(printf '%s' "$raw" | python "$STATE_PY" new --runs "$SANDBOX_M/runs" --id "$id")"
  rd="$(jf "$created" run_dir)"
  for st in 01-research 02-expansion 03-gate; do
    cp -r "$FROZEN/$st/." "$rd/$st/"
    python "$STATE_PY" stage-start "$rd" "$st" >/dev/null
    python "$STATE_PY" stage-done "$rd" "$st" --schemas "$REPO_DIR/pipeline/stages" >/dev/null \
      || printf 'seed_run: the frozen %s did not validate\n' "$st" >&2
  done
  printf '%s' "$rd"
}

make_fake_fixtures() {  # make_fake_fixtures <dir> [overlay]: the m5 fake answers, the brief as a JSON answer, the index answer
  local d="$1" overlay="${2:-}"
  rm -rf "$d"; mkdir -p "$d"
  cp "$FAKE_M5"/*.json "$d/"
  [ -n "$overlay" ] && cp "$overlay"/*.json "$d/"
  python - "$d" "$FAKE_M5/brief.md" <<'EOF'
import json, sys, os
d, md = sys.argv[1], sys.argv[2]
body = open(md, encoding="utf-8").read()
with open(os.path.join(d, "05-hooks.2.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump({"brief_markdown": body, "video_type": "default", "suggested_tones": ["insider", "calm expert", "warning"]}, f, ensure_ascii=False)
EOF
  # (the parse output goes through a file: a `python -` script fed by a heredoc cannot also read a pipe)
  python "$HOOKS_PY" parse --file "$SANDBOX/library/hooks.txt" > "$d/parsed.json"
  python - "$d" <<'EOF'
import json, sys, os
fams = ["tools-listicle", "how-to-system", "mistake-warning", "myth-contrarian", "story-confession", "transformation"]
entries = json.load(open(os.path.join(sys.argv[1], "parsed.json"), encoding="utf-8"))
seen, out = set(), []
for i, e in enumerate(entries):
    if e["id"] in seen: continue
    seen.add(e["id"])
    out.append({"id": e["id"], "family": fams[i % 6], "fits_problem_solution": i % 3 != 2,
                "issue": "possible lost blank" if e["broken_blank"] else ""})
with open(os.path.join(sys.argv[1], "index-hooks.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump({"hooks": out}, f)
EOF
}

# ----------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. units: hooks.py, index-hooks, judge.py, voiceprofile.py, session_call --seed-if-new (no model)"
sandbox_init
fake_claude_on
export REELS_SLEEP_SCALE=0
mkdir -p "$SANDBOX/work"
W="$SANDBOX_M/work"

# hooks.py parse: quotes, em dash, a lost blank, a duplicate, comments, CRLF
printf '# my hooks\r\n"5 small habits that improved my __ instantly."\r\n\r\n5 small habits that improved my __ instantly.\r\nThis mindset shift changed everything in .\r\nI used to think __ was selfish %s now I see it as self-care.\r\nThe mistake every beginner makes in __.\r\n  3 tools for __ (no quotes)  \r\n' "$(printf '\xe2\x80\x94')" > "$SANDBOX/work/hooks.txt"
parsed="$(python "$HOOKS_PY" parse --file "$W/hooks.txt")"
assert_eq "$(printf '%s' "$parsed" | python -c 'import json, sys; print(len(json.load(sys.stdin)))')" "6" "parse: 6 hook lines (comments and empty lines skipped)"
assert_true "parse: the quoted and the unquoted line share one id, the second is a duplicate" python -c '
import json, sys; e = json.loads(sys.argv[1]); sys.exit(0 if e[0]["id"] == e[1]["id"] and e[1]["duplicate_of"] == 2 and e[0]["duplicate_of"] is None else 1)' "$parsed"
assert_true "parse: the lost blank is a broken blank, the normal lines are not" python -c '
import json, sys; e = json.loads(sys.argv[1]); sys.exit(0 if e[2]["broken_blank"] and not e[0]["broken_blank"] and not e[4]["broken_blank"] else 1)' "$parsed"
assert_true "parse: the em dash is noted and read as a comma in the text" python -c '
import json, sys; e = json.loads(sys.argv[1]); sys.exit(0 if e[3]["em_dash"] and chr(0x2014) not in e[3]["text"] and "selfish, now" in e[3]["text"] else 1)' "$parsed"
assert_true "parse: blanks are counted and the quotes and spaces are stripped" python -c '
import json, sys; e = json.loads(sys.argv[1]); sys.exit(0 if e[0]["blanks"] == 1 and e[0]["text"].startswith("5 small") and e[5]["text"] == "3 tools for __ (no quotes)" and e[2]["blanks"] == 0 else 1)' "$parsed"
id_a="$(python -c 'import sys; sys.path.insert(0, "pipeline/lib"); import hooks; print(hooks.hook_id("\"How I plan my __ week\""))')"
id_b="$(python -c 'import sys; sys.path.insert(0, "pipeline/lib"); import hooks; print(hooks.hook_id("how i plan my __ week"))')"
id_c="$(python -c 'import sys; sys.path.insert(0, "pipeline/lib"); import hooks; print(hooks.hook_id("How I plan my __ weekend"))')"
assert_eq "$id_a" "$id_b" "hook_id: quotes and case do not change the id (10 hex characters: $id_a)"
assert_ne "$id_a" "$id_c" "hook_id: a different text gives a different id"
assert_true "hook_id: 10 hex characters" grep -q -E '^[0-9a-f]{10}$' <<<"$id_a"

# the index cache and the lint
IDX="$W/index.json"; LINT="$W/lint.txt"; STATS="$W/stats.json"; SUGG="$W/suggested.txt"
plan="$(python "$HOOKS_PY" index-plan --file "$W/hooks.txt" --index "$IDX")"
assert_eq "$(jf "$plan" unchanged)" "False" "index-plan: a missing index is not up to date"
assert_eq "$(printf '%s' "$plan" | python -c 'import json, sys; print(len(json.load(sys.stdin)["to_classify"]))')" "5" "index-plan: 5 unique hooks to classify"
printf '%s' "$plan" | python -c '
import json, sys
p = json.load(sys.stdin); fams = ["how-to-system", "transformation", "story-confession", "mistake-warning", "tools-listicle"]
ans = {"hooks": [{"id": h["id"], "family": fams[i], "fits_problem_solution": i != 2, "issue": "a word is missing before the period" if "in ." in h["text"] else ""} for i, h in enumerate(p["to_classify"])]}
json.dump(ans, open(sys.argv[1], "w", encoding="utf-8"))' "$W/answer.json"
res="$(python "$HOOKS_PY" index-write --file "$W/hooks.txt" --index "$IDX" --answer "$W/answer.json" --lint "$LINT" --stats "$STATS" --suggested "$SUGG" --model haiku)"
assert_eq "$(jf "$res" total)" "5" "index-write: 5 hooks indexed"
assert_eq "$(jf "$res" unclassified)" "0" "index-write: every hook classified"
assert_true "index: every entry has id, family, fits_problem_solution and blanks" python -c '
import json, sys, re
d = json.load(open(sys.argv[1], encoding="utf-8")); ok = all(re.match(r"^[0-9a-f]{10}$", h["id"]) and h["family"] and isinstance(h["fits_problem_solution"], bool) and isinstance(h["blanks"], int) for h in d["hooks"])
sys.exit(0 if ok and d["source_sha1"] and d["counts"]["total"] == 5 else 1)' "$IDX"
assert_grep "^line 4: duplicate of line 2" "$LINT" "lint: the duplicate line"
assert_grep "^line 5: broken blank" "$LINT" "lint: the broken blank"
assert_grep "^line 6: em dash" "$LINT" "lint: the em dash line"
assert_grep "^line 5: grammar: a word is missing" "$LINT" "lint: the model's grammar note"
assert_file "$STATS" "index-write: the stats file is created empty"
assert_file "$SUGG" "index-write: hooks.suggested.txt is created"
plan="$(python "$HOOKS_PY" index-plan --file "$W/hooks.txt" --index "$IDX")"
assert_eq "$(jf "$plan" unchanged)" "True" "index-plan: unchanged after the write (no model call needed)"
printf '"The checklist I follow before every __."\r\n' >> "$SANDBOX/work/hooks.txt"
plan="$(python "$HOOKS_PY" index-plan --file "$W/hooks.txt" --index "$IDX")"
assert_eq "$(printf '%s' "$plan" | python -c 'import json, sys; print(len(json.load(sys.stdin)["to_classify"]))')" "1" "index-plan: an added line means one hook to classify, the others keep their family"
res="$(python "$HOOKS_PY" index-write --file "$W/hooks.txt" --index "$IDX" --lint "$LINT" --stats "$STATS" --suggested "$SUGG")"
assert_eq "$(jf "$res" unclassified)" "1" "index-write without an answer: the new hook is unclassified, the old ones kept"
plan="$(python "$HOOKS_PY" index-plan --file "$W/hooks.txt" --index "$IDX")"
assert_eq "$(jf "$plan" unchanged)" "False" "index-plan: an unclassified hook means the next run calls the model again"

# index-hooks with the fake indexer: one call, then none
mkdir -p "$SANDBOX/fixtures-index"
make_fake_fixtures "$SANDBOX/fixtures-index"
export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures-index"
fake_claude_reset
out="$(bash pipeline/bin/index-hooks 2>&1)"; rc=$?
assert_rc 0 $rc "index-hooks: exits 0 ($(printf '%s' "$out" | tail -n 1 | cut -c1-90))"
assert_eq "$(fake_calls)" "1" "index-hooks: one batched call to the indexer"
assert_eq "$(fake_field 1 role)" "indexer" "index-hooks: the call's role is indexer"
assert_eq "$(fake_field 1 model)" "haiku" "index-hooks: the indexer model from config"
assert_eq "$(fake_field 1 tools)" '[""]' "index-hooks: no tools"
assert_file "$SANDBOX/library/.hooks.index.json" "index-hooks: library/.hooks.index.json written"
assert_file "$SANDBOX/library/hooks.lint.txt" "index-hooks: library/hooks.lint.txt written"
assert_file "$SANDBOX/library/.hooks.stats.json" "index-hooks: library/.hooks.stats.json created"
n_lines="$(python "$HOOKS_PY" parse --file "$SANDBOX_M/library/hooks.txt" | python -c 'import json, sys; print(len({e["id"] for e in json.load(sys.stdin)}))')"
assert_eq "$(json_get "$SANDBOX/library/.hooks.index.json" counts.total)" "$n_lines" "index-hooks: one entry per unique hook line of hooks.txt ($n_lines)"
assert_eq "$(grep -c -E '^- id [0-9a-f]{10}: .' "$SANDBOX/logs/index-hooks/prompt-index.md")" "$n_lines" "index-hooks: the prompt lists every hook with its id"
assert_eq "$(json_get "$SANDBOX/library/.hooks.index.json" counts.unclassified)" "0" "index-hooks: every hook classified from the answer"
fake_claude_reset
out="$(bash pipeline/bin/index-hooks 2>&1)"; rc=$?
assert_rc 0 $rc "index-hooks: a second run exits 0"
assert_eq "$(fake_calls)" "0" "index-hooks: a second run with no change makes no model call"
assert_true "index-hooks: the second run says it is up to date" grep -q "up to date" <<<"$out"
ls "$SANDBOX"/logs/index-hooks/calls/*.json >/dev/null 2>&1 && pass "index-hooks: the call files live under logs/index-hooks/calls/" || fail "index-hooks: no call files under logs/index-hooks/calls/"

# the vendor formulas and the shortlist
assert_eq "$(python "$HOOKS_PY" vendor --vendor "$VENDOR/hooks.json" | python -c 'import json, sys; d = json.load(sys.stdin); print(len(d), d[0]["id"], d[-1]["id"], all(h["family"] for h in d))')" "26 v01 v26 True" "vendor: 26 formulas v01 to v26, each with a family"
sl="$(python "$HOOKS_PY" shortlist --index "$SANDBOX_M/library/.hooks.index.json" --stats "$SANDBOX_M/library/.hooks.stats.json" --vendor "$VENDOR/hooks.json" --n 24 --seed test-idea --out "$W/shortlist.json")"
assert_eq "$(jf "$sl" n)" "24" "shortlist: 24 templates"
assert_true "shortlist: at least 3 families, library and vendor templates both present" python -c '
import json, sys; s = json.loads(sys.argv[1]); sys.exit(0 if len(s["families"]) >= 3 and s["library"] > 0 and s["vendor"] > 0 else 1)' "$sl"
assert_true "shortlist: no broken-blank template is offered" python -c '
import json, sys
idx = json.load(open(sys.argv[1], encoding="utf-8")); broken = {h["id"] for h in idx["hooks"] if h["broken_blank"]}
sl = json.load(open(sys.argv[2], encoding="utf-8")); sys.exit(1 if any(c["template_id"] in broken for c in sl) else 0)' "$SANDBOX_M/library/.hooks.index.json" "$W/shortlist.json"
python "$HOOKS_PY" shortlist --index "$SANDBOX_M/library/.hooks.index.json" --stats "$SANDBOX_M/library/.hooks.stats.json" --vendor "$VENDOR/hooks.json" --n 24 --seed test-idea --out "$W/shortlist2.json" >/dev/null
assert_true "shortlist: the same seed gives the same shortlist" cmp -s "$W/shortlist.json" "$W/shortlist2.json"
assert_true "templates-text: one line per template with the id, the family and the fit" test "$(python "$HOOKS_PY" templates-text --shortlist "$W/shortlist.json" | grep -c 'template_id `.*` | family .* | fits problem to solution: ')" = 24
# stats weighting: a template that always wins is picked more often than one that never does
python - "$W/stats-biased.json" "$W/shortlist.json" <<'EOF'
import json, sys
sl = json.load(open(sys.argv[2], encoding="utf-8"))
ids = [c["template_id"] for c in sl]
stats = {"version": 1, "updated": "", "hooks": {ids[0]: {"picked": 20, "won": 19}, ids[1]: {"picked": 20, "won": 0}}}
json.dump(stats, open(sys.argv[1], "w", encoding="utf-8"))
print(ids[0], ids[1])
EOF
read -r win_id lose_id < <(python -c 'import json; sl = json.load(open("'"$W/shortlist.json"'", encoding="utf-8")); print(sl[0]["template_id"], sl[1]["template_id"])')
wins=0; loses=0
for s in 1 2 3 4 5 6 7 8 9 10 11 12; do
  python "$HOOKS_PY" shortlist --index "$SANDBOX_M/library/.hooks.index.json" --stats "$W/stats-biased.json" --vendor "$VENDOR/hooks.json" --n 10 --per-family 0 --seed "s$s" --out "$W/sl-$s.json" >/dev/null
  grep -q "\"$win_id\"" "$W/sl-$s.json" && wins=$((wins + 1))
  grep -q "\"$lose_id\"" "$W/sl-$s.json" && loses=$((loses + 1))
done
assert_true "shortlist: the win rate weights the choice once there is data (winner in $wins of 12 shortlists, loser in $loses)" test "$wins" -gt "$loses"

# the spoken-word cap
assert_eq "$(python "$HOOKS_PY" limits --wpm 150 | python -c 'import json, sys; print(json.load(sys.stdin)["max_words"])')" "7" "limits: 7 words at 150 wpm (8 words would be 3.2 s)"
assert_eq "$(python "$HOOKS_PY" limits --wpm 165 | python -c 'import json, sys; print(json.load(sys.stdin)["max_words"])')" "8" "limits: 8 words at 165 wpm"
assert_eq "$(python "$HOOKS_PY" limits --wpm 140 | python -c 'import json, sys; print(json.load(sys.stdin)["max_words"])')" "6" "limits: 6 words at 140 wpm"
assert_eq "$(python "$HOOKS_PY" limits --wpm 195 | python -c 'import json, sys; print(json.load(sys.stdin)["max_words"])')" "8" "limits: the cap never exceeds 8 words"

# the hook checks
chk_args=(--shortlist "$W/shortlist.json" --index "$SANDBOX_M/library/.hooks.index.json" --vendor "$VENDOR/hooks.json" --wpm 150 --idea-id test)
res="$(python "$HOOKS_PY" check --answer "$FAKE_M5/05-hooks.1.json" --out "$W/hooks.json" "${chk_args[@]}")"
assert_eq "$(jf "$res" ok)" "True" "check: the fixture answer passes every rule ($(jf "$res" kept) hooks)"
assert_true "check: hooks.json validates against the stage schema" python pipeline/bin/validate-json pipeline/stages/05-hooks/schema.json "$W/hooks.json"
summary="$(hooks_rules_ok "$W/hooks.json" 12 7)"; rc=$?
assert_rc 0 $rc "check: the written hooks keep the rules of spec S5 ($summary)"
assert_eq "$(json_get "$W/hooks.json" hooks.0.id)" "h01" "check: ids are h01.. in order"
assert_eq "$(json_get "$W/hooks.json" hooks.0.template_source)" "vendor" "check: the template source is recorded"
python - "$W/bad.json" <<'EOF'
import json, sys
bad = {"hooks": [
  {"template_id": "v03", "family": "myth-contrarian", "spoken": "Nobody tells you that Claude Code has a frontend design skill", "on_screen": "A SKILL", "marker": "Claude Code", "marker_kind": "tool"},
  {"template_id": "v02", "family": "mistake-warning", "spoken": "Stop using all-caps labels. Anthropic says so.", "on_screen": "STOP USING ALL CAPS LABELS NOW PLEASE", "marker": "Anthropic", "marker_kind": "tool"},
  {"template_id": "v07", "family": "mistake-warning", "spoken": "Stop pasting purple gradients everywhere.", "on_screen": "PURPLE GRADIENTS", "marker": "", "marker_kind": "tool"},
  {"template_id": "nope", "family": "how-to-system", "spoken": "Steal Anthropic's list of 5 AI tells.", "on_screen": "STEAL THE LIST", "marker": "5", "marker_kind": "number"},
  {"template_id": "v24", "family": "weird-family", "spoken": "frontend-design 1.1.1 kills the SaaS card look.", "on_screen": "NO MORE SAAS CARDS", "marker": "1.1.1", "marker_kind": "number"},
  {"template_id": "v18", "family": "how-to-system", "spoken": "Claude Code plans colors before writing code.", "on_screen": "PLAN FIRST", "marker": "Claude Code", "marker_kind": "tool"},
  {"template_id": "v10", "family": "how-to-system", "spoken": "Claude Code plans colors before writing code.", "on_screen": "PLAN FIRST AGAIN", "marker": "Claude Code", "marker_kind": "tool"},
  {"template_id": "v19", "family": "mistake-warning", "spoken": "Stop shipping AI sites clients spot instantly.", "on_screen": "CLIENTS SPOT AI SITES", "marker": "instantly", "marker_kind": "time"},
  {"template_id": "v23", "family": "myth-contrarian", "spoken": "1,134,112 installs: Claude's frontend-design skill.", "on_screen": "1,134,112 INSTALLS", "marker": "1,134,112", "marker_kind": "number"},
  {"template_id": "v13", "family": "transformation", "spoken": "Two passes, zero generic pages: frontend-design.", "on_screen": "PLAN, REVIEW, THEN CODE", "marker": "Two", "marker_kind": "number"},
  {"template_id": "v11", "family": "tools-listicle", "spoken": "The thing about websites and vibes.", "on_screen": "VIBES", "marker": "vibes", "marker_kind": "tool"}
 ], "notes": ""}
json.dump(bad, open(sys.argv[1], "w", encoding="utf-8"))
EOF
res="$(python "$HOOKS_PY" check --answer "$W/bad.json" --out "$W/hooks-bad.json" "${chk_args[@]}")"
assert_eq "$(jf "$res" ok)" "False" "check: a bad answer fails"
errs="$(printf '%s' "$res" | python -c 'import json, sys; print("\n".join(json.load(sys.stdin)["errors"]))')"
assert_true "check: an 11-word spoken line is named with the cap" grep -q "spoken line has 11 words, the cap is 7" <<<"$errs"
assert_true "check: a 7-word on-screen line is named" grep -q "on-screen line has 7 words, the cap is 6" <<<"$errs"
assert_true "check: a missing marker is named" grep -q "no marker given" <<<"$errs"
assert_true "check: an unknown template_id is named" grep -q 'template_id "nope" is not in the list' <<<"$errs"
assert_true "check: an unknown family is named" grep -q 'family "weird-family" is not one of' <<<"$errs"
assert_true "check: a repeated spoken line is named" grep -q "the same spoken line appears twice" <<<"$errs"
assert_true "check: a marker that is neither a tool, a number nor a time is named" grep -q 'is neither a named tool, a number nor a time' <<<"$errs"
assert_true "check: too few valid hooks is named with the minimum" grep -q "only 4 valid hooks, at least 12 are needed" <<<"$errs"
assert_no_file "$W/hooks-bad.json" "check: nothing is written when the rules fail without --force"
res="$(python "$HOOKS_PY" check --answer "$W/bad.json" --out "$W/hooks-forced.json" --force "${chk_args[@]}")"
assert_eq "$(jf "$res" written)" "True" "check --force: the valid hooks are written (4 of 11, enough for the judge)"
assert_eq "$(json_len "$W/hooks-forced.json" hooks)" "4" "check --force: 4 hooks in the file"
assert_true "check --force: rule_errors recorded in the file" test "$(json_len "$W/hooks-forced.json" rule_errors)" -ge 2
res="$(python "$HOOKS_PY" check --answer "$FAKE_M5_REGEN/05-hooks.3.json" --out "$W/hooks-regen.json" --keep "$W/hooks.json" --survivors h01,h02,h08 --written-by "05-hooks regenerate" "${chk_args[@]}")"
assert_eq "$(jf "$res" ok)" "True" "check --keep: survivors plus the valid replacements pass ($(jf "$res" kept) hooks)"
assert_eq "$(json_get "$W/hooks-regen.json" regenerated)" "true" "check --keep: hooks.json says regenerated"
assert_eq "$(json_get "$W/hooks-regen.json" hooks.0.spoken)" "$(json_get "$W/hooks.json" hooks.0.spoken)" "check --keep: the survivors come first, unchanged"

# the brief measure
make_fake_fixtures "$SANDBOX/fixtures-brief" >/dev/null
printf '# Brief: test\n\n- header line one\n- header line two\n' > "$W/header.md"
res="$(python "$HOOKS_PY" brief --answer "$SANDBOX_M/fixtures-brief/05-hooks.2.json" --out "$W/brief.md" --header "$W/header.md" --min 2000 --max 3000)"
assert_eq "$(jf "$res" ok)" "True" "brief: the fixture brief is inside the token range ($(jf "$res" tokens) tokens, $(jf "$res" words) words)"
assert_grep "^# Brief: test$" "$W/brief.md" "brief: the header comes first"
assert_grep "^## 1. The one idea" "$W/brief.md" "brief: the body follows"
assert_eq "$(python "$HOOKS_PY" tokens --file "$W/brief.md" | python -c 'import json, sys; print(json.load(sys.stdin)["tokens"])')" "$(jf "$res" tokens)" "tokens: the same measure on the written file"
printf '{"brief_markdown": "## Too short\\n\\nOnly a few words here.", "video_type": "list", "suggested_tones": ["warning"]}' > "$W/short.json"
res="$(python "$HOOKS_PY" brief --answer "$W/short.json" --out "$W/brief-short.md" --min 2000 --max 3000)"
assert_eq "$(jf "$res" ok)" "False" "brief: a short brief fails"
assert_true "brief: the error says how many words to add" grep -q "add about" <<<"$(printf '%s' "$res" | python -c 'import json, sys; print(json.load(sys.stdin)["errors"][0])')"
assert_no_file "$W/brief-short.md" "brief: nothing written without --force"
res="$(python "$HOOKS_PY" brief --answer "$W/short.json" --out "$W/brief-short.md" --min 2000 --max 3000 --force)"
assert_file "$W/brief-short.md" "brief --force: written anyway (the stage flags it)"
assert_eq "$(jf "$res" video_type)" "list" "brief: the video type is reported"

# the stats and the pace
python "$HOOKS_PY" stats-update --stats "$W/stats2.json" --picked v01,v02,abc1234567 --won v02 --scores '{"v01": 0.5, "v02": 0.9}' --texts '{"v01": "t1"}' --date 2026-11-01 >/dev/null
python "$HOOKS_PY" stats-update --stats "$W/stats2.json" --picked v01,v02 --won v02 --scores '{"v02": 1.0}' --date 2026-11-02 >/dev/null
assert_eq "$(json_get "$W/stats2.json" hooks.v02.picked),$(json_get "$W/stats2.json" hooks.v02.won),$(json_get "$W/stats2.json" hooks.v01.won),$(json_get "$W/stats2.json" hooks.abc1234567.picked)" "2,2,0,1" "stats-update: picked, won and scores accumulate per id"
assert_eq "$(json_get "$W/stats2.json" hooks.v02.scores)" "[0.9, 1.0]" "stats-update: the judge scores are kept per id"
printf '# voice\n\n## What I sound like\n\n- **Pace:** 172 words per minute, measured from memo.wav\n' > "$W/voice.md"
assert_eq "$(python "$HOOKS_PY" wpm --voice "$W/voice.md" --default 150)" "172" "wpm: the measured pace of voice.md wins"
assert_eq "$(python "$HOOKS_PY" wpm --voice "$W/nonexistent.md" --default 150)" "150" "wpm: the default without a voice.md"
printf '# voice\n\n- **Pace:** [FILL IN: words per minute]\n' > "$W/voice2.md"
assert_eq "$(python "$HOOKS_PY" wpm --voice "$W/voice2.md" --default 150)" "150" "wpm: a placeholder pace falls back to the default"

# judge.py: the hookscore filter and the candidates
res="$(python "$JUDGE_PY" score --hooks "$W/hooks.json" --hookscore "$VENDOR/hookscore.py" --out "$W/scores.json" --min 50)"
assert_eq "$(printf '%s' "$res" | python -c 'import json, sys; d = json.load(sys.stdin); print(len(d["survivors"]), len(d["dropped"]), d["n"])')" "14 0 14" "score: every fixture hook passes hookscore (score 50 or more, no dealbreaker)"
assert_true "score: scores.json holds a score and a verdict per hook" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if len(d["hooks"]) == 14 and all("score" in v and "verdict" in v for v in d["hooks"].values()) else 1)' "$W/scores.json"
python "$HOOKS_PY" check --answer "$FAKE_M5_REGEN/05-hooks.1.json" --out "$W/hooks-weak.json" "${chk_args[@]}" >/dev/null
res="$(python "$JUDGE_PY" score --hooks "$W/hooks-weak.json" --hookscore "$VENDOR/hookscore.py" --out "$W/scores-weak.json" --min 50)"
assert_eq "$(printf '%s' "$res" | python -c 'import json, sys; d = json.load(sys.stdin); print(len(d["survivors"]), len(d["dropped"]))')" "3 9" "score: the weak fixture keeps 3 of 12 (the regeneration case)"
python "$JUDGE_PY" feedback --hooks "$W/hooks-weak.json" --scores "$W/scores-weak.json" --out "$W/feedback.json" >/dev/null
assert_true "feedback: survivors, failures and the filter's reasons for S5" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if len(d["survivors"]) == 3 and len(d["failures"]) == 9 and "score" in d["failures_text"] and d["survivors_text"].count("\n") == 2 else 1)' "$W/feedback.json"
res="$(python "$JUDGE_PY" candidates --hooks "$W/hooks-weak.json" --scores "$W/scores-weak.json" --min-survivors 4 --top 4)"
assert_eq "$(printf '%s' "$res" | python -c 'import json, sys; d = json.load(sys.stdin); print(len(d["candidates"]), d["mode"])')" "3 survivors (fewer than wanted)" "candidates: the survivors when at least 2 passed"
printf '{"hooks": [{"id": "h01", "spoken": "Your AI site looks fake. One command fixes it.", "on_screen": "x", "marker": "One", "family": "a", "template_id": "v01"}, {"id": "h02", "spoken": "Anthropic says purple gradients scream AI.", "on_screen": "x", "marker": "Anthropic", "family": "a", "template_id": "v02"}, {"id": "h03", "spoken": "Stop scrolling, this is for you.", "on_screen": "x", "marker": "you", "family": "a", "template_id": "v03"}]}' > "$W/hooks-poor.json"
python "$JUDGE_PY" score --hooks "$W/hooks-poor.json" --hookscore "$VENDOR/hookscore.py" --out "$W/scores-poor.json" --min 50 >/dev/null
res="$(python "$JUDGE_PY" candidates --hooks "$W/hooks-poor.json" --scores "$W/scores-poor.json" --min-survivors 4 --top 4)"
assert_eq "$(printf '%s' "$res" | python -c 'import json, sys; d = json.load(sys.stdin); print(d["mode"], len(d["candidates"]), d["candidates"][-1])')" "best available 3 h03" "candidates: fewer than 2 survivors means the best available by score, the dealbreaker last"

# judge.py: labels, shuffles, the lenient ranking parse, Borda, pairwise, tally, judge.json
cands="$(json_get "$W/scores.json" survivors | tr -d '[]" ')"
python "$JUDGE_PY" rank-prompt --hooks "$W/hooks.json" --candidates "$cands" --seed "x:1" --out "$W/labels-1.json" > "$W/rank-1.txt"
python "$JUDGE_PY" rank-prompt --hooks "$W/hooks.json" --candidates "$cands" --seed "x:2" --out "$W/labels-2.json" > "$W/rank-2.txt"
assert_eq "$(grep -c '^- [A-N]: spoken "' "$W/rank-1.txt")" "14" "rank-prompt: 14 labeled lines A to N"
assert_ne "$(json_get "$W/labels-1.json" order)" "$(json_get "$W/labels-2.json" order)" "rank-prompt: the two seeds give different shuffles"
python "$JUDGE_PY" rank-prompt --hooks "$W/hooks.json" --candidates "$cands" --seed "x:1" --out "$W/labels-1b.json" >/dev/null
assert_eq "$(json_get "$W/labels-1.json" order)" "$(json_get "$W/labels-1b.json" order)" "rank-prompt: the same seed gives the same shuffle"
res="$(python "$JUDGE_PY" parse-ranking --labels "$W/labels-1.json" --answer "$FAKE_M5/06-judge.1.json" --out "$W/ranking-1.json")"
assert_eq "$(jf "$res" complete)" "True" "parse-ranking: a full ranking (extra labels ignored) is complete"
assert_eq "$(json_len "$W/ranking-1.json" ranking)" "14" "parse-ranking: 14 ids, each once"
printf '{"ranking": ["B", "Z", "A", "B"], "notes": [{"label": "B", "note": "best"}]}' > "$W/partial.json"
res="$(python "$JUDGE_PY" parse-ranking --labels "$W/labels-1.json" --answer "$W/partial.json" --out "$W/ranking-partial.json")"
assert_eq "$(jf "$res" complete)" "False" "parse-ranking: a partial ranking is flagged incomplete"
assert_eq "$(json_len "$W/ranking-partial.json" ranking)" "14" "parse-ranking: the missing hooks are appended, duplicates and unknown labels dropped"
assert_eq "$(json_get "$W/ranking-partial.json" ranking.0)" "$(json_get "$W/labels-1.json" labels.B)" "parse-ranking: the first id is label B's hook"
printf '{"ranking": ["a", "b", "c"]}' > "$W/r1.json"; printf '{"ranking": ["b", "a", "c"]}' > "$W/r2.json"
res="$(python "$JUDGE_PY" borda --rankings "$W/r1.json" "$W/r2.json" --top 2 --out "$W/borda-small.json")"
assert_eq "$(printf '%s' "$res" | python -c 'import json, sys; d = json.load(sys.stdin); print(d["points"]["a"], d["points"]["b"], d["points"]["c"], ",".join(d["top"]))')" "3 3 0 a,b" "borda: n-1-position points per ranking, ties by the first ranking"
python "$JUDGE_PY" parse-ranking --labels "$W/labels-2.json" --answer "$FAKE_M5/06-judge.2.json" --out "$W/ranking-2.json" >/dev/null
res="$(python "$JUDGE_PY" borda --rankings "$W/ranking-1.json" "$W/ranking-2.json" --top 4 --out "$W/borda.json")"
assert_eq "$(json_len "$W/borda.json" top)" "4" "borda: the top 4 for the pairwise call"
python "$JUDGE_PY" pair-prompt --hooks "$W/hooks.json" --top "$(json_get "$W/borda.json" top | tr -d '[]" ')" --out "$W/pairs.json" > "$W/pairs.txt"
assert_eq "$(json_len "$W/pairs.json" comparisons)" "12" "pair-prompt: 4 hooks give 12 comparisons (every pair in both orders)"
assert_true "pair-prompt: every pair appears once in each order" python -c '
import json, sys; c = json.load(open(sys.argv[1], encoding="utf-8"))["comparisons"]
pairs = [(x["first"], x["second"]) for x in c]; sys.exit(0 if len(set(pairs)) == 12 and all((b, a) in pairs for a, b in pairs) else 1)' "$W/pairs.json"
assert_grep "^12\. first [WXYZ], second [WXYZ]$" "$W/pairs.txt" "pair-prompt: the comparisons are numbered in the prompt"
res="$(python "$JUDGE_PY" tally --pairs "$W/pairs.json" --answer "$FAKE_M5/06-judge.3.json" --borda "$W/borda.json" --scores "$W/scores.json" --out "$W/tally.json")"
assert_eq "$(jf "$res" winner)" "$(json_get "$W/pairs.json" labels.W)" "tally: the hook that won every comparison is the winner"
assert_eq "$(jf "$res" runner_up)" "$(json_get "$W/pairs.json" labels.X)" "tally: the runner-up is the next by wins"
assert_eq "$(jf "$res" answered)" "12" "tally: 12 comparisons counted"
printf '{"comparisons": [{"n": 1, "winner": "X", "why": "x"}, {"n": 2, "winner": "W", "why": "w"}, {"n": 99, "winner": "W", "why": "ignored"}, {"n": 3, "winner": "Q", "why": "not in the pair"}]}' > "$W/pair-tie.json"
res="$(python "$JUDGE_PY" tally --pairs "$W/pairs.json" --answer "$W/pair-tie.json" --borda "$W/borda.json" --scores "$W/scores.json" --out "$W/tally-tie.json")"
assert_eq "$(jf "$res" answered)" "2" "tally: an unknown comparison number or a winner outside the pair is ignored"
assert_eq "$(jf "$res" winner)" "$(json_get "$W/borda.json" top.0)" "tally: a tie in wins is broken by Borda points"
res="$(python "$JUDGE_PY" compose --hooks "$W/hooks.json" --scores "$W/scores.json" --rankings "$W/ranking-1.json" "$W/ranking-2.json" --borda "$W/borda.json" --tally "$W/tally.json" --out "$W/judge.json" --regenerated 0 --candidates-mode survivors --today 2026-11-01)"
assert_true "compose: judge.json validates against the stage schema" python pipeline/bin/validate-json pipeline/stages/06-judge/schema.json "$W/judge.json"
assert_ne "$(json_get "$W/judge.json" winner.id)" "$(json_get "$W/judge.json" runner_up.id)" "compose: winner and runner-up differ"
assert_true "compose: reasons, two rankings, 12 pairwise results, 14 hookscores" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if len(d["reasons"]) >= 2 and len(d["rankings"]) == 2 and len(d["pairwise"]) == 12 and len(d["hookscore"]) == 14 and d["calls"] == 3 else 1)' "$W/judge.json"
assert_eq "$(printf '%s' "$res" | python -c 'import json, sys; d = json.load(sys.stdin); print(len(d["picked"]), d["winner_template"] in d["picked"], len(d["scores"]) > 0)')" "14 True True" "compose: the stats payload lists every template, the winner among them, with judge scores"

# voiceprofile.py
python - "$W/words.json" <<'EOF'
import json, sys
words, segs, t = [], [], 0.0
texts = ["this is how i normally talk on reels with a normal energetic voice and a calm tone", "for example if you want to create new animation videos easily without paying for expensive software", "use the new motion graphics software that allows you to create beautiful animations in the blink of an eye"]
for k, text in enumerate(texts):
    seg_words = []
    for w in text.split():
        seg_words.append({"word": w, "start": round(t, 2), "end": round(t + 0.3, 2)}); t += 0.33
    segs.append({"start": seg_words[0]["start"], "end": seg_words[-1]["end"], "text": text, "words": seg_words})
    words += seg_words
    t += 4.0 if k == 0 else 0.4   # one long pause after the first segment
json.dump({"audio": "memo.wav", "model": "small", "language": "en", "duration": t, "segments": segs, "words": words}, open(sys.argv[1], "w", encoding="utf-8"))
EOF
res="$(python "$VP_PY" measure --words "$W/words.json" --out "$W/measure.json")"
assert_true "measure: the pace removes the long pause (wpm $(jf "$res" wpm), raw $(jf "$res" wpm_raw), $(jf "$res" words) words)" python -c '
import json, sys; d = json.loads(sys.argv[1]); sys.exit(0 if d["words"] == 52 and d["wpm"] > d["wpm_raw"] and 150 <= d["wpm"] <= 200 and d["pauses_removed_seconds"] > 2 else 1)' "$res"
assert_eq "$(printf '%s' "$res" | python -c 'import json, sys; print(len(json.load(sys.stdin)["excerpts"]))')" "3" "measure: 3 verbatim excerpts"
res="$(python "$VP_PY" compose --template "$VENDOR/templates/voice.md" --out "$W/voice-draft.md" --measure "$W/measure.json" --source memo.wav --date 2026-11-01)"
assert_eq "$(jf "$res" draft),$(jf "$res" from_model)" "True,False" "compose: without a model answer the file is a draft from the template"
assert_grep "^- \*\*Pace:\*\* [0-9]+ words per minute, measured from memo.wav" "$W/voice-draft.md" "compose: the Pace line is filled with the measurement"
assert_grep "^## Verbatim excerpts of my real speech" "$W/voice-draft.md" "compose: the excerpts section"
assert_grep "^- \*\*Name:\*\* \[FILL IN\]" "$W/voice-draft.md" "compose: the placeholders"
assert_grep "^## My positions" "$W/voice-draft.md" "compose: the template's headings are kept"
assert_not_grep "Copy this to" "$W/voice-draft.md" "compose: the vendor's intro is replaced"
assert_true "is-draft: a draft is a draft" python "$VP_PY" is-draft "$W/voice-draft.md"
printf '{"voice_md": "## Who I am\\n\\n- **Name:** Gabriele\\n- **Pace:** fast\\n\\n## What I sound like\\n\\n- **On camera I am:** calm\\n", "account_md": "## Who the account is for\\n\\nBuilders.\\n", "notes": ""}' > "$W/vp-answer.json"
res="$(python "$VP_PY" compose --template "$VENDOR/templates/voice.md" --out "$W/voice-model.md" --answer "$W/vp-answer.json" --measure "$W/measure.json" --source memo.wav --memo-name memo.wav)"
assert_eq "$(jf "$res" from_model)" "True" "compose: with a model answer the draft comes from the memo"
assert_grep "^- \*\*Name:\*\* Gabriele" "$W/voice-model.md" "compose: the model's text is kept"
assert_grep "^- \*\*Pace:\*\* [0-9]+ words per minute, measured" "$W/voice-model.md" "compose: the measured pace replaces the model's Pace line"
assert_false "is-draft: a filled file is not a draft" python "$VP_PY" is-draft "$W/voice-model.md"
python "$VP_PY" account --out "$W/account.md" >/dev/null
assert_grep "^## Topics out" "$W/account.md" "account: the draft has the spec's sections"
cp "$REPO_DIR/config.json" "$W/config-copy.json"
python "$VP_PY" set-wpm --config "$W/config-copy.json" --wpm 177 >/dev/null
assert_grep '"wpm": 177,' "$W/config-copy.json" "set-wpm: voice.wpm rewritten"
assert_eq "$(diff "$REPO_DIR/config.json" "$W/config-copy.json" | grep -c '^[<>]')" "2" "set-wpm: only that one line changed"
# build-voice-profile in the sandbox: no memo, the drafts are written, the pace is measured when a whisper interpreter exists
mkdir -p "$SANDBOX/library/voice"
if [ -f "$REPO_DIR/library/voice/engine.txt" ]; then cp "$REPO_DIR/library/voice/engine.txt" "$SANDBOX/library/voice/"; fi
if [ -f "$REPO_DIR/library/voice/reference.wav" ]; then cp "$REPO_DIR/library/voice/reference.wav" "$SANDBOX/library/voice/"; fi
rm -f "$SANDBOX/library/profile/voice.md" "$SANDBOX/library/profile/account.md"
out="$(bash pipeline/bin/build-voice-profile --no-model 2>&1)"; rc=$?
assert_rc 0 $rc "build-voice-profile: exits 0 in the sandbox"
assert_file "$SANDBOX/library/profile/voice.md" "build-voice-profile: voice.md written"
assert_file "$SANDBOX/library/profile/account.md" "build-voice-profile: account.md written"
assert_true "build-voice-profile: both files are drafts with placeholders" python -c '
import sys; sys.exit(0 if all("[FILL IN" in open(p, encoding="utf-8").read() for p in sys.argv[1:]) else 1)' "$SANDBOX_M/library/profile/voice.md" "$SANDBOX_M/library/profile/account.md"
assert_true "build-voice-profile: the next step for the user is printed" grep -q "NEXT STEP" <<<"$out"
if ls "$SANDBOX"/logs/voice-profile/*.words.json >/dev/null 2>&1; then
  assert_grep "^- \*\*Pace:\*\* [0-9]+ words per minute, measured from library/voice/reference.wav" "$SANDBOX/library/profile/voice.md" "build-voice-profile: the pace measured from the reference recording"
  assert_grep "^1\. \"" "$SANDBOX/library/profile/voice.md" "build-voice-profile: at least one verbatim excerpt"
else
  printf '    (no whisper interpreter on this PC: the pace was not measured, which the script reports)\n'
  assert_true "build-voice-profile: says why the pace was not measured" grep -q -i "not measured\|no interpreter\|no recording" <<<"$out"
fi
out="$(bash pipeline/bin/build-voice-profile --no-model 2>&1)"
assert_true "build-voice-profile: existing files are kept without --force" grep -q "kept .*voice.md" <<<"$out"
assert_eq "$(fake_calls)" "0" "build-voice-profile: no model call without a memo"

# session_call --seed-if-new: no stored session means the first call is the seeded one
RD="$SANDBOX_M/runs/seed-test"
mkdir -p "$RD/01-research" "$RD/02-expansion" "$RD/03-gate" "$RD/05-hooks"
cp "$FROZEN/01-research/facts.md" "$RD/01-research/"; cp "$FROZEN/02-expansion/expansion.md" "$RD/02-expansion/"; cp "$FROZEN/03-gate/gate.json" "$RD/03-gate/"
printf '{"version": 1, "run_id": "seed-test", "idea": {"id": "x", "text": "the idea", "raw": "the idea"}, "status": "running", "stages": {}, "sessions": {}, "flags": [], "timing": {}}' > "$RD/state.json"
printf '# Role: research\n# Stage: 05-hooks\n\nTask: write the hooks.\n' > "$RD/p.md"
unset FAKE_CLAUDE_FIXTURES
fake_claude_reset
out="$(FAKE_CLAUDE_MODE=ok bash pipeline/tests/session-driver.sh A research "$RD/05-hooks" "$RD/p.md" --seed-if-new --tools "" 2>&1)"; rc=$?
assert_rc 0 $rc "seed-if-new: the call succeeds"
assert_true "seed-if-new: the INFO line names the seed" grep -q "INFO   session A has no stored id: starting a new one seeded with facts.md" <<<"$out"
assert_eq "$(fake_calls)" "1" "seed-if-new: one call (no failed resume first)"
assert_true "seed-if-new: the prompt is the seeded one, header first" python -c '
import json, sys; c = json.loads(open(sys.argv[1], encoding="utf-8").readline()); h = c["prompt_head"]
sys.exit(0 if h.startswith("# Role: research\n# Stage: 05-hooks") and "# Context: this session continues" in h else 1)' "$FAKE_CLAUDE_LOG"
seed="$(ls "$RD"/05-hooks/calls/*-reseed.prompt.md | tail -n 1)"
assert_grep "^## facts.md" "$seed" "seed-if-new: the seed carries facts.md"
assert_grep "^Task: write the hooks\.$" "$seed" "seed-if-new: the task follows the seed"
sid="$(state_get "$RD" sessions.A "")"
assert_true "seed-if-new: the new session id is stored" test -n "$sid"
fake_claude_reset
out="$(FAKE_CLAUDE_MODE=ok bash pipeline/tests/session-driver.sh A research "$RD/05-hooks" "$RD/p.md" --seed-if-new --tools "" 2>&1)"
assert_eq "$(fake_field 1 resume)" "$sid" "seed-if-new: the next call resumes the stored session with the plain prompt"
assert_false "seed-if-new: no INFO line on a resumed session" grep -q "has no stored id" <<<"$out"
unset REELS_SLEEP_SCALE
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. S5 and S6 through the runner with the fake claude, from the frozen M4 outputs (then the regeneration path)"
sandbox_init --with-pipeline
fake_claude_on
make_fake_fixtures "$SANDBOX/fixtures"
export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
RD="$(seed_run)"
fast_mode
run_once "$SANDBOX/fake.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/fake.out"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0"
assert_grep "${ts_regex}START  idea 1/1 .* \(resumed at picking hooks, 3 stages done\)$" "$OUT" "START: the run seeded from the frozen outputs resumes at S5"
assert_grep "${ts_regex}INFO   session A has no stored id: starting a new one seeded with facts.md" "$OUT" "S5: no session A stored, so the first call is seeded (the reseed path)"
assert_grep "${ts_regex}STEP   picking hooks done \([0-9hms]+\) -> judging hooks$" "$OUT" "S5 done"
assert_grep "${ts_regex}INFO   S5: 14 hooks from " "$OUT" "S5: the INFO line counts the hooks"
assert_grep "${ts_regex}INFO   S5: brief.md [0-9]+ tokens" "$OUT" "S5: the INFO line measures the brief"
assert_grep "${ts_regex}INFO   S6: 14 of 14 hooks passed hookscore" "$OUT" "S6: the filter line"
assert_grep "${ts_regex}INFO   S6: hook 1 h[0-9]+ \".*\" \(.*\), hook 2 h[0-9]+ \"" "$OUT" "S6: the verdict line"
assert_grep "${ts_regex}STEP   judging hooks done \([0-9hms]+\) -> writing script$" "$OUT" "S6 done"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the run continued to the (dummy) export"
assert_not_grep "${ts_regex}ERROR" "$OUT" "no ERROR line"
assert_not_grep "${ts_regex}BLOCK" "$OUT" "no BLOCK line"
if python "$VP_PY" is-draft "$SANDBOX_M/library/profile/voice.md" 2>/dev/null; then
  assert_grep "${ts_regex}FLAG   needs review: library/profile/voice.md is still a draft" "$OUT" "FLAG: the draft voice.md is a NEEDS REVIEW flag"
fi
H="$RD/05-hooks"; J="$RD/06-judge"
assert_true "hooks.json validates" python pipeline/bin/validate-json pipeline/stages/05-hooks/schema.json "$H/hooks.json"
summary="$(hooks_rules_ok "$H/hooks.json" 12 8)"; rc=$?
assert_rc 0 $rc "hooks.json keeps the rules ($summary)"
assert_file "$H/shortlist.json" "the template shortlist is kept"
assert_file "$H/brief.md" "brief.md written"
tok="$(python "$HOOKS_PY" tokens --file "$H/brief.md" | python -c 'import json, sys; print(json.load(sys.stdin)["tokens"])')"
assert_true "brief.md is within 2000 to 3000 tokens ($tok)" test "$tok" -ge 2000 -a "$tok" -le 3000
assert_grep "^# Brief: Claude Code" "$H/brief.md" "brief.md starts with the header"
assert_grep "^- Comment keyword: TELLS" "$H/brief.md" "brief.md header names the keyword"
assert_true "judge.json validates" python pipeline/bin/validate-json pipeline/stages/06-judge/schema.json "$J/judge.json"
w="$(json_get "$J/judge.json" winner.id)"; r="$(json_get "$J/judge.json" runner_up.id)"
assert_ne "$w" "$r" "judge.json: winner ($w) and runner-up ($r) differ"
assert_true "judge.json: both are hooks of hooks.json" python -c '
import json, sys; ids = {h["id"] for h in json.load(open(sys.argv[1], encoding="utf-8"))["hooks"]}; sys.exit(0 if sys.argv[2] in ids and sys.argv[3] in ids else 1)' "$H/hooks.json" "$w" "$r"
assert_true "judge.json: reasons, two complete rankings, 12 pairwise results, nothing filtered" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(0 if d["reasons"] and len(d["rankings"]) == 2 and all(r["complete"] for r in d["rankings"]) and len(d["pairwise"]) == 12 and d["filtered_out"] == [] and d["regenerated"] is False else 1)' "$J/judge.json"
assert_ne "$(json_get "$J/labels-1.json" order)" "$(json_get "$J/labels-2.json" order)" "the two ranking calls used different shuffles"
ST="$SANDBOX/library/.hooks.stats.json"
assert_true "stats: every template of hooks.json was picked once and the winner's template won once" python -c '
import json, sys
hooks = json.load(open(sys.argv[1], encoding="utf-8"))["hooks"]; judge = json.load(open(sys.argv[2], encoding="utf-8")); st = json.load(open(sys.argv[3], encoding="utf-8"))["hooks"]
tids = {h["template_id"] for h in hooks}; wt = judge["winner"]["template_id"]
ok = all(st.get(t, {}).get("picked") == 1 for t in tids) and st[wt]["won"] == 1 and all(st[t].get("scores") for t in tids)
sys.exit(0 if ok else 1)' "$H/hooks.json" "$J/judge.json" "$ST"
# the fake's log: the index call, the seeded hooks call, the brief in the same session, three fresh judge calls
assert_eq "$(fake_calls)" "6" "6 model calls: index, hooks, brief, two rankings, the pairwise comparison"
assert_eq "$(fake_field 1 role),$(fake_field 2 role),$(fake_field 3 role),$(fake_field 4 role),$(fake_field 5 role),$(fake_field 6 role)" "indexer,research,research,judge,judge,judge" "the roles in order"
assert_eq "$(fake_field 2 resume)" "" "the hooks call starts a new session (seeded)"
sid="$(python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig")).get("session_id", ""))' "$(ls "$H"/calls/*-hooks-try1.json | head -n 1)")"
assert_eq "$(fake_field 3 resume)" "$sid" "the brief call resumes the hooks call's session (session A)"
assert_eq "$(fake_field 4 resume),$(fake_field 5 resume),$(fake_field 6 resume)" ",," "the three judge calls are fresh sessions"
assert_eq "$(fake_field 4 model)" "$(json_get "$REPO_DIR/config.json" models.judge.model)" "the judge model from config"
assert_eq "$(fake_field 2 tools),$(fake_field 4 tools)" '[""],[""]' "no tools for the hooks and judge calls"
no_emdash_in "no em dash in the stage files" "$H/hooks.json" "$H/brief.md" "$J/judge.json" "$SANDBOX/logs/runner.log" "$ST"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "ideas.txt: the idea is gone after the export"

# the regeneration path: only 3 of 12 hooks pass hookscore, S5 regenerates once, the judge continues
make_fake_fixtures "$SANDBOX/fixtures" "$FAKE_M5_REGEN"
fake_claude_reset
RD2="$(seed_run)"
run_once "$SANDBOX/regen.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/regen.out"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "regeneration: the runner exits 0"
assert_grep "${ts_regex}WARN   S6: only 3 of 12 hooks passed hookscore \(min 50, no dealbreaker\): asking S5 to regenerate once$" "$OUT" "regeneration: the WARN line"
assert_grep "${ts_regex}INFO   S5: regenerating hooks for the judge \(3 passed the filter, " "$OUT" "regeneration: S5 announces the regeneration"
assert_grep "${ts_regex}INFO   S5: hooks regenerated: 13 hooks from " "$OUT" "regeneration: 3 survivors plus 10 replacements"
assert_grep "${ts_regex}INFO   S6: 13 of 13 hooks passed hookscore" "$OUT" "regeneration: the judge re-scored the new file"
assert_grep "${ts_regex}DONE   exported #2 -> exports/2/" "$OUT" "regeneration: the run continued to the export"
assert_not_grep "${ts_regex}ERROR" "$OUT" "regeneration: no ERROR line"
H2="$RD2/05-hooks"; J2="$RD2/06-judge"
assert_file "$J2/regenerated.json" "regeneration: the marker file (so a rerun never regenerates twice)"
assert_file "$H2/hooks-before-regenerate.json" "regeneration: the previous hooks.json is kept"
assert_eq "$(json_get "$H2/hooks.json" regenerated),$(json_len "$H2/hooks.json" hooks)" "true,13" "regeneration: hooks.json says regenerated with 13 hooks"
assert_true "regeneration: hooks.json still validates" python pipeline/bin/validate-json pipeline/stages/05-hooks/schema.json "$H2/hooks.json"
assert_eq "$(json_get "$J2/judge.json" regenerated)" "true" "regeneration: judge.json records it"
assert_ne "$(json_get "$J2/judge.json" winner.id)" "$(json_get "$J2/judge.json" runner_up.id)" "regeneration: a winner and a runner-up"
assert_eq "$(fake_calls)" "6" "regeneration: 6 calls (hooks, brief, the regeneration in session A, two rankings, pairwise; the index was up to date)"
assert_eq "$(fake_field 3 role)" "research" "regeneration: the third call is S5's regeneration (research model)"
assert_eq "$(fake_field 3 resume)" "$(fake_field 2 resume)" "regeneration: it resumes session A"
assert_true "regeneration: the prompt carries the failures with the filter's reasons" grep -q "score .* under 50" "$H2/prompt-regenerate.md"
unset FAKE_CLAUDE_FIXTURES
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. index-hooks over the real library/hooks.txt with the real indexer model"
sandbox_init
fake_claude_off
started="$EPOCHSECONDS"
out="$(bash pipeline/bin/index-hooks 2>&1)"; rc=$?
printf '    %s (%ss)\n' "$(printf '%s' "$out" | tail -n 1)" "$((EPOCHSECONDS - started))"
assert_rc 0 $rc "index-hooks exits 0 with the real indexer"
IDX="$SANDBOX/library/.hooks.index.json"; LINT="$SANDBOX/library/hooks.lint.txt"
assert_file "$IDX" "library/.hooks.index.json written"
parsed="$(python "$HOOKS_PY" parse --file "$SANDBOX_M/library/hooks.txt")"
n_unique="$(printf '%s' "$parsed" | python -c 'import json, sys; print(len({e["id"] for e in json.load(sys.stdin)}))')"
assert_eq "$(json_get "$IDX" counts.total)" "$n_unique" "one entry per unique hook line ($n_unique)"
assert_true "every entry has id, family (one of the six), fits_problem_solution (boolean) and blanks" python -c '
import json, re, sys
fams = {"tools-listicle", "how-to-system", "mistake-warning", "myth-contrarian", "story-confession", "transformation"}
d = json.load(open(sys.argv[1], encoding="utf-8")); hs = d["hooks"]
bad = [h for h in hs if not (re.match(r"^[0-9a-f]{10}$", h["id"]) and h["family"] in fams and isinstance(h["fits_problem_solution"], bool) and isinstance(h["blanks"], int))]
print("    families: " + str(d["counts"]["by_family"]) + "; unclassified " + str(d["counts"]["unclassified"]) + "; fit " + str(sum(1 for h in hs if h["fits_problem_solution"])) + " of " + str(len(hs)))
sys.exit(1 if bad else 0)' "$IDX"
assert_true "at least 3 families are used" test "$(json_get "$IDX" counts.by_family | python -c 'import json, sys; print(len([k for k, v in json.load(sys.stdin).items() if v and k != "unclassified"]))')" -ge 3
assert_true "the lint names every broken-blank line and every em-dash line of the user's file" python - "$LINT" "$parsed" <<'EOF'
import json, sys
lint = open(sys.argv[1], encoding="utf-8").read()
entries = json.loads(sys.argv[2])
missing = []
for e in entries:
    if e["broken_blank"] and f"line {e['line']}: broken blank" not in lint: missing.append(("broken", e["line"]))
    if e["em_dash"] and f"line {e['line']}: em dash" not in lint: missing.append(("em dash", e["line"]))
print("    lint lines: " + ", ".join(l.split(":")[0] + ":" + l.split(":")[1] for l in lint.splitlines() if l.startswith("line ")))
sys.exit(1 if missing else 0)
EOF
fake_claude_on
fake_claude_reset
out="$(FAKE_CLAUDE_MODE=error bash pipeline/bin/index-hooks 2>&1)"; rc=$?
assert_rc 0 $rc "a second run with no change exits 0"
assert_eq "$(fake_calls)" "0" "a second run with no change makes no model call"
assert_true "the second run says the index is up to date" grep -q "up to date" <<<"$out"
fake_claude_off
no_emdash_in "no em dash in the index and the stats" "$IDX" "$SANDBOX/library/.hooks.stats.json"
fi

# ----------------------------------------------------------------------------------------------------------------
if want 4; then
section "4. S5 and S6 on the frozen M4 outputs with the real models (several minutes)"
sandbox_init --with-pipeline
fake_claude_off
RD="$(seed_run)"
started="$EPOCHSECONDS"
run_once "$SANDBOX/real.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/real.out"
printf 'real run took %ss, kept at %s\n' "$((EPOCHSECONDS - started))" "$RD"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0"
assert_grep "${ts_regex}INFO   session A has no stored id: starting a new one seeded with facts.md" "$OUT" "S5: the seeded session (no session A in the frozen state)"
assert_grep "${ts_regex}STEP   picking hooks done \([0-9hms]+\) -> judging hooks$" "$OUT" "S5 done"
assert_grep "${ts_regex}STEP   judging hooks done \([0-9hms]+\) -> writing script$" "$OUT" "S6 done"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the run continued to the (dummy) export"
assert_not_grep "${ts_regex}ERROR" "$OUT" "no ERROR line"
assert_not_grep "${ts_regex}BLOCK" "$OUT" "no BLOCK line"
H="$RD/05-hooks"; J="$RD/06-judge"
assert_true "hooks.json validates against schema.json" python pipeline/bin/validate-json pipeline/stages/05-hooks/schema.json "$H/hooks.json"
wpm="$(json_get "$H/hooks.json" wpm 150)"; cap="$(json_get "$H/hooks.json" max_spoken_words 7)"
summary="$(hooks_rules_ok "$H/hooks.json" 12 "$cap")"; rc=$?
assert_rc 0 $rc "hooks.json: 12 to 20 hooks from 3 families or more, spoken $cap words or fewer and under 3 s at $wpm wpm, on-screen 6 or fewer, a marker in every spoken line ($summary)"
assert_eq "$(json_get "$H/hooks.json" rule_errors)" "[]" "hooks.json: every rule held (no forced write)"
python -c '
import json, sys
for h in json.load(open(sys.argv[1], encoding="utf-8"))["hooks"]:
    print("    " + h["id"] + " [" + h["family"] + ", " + h["template_source"] + " " + h["template_id"] + "] " + h["spoken"] + "  |  " + h["on_screen"] + "  |  " + h["marker"] + " (" + h["marker_kind"] + ")")' "$H/hooks.json"
assert_true "hooks.json: at least one template from the user's hooks.txt and one vendor shape" python -c '
import json, sys; s = {h["template_source"] for h in json.load(open(sys.argv[1], encoding="utf-8"))["hooks"]}; sys.exit(0 if {"library", "vendor"} <= s else 1)' "$H/hooks.json"
assert_file "$H/brief.md" "brief.md written"
tok="$(python "$HOOKS_PY" tokens --file "$H/brief.md" | python -c 'import json, sys; print(json.load(sys.stdin)["tokens"])')"
assert_true "brief.md is within 2000 to 3000 tokens ($tok)" test "$tok" -ge 2000 -a "$tok" -le 3000
assert_grep "facts.md#[0-9]+" "$H/brief.md" "brief.md cites claims by number"
assert_true "judge.json validates against schema.json" python pipeline/bin/validate-json pipeline/stages/06-judge/schema.json "$J/judge.json"
w="$(json_get "$J/judge.json" winner.id)"; r="$(json_get "$J/judge.json" runner_up.id)"
assert_ne "$w" "$r" "judge.json: a winner ($w) and a different runner-up ($r)"
printf '    hook 1: %s | %s\n    hook 2: %s | %s\n' "$(json_get "$J/judge.json" winner.spoken)" "$(json_get "$J/judge.json" winner.on_screen)" "$(json_get "$J/judge.json" runner_up.spoken)" "$(json_get "$J/judge.json" runner_up.on_screen)"
python -c 'import json, sys; [print("    reason: " + r) for r in json.load(open(sys.argv[1], encoding="utf-8"))["reasons"][:4]]' "$J/judge.json"
assert_true "judge.json: reasons, two rankings, the pairwise results" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if len(d["reasons"]) >= 1 and len(d["rankings"]) == 2 and len(d["pairwise"]) >= 6 and d["calls"] == 3 else 1)' "$J/judge.json"
printf '    hookscore: %s passed of %s; filtered out: %s
' "$(json_len "$J/judge.json" candidates)" "$(json_len "$H/hooks.json" hooks)" "$(json_get "$J/judge.json" filtered_out | python -c 'import json, sys; print(", ".join(d["id"] + " (" + str(d["score"]) + ")" for d in json.load(sys.stdin)) or "none")')"
ST="$SANDBOX/library/.hooks.stats.json"
assert_true "stats: the picks and the win are recorded" python -c '
import json, sys
hooks = json.load(open(sys.argv[1], encoding="utf-8"))["hooks"]; judge = json.load(open(sys.argv[2], encoding="utf-8")); st = json.load(open(sys.argv[3], encoding="utf-8"))["hooks"]
tids = {h["template_id"] for h in hooks}; wt = judge["winner"]["template_id"]
sys.exit(0 if all(st.get(t, {}).get("picked", 0) >= 1 for t in tids) and st[wt]["won"] >= 1 else 1)' "$H/hooks.json" "$J/judge.json" "$ST"
first_call="$(ls "$H"/calls/*-hooks-try1.json | head -n 1)"
assert_true "S5: the first call's prompt was the seeded one" grep -q "^## facts.md" "$(ls "$H"/calls/*-reseed.prompt.md | head -n 1)"
sid="$(python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig")).get("session_id", ""))' "$first_call")"
assert_grep "^resume: $sid$" "$(ls "$H"/calls/*-brief-try1.meta | head -n 1)" "S5: the brief resumed the hooks call's session (session A)"
assert_grep "^resume: $" "$J/calls/001-rank-1.meta" "S6: the first ranking ran in a fresh session"
assert_grep "^resume: $" "$J/calls/002-rank-2.meta" "S6: the second ranking ran in a fresh session"
no_emdash_in "no em dash in the stage files" "$H/hooks.json" "$H/brief.md" "$J/judge.json" "$SANDBOX/logs/runner.log" "$ST"
if [ -n "${M5_FREEZE:-}" ] && [ "$rc" = 0 ]; then
  for st in 05-hooks 06-judge; do
    rm -rf "$FROZEN/$st"; mkdir -p "$FROZEN/$st/calls"
    ( cd "$RD/$st" && find . -maxdepth 1 -type f \( -name '*.json' -o -name '*.md' \) ! -name 'prompt-*' ! -name 'error.json' ! -name 'result.json' -exec cp {} "$FROZEN/$st/" \; )
    cp "$RD/$st"/calls/*.out.json "$FROZEN/$st/calls/" 2>/dev/null || true
  done
  python - "$FROZEN" <<'PYEOF'
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "pipeline", "lib"))
from errors import undash
def clean(x):
    if isinstance(x, str): return undash(x)
    if isinstance(x, list): return [clean(v) for v in x]
    if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
    return x
em = bytes([0xE2, 0x80, 0x94])
for st in ("05-hooks", "06-judge"):
    for dp, _, names in os.walk(os.path.join(sys.argv[1], st)):
        for name in names:
            path = os.path.join(dp, name)
            data = open(path, "rb").read()
            if em not in data:
                continue
            if name.endswith(".json"):
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    json.dump(clean(json.loads(data.decode("utf-8-sig"))), fh, ensure_ascii=False, indent=1); fh.write("\n")
            else:
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(undash(data.decode("utf-8-sig")))
PYEOF
  printf 'frozen 05-hooks and 06-judge outputs added by M5_FREEZE=1 bash pipeline/tests/test-m5.sh on %s from %s\n' "$(date '+%Y-%m-%d %H:%M')" "$(basename "$RD")" >> "$FROZEN/README.txt"
  pass "frozen: 05-hooks and 06-judge copied to pipeline/tests/fixtures/runs/test-idea/"
fi
fi

test_summary
