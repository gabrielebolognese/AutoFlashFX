#!/usr/bin/env bash
# test-m12.sh: acceptance test for M12 (Final render S13, caption and export S14, end to end; the problem-first solution
# choice retrofitted into S1 to S4 and S7; BUILD_SPEC.md section 12 and PLAN.md M12).
#   bash pipeline/tests/test-m12.sh                       every section (section 4 runs the whole pipeline with the real
#                                                         models and the real engine on the test idea: 1 to 3 hours)
#   M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh  the fake-only sections (about 12 minutes, two renders)
#   M12_FREEZE=1 bash pipeline/tests/test-m12.sh          section 4 also copies the M12 outputs of the real run into
#                                                         pipeline/tests/fixtures/runs/test-idea/ (solution.json,
#                                                         render.json, export.json, caption.txt)
#   M12_TIMEOUT=<seconds>                                 the real run's time limit (default 14400)
# Sections:
#   1. units: solution.py (the type, the SOLUTION block, the balance, the proof lines, the FlashFX rules), the
#      expansion's decision and keyword rule, the gate's honesty check H, the script's solution checks, the history
#      line with the solution field, S13's checks on the golden render, the caption composer, the dummies and schemas
#   2. S13 and S14 through the runner on the frozen build (S11 real, S12 dummy, the fake caption model): exports/1 with
#      every ffprobe check, the captions file in the spec's format, the history line, the idea gone
#   3. the honesty loop with the fake claude: a forced FlashFX solution fails H, S4 decides the skill, the gate passes
#      on round 2 and the run reaches the export (dummy stages after S4), never a drop
#   4. the test idea end to end with the real models and the real engine: exports/flashfx-1/flashfx-1.mp4, 1captions.txt, 1hook2.mp4
#   5. no em dash in the files M12 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M12_SECTIONS:-1 2 3 4 5}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
VALIDATE="$REPO_DIR/pipeline/bin/validate-json"
FROZEN="$FIXTURES/runs/test-idea"
FAKE_M12="$FIXTURES/fake/m12"
FAKE_M4="$FIXTURES/fake/m4"
FAKES="$REPO_DIR/pipeline/tests/fakes"
VENDOR="$REPO_DIR/pipeline/vendor/ig-agent-skill"
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
SFX_DIR_REAL="$(mixed "$REPO_DIR/channels/flashfx/styles/sfx")"
export REELS_SFX_DIR="$SFX_DIR_REAL" REELS_SFX_NO_BUILD=1
export PYTHONUTF8=1
TEST_IDEA="$(tr -d '\r' < "$FROZEN/idea.txt")"

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
jf() { python -c 'import json, sys; d = json.loads(sys.argv[1]); v = d.get(sys.argv[2], ""); print(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict, bool)) else v)' "$1" "$2"; }
state_get() { python "$STATE_PY" get "$@"; }
run_dirs() { ls -d "$SANDBOX"/channels/flashfx/runs/*/ 2>/dev/null | sed 's|/$||'; }
first_run() { run_dirs | head -n 1; }
run_once() {  # run_once <outfile> <timeout> [env...]: the sandbox's own run.sh
  local out="$1" to="$2"; shift 2
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout "$to" bash "$SANDBOX/run.sh" --once ) > "$out" 2>&1
}
event_tags() {  # the event lines' tags in order, comma separated
  grep -E "$ts_regex" "$1" | awk '{print $2}' | grep -v -E '^(REEL|INFO|QUEUE|READY|WARN|IDLE|FLAG|START|NEXT)$' | paste -sd,
}
fake_calls() { python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG" 2>/dev/null || echo 0; }
fake_field() {  # fake_field <call n> <key>
  python -c 'import json, sys
calls = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
v = calls[int(sys.argv[2]) - 1].get(sys.argv[3])
print(json.dumps(v) if isinstance(v, (list, dict, bool)) else ("" if v is None else v))' "$FAKE_CLAUDE_LOG" "$1" "$2"
}
no_emdash_in() {  # no_emdash_in <name> <file>...
  local name="$1"; shift
  if python -c 'import sys
bad = [p for p in sys.argv[1:] if open(p, "rb").read().find(bytes([0xE2, 0x80, 0x94])) >= 0]
print("\n".join(bad)); sys.exit(1 if bad else 0)' "$@" >/tmp/m12-emdash.txt; then pass "$name"; else fail "$name (em dash in: $(tr '\n' ' ' </tmp/m12-emdash.txt))"; fi
}
seed_run() {  # a run in the sandbox with S1 to S10 done from the frozen outputs, the projects rebuilt; prints the run dir
  local raw id created rd st
  raw="$TEST_IDEA"
  printf '{%s}\n' "$raw" > "$SANDBOX/channels/flashfx/ideas.txt"
  id="$(printf '%s' "$raw" | python pipeline/lib/ideas.py id)"
  created="$(printf '%s' "$raw" | python "$STATE_PY" new --runs "$SANDBOX_M/channels/flashfx/runs" --id "$id")"
  rd="$(jf "$created" run_dir)"
  for st in 01-research 02-expansion 03-gate 05-hooks 06-judge 07-script 08-voiceover 09a-animations 09b-text 09c-transitions 10-build; do
    cp -r "$FROZEN/$st/." "$rd/$st/"
    python "$STATE_PY" stage-start "$rd" "$st" >/dev/null
    python "$STATE_PY" stage-done "$rd" "$st" --schemas "$REPO_DIR/pipeline/stages" >/dev/null \
      || printf 'seed_run: the frozen %s did not validate\n' "$st" >&2
  done
  python pipeline/tests/materialize-project.py "$rd" --render-missing >"$rd/materialize.log" 2>&1 || printf 'seed_run: materialize failed (see %s/materialize.log)\n' "$rd" >&2
  printf '%s' "$rd"
}
captions_sections() {  # the section headings of a captions file, in order
  grep -E '^(CAPTION|HASHTAGS|COMMENT KEYWORD|SOLUTION|HOOKS|NEEDS REVIEW|FACTS AND SOURCES|RUN)$' "$1" | paste -sd,
}
caption_text() {  # the CAPTION block of a captions file (up to the blank line before HASHTAGS), for the vendor lint
  python -c 'import sys
t = open(sys.argv[1], encoding="utf-8").read().replace("\r\n", "\n")
body = t.split("\nHASHTAGS\n", 1)[0].split("CAPTION\n", 1)[1]
tags = t.split("\nHASHTAGS\n", 1)[1].split("\n", 1)[0]
sys.stdout.write(body.rstrip() + "\n\n" + tags + "\n")' "$1"
}
check_export() {  # check_export <sandbox exports dir> <N> <run dir> <label>: the acceptance checks on exports/N
  local E="$1" n="$2" rd="$3" lbl="$4" cap="$1/flashfx-$2/flashfx-${2}captions.txt" res first hook1
  assert_file "$E/flashfx-$n/flashfx-$n.mp4" "$lbl: exports/flashfx-$n/flashfx-$n.mp4"
  assert_file "$cap" "$lbl: exports/flashfx-$n/flashfx-${n}captions.txt"
  assert_file "$E/flashfx-$n/flashfx-${n}hook2.mp4" "$lbl: exports/flashfx-$n/flashfx-${n}hook2.mp4"
  res="$(python pipeline/lib/finalrender.py check --file "$E/flashfx-$n/flashfx-$n.mp4" --voice "$rd/08-voiceover/vo.wav" --config "$(resolved_config)")"
  assert_eq "$(jf "$res" pass)" "true" "$lbl: $n.mp4 passes every ffprobe and loudness check (1080x1920, 30 fps, h264 High, yuv420p, aac 48 kHz, the voice's length, -14 LUFS) [$(jf "$res" failing)]"
  python -c 'import json, sys
d = json.loads(sys.argv[1])["checks"]
print("   ", {k: d[k]["got"] for k in ("width", "height", "fps", "video_codec", "profile", "pix_fmt", "audio_codec", "sample_rate", "duration")}, "loudness", d["loudness"]["lufs"], "LUFS", d["loudness"]["true_peak_dbtp"], "dBTP")' "$res"
  res="$(python pipeline/lib/finalrender.py check --file "$E/flashfx-$n/flashfx-${n}hook2.mp4" --hook2 --config "$(resolved_config)")"
  assert_eq "$(jf "$res" pass)" "true" "$lbl: ${n}hook2.mp4 is 3.5 s or shorter with audio, 1080x1920, aac 48 kHz [$(jf "$res" failing)]"
  assert_eq "$(captions_sections "$cap")" "$(if grep -q '^NEEDS REVIEW$' "$cap"; then echo "CAPTION,HASHTAGS,COMMENT KEYWORD,SOLUTION,HOOKS,NEEDS REVIEW,FACTS AND SOURCES,RUN"; else echo "CAPTION,HASHTAGS,COMMENT KEYWORD,SOLUTION,HOOKS,FACTS AND SOURCES,RUN"; fi)" "$lbl: the captions file has the sections of spec section 8 in order, SOLUTION included"
  first="$(sed -n 2p "$cap")"
  hook1="$(json_get "$rd/07-script/script.json" hook.spoken)"
  assert_eq "$first" "$hook1" "$lbl: the caption's first line is hook 1"
  assert_true "$lbl: the first line is 125 characters or fewer (${#first})" test "${#first}" -le 125
  assert_true "$lbl: HASHTAGS has 1 to 5 tags" python -c 'import sys
t = open(sys.argv[1], encoding="utf-8").read().split("\nHASHTAGS\n", 1)[1].split("\n", 1)[0].split()
sys.exit(0 if 1 <= len(t) <= 5 and all(x.startswith("#") for x in t) else 1)' "$cap"
  assert_grep "^SOLUTION$" "$cap" "$lbl: the SOLUTION block"
  assert_grep "^(flashfx|external: .+|method.*)$" "$cap" "$lbl: the SOLUTION line reads flashfx, external: name link, or method"
  assert_grep "^flashfx-$n\.mp4 uses: \"" "$cap" "$lbl: HOOKS line with the number"
  assert_grep "^channels/flashfx/runs/$(basename "$rd")$" "$cap" "$lbl: the RUN section names the run"
  caption_text "$cap" > "$SANDBOX/lint-$n.txt"
  python "$VENDOR/caption.py" "$SANDBOX_M/lint-$n.txt" --json > "$SANDBOX/lint-$n.json" 2>/dev/null || true
  assert_eq "$(python -c 'import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); print(",".join(c["check"] for c in d["checks"] if c["status"] == "FAIL") or "none")' "$SANDBOX/lint-$n.json")" "none" "$lbl: the vendor caption.py lint reports no FAIL"
  no_emdash_in "$lbl: no em dash in the captions file" "$cap"
  assert_true "$lbl: export.json validates against 14-export/schema.json" python "$VALIDATE" pipeline/stages/14-export/schema.json "$rd/14-export/export.json"
  assert_true "$lbl: render.json validates against 13-render/schema.json" python "$VALIDATE" pipeline/stages/13-render/schema.json "$rd/13-render/render.json"
  assert_eq "$(json_get "$rd/13-render/render.json" pass)" "true" "$lbl: render.json pass"
  if [ "$(json_get "$rd/02-expansion/solution.json" type none)" != flashfx ]; then
    assert_false "$lbl: a non-FlashFX reel: script.json never mentions FlashFX" grep -q -i -E 'flash ?-?f ?x' "$rd/07-script/script.json"
    assert_false "$lbl: a non-FlashFX reel: the caption never mentions FlashFX" grep -q -i -E 'flash ?-?f ?x' "$SANDBOX/lint-$n.txt"
  fi
}

# ----------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. units: the solution module, the expansion's decision, the gate's H, the script's rules, the history line, the SOLUTION block, S13's checks, the caption composer, the dummies"
sandbox_init --with-pipeline
mkdir -p "$SANDBOX/channels/flashfx/logs"
W="$SANDBOX/w"; mkdir -p "$W"

# solution.py on the frozen run (an external solution)
RD="$SANDBOX/channels/flashfx/runs/frozen"; mkdir -p "$RD"
cp -r "$FROZEN/01-research" "$RD/"; cp -r "$FROZEN/02-expansion" "$RD/"
assert_eq "$(python pipeline/lib/solution.py type --run-dir "$RD")" "external" "solution.py type: external on the frozen run"
assert_eq "$(python pipeline/lib/solution.py block --run-dir "$RD")" "external: frontend-design, the Claude Code plugin https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design" "solution.py block: external: name link"
assert_eq "$(python pipeline/lib/solution.py type --run-dir "$SANDBOX/channels/flashfx/runs/none")" "-" "solution.py type: - without solution.json"
assert_grep "no solution decision" <(python pipeline/lib/solution.py block --run-dir "$SANDBOX/channels/flashfx/runs/none") "solution.py block without solution.json says so"
printf '2026-11-01 10:00 | idea a | external | exported 1\n2026-11-01 11:00 | idea b | - | dropped: x\n2026-11-01 12:00 | idea c | flashfx | exported 2\n2026-11-01 13:00 | idea d | method | exported 3\n' > "$SANDBOX/channels/flashfx/logs/history.txt"
bal="$(python pipeline/lib/solution.py balance --history "$SANDBOX_M/channels/flashfx/logs/history.txt")"
assert_eq "$(jf "$bal" last)" '["method", "flashfx", "external"]' "solution.py balance: the exported reels' types, newest first (dropped ideas left out)"
assert_true "solution.py balance: the text names the counts" grep -q "1 flashfx, 1 external, 1 method" <<<"$(jf "$bal" text)"
printf '# voice\n\n## Proof I can use\n\n- [FILL IN: a real number]\n- FlashFX renders a 30 s reel in under a minute on my laptop\n- 40 client reels shipped with it\n\n## The ask\n\n- x\n' > "$W/voice.md"
assert_eq "$(python pipeline/lib/solution.py proof --voice "$W/voice.md" | paste -sd '|')" "FlashFX renders a 30 s reel in under a minute on my laptop|40 client reels shipped with it" "solution.py proof: the usable lines of Proof I can use (placeholders skipped)"
# the drafts build-voice-profile writes before the user fills them (placeholders only, no Content strategy section);
# the test never reads library/profile itself: the user's filled profile is theirs (DECISIONS.md 305)
printf '# voice\n\n## Proof I can use\n\n- [FILL IN: a real number]\n- [FILL IN: a client result]\n\n## The ask\n\n- [FILL IN]\n' > "$W/voice-draft.md"
printf '# account\n\n## Who follows\n\n- [FILL IN]\n\n## Deliverables\n\n- [FILL IN]\n' > "$W/account-draft.md"
assert_eq "$(python pipeline/lib/solution.py proof --voice "$W/voice-draft.md" | grep -c .)" "0" "solution.py proof: a placeholder draft voice.md has no usable proof line"
printf '{"b3 display": "Open FlashFX and press play", "b4 spoken": "I made this reel in flash F X", "b5 display": "Sign up today", "b6 display": "a plain line"}' > "$W/texts.json"
chk="$(python pipeline/lib/solution.py check --solution "$RD/02-expansion/solution.json" --texts "$W/texts.json")"
assert_eq "$(python -c 'import json, sys; print(",".join(sorted(p["kind"] for p in json.loads(sys.argv[1])["problems"])))' "$chk")" "ad_language,flashfx_mention,flashfx_mention,made_in_flashfx" "solution.py check (external): two FlashFX mentions, one made-in, one sales phrase"
printf '{"type": "flashfx", "name": "FlashFX", "url": "https://flashfx.app"}' > "$W/sol-flash.json"
chk="$(python pipeline/lib/solution.py check --solution "$W/sol-flash.json" --texts "$W/texts.json")"
assert_eq "$(python -c 'import json, sys; print(",".join(sorted(p["kind"] for p in json.loads(sys.argv[1])["problems"])))' "$chk")" "ad_language,made_in_flashfx" "solution.py check (flashfx): the mention is allowed, made-in and the sales phrase are not"
prompt_text="$(python pipeline/lib/solution.py prompt --run-dir "$RD" --voice "$W/voice-draft.md" --account "$W/account-draft.md" --history "$SANDBOX_M/channels/flashfx/logs/history.txt" --deliverables channels/flashfx/library/profile/deliverables.txt)"
assert_true "solution.py prompt: the rules, the empty proof, the balance and the keyword rule" python -c 'import sys
t = sys.argv[1]
sys.exit(0 if all(x in t for x in ("Problem-first reels", "no Content strategy section", "Proof I can use\" is empty", "1 flashfx, 1 external, 1 method", "flashfx -> FLASH", "external -> LINK")) else 1)' "$prompt_text"

# the research's solution candidates and the expansion's decision (research.py finish, expansion.py compose)
RD2="$SANDBOX/channels/flashfx/runs/fake"; mkdir -p "$RD2/01-research"
res="$(python pipeline/lib/research.py finish --run-dir "$RD2" --model-out "$FAKE_M4/01-research.json" --today 2026-11-01 --idea-id abc --idea "$TEST_IDEA")"
assert_eq "$(jf "$res" solution_candidates)" "1" "research.py finish: the solution candidate is kept"
assert_grep "^## Solution candidates" "$RD2/01-research/facts.md" "facts.md: the Solution candidates section"
assert_grep "^- external: the frontend-design skill \(anthropics/skills\) \(https://github.com/anthropics/skills\): " "$RD2/01-research/facts.md" "facts.md: the candidate line"
assert_true "research.json with candidates validates" python "$VALIDATE" pipeline/stages/01-research/schema.json "$RD2/01-research/research.json"
assert_true "the fake research fixture validates against the model schema" python "$VALIDATE" pipeline/stages/01-research/model.schema.json "$FAKE_M4/01-research.json"
res="$(python pipeline/lib/expansion.py compose --run-dir "$RD2" --model-out "$FAKE_M4/02-expansion.json" --deliverables channels/flashfx/library/profile/deliverables.txt --written-by 02-expansion --round 0 --idea "$TEST_IDEA")"
assert_eq "$(jf "$res" ok),$(jf "$res" keyword),$(jf "$res" solution_type)" "true,LINK,external" "expansion.py: an external decision takes the keyword LINK (the model wrote SKILL)"
assert_file "$RD2/02-expansion/solution.json" "expansion.py writes 02-expansion/solution.json"
assert_eq "$(json_get "$RD2/02-expansion/solution.json" type)/$(json_get "$RD2/02-expansion/solution.json" keyword)/$(json_get "$RD2/02-expansion/solution.json" deliverable_link)" "external/LINK/https://github.com/anthropics/skills" "solution.json: type, keyword, the deliverable is the tool's link"
assert_grep "^Solution decision: external \(the frontend-design skill \(anthropics/skills\), https://github.com/anthropics/skills\): fixture" "$RD2/02-expansion/expansion.md" "expansion.md: the solution decision line"
assert_grep "^Comment keyword: LINK\. Deliverable \(existing\): the link to " "$RD2/02-expansion/expansion.md" "expansion.md: the LINK deliverable"
assert_true "expansion.json with the decision validates" python "$VALIDATE" pipeline/stages/02-expansion/schema.json "$RD2/02-expansion/expansion.json"
assert_true "the fake expansion fixtures validate against the model schema (m4 and m12)" bash -c "python '$VALIDATE' pipeline/stages/02-expansion/model.schema.json '$FAKE_M4/02-expansion.json' && python '$VALIDATE' pipeline/stages/02-expansion/model.schema.json '$FAKE_M12/02-expansion.json'"
res="$(python pipeline/lib/expansion.py compose --run-dir "$RD2" --model-out "$FAKE_M12/02-expansion.json" --deliverables channels/flashfx/library/profile/deliverables.txt --written-by 02-expansion --round 0 --idea "$TEST_IDEA")"
assert_eq "$(jf "$res" ok),$(jf "$res" keyword),$(jf "$res" solution_type)" "true,FLASH,flashfx" "expansion.py: a flashfx decision takes the keyword FLASH"
assert_grep "^Comment keyword: FLASH\. Deliverable \(existing\): access to FlashFX, the editor shown in the reel \(https://flashfx.app\)$" "$RD2/02-expansion/expansion.md" "expansion.md: FLASH with deliverables.txt's entry"
python - "$FAKE_M4/02-expansion.json" "$W/bad-url.json" "$W/method.json" "$W/no-type.json" <<'EOF'
import json, sys
base = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.loads(json.dumps(base)); b["solution_decision"]["url"] = "https://example.org/other"; json.dump(b, open(sys.argv[2], "w", encoding="utf-8"))
m = json.loads(json.dumps(base)); m["solution_decision"] = {"type": "method", "name": "copy the skill folder by hand", "url": "", "reason": "a method"}; m["keyword"] = "SKILL"; json.dump(m, open(sys.argv[3], "w", encoding="utf-8"))
n = json.loads(json.dumps(base)); n["solution_decision"] = {"type": "product", "name": "", "url": "", "reason": ""}; json.dump(n, open(sys.argv[4], "w", encoding="utf-8"))
EOF
res="$(python pipeline/lib/expansion.py compose --run-dir "$RD2" --model-out "$W/bad-url.json" --deliverables channels/flashfx/library/profile/deliverables.txt --written-by 02-expansion --round 0)"
assert_true "expansion.py: an external URL that is not a source of facts.md is refused" grep -q "is not a source of facts.md" <<<"$res"
res="$(python pipeline/lib/expansion.py compose --run-dir "$RD2" --model-out "$W/method.json" --deliverables channels/flashfx/library/profile/deliverables.txt --written-by 02-expansion --round 0)"
assert_eq "$(jf "$res" ok),$(jf "$res" keyword),$(jf "$res" solution_type),$(jf "$res" deliverable_status)" "true,SKILL,method,new" "expansion.py: a method keeps the model's keyword (NEW deliverable)"
res="$(python pipeline/lib/expansion.py compose --run-dir "$RD2" --model-out "$W/no-type.json" --deliverables channels/flashfx/library/profile/deliverables.txt --written-by 02-expansion --round 0)"
assert_true "expansion.py: an unknown type is refused" grep -q "type must be flashfx, external or method" <<<"$res"
assert_true "expansion.py: an empty reason is refused" grep -q "reason is empty" <<<"$res"
# the dummy S2 writes a solution too
mkdir -p "$SANDBOX/channels/flashfx/runs/dummy"
( cd "$SANDBOX" && REELS_DUMMY_SECONDS=0 bash "$SANDBOX/pipeline/stages/02-expansion/dummy.sh" "$SANDBOX_M/channels/flashfx/runs/dummy" ) >/dev/null 2>&1
assert_eq "$(json_get "$SANDBOX/channels/flashfx/runs/dummy/02-expansion/solution.json" type)" "external" "the dummy S2 writes an external solution.json"

# the gate's honesty check H (gate.py decide)
RD3="$SANDBOX/channels/flashfx/runs/gate"; mkdir -p "$RD3/01-research" "$RD3/02-expansion"
cp "$FROZEN/01-research/research.json" "$RD3/01-research/"
printf '{"type": "flashfx", "name": "FlashFX", "url": "https://flashfx.app", "reason": "forced", "keyword": "FLASH"}' > "$RD3/02-expansion/solution.json"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD3" --model-out "$FAKE_M12/03-gate.1.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01 --solution "$RD3/02-expansion/solution.json" --proof-count 3)"
assert_true "gate: the model's H fail is an angle round, not a drop" grep -q '"decision": "angle", "scores_text": "P3 S3 C3 F ok H fail", "failing_text": "H"' <<<"$res"
assert_true "gate: the angle hint asks to decide the solution again" grep -q '"angle_hint": "decide the solution again (the honesty check failed): the frontend-design skill' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD3" --model-out "$FAKE_M12/03-gate.2.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01 --solution "$RD3/02-expansion/solution.json" --proof-count 0)"
assert_true "gate: flashfx with no proof line fails H whatever the model said (forced)" grep -q '"decision": "angle", "scores_text": "P3 S3 C3 F ok H fail", .*"H_forced": true' <<<"$res"
assert_grep "Proof I can use" "$RD3/03-gate/gate.json" "gate.json: H_forced names the empty proof section"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD3" --model-out "$FAKE_M12/03-gate.1.json" --round 3 --angles-done 2 --cap 2 --core-status verified --today 2026-11-01 --solution "$RD3/02-expansion/solution.json" --proof-count 3)"
assert_true "gate: an H fail with no round left drops with the scores" grep -q '"decision": "drop", .*"reason": "still failing after 2 angle rounds (P3 S3 C3 F ok H fail): ' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD3" --model-out "$FAKE_M12/03-gate.2.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01 --solution "$RD3/02-expansion/solution.json" --proof-count 2)"
assert_true "gate: flashfx with proof lines and the model's H pass passes" grep -q '"decision": "pass", "scores_text": "P3 S3 C3 F ok H ok"' <<<"$res"
cp "$FROZEN/02-expansion/solution.json" "$RD3/02-expansion/solution.json"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD3" --model-out "$FAKE_M12/03-gate.2.json" --round 2 --angles-done 1 --cap 2 --core-status verified --today 2026-11-01 --solution "$RD3/02-expansion/solution.json" --proof-count 0)"
assert_true "gate: an external solution with no proof passes H (the proof matters for FlashFX only)" grep -q '"decision": "pass", "scores_text": "P3 S3 C3 F ok H ok"' <<<"$res"
res="$(python pipeline/lib/gate.py decide --run-dir "$RD3" --model-out "$FAKE_M12/03-gate.2.json" --round 1 --angles-done 0 --cap 2 --core-status verified --today 2026-11-01)"
assert_true "gate: without --solution (an older run) H comes from the model" grep -q '"decision": "pass", "scores_text": "P3 S3 C3 F ok H ok"' <<<"$res"
assert_true "gate.json validates with the H fields" python "$VALIDATE" pipeline/stages/03-gate/schema.json "$RD3/03-gate/gate.json"
assert_eq "$(json_get "$RD3/03-gate/gate.json" H)/$(json_get "$RD3/03-gate/gate.json" solution_type)" "ok/none" "gate.json: H ok, solution_type none without solution.json"
assert_true "the fake gate fixtures validate against the model schema" bash -c "for f in '$FAKE_M12/03-gate.1.json' '$FAKE_M12/03-gate.2.json' '$FAKE_M4/03-gate.json' '$FAKE_M4'/variants/*.json; do python '$VALIDATE' pipeline/stages/03-gate/model.schema.json \"\$f\" || exit 1; done"
assert_true "the fake angle fixtures validate against the model schema" bash -c "python '$VALIDATE' pipeline/stages/04-angle/model.schema.json '$FAKE_M4/04-angle.json' && python '$VALIDATE' pipeline/stages/04-angle/model.schema.json '$FAKE_M12/04-angle.json'"
assert_true "the frozen gate.json carries H" test "$(json_get "$FROZEN/03-gate/gate.json" H)" = ok

# the script's solution rules (script_checks.py)
python pipeline/lib/script_checks.py setup --config "$(REELS_ROOT="$REPO_DIR" resolved_config)" --brief "$FROZEN/05-hooks/brief.md" --judge "$FROZEN/06-judge/judge.json" --expansion "$FROZEN/02-expansion/expansion.json" \
  --voice channels/flashfx/library/profile/voice.md --tweaks channels/flashfx/styles/paper-cards/tweaks.md --style channels/flashfx/styles/paper-cards/style.md --wpm 195 --rounds 3 --solution "$FROZEN/02-expansion/solution.json" --out "$W/plan.json" >/dev/null
assert_eq "$(json_get "$W/plan.json" solution_decision.type)" "external" "script setup: the plan carries the solution decision"
assert_grep "Never mention FlashFX" <(json_get "$W/plan.json" solution_rules) "script setup: the rules text for an external solution"
cp "$FROZEN/07-script/draft-a.r2.json" "$W/clean.json"
res="$(python pipeline/lib/script_checks.py check --draft "$W/clean.json" --plan "$W/plan.json" --vendor "$VENDOR" --out "$W/rep-clean.json")"
assert_eq "$(jf "$res" ok)" "true" "script check: the frozen draft passes every check with the solution rules"
python - "$W/clean.json" "$W/planted.json" "$W/made.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
p = json.loads(json.dumps(d)); p["beats"][3]["display"] = "It's not your fault. I fixed mine in FlashFX in five minutes."; p["beats"][3]["spoken"] = "It's not your fault. I fixed mine in flash F X in five minutes."
json.dump(p, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
m = json.loads(json.dumps(d)); m["beats"][6]["display"] = "I animated this whole reel in FlashFX. Sign up today."; m["beats"][6]["spoken"] = "I animated this whole reel in flash F X. Sign up today."
json.dump(m, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False)
EOF
res="$(python pipeline/lib/script_checks.py check --draft "$W/planted.json" --plan "$W/plan.json" --vendor "$VENDOR" --out "$W/rep-planted.json")"
assert_eq "$(jf "$res" ok),$(jf "$res" hard)" "false,2" "script check: a FlashFX mention in a non-FlashFX reel is a hard failure (display and spoken)"
assert_eq "$(json_get "$W/rep-planted.json" hard.0.check)/$(json_get "$W/rep-planted.json" hard.0.beat)" "solution/b4" "script check: the failure is check solution on the beat"
python - "$W/plan.json" "$W/plan-flash.json" <<'EOF'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
p["solution_decision"] = {"type": "flashfx", "name": "FlashFX", "url": "https://flashfx.app"}
json.dump(p, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF
res="$(python pipeline/lib/script_checks.py check --draft "$W/planted.json" --plan "$W/plan-flash.json" --vendor "$VENDOR" --out "$W/rep-planted-flash.json")"
assert_true "script check: the same mention raises no solution failure when the solution is flashfx" python -c 'import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(1 if [f for f in r["hard"] + r["soft"] if f["check"] == "solution"] else 0)' "$W/rep-planted-flash.json"
res="$(python pipeline/lib/script_checks.py check --draft "$W/made.json" --plan "$W/plan-flash.json" --vendor "$VENDOR" --out "$W/rep-made.json")"
assert_true "script check (flashfx): 'animated this reel in FlashFX' and 'sign up' are hard failures" bash -c "python -c 'import json, sys
r = json.load(open(sys.argv[1], encoding=\"utf-8\"))
kinds = [f[\"message\"][:40] for f in r[\"hard\"] if f[\"check\"] == \"solution\"]
sys.exit(0 if len(kinds) >= 2 and any(\"made in FlashFX\" in f[\"message\"] for f in r[\"hard\"]) and any(\"ad language\" in f[\"message\"] for f in r[\"hard\"]) else 1)' '$W/rep-made.json'"
python - "$FIXTURES/fake/m6/07-script.claims.json" "$W/claims.json" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1], encoding="utf-8"))
c["solution_issues"] = [{"beat": "b7", "kind": "ad_language", "text": "the best editor on the market", "note": "a superlative"}]
json.dump(c, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF
assert_true "the claims answer with solution_issues validates" python "$VALIDATE" pipeline/stages/07-script/claims.schema.json "$W/claims.json"
assert_true "the old claims fixture (no solution_issues) still validates" python "$VALIDATE" pipeline/stages/07-script/claims.schema.json "$FIXTURES/fake/m6/07-script.claims.json"
res="$(python pipeline/lib/script_checks.py claims --report "$W/rep-clean.json" --answer "$W/claims.json" --draft "$W/clean.json" --out "$W/rep-claims.json")"
assert_eq "$(jf "$res" ok),$(jf "$res" hard)" "false,1" "claims merge: the checks model's ad-language issue is one hard failure"
assert_grep "reads as ad language" <(json_get "$W/rep-claims.json" hard.0.message) "claims merge: the failure names the ad language"
res="$(python pipeline/lib/script_checks.py claims --report "$W/rep-claims.json" --answer "$FIXTURES/fake/m6/07-script.claims.json" --draft "$W/clean.json" --out "$W/rep-claims2.json")"
assert_eq "$(jf "$res" ok)" "true" "claims merge: a later clean answer removes the model's solution failure"
assert_eq "$(json_get "$FROZEN/07-script/script.json" solution.type none)" "none" "the frozen script.json has no solution (older run): read as none"

# the history line with the solution field (history.sh)
( cd "$SANDBOX" && REELS_ROOT="$SANDBOX_M" bash -c '
source pipeline/lib/common.sh; source pipeline/lib/log.sh; source pipeline/lib/history.sh
rm -f "$REELS_LOGS/history.txt"
history_add exported "Idea one" flashfx-1 "$(history_solution "'"$RD2"'")"
history_add dropped "Idea two" "facts do not hold" "$(history_solution "'"$SANDBOX_M"'/runs/none")"
history_add blocked "Idea three" "env" method
history_add exported "Idea one" flashfx-1 external
history_counts > "$REELS_LOGS/.counts"' )
assert_grep "^20[0-9-]+ [0-9:]+ \| Idea one \| method \| exported flashfx-1$" "$SANDBOX/channels/flashfx/logs/history.txt" "history: date | idea | solution | exported N (the run's solution.json type, last written as a method)"
assert_grep "^20[0-9-]+ [0-9:]+ \| Idea two \| - \| dropped: facts do not hold$" "$SANDBOX/channels/flashfx/logs/history.txt" "history: - before S2 decided"
assert_grep "^20[0-9-]+ [0-9:]+ \| Idea three \| method \| blocked: env$" "$SANDBOX/channels/flashfx/logs/history.txt" "history: the blocked line with the solution"
assert_eq "$(grep -c "exported flashfx-1" "$SANDBOX/channels/flashfx/logs/history.txt")" "1" "history: an exported line is not repeated"
assert_eq "$(cat "$SANDBOX/channels/flashfx/logs/.counts")" "1 1 1" "history_counts still counts with the new field"

# the SOLUTION block (export.py render) and the dummies
created="$(printf 'Idea for the export' | python "$STATE_PY" new --runs "$SANDBOX_M/channels/flashfx/runs" --id abcdef123456)"
RD4="$(jf "$created" run_dir)"
for st in 02-expansion 13-render 14-export; do ( cd "$SANDBOX" && REELS_DUMMY_SECONDS=0 bash "$SANDBOX/pipeline/stages/$st/dummy.sh" "$RD4" ) >/dev/null 2>&1; done
assert_true "the 13-render dummy validates" python "$VALIDATE" pipeline/stages/13-render/schema.json "$RD4/13-render/render.json"
assert_true "the 14-export dummy validates" python "$VALIDATE" pipeline/stages/14-export/schema.json "$RD4/14-export/export.json"
assert_eq "$(json_get "$RD4/14-export/export.json" solution.type)" "external" "the 14-export dummy takes the solution from solution.json"
caps="$(python pipeline/lib/export.py render --run-dir "$RD4" --number 7)"
assert_eq "$(printf '%s\n' "$caps" | grep -E '^(CAPTION|HASHTAGS|COMMENT KEYWORD|SOLUTION|HOOKS|NEEDS REVIEW|FACTS AND SOURCES|RUN)$' | paste -sd,)" "CAPTION,HASHTAGS,COMMENT KEYWORD,SOLUTION,HOOKS,FACTS AND SOURCES,RUN" "captions: the SOLUTION block sits between COMMENT KEYWORD and HOOKS"
assert_true "captions: the SOLUTION line" grep -q -x "external: the frontend-design skill https://github.com/anthropics/skills" <<<"$caps"
python - "$RD4/14-export/export.json" <<'EOF'
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8")); m["solution"] = {"type": "flashfx", "name": "FlashFX", "url": "https://flashfx.app"}
json.dump(m, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
EOF
assert_true "captions: a flashfx solution reads flashfx" grep -q -x "flashfx" <<<"$(python pipeline/lib/export.py render --run-dir "$RD4" --number 7)"
python - "$RD4/14-export/export.json" <<'EOF'
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8")); m["solution"] = {"type": "method", "name": "copy the folder by hand", "url": ""}
json.dump(m, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
EOF
assert_true "captions: a method reads method: name" grep -q -x "method: copy the folder by hand" <<<"$(python pipeline/lib/export.py render --run-dir "$RD4" --number 7)"

# S13's checks (finalrender.py check) on the golden render: the video details pass; HyperFrames' own audio path misses
# the loudness target (DECISIONS.md: that is why S13 muxes the mix with ffmpeg)
if [ -f channels/flashfx/golden/test-idea/golden.mp4 ] && [ -f "$FROZEN/08-voiceover/vo.wav" ]; then
  res="$(python pipeline/lib/finalrender.py check --file channels/flashfx/golden/test-idea/golden.mp4 --voice "$FROZEN/08-voiceover/vo.wav")"
  assert_eq "$(jf "$res" failing)" '["loudness"]' "finalrender check: the golden render passes every video and container check and fails only the loudness (HyperFrames' audio path, +3 LU)"
  assert_true "finalrender check: the duration matches the voice within 0.2 s" python -c 'import json, sys; d = json.loads(sys.argv[1])["checks"]["duration"]; sys.exit(0 if d["ok"] and abs(d["diff_s"]) <= 0.2 else 1)' "$res"
else
  echo "   (golden/test-idea/golden.mp4 or the frozen vo.wav is missing: the S13 check on the golden render is skipped; test-m9 and test-m7 section 3 make them)"
fi
# the mux and the checks on a short real clip: the frozen hook 2 draft (540x960, silent) gets its voice, is re-encoded to
# 1080x1920 by the post-pass and passes
if [ -f "$FROZEN/10-build/hook2.mp4" ] && [ -f "$FROZEN/08-voiceover/vo_hook2.wav" ]; then
  res="$(python - "$FROZEN/10-build/hook2.mp4" "$FROZEN/08-voiceover/vo_hook2.wav" "$W/h2.mp4" <<'EOF'
import json, os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
import finalrender as fr
from visual import common
cfg = common.load_config(); cfg.setdefault("render", {}); cfg.setdefault("voice", {})
fr.mux(sys.argv[1], sys.argv[2], sys.argv[3], cfg, 600)
res = fr.check_file(sys.argv[3], None, cfg, hook2=True)
before = list(res["failing"])
fixed = fr.post_pass(sys.argv[1], sys.argv[2], sys.argv[3], res, cfg, 600, None)
after = fr.check_file(sys.argv[3], None, cfg, hook2=True)
print(json.dumps({"before": before, "fixed": fixed, "after": after["failing"], "pass": after["pass"], "soft": after["soft_failing"]}))
EOF
)"
  assert_eq "$(jf "$res" before)" '["width", "height"]' "post-pass: the 540x960 draft with the voice fails only the size checks"
  assert_true "post-pass: the video is re-encoded at 1080x1920" grep -q "re-encoded to H.264 High yuv420p 30 fps at 1080x1920" <<<"$(jf "$res" fixed)"
  assert_eq "$(jf "$res" pass)" "true" "post-pass: every hard check passes afterwards (aac 48 kHz, h264 High, yuv420p, 3.5 s at most)"
  # the voice (2.68 s) is shorter than the clip (3.2 s, the voice plus the tail): the audio is padded, the video keeps its length
  assert_true "mux: a mix shorter than the video keeps the video's length (apad, DECISIONS.md 273)" python -c 'import subprocess, sys
d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", sys.argv[1]], capture_output=True, text=True).stdout)
print(d); sys.exit(0 if abs(d - 3.2) <= 0.1 else 1)' "$(mixed "$W/h2.mp4")"
  # M11's style check, found by the real run of M12: a second review round analyzes into the same folder, and the
  # analyzer's ffmpeg (no -y) waited for "Overwrite? [y/N]" until the stage timed out. Two runs in a row must both finish.
  assert_true "style check: the analyzer runs twice into the same folder without hanging (DECISIONS.md 274)" timeout 240 python - "$(mixed "$FROZEN/10-build/hook2.mp4")" "$(mixed "$W/style-out")" <<'EOF'
import os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from review import style_check
class Ctx:
    repo = os.getcwd()
    def c(self, key, default=None):
        return 60
for i in (1, 2):
    s = style_check.run_analyzer(Ctx(), sys.argv[1], sys.argv[2])
    print("run", i, "ok" if s else "no summary")
EOF
else
  echo "   (the frozen hook2.mp4 or vo_hook2.wav is missing: the mux and post-pass unit is skipped)"
fi

# the caption composer (caption.py) on the frozen run
created="$(printf '%s' "$TEST_IDEA" | python "$STATE_PY" new --runs "$SANDBOX_M/channels/flashfx/runs" --id c26c94b17281)"
RD5="$(jf "$created" run_dir)"
for st in 01-research 02-expansion 05-hooks 06-judge 07-script; do cp -r "$FROZEN/$st" "$RD5/"; done
python "$STATE_PY" flag "$RD5" 07-script "soft script check failed: detect 64" >/dev/null
mkdir -p "$RD5/14-export" "$RD5/13-render"; printf 'x' > "$RD5/13-render/final.mp4"; printf 'x' > "$RD5/13-render/hook2.mp4"
res="$(REELS_ROOT="$SANDBOX_M" python pipeline/lib/caption.py data --run-dir "$RD5" --out "$RD5/14-export/caption-data.json" --config "$(resolved_config)")"
assert_eq "$(jf "$res" hook1),$(jf "$res" keyword),$(jf "$res" solution),$(jf "$res" needs_review)" "Why your Claude Code cards all look identical.,TELLS,external,1" "caption data: hook 1, the keyword, the solution, the flag"
assert_true "caption data: the facts the script cites, with URL and date" python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); f = d["facts"]
sys.exit(0 if len(f) >= 5 and all(x["url"].startswith("http") and x["checked"] for x in f) else 1)' "$RD5/14-export/caption-data.json"
assert_true "the fake caption answer validates against the model schema" python "$VALIDATE" pipeline/stages/14-export/model.schema.json "$FAKE_M12/14-export.json"
res="$(python pipeline/lib/caption.py compose --run-dir "$RD5" --data "$RD5/14-export/caption-data.json" --answer "$FAKE_M12/14-export.json" --out "$RD5/14-export/export.json")"
assert_eq "$(jf "$res" ok),$(jf "$res" lint_verdict),$(jf "$res" first_line_chars)" "true,READY,46" "caption compose: the fixture answer passes every check and the vendor lint"
assert_true "export.json validates" python "$VALIDATE" pipeline/stages/14-export/schema.json "$RD5/14-export/export.json"
assert_eq "$(head -n 1 "$RD5/14-export/caption.txt")" "Why your Claude Code cards all look identical." "caption.txt: the first line is hook 1"
assert_eq "$(json_get "$RD5/14-export/export.json" hashtags)" '["#claudecode", "#frontenddesign", "#webdesign", "#aitools"]' "export.json: the hashtags"
assert_eq "$(json_get "$RD5/14-export/export.json" needs_review.0)" "07-script: soft script check failed: detect 64" "export.json: the flag as stage: text"
assert_eq "$(json_get "$RD5/14-export/export.json" solution.type)/$(json_get "$RD5/14-export/export.json" files.reel)" "external/../13-render/final.mp4" "export.json: the solution and the files"
python - "$FAKE_M12/14-export.json" "$W/cap-bad.json" <<'EOF'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
a["body"] = a["body"] + "\n\nI made this reel in FlashFX " + chr(0x2014) + " follow me for more. #viral https://flashfx.app"
a["ask_line"] = "Comment TELLS and tell me which one you hate most."
a["hashtags"] = ["#a", "#b", "#c", "#d", "#e", "#f", "#g", "#TELLS"]
json.dump(a, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF
res="$(python pipeline/lib/caption.py compose --run-dir "$RD5" --data "$RD5/14-export/caption-data.json" --answer "$W/cap-bad.json" --out "$W/export-bad.json")"
assert_eq "$(jf "$res" ok)" "false" "caption compose: a bad answer is refused"
assert_true "caption compose: it names the hashtag in the body, the link, the second asks, the FlashFX mention, the made-in and caption.py's two asks" python -c 'import json, sys
e = " || ".join(json.loads(sys.argv[1])["errors"])
need = ("hashtag sits inside the body", "a link sits in the caption", "second ask in the body", "FlashFX is named although", "made in FlashFX", "caption.py counts", "answer a question")
missing = [n for n in need if n not in e]
print(missing); sys.exit(1 if missing else 0)' "$res"
assert_true "caption compose: 8 hashtags are cut to 5 and the keyword tag dropped" bash -c "grep -q 'kept the first 5' <<<'$(jf "$res" notes)' && grep -q 'must not repeat the comment keyword' <<<'$(jf "$res" notes)'"
assert_no_file "$W/export-bad.json" "caption compose: nothing written for a refused answer"
res="$(python pipeline/lib/caption.py compose --run-dir "$RD5" --data "$RD5/14-export/caption-data.json" --answer "$W/cap-bad.json" --out "$W/export-bad.json" --force)"
assert_eq "$(jf "$res" forced)" "true" "caption compose --force writes the last answer anyway"
no_emdash_in "caption compose: humanize.py removed the em dash from the forced caption" "$W/export-bad.json"
caps="$(python pipeline/lib/export.py render --run-dir "$RD5" --number 1)"
assert_eq "$(printf '%s\n' "$caps" | grep -E '^(CAPTION|HASHTAGS|COMMENT KEYWORD|SOLUTION|HOOKS|NEEDS REVIEW|FACTS AND SOURCES|RUN)$' | paste -sd,)" "CAPTION,HASHTAGS,COMMENT KEYWORD,SOLUTION,HOOKS,NEEDS REVIEW,FACTS AND SOURCES,RUN" "captions (frozen run): every section in order"
assert_eq "$(printf '%s\n' "$caps" | sed -n 2p)" "Why your Claude Code cards all look identical." "captions (frozen run): the first line is hook 1"
assert_true "captions (frozen run): the facts carry URL and date" grep -q -E '^- .*: https?://.* \(checked 2026-[0-9-]+\)$' <<<"$caps"

# one model at its own limit ("You've reached your Fable limit. Switch to another model"): the escalated call carries on
# with opus instead of failing as a code error (DECISIONS.md 275; a tiny stand-in for claude that refuses fable). Only an
# idea marked [important] escalates to fable at all (DECISIONS.md 334): the run's state.json says so.
FL="$W/fable-limit"; mkdir -p "$FL/runs/r1/10-build" "$FL/logs"
printf '{"idea": {"id": "r1", "text": "x", "important": true}}\n' > "$FL/runs/r1/state.json"
cat > "$FL/claude" <<'EOF'
#!/usr/bin/env bash
m=""; while [ $# -gt 0 ]; do [ "$1" = --model ] && m="$2"; shift; done
cat >/dev/null
echo "$m" >> "$(dirname "$0")/models.log"
if [ "$m" = fable ]; then
  printf '{"type":"result","subtype":"success","is_error":true,"api_error_status":429,"api_error":"model_requires_usage_credits","terminal_reason":"api_error","result":"You%sve reached your Fable limit. Switch to another model, or manage usage credits at https://claude.ai/settings/usage, to continue.","session_id":"s1"}\n' "'"; exit 1
fi
printf '{"type":"result","subtype":"success","is_error":false,"result":"ok from %s","session_id":"s2"}\n' "$m"
EOF
chmod +x "$FL/claude"; printf 'hi\n' > "$FL/p.md"
res="$(REELS_ROOT="$(mixed "$FL")" REELS_CLAUDE="$FL/claude" bash -c 'source pipeline/lib/common.sh; source pipeline/lib/log.sh; source pipeline/lib/config.sh; source pipeline/lib/state.sh; source pipeline/lib/status.sh; source pipeline/lib/ai.sh
ai builder_escalation "$1/runs/r1/10-build" "$1/p.md" --no-protect >/dev/null 2>&1; echo "$?|$AI_CLASS|$AI_RESULT"' _ "$FL" 2>/dev/null | tail -n 1)"
assert_eq "$res" "0|ok|ok from opus" "ai: a fable call at Fable's own limit carries on with opus"
assert_eq "$(paste -sd, "$FL/models.log")" "fable,opus" "ai: one fable try, then opus"
fi

# ----------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. S13 and S14 through the runner on the frozen build: the real sound pass, a dummy review, the final render, the caption with the fake model, the export"
sandbox_init --with-review
fast_mode
fake_claude_on
mkdir -p "$SANDBOX/fixtures"; cp "$FAKE_M12/14-export.json" "$SANDBOX/fixtures/"
export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
RD="$(seed_run)"
# one flag as an earlier stage raises it (the seeded stages did not run, so they raised none): NEEDS REVIEW must carry it
python "$STATE_PY" flag "$RD" 05-hooks "voice.md is still the draft profile (planted by test-m12)" >/dev/null
started="$EPOCHSECONDS"
run_once "$SANDBOX/export.out" 3600 REELS_DUMMY=12-review; rc=$?
OUT="$SANDBOX/export.out"
printf 'S11, S12 (dummy), S13 and S14 took %ss\n' "$((EPOCHSECONDS - started))"
grep -E "$ts_regex(STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0"
assert_grep "${ts_regex}STEP   adding sound effects done \([0-9hms]+\) -> reviewing: mechanical checks$" "$OUT" "STEP after S11"
assert_grep "${ts_regex}STEP   reviewing: mechanical checks done \([0-9hms]+\) -> rendering final video$" "$OUT" "STEP: the review hands over to the final render"
assert_grep "${ts_regex}STEP   rendering final video done \([0-9hms]+\) -> writing caption$" "$OUT" "STEP: the render hands over to the caption"
assert_grep "${ts_regex}STEP   writing caption done \([0-9hms]+\) -> exporting #1$" "$OUT" "STEP: the caption hands over to the export (the activity exporting #1)"
assert_grep "${ts_regex}DONE   exported flashfx-1 -> exports/flashfx-1/ \([0-9]+ (min|s), 0 issues fixed\)$" "$OUT" "the DONE line"
assert_not_grep "${ts_regex}(ERROR|BLOCK|DROP)" "$OUT" "no ERROR, BLOCK or DROP line"
assert_grep "${ts_regex}INFO   S13: the reel rendered at 1080x1920 in [0-9.]+ s" "$OUT" "S13: the render line"
assert_grep "${ts_regex}INFO   S13: final.mp4 1080x1920 30.0 fps High yuv420p, aac 48000 Hz, [0-9.]+ s \(voice [0-9.]+ s\), -1[0-9.]+ LUFS, -[0-9.]+ dBTP: every check passes$" "$OUT" "S13: every check passes on final.mp4"
assert_grep "${ts_regex}INFO   S13: hook2.mp4 [0-9.]+ s, aac audio: every check passes$" "$OUT" "S13: the hook 2 clip passes"
assert_grep "${ts_regex}INFO   S14: caption [0-9]+ chars \(first line [0-9]+\), #claudecode #frontenddesign #webdesign #aitools, lint READY" "$OUT" "S14: the caption line"
assert_grep "^activity: rendering hook 2 clip$" "$RD/13-render/stage.log" "S13: the activity 'rendering hook 2 clip'"
assert_grep "^activity: rendering final video$" "$RD/13-render/stage.log" "S13: the activity 'rendering final video'"
assert_grep "^activity: writing caption$" "$RD/14-export/stage.log" "S14: the activity 'writing caption'"
assert_grep "exporting #1" "$SANDBOX/channels/flashfx/logs/runner.log" "the activity 'exporting #1' reached the log"
check_export "$SANDBOX/exports" 1 "$RD" "section 2"
assert_file "$RD/13-render/video.mp4" "13-render/video.mp4: the silent render is kept"
assert_true "13-render/video.mp4 has no audio stream" bash -c "! ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 '$RD/13-render/video.mp4' | grep -q audio"
assert_eq "$(json_get "$RD/13-render/render.json" post_pass.reel)" "[]" "render.json: no post-pass was needed for the reel"
assert_eq "$(json_get "$RD/13-render/render.json" reel.audio)" "11-sfx/mix.wav" "render.json: the reel carries the sound stage's mix"
assert_eq "$(json_get "$RD/13-render/render.json" hook2.audio)" "11-sfx/mix_hook2.wav" "render.json: the hook 2 clip carries its own mix"
assert_true "render.json: the mix's loudness survived the AAC encode (-14 LUFS plus or minus 1)" python -c 'import json, sys
l = json.load(open(sys.argv[1], encoding="utf-8"))["checks"]["reel"]["loudness"]
sys.exit(0 if l["lufs"] is not None and abs(l["lufs"] + 14) <= 1.0 and l["true_peak_dbtp"] <= -1.0 else 1)' "$RD/13-render/render.json"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/channels/flashfx/ideas.txt")" "0" "ideas.txt: the idea is gone after the export"
assert_grep "^20[0-9-]+ [0-9:]+ \| $TEST_IDEA \| external \| exported flashfx-1$" "$SANDBOX/channels/flashfx/logs/history.txt" "history: date | idea | external | exported 1"
assert_true "the run folder is kept" test -d "$RD" -a -f "$RD/state.json"
assert_eq "$(state_get "$RD" status)" "exported" "state.json: exported"
assert_eq "$(state_get "$RD" export.number)" "1" "state.json: export number 1"
assert_eq "$(fake_calls)" "1" "one model call: the caption"
assert_eq "$(fake_field 1 model)" "$(python -c 'import json; print(json.load(open("config.json"))["models"]["script"]["model"])')" "the caption call uses the script model"
assert_eq "$(fake_field 1 tools)" '[""]' "the caption call has no tools"
assert_grep "^# Stage: 14-export$" "$RD/14-export/prompt-caption.md" "the caption prompt header"
assert_grep "^- Hook 1, the caption's first line \(fixed, do not rewrite it\): Why your Claude Code cards all look identical\.$" "$RD/14-export/prompt-caption.md" "the caption prompt carries hook 1"
assert_grep "FlashFX is not mentioned anywhere in the caption" "$RD/14-export/prompt-caption.md" "the caption prompt carries the solution rule for an external solution"
assert_grep "^NEEDS REVIEW$" "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt" "captions: NEEDS REVIEW (the planted flag)"
assert_grep "voice.md is still the draft profile \(planted by test-m12\)" "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt" "captions: NEEDS REVIEW carries the flag's text"
assert_grep "^- Install command: /plugin install frontend-design@claude-plugins-official.*: https://code.claude.com/docs/en/discover-plugins \(checked 2026-11-01\)$" "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt" "captions: a cited fact with its URL and date"
no_emdash_in "no em dash in the stage files and the logs" "$RD/13-render/render.json" "$RD/14-export/export.json" "$RD/14-export/caption.txt" "$SANDBOX/channels/flashfx/logs/runner.log" "$SANDBOX/channels/flashfx/logs/history.txt"
unset FAKE_CLAUDE_FIXTURES
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. the honesty loop with the fake claude: a forced FlashFX solution fails H, S4 decides the skill, the gate passes on round 2, the run reaches the export"
sandbox_init --with-pipeline
# the premise of this section is a voice.md with no usable proof line; the user's filled profile stays out of the
# test (DECISIONS.md 305)
printf '# voice

## Proof I can use

- [FILL IN: a real number]

## The ask

- [FILL IN]
' > "$SANDBOX/channels/flashfx/library/profile/voice.md"
fast_mode
fake_claude_on
mkdir -p "$SANDBOX/fixtures"
for f in 01-research.json 02-expansion.json 03-gate.1.json 03-gate.2.json 04-angle.json; do cp "$FAKE_M12/$f" "$SANDBOX/fixtures/"; done
export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/channels/flashfx/ideas.txt"
run_once "$SANDBOX/honesty.out" 1800 REELS_DUMMY="$(dummy_after 04-angle)"; rc=$?
OUT="$SANDBOX/honesty.out"; RD="$(first_run)"
grep -E "$ts_regex(STEP|GATE|ANGLE|DROP|DONE|ERROR|BLOCK|FLAG|INFO)" "$OUT" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0"
assert_grep "${ts_regex}INFO   S2: expansion [0-9]+ chars, solution flashfx \(FlashFX\), keyword FLASH \(existing\)" "$OUT" "S2: the forced FlashFX decision with the keyword FLASH"
assert_grep "${ts_regex}ANGLE  gate failed \(H\): finding a better angle, round 1/2$" "$OUT" "ANGLE: the gate fails H and asks for an angle round"
assert_not_grep "${ts_regex}DROP" "$OUT" "an H failure never drops the idea"
assert_grep "${ts_regex}INFO   S4: angle round 1/2, [0-9]+ new claims?, solution external \(the frontend-design skill" "$OUT" "S4: the solution decided again (external)"
assert_grep "${ts_regex}GATE   passed \(P3 S3 C3 F ok H ok\) after 1 angle round$" "$OUT" "GATE: round 2 passes with H ok"
assert_grep "${ts_regex}DONE   exported flashfx-1 -> exports/flashfx-1/" "$OUT" "the run reaches the export (dummy stages after S4)"
assert_eq "$(event_tags "$OUT")" "STEP,STEP,ANGLE,STEP,STEP,GATE,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,STEP,DONE" "the event lines: one angle round, the pass, the dummy stages, the export"
assert_eq "$(json_get "$RD/03-gate/gate-1.json" H)/$(json_get "$RD/03-gate/gate-1.json" decision)/$(json_get "$RD/03-gate/gate-1.json" solution_type)" "fail/angle/flashfx" "gate-1.json: H fail, decision angle, the flashfx solution"
assert_eq "$(json_get "$RD/03-gate/gate-1.json" failing)" '["H"]' "gate-1.json: failing lists H alone"
assert_eq "$(json_get "$RD/03-gate/gate.json" H)/$(json_get "$RD/03-gate/gate.json" pass)/$(json_get "$RD/03-gate/gate.json" solution_type)" "ok/true/external" "gate.json (round 2): H ok, pass, the external solution"
assert_eq "$(json_get "$RD/02-expansion/solution.json" type)/$(json_get "$RD/02-expansion/solution.json" keyword)/$(json_get "$RD/02-expansion/solution.json" written_by)" "external/LINK/04-angle round 1" "solution.json: rewritten by the angle round, external with LINK"
assert_eq "$(json_get "$RD/02-expansion/solution-r0.json" type)/$(json_get "$RD/02-expansion/solution-r0.json" keyword)" "flashfx/FLASH" "solution-r0.json: the first decision is kept"
assert_eq "$(json_get "$RD/02-expansion/expansion.json" keyword)" "LINK" "expansion.json: the keyword follows the new solution"
assert_grep "^Solution decision: external \(the frontend-design skill \(anthropics/skills\), https://github.com/anthropics/skills\): " "$RD/02-expansion/expansion.md" "expansion.md: the new decision line"
assert_grep "^Solution: flashfx: FlashFX \(https://flashfx.app\)\. Reason given: fixture: FlashFX forced" "$RD/03-gate/prompt-gate-r1.md" "the gate prompt (round 1) shows the FlashFX decision"
assert_grep "^voice.md \"Proof I can use\" \(the only FlashFX claims a reel may make\): \(empty: no FlashFX claim can be backed today\)$" "$RD/03-gate/prompt-gate-r1.md" "the gate prompt shows the empty proof section"
assert_grep "^## H failed: decide the solution again$" "$RD/04-angle/prompt-angle-r1.md" "the angle prompt asks to decide the solution again"
assert_grep "^## The solution rules \(flashfx, external or method; the keyword follows it\)$" "$RD/04-angle/prompt-angle-r1.md" "the angle prompt carries the solution rules"
assert_grep "^Scores: P3 S3 C3 F ok H fail\. Failing: H\.$" "$RD/04-angle/prompt-angle-r1.md" "the angle prompt names the failing criterion H"
assert_grep "gate round 1: P3 S3 C3 F ok H fail, decision angle" "$RD/03-gate/prompt-gate-r2.md" "the second gate round sees the first round's H"
assert_eq "$(json_get "$RD/04-angle/angle.json" previous_H)/$(json_get "$RD/04-angle/angle.json" solution.type)" "fail/external" "angle.json records the H it repaired and the new solution"
assert_true "angle.json validates" python "$VALIDATE" pipeline/stages/04-angle/schema.json "$RD/04-angle/angle.json"
assert_grep "^20[0-9-]+ [0-9:]+ \| $TEST_IDEA \| external \| exported flashfx-1$" "$SANDBOX/channels/flashfx/logs/history.txt" "history: the solution type external"
assert_grep "^external: the frontend-design skill \(anthropics/skills\) https://github.com/anthropics/skills$" "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt" "captions: the SOLUTION block from solution.json (the dummy export)"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/channels/flashfx/ideas.txt")" "0" "ideas.txt: the idea is gone"
calls="$(python -c 'import json, sys; print(",".join(json.loads(l)["stage"] for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG")"
assert_eq "$calls" "01-research,02-expansion,03-gate,04-angle,03-gate" "the fake answered S1, S2, S3, S4, S3"
no_emdash_in "no em dash in the stage files" "$RD/02-expansion/expansion.md" "$RD/02-expansion/solution.json" "$RD/03-gate/gate-1.json" "$RD/03-gate/gate.json" "$RD/04-angle/angle.json" "$SANDBOX/channels/flashfx/logs/history.txt"
unset FAKE_CLAUDE_FIXTURES
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 4; then
section "4. the test idea end to end with the real models and the real engine: research to export (1 to 3 hours)"
sandbox_init --with-review
fake_claude_off
printf '{%s}\n' "$TEST_IDEA" > "$SANDBOX/channels/flashfx/ideas.txt"
started="$EPOCHSECONDS"
run_once "$SANDBOX/real.out" "${M12_TIMEOUT:-14400}"; rc=$?
OUT="$SANDBOX/real.out"; RD="$(first_run)"
printf 'the real run took %ss (%s), kept at %s\n' "$((EPOCHSECONDS - started))" "$(( (EPOCHSECONDS - started) / 60 )) min" "$RD"
grep -E "$ts_regex(STEP|GATE|ANGLE|DROP|DONE|ERROR|FIXED|ESCAL|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0"
assert_grep "${ts_regex}DONE   exported flashfx-1 -> exports/flashfx-1/" "$OUT" "DONE: exported flashfx-1"
assert_not_grep "${ts_regex}(BLOCK|DROP|STOP)" "$OUT" "no BLOCK, DROP or STOP line"
assert_grep "${ts_regex}GATE   passed \(P[2-3] S[2-3] C[2-3] F ok H ok\)" "$OUT" "GATE passed with H ok"
assert_true "research.json lists solution candidates" test "$(json_get "$RD/01-research/research.json" solution_candidates | python -c 'import json, sys; print(len(json.loads(sys.stdin.read() or "[]")))')" -ge 1
assert_file "$RD/02-expansion/solution.json" "02-expansion/solution.json exists"
sol="$(json_get "$RD/02-expansion/solution.json" type)"
assert_true "solution.json: a known type ($sol)" bash -c "case '$sol' in flashfx|external|method) exit 0;; *) exit 1;; esac"
assert_eq "$(json_get "$RD/03-gate/gate.json" H)" "ok" "gate.json: H ok"
assert_eq "$(json_get "$RD/07-script/script.json" solution.type)" "$sol" "script.json carries the solution"
check_export "$SANDBOX/exports" 1 "$RD" "real run"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/channels/flashfx/ideas.txt")" "0" "ideas.txt: the idea is gone"
assert_grep "^20[0-9-]+ [0-9:]+ \| $TEST_IDEA \| $sol \| exported flashfx-1$" "$SANDBOX/channels/flashfx/logs/history.txt" "history: the exported line with the solution type"
assert_true "the run folder is kept with every stage" test -d "$RD/13-render" -a -d "$RD/14-export" -a -f "$RD/state.json"
no_emdash_in "no em dash in the exports and the logs" "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt" "$SANDBOX/channels/flashfx/logs/runner.log" "$SANDBOX/channels/flashfx/logs/history.txt" "$RD/14-export/export.json" "$RD/13-render/render.json"
echo "   the captions file:"; sed 's/^/      /' "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt"
if [ -n "${M12_FREEZE:-}" ] && [ "$rc" = 0 ] && [ -f "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt" ]; then
  FR="$FROZEN"
  mkdir -p "$FR/13-render" "$FR/14-export" "$FR/02-expansion"
  cp "$RD/02-expansion/solution.json" "$FR/02-expansion/solution.json"
  cp "$RD/13-render/render.json" "$FR/13-render/render.json"
  for f in export.json caption.txt caption-data.json; do cp "$RD/14-export/$f" "$FR/14-export/$f" 2>/dev/null || true; done
  printf 'frozen 02-expansion/solution.json, 13-render/render.json and 14-export outputs added by M12_FREEZE=1 bash pipeline/tests/test-m12.sh on %s from %s (the mp4 files are kept out of git)\n' "$(date '+%Y-%m-%d %H:%M')" "$(basename "$RD")" >> "$FR/README.txt"
  echo "   frozen: the M12 outputs copied into $FR"
fi
fi

# ----------------------------------------------------------------------------------------------------------------
if want 5; then
section "5. no em dash in the files M12 wrote"
no_emdash_in "no em dash in the M12 sources, prompts, schemas, contracts and fixtures" \
  pipeline/lib/solution.py pipeline/lib/finalrender.py pipeline/lib/caption.py pipeline/lib/export.py pipeline/lib/history.sh \
  pipeline/lib/expansion.py pipeline/lib/gate.py pipeline/lib/research.py pipeline/lib/script_checks.py \
  pipeline/stages/13-render/run.sh pipeline/stages/13-render/CONTRACT.md pipeline/stages/13-render/schema.json \
  pipeline/stages/14-export/run.sh pipeline/stages/14-export/CONTRACT.md pipeline/stages/14-export/schema.json \
  pipeline/stages/14-export/prompt-caption.md pipeline/stages/14-export/model.schema.json pipeline/stages/14-export/dummy.sh \
  pipeline/stages/01-research/prompt.md pipeline/stages/02-expansion/prompt.md pipeline/stages/02-expansion/run.sh pipeline/stages/02-expansion/dummy.sh \
  pipeline/stages/03-gate/prompt.md pipeline/stages/03-gate/run.sh pipeline/stages/04-angle/prompt.md pipeline/stages/04-angle/run.sh \
  pipeline/stages/07-script/prompt.md pipeline/stages/07-script/prompt-claims.md pipeline/stages/05-hooks/run.sh \
  pipeline/tests/test-m12.sh "$FAKE_M12"/*.json "$FROZEN/02-expansion/solution.json"
fi

test_summary
