#!/usr/bin/env bash
# test-models.sh: the [important] label and the model choice (DECISIONS.md 333 to 335). No model call, about 1 minute.
#   1. the label in the queue: ideas.py reads [important] at the start or the end of a block, the text and the id leave it
#      out, add-idea.sh says "marked important", the runner's remove still finds the block
#   2. the label in the run: state.py new keeps idea.important and strips the label from the text and idea.txt
#   3. the model choice: config models.<role>, models.<role>.important on an idea marked important, never fable otherwise
#      (even with fable written into a base role), the visual director's design, fine tuning and escalation
#   4. ai() end to end with a stand-in claude: the models it is really called with, on a normal and an important run
#   5. the review loop's routing labels (route.py) on a normal and an important run
#   6. config.json: fable appears only under "important", every role the code calls has a model
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
TEST_NAME="test-models"
MC="$REPO_DIR/pipeline/lib/model_choice.py"
W="$(mktemp -d)"; WM="$(mixed "$W")"
trap 'rm -rf "$W"; tests_cleanup' EXIT
jget() { python -c 'import json, sys
cur = json.loads(sys.argv[1])
for p in sys.argv[2].split("."):
    cur = cur[int(p)] if isinstance(cur, list) else cur[p]
print(("true" if cur else "false") if isinstance(cur, bool) else cur)' "$1" "$2"; }

section "1. the label in the queue"
Q="$W/q"; mkdir -p "$Q/logs"
printf '{[important] Claude Code skills that save an hour}\n{A plain idea}\n{Another one [IMPORTANT]}\n{An [important] word inside}\n' > "$Q/ideas.txt"
list="$(python pipeline/lib/ideas.py list --file "$Q/ideas.txt")"
assert_eq "$(jget "$list" 0.important)|$(jget "$list" 0.text)" "true|Claude Code skills that save an hour" "a leading [important] marks the idea and leaves the text"
assert_eq "$(jget "$list" 1.important)" "false" "an idea without the label is not important"
assert_eq "$(jget "$list" 2.important)|$(jget "$list" 2.text)" "true|Another one" "a trailing [IMPORTANT] (any case) marks it too"
assert_eq "$(jget "$list" 3.important)" "false" "the word inside the text is not the label"
assert_eq "$(jget "$list" 0.id)" "$(printf 'Claude Code skills that save an hour' | python pipeline/lib/ideas.py id)" "the id leaves the label out (the same idea with or without it)"
assert_eq "$(printf '{[important] Claude Code skills that save an hour}' | python pipeline/lib/ideas.py id)" "$(jget "$list" 0.id)" "ideas.py id strips the label too"
first="$(python pipeline/lib/ideas.py first --file "$Q/ideas.txt")"
assert_eq "$(jget "$first" important)|$(jget "$first" raw)" "true|[important] Claude Code skills that save an hour" "first: the row carries important and the raw block keeps the label"
out="$(REELS_ROOT="$(mixed "$Q")" REELS_IDEAS="$(mixed "$Q/ideas.txt")" bash pipeline/bin/add-idea.sh "{[important] A new labelled idea}" 2>&1)"
assert_eq "$out" "added 1 idea to ideas.txt (queue: 5), marked important" "add-idea.sh says the idea is marked important"
out="$(REELS_ROOT="$(mixed "$Q")" REELS_IDEAS="$(mixed "$Q/ideas.txt")" bash pipeline/bin/add-idea.sh "{one} {[important] two} {three [important]}" 2>&1)"
assert_eq "$out" "added 3 ideas to ideas.txt (queue: 8), 2 marked important" "add-idea.sh counts the labelled ideas"
assert_grep "^\{\[important\] A new labelled idea\}$" "$Q/ideas.txt" "the file keeps the label"
out="$(REELS_ROOT="$(mixed "$Q")" REELS_IDEAS="$(mixed "$Q/ideas.txt")" bash pipeline/bin/add-idea.sh "{plain}" 2>&1)"
assert_eq "$out" "added 1 idea to ideas.txt (queue: 9)" "an unlabelled idea: the line is the same as before"
id0="$(jget "$list" 0.id)"
python pipeline/lib/ideas.py remove --file "$Q/ideas.txt" --root "$(mixed "$Q")" --id "$id0" >/dev/null 2>&1
assert_not_grep "Claude Code skills that save an hour" "$Q/ideas.txt" "remove by the id finds the labelled block and removes it whole"
assert_grep "^\{A plain idea\}$" "$Q/ideas.txt" "the other ideas stay"

section "2. the label in the run"
R="$W/runs"; mkdir -p "$R"
created="$(printf '[important] Claude Code skills that save an hour' | python pipeline/lib/state.py new --runs "$(mixed "$R")" --id "$id0")"
RD="$(jget "$created" run_dir)"
assert_eq "$(python pipeline/lib/state.py get "$RD" idea.important)" "true" "state.json: idea.important is true"
assert_eq "$(python pipeline/lib/state.py get "$RD" idea.text)" "Claude Code skills that save an hour" "state.json: the text has no label (the stages never see it)"
assert_eq "$(tr -d '\r' < "$RD/idea.txt")" "Claude Code skills that save an hour" "idea.txt has no label"
assert_eq "$(jget "$(python pipeline/lib/state.py summary "$RD")" idea_important)" "true" "the summary (the runner's START line) says important"
created2="$(printf 'A plain idea' | python pipeline/lib/state.py new --runs "$(mixed "$R")" --id abc)"
RD2="$(jget "$created2" run_dir)"
assert_eq "$(python pipeline/lib/state.py get "$RD2" idea.important)" "false" "an unlabelled idea: idea.important is false"
assert_eq "$(python "$MC" important --run-dir "$RD")|$(python "$MC" important --run-dir "$RD2")|$(python "$MC" important --run-dir "$W/nowhere")" "true|false|false" "model_choice reads the label from state.json (no run: not important)"

section "3. the model choice"
res() { python "$MC" resolve "$1" --config "${3:-config.json}" ${2:+--run-dir "$2"}; }
assert_eq "$(res visual_director_escalation "$RD2")" "opus xhigh" "normal idea: the escalated director is opus"
assert_eq "$(res visual_director_escalation "$RD")" "fable xhigh" "important idea: the escalated director is fable"
assert_eq "$(res builder_escalation "$RD2")|$(res reviewer_escalation "$RD2")" "opus xhigh|opus xhigh" "normal idea: the builder and reviewer escalations are opus"
assert_eq "$(res builder_escalation "$RD")|$(res reviewer_escalation "$RD")" "fable xhigh|fable xhigh" "important idea: the builder and reviewer escalations are fable"
assert_eq "$(res visual_director_escalation)" "opus xhigh" "no run (a tool outside the runner): never fable"
for role in research script judge gate visual_director_fix builder reviewer cut checks fixer; do
  assert_eq "$(res "$role" "$RD2" | cut -d' ' -f1)|$(res "$role" "$RD" | cut -d' ' -f1)" "sonnet|sonnet" "$role is sonnet on both"
done
assert_eq "$(res visual_director "$RD2")|$(res visual_director "$RD")" "opus high|opus high" "the first plan (the design) is opus on both"
python - "$WM/fable-base.json" <<'EOF'
import json, sys
c = json.load(open("config.json", encoding="utf-8"))
c["models"]["script"] = {"model": "fable", "effort": "high"}
c["models"]["judge"] = {"model": "claude-fable-5-1", "effort": "low"}
json.dump(c, open(sys.argv[1], "w", encoding="utf-8"))
EOF
assert_eq "$(res script "$RD2" "$WM/fable-base.json")|$(res judge "$RD2" "$WM/fable-base.json")" "opus high|opus low" "fable written into a base role: a normal idea still never runs it (opus, the role's effort)"
assert_eq "$(res script "$RD" "$WM/fable-base.json")" "fable high" "... an important idea does"
assert_rc 1 "$(res no_such_role "$RD2" >/dev/null 2>&1; echo $?)" "an unknown role is an error"
got=""; for n in 0 1 2 3 4; do got="$got$(python "$MC" director-role "$n" --config config.json) "; done
assert_eq "$got" "visual_director visual_director_fix visual_director_fix visual_director_escalation visual_director_escalation " "the director: design, fine tuning after rounds 1 and 2, escalation from round 3"

section "4. ai() with a stand-in claude"
cat > "$W/claude" <<'EOF'
#!/usr/bin/env bash
m=""; e=""; while [ $# -gt 0 ]; do case "$1" in --model) m="$2" ;; --effort) e="$2" ;; esac; shift; done
cat >/dev/null
echo "$m $e" >> "$(dirname "$0")/models.log"
printf '{"type":"result","subtype":"success","is_error":false,"result":"ok from %s","session_id":"s1"}\n' "$m"
EOF
chmod +x "$W/claude"; printf 'hi\n' > "$W/p.md"
call() {  # call ROLE RUN_DIR -> "rc|class|result" of one ai() call from RUN_DIR/10-build
  mkdir -p "$2/10-build"
  REELS_ROOT="$WM" REELS_CLAUDE="$W/claude" bash -c 'source pipeline/lib/common.sh; source pipeline/lib/log.sh; source pipeline/lib/config.sh; source pipeline/lib/state.sh; source pipeline/lib/status.sh; source pipeline/lib/ai.sh
ai "$1" "$2/10-build" "$3" --no-protect >/dev/null 2>&1; echo "$?|$AI_CLASS|$AI_RESULT"' _ "$1" "$2" "$WM/p.md" 2>/dev/null | tail -n 1
}
: > "$W/models.log"
for role in visual_director visual_director_fix visual_director_escalation builder_escalation reviewer_escalation script research; do call "$role" "$RD2" >/dev/null; done
assert_eq "$(paste -sd, "$W/models.log")" "opus high,sonnet high,opus xhigh,opus xhigh,opus xhigh,sonnet high,sonnet high" "normal idea: the CLI is called with these models and efforts"
assert_not_grep "fable" "$W/models.log" "normal idea: fable is never on a command line"
: > "$W/models.log"
for role in visual_director visual_director_fix visual_director_escalation builder_escalation reviewer_escalation script; do call "$role" "$RD" >/dev/null; done
assert_eq "$(paste -sd, "$W/models.log")" "opus high,sonnet high,fable xhigh,fable xhigh,fable xhigh,sonnet high" "important idea: only the escalations use fable"
assert_eq "$(call visual_director_escalation "$RD")" "0|ok|ok from fable" "important idea: the escalated call answers"
assert_eq "$(call no_such_role "$RD2" | cut -d'|' -f1,2)" "1|error" "ai(): an unknown role is a code error, as before"
ai_name="$(REELS_ROOT="$WM" bash -c 'source pipeline/lib/common.sh; source pipeline/lib/log.sh; source pipeline/lib/config.sh; source pipeline/lib/state.sh; source pipeline/lib/status.sh; source pipeline/lib/ai.sh
echo "$(ai_model_name reviewer_escalation "$1")|$(ai_model_name reviewer_escalation "$2")|$(ai_model_name reviewer "$1")"' _ "$RD2" "$RD" 2>/dev/null | tail -n 1)"
assert_eq "$ai_name" "opus|fable|sonnet" "ai_model_name (the terminal lines) names the model that really runs"

section "5. the review loop's routing labels"
python - "$RD2" "$RD" > "$W/route.txt" <<'EOF'
import os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from review import common as rc, route
for name, rd in (("normal", sys.argv[1]), ("important", sys.argv[2])):
    ctx = rc.Ctx(rd)
    print(name, "labels", ",".join(route.model_for_round(ctx, n)[0] for n in (2, 3, 4, 5)))
    ok = {"pass": True, "issues": []}
    low = {"scores": {k: 4 for k in route.SCORE_KEYS}, "branding_natural": True, "summary": "x",
           "issues": [{"tag": "text", "text": "the s4 chip doubles the title", "scene": "s4"}]}
    low["scores"]["hierarchy"] = 3
    r = route.decide(ctx, 3, ok, ok, ok, low)
    print(name, "activity", r["routing"]["activity"], "|", r["routing"]["next_model"][0])
    r = route.decide(ctx, 5, ok, ok, ok, low)
    print(name, "cap", r["verdict"], "|", r["flags"][0].split(";")[0])
EOF
assert_grep "^normal labels sonnet,sonnet,opus,opus$" "$W/route.txt" "normal idea: rounds 2 and 3 are fixed by sonnet, 4 and 5 escalate to opus"
assert_grep "^important labels sonnet,sonnet,fable,fable$" "$W/route.txt" "important idea: rounds 4 and 5 escalate to fable"
assert_grep "^normal activity fixing \[text\] issues \(round 4, opus\) \| opus$" "$W/route.txt" "normal idea: the activity names opus"
assert_grep "^important activity fixing \[text\] issues \(round 4, fable\) \| fable$" "$W/route.txt" "important idea: the activity names fable"
assert_grep "^normal cap cap \| edit review: still failing after 5 rounds \(3 main, 2 escalated on opus\)$" "$W/route.txt" "normal idea: the cap flag names the escalation model"
assert_grep "^important cap cap \| edit review: still failing after 5 rounds \(3 main, 2 escalated on fable\)$" "$W/route.txt" "important idea: the cap flag names fable"

section "6. config.json"
python - > "$W/cfg.txt" <<'EOF'
import json, re, glob
c = json.load(open("config.json", encoding="utf-8"))
m = c["models"]
bad = [k for k, v in m.items() if "fable" in str(v.get("model", "")).lower()]
print("base-fable", ",".join(bad) or "none")
under = sorted(k for k, v in m.items() if isinstance(v.get("important"), dict) and "fable" in str(v["important"].get("model", "")))
print("important-fable", ",".join(under))
used = set()
for f in glob.glob("pipeline/stages/*/run.sh") + glob.glob("pipeline/lib/*.sh") + glob.glob("pipeline/bin/*"):
    s = open(f, encoding="utf-8", errors="replace").read()
    used |= set(re.findall(r"(?:^|[\s(])(?:ai|session_call [A-Z]) ([a-z_]+) ", s, re.M))
used |= {"visual_director", "visual_director_fix", "visual_director_escalation", "builder", "builder_escalation", "reviewer", "reviewer_escalation"}
print("missing", ",".join(sorted(r for r in used if r not in m)) or "none")
EOF
assert_grep "^base-fable none$" "$W/cfg.txt" "no role has fable as its own model"
assert_grep "^important-fable builder_escalation,reviewer_escalation,visual_director_escalation$" "$W/cfg.txt" "fable sits only under the three escalations' important"
assert_grep "^missing none$" "$W/cfg.txt" "every role the code calls has a model in config.json"

test_summary
