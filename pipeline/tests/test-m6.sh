#!/usr/bin/env bash
# test-m6.sh: acceptance test for M6 (Script: S7). Section 3 makes real model calls (the script, cut, checks and
# judge models on the frozen M5 outputs of the test idea); everything else uses the fake claude in pipeline/tests/fakes.
#   bash pipeline/tests/test-m6.sh                    everything (10 to 25 minutes, dominated by the real S7)
#   M6_SECTIONS="1 2" bash pipeline/tests/test-m6.sh  only those sections (1 and 2 use no model, a few minutes)
#   M6_FREEZE=1 bash pipeline/tests/test-m6.sh        also copy the real 07-script outputs into
#                                                    pipeline/tests/fixtures/runs/test-idea/ (the frozen fixtures M7 starts from)
#
# Covers (BUILD_SPEC.md section 12, M6, and PLAN.md M6):
#   1. units, no model: script_checks.py (numbers written out, pronunciations, the Length line of tweaks.md, the
#      tones, the plan from the frozen fixtures, the draft normalization, the five script fixtures: the good one
#      passes every check and each bad one fails exactly its check, the cut judgement, the claims merge, the
#      feedback text, the pick, compose and the schema, the one-line rewrite), the fake's "# Task:" fixtures
#   2. S7 through the whole runner with the fake claude answering from fixtures, from the frozen M5 outputs: the
#      happy path (two drafts, two cuts, two claims checks, the pick, 7 calls, script.json), S8's one-line rewrite,
#      then a rewrite round (round 2 fixes an overstated claim), the block path (a claim nobody can back), the soft
#      path (a long beat left after 3 rounds: a FLAG, the export continues)
#   3. S7 on the frozen M5 outputs with the real models: script.json validates, passes every check, the cut removed
#      10 to 30 percent, two drafts and the pick are recorded, no em dash
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
export SANDBOX_WPM="${SANDBOX_WPM:-195}"  # the frozen fixtures and the asserted numbers were made at 195 wpm (M7 made config voice.wpm the reel voice's pace)
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
SC="$REPO_DIR/pipeline/lib/script_checks.py"
VENDOR="$REPO_DIR/pipeline/vendor/ig-agent-skill"
SECTIONS="${M6_SECTIONS:-1 2 3}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
FAKE_M6="$FIXTURES/fake/m6"
SCRIPTS="$FIXTURES/scripts"
FROZEN="$FIXTURES/runs/test-idea"
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
LATER_DUMMIES="$(dummy_after 07-script)"
SCHEMA="$REPO_DIR/pipeline/stages/07-script/schema.json"

state_get() { python "$STATE_PY" get "$@"; }
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
jf() { python -c 'import json, sys; d = json.loads(sys.argv[1]); v = d.get(sys.argv[2], ""); print(json.dumps(v) if isinstance(v, (list, dict, bool)) else v)' "$1" "$2"; }
failing_checks() {  # failing_checks <report.json>: the sorted set of failing check names, comma separated
  python -c 'import json, sys; r = json.load(open(sys.argv[1], encoding="utf-8")); print(",".join(sorted({f["check"] for f in r["hard"] + r["soft"]})))' "$1"
}
sid_of() { python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig")).get("session_id", ""))' "$1"; }
script_ok() {  # script_ok <script.json> <hook spoken>: the rules of spec S7 on the written file; prints a summary
  python - "$1" "$2" <<'EOF'
import json, re, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig")); hook = sys.argv[2]
beats = d["beats"]; bad = []
def norm(t): return " ".join(re.sub(r"[^a-z0-9'@/#.-]+", " ", t.lower()).split())
if norm(beats[0]["display"]) != norm(hook): bad.append("hook display is not hook 1's line")
if beats[0]["type"] != "hook" or beats[-1]["type"] != "ask": bad.append("hook first and ask last")
if beats[1]["type"] != "stake": bad.append("no stake after the hook")
for b in beats:
    if len([w for w in b["card"].split() if re.search(r"[A-Za-z0-9]", w)]) > 6: bad.append(b["id"] + ": card over 6 words")
    if not b["display"].strip() or not b["spoken"].strip(): bad.append(b["id"] + ": empty track")
    if re.search(r"\{\{|\[FILL IN", b["display"] + b["spoken"] + b["card"]): bad.append(b["id"] + ": placeholder")
    if any(w.lower().strip(".,;:!?\"'()") not in b["display"].lower() for w in b["emphasis"]): bad.append(b["id"] + ": emphasis not in display")
kw = d["ask"]["keyword"]
if not re.search(r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])", beats[-1]["display"], re.I): bad.append("keyword not in the ask")
if sum(1 for b in beats if re.search(r"\bcomment", b["display"], re.I)) != 1: bad.append("comment appears in more than one beat")
if not d["checks"]["ok"]: bad.append("checks not ok: " + "; ".join(f["message"][:60] for f in d["checks"]["hard"] + d["checks"]["soft"]))
if d["cut"].get("removed_pct") is None or not (10 <= float(d["cut"]["removed_pct"]) <= 30): bad.append(f"cut removed {d['cut'].get('removed_pct')}%")
if not (d["length_s"][0] <= d["estimated_seconds"] <= d["length_s"][1]): bad.append(f"length {d['estimated_seconds']} s outside {d['length_s']}")
if chr(0x2014) in json.dumps(d, ensure_ascii=False): bad.append("em dash")
print(f"{len(beats)} beats, {d['estimated_seconds']} s, {d['words']} words, tone {d['tone']}, picked {d['picked']}, cut {d['cut'].get('removed_pct')}%, detect {d['checks']['summary'].get('detect')}, rounds {d['rounds']}" + (f"; problems: {bad}" if bad else ""))
sys.exit(1 if bad else 0)
EOF
}

seed_run() {  # a run in the sandbox with S1 to S6 done from the frozen outputs (04-angle stays skipped); prints the run dir
  local raw id created rd st
  raw="$(tr -d '\r' < "$FROZEN/idea.txt")"
  printf '{%s}\n' "$raw" > "$SANDBOX/ideas.txt"
  id="$(printf '%s' "$raw" | python pipeline/lib/ideas.py id)"
  created="$(printf '%s' "$raw" | python "$STATE_PY" new --runs "$SANDBOX_M/runs" --id "$id")"
  rd="$(jf "$created" run_dir)"
  for st in 01-research 02-expansion 03-gate 05-hooks 06-judge; do
    cp -r "$FROZEN/$st/." "$rd/$st/"
    python "$STATE_PY" stage-start "$rd" "$st" >/dev/null
    python "$STATE_PY" stage-done "$rd" "$st" --schemas "$REPO_DIR/pipeline/stages" >/dev/null \
      || printf 'seed_run: the frozen %s did not validate\n' "$st" >&2
  done
  printf '%s' "$rd"
}

make_fake_fixtures() {  # make_fake_fixtures <dir> [overlay]: the m6 fake answers, plus an overlay's files on top
  local d="$1" overlay="${2:-}"
  rm -rf "$d"; mkdir -p "$d"
  cp "$FAKE_M6"/*.json "$d/"
  [ -n "$overlay" ] && cp "$overlay"/*.json "$d/"
  return 0
}

HOOK_SPOKEN="$(json_get "$FROZEN/06-judge/judge.json" winner.spoken)"

# ----------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. units: script_checks.py and the fake's task fixtures (no model)"
sandbox_init
fake_claude_on
mkdir -p "$SANDBOX/work"
W="$SANDBOX_M/work"

# numbers written out, pronunciations applied
printf '# test\nFlashFX = flash F X\nClaude Code = Claude Code\n' > "$SANDBOX/work/pron.txt"
n="$(python "$SC" numbers --text 'FlashFX shows 1,134,112 installs, 4-6 colors, #D97757, 20% off at $4.99, since 2025, version 1.1.1, 01 02 03, the 3rd time.' --pronunciations "$W/pron.txt")"
sp="$(jf "$n" spoken)"
assert_true "numbers: thousands, ranges, hex, percent, money, year, version, leading zeros, ordinals ($(printf '%s' "$sp" | cut -c1-80)...)" python -c '
import sys; s = sys.argv[1]
need = ["one million one hundred thirty-four thousand one hundred twelve", "four to six", "D nine seven seven five seven", "twenty percent", "four dollars ninety-nine", "twenty twenty-five", "one point one point one", "oh one oh two oh three", "third"]
sys.exit(0 if all(x in s for x in need) and not any(c.isdigit() for c in s) else 1)' "$sp"
assert_true "numbers: the pronunciation file is applied (FlashFX -> flash F X)" grep -q "flash F X shows" <<<"$sp"

# the Length line of tweaks.md, and the tones
lr="$(python "$SC" length-rule --tweaks "$REPO_DIR/styles/paper-cards/tweaks.md")"
assert_eq "$(jf "$lr" default),$(jf "$lr" list)" "[25, 40],[45, 75]" "length-rule: tweaks.md gives 25 to 40 s by default and 45 to 75 s for lists"
printf -- '- PROPOSED **Length:** list and explainer videos 40 to 75s; everything else 25 to 40s.\n- **Other:** nothing\n' > "$SANDBOX/work/tweaks-proposed.md"
assert_eq "$(python "$SC" length-rule --tweaks "$W/tweaks-proposed.md")" "{}" "length-rule: a PROPOSED Length line is ignored"
t="$(python "$SC" tones --brief "$FROZEN/05-hooks/brief.md" --family mistake-warning)"
assert_eq "$(jf "$t" tones),$(jf "$t" source)" '["insider", "warning"],brief' "tones: the brief's first two suggested tones"
t="$(python "$SC" tones --family story-confession)"
assert_eq "$(jf "$t" tones)" '["confession", "insider"]' "tones: no brief suggestion, the hook's family decides, then the default order"
t="$(python "$SC" tones --family nonsense)"
assert_eq "$(jf "$t" tones)" '["insider", "calm expert"]' "tones: unknown family, the default order"

# the plan from the frozen fixtures
PLAN="$W/plan.json"
res="$(python "$SC" setup --config "$REPO_DIR/config.json" --brief "$FROZEN/05-hooks/brief.md" --judge "$FROZEN/06-judge/judge.json" \
  --expansion "$FROZEN/02-expansion/expansion.json" --voice "$REPO_DIR/library/profile/voice.md" --pronunciations "$W/pron.txt" \
  --tweaks "$REPO_DIR/styles/paper-cards/tweaks.md" --style "$REPO_DIR/styles/paper-cards/style.md" --wpm 195 --rounds 3 --idea-id test --idea-text "idea" --out "$PLAN")"
assert_eq "$(jf "$res" ok)" "true" "setup: plan.json written"
assert_eq "$(json_get "$PLAN" length_s),$(json_get "$PLAN" length_source),$(json_get "$PLAN" video_type)" "[25.0, 40.0],tweaks.md,default" "setup: the length range from tweaks.md for a default reel"
assert_eq "$(json_get "$PLAN" final_words),$(json_get "$PLAN" write_words)" "[81, 130],[121, 143]" "setup: 81 to 130 words at 195 wpm, the writer aims at 121 to 143 before the cut"
assert_eq "$(json_get "$PLAN" hook.spoken)" "$HOOK_SPOKEN" "setup: hook 1 is the judge's winner"
assert_eq "$(json_get "$PLAN" hook2.id),$(json_get "$PLAN" keyword)" "h07,TELLS" "setup: hook 2 and the keyword"
assert_true "setup: the beat map comes from style.md and the excerpts from voice.md" python -c '
import json, sys; p = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if "| beat | component" in p["beat_map"] and "FlashFX" in p["voice_excerpts"] and len(p["pronunciations"]) == 2 else 1)' "$PLAN"

# the draft normalization: the hook forced, emphasis filtered, pronunciations and numbers in the spoken track
python - "$SCRIPTS/good.json" "$W/answer-odd.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["beats"][0]["display"] = "Why do your Claude Code cards look the same?"
d["beats"][0]["card"] = "SAME CARDS"
d["beats"][3]["emphasis"] = ["convergence", "unicorn"]
d["beats"][7]["spoken"] = "With FlashFX on, Claude plans 4 to 6 colours, reviews them, then codes."
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF
res="$(python "$SC" draft --answer "$W/answer-odd.json" --plan "$PLAN" --label a --tone insider --round 1 --source write --out "$W/draft-odd.json")"
assert_eq "$(json_get "$W/draft-odd.json" beats.0.display)|$(json_get "$W/draft-odd.json" beats.0.card)" "$HOOK_SPOKEN|IDENTICAL CARDS LOOK AI" "draft: the hook beat's display and card are hook 1's lines whatever the model wrote"
assert_eq "$(json_get "$W/draft-odd.json" beats.3.emphasis)" '["convergence"]' "draft: an emphasis word that is not in the display line is dropped"
assert_eq "$(json_get "$W/draft-odd.json" beats.7.spoken)" "With flash F X on, Claude plans four to six colours, reviews them, then codes." "draft: pronunciations and numbers applied to the spoken track"
assert_true "draft: the normalizer notes the replaced hook" grep -q "replaced by hook 1" <<<"$res"

# the five fixtures: the good one passes every check, each bad one fails exactly its own
for f in good placeholder two-asks abstract-run long-beat; do
  python "$SC" draft --answer "$SCRIPTS/$f.json" --plan "$PLAN" --label a --tone insider --round 1 --source write --out "$W/$f.draft.json" >/dev/null
  res="$(python "$SC" check --draft "$W/$f.draft.json" --plan "$PLAN" --out "$W/$f.report.json")"
  case "$f" in
    good) assert_eq "$(jf "$res" ok)" "true" "fixture good passes every local check ($(jf "$(jf "$res" summary)" seconds) s, detect $(jf "$(jf "$res" summary)" detect))" ;;
    placeholder) assert_eq "$(failing_checks "$W/$f.report.json")" "placeholders" "fixture placeholder fails exactly the placeholders check (hard)" ;;
    two-asks) assert_eq "$(failing_checks "$W/$f.report.json")" "ask" "fixture two-asks fails exactly the one-ask check (hard)" ;;
    abstract-run) assert_eq "$(failing_checks "$W/$f.report.json")" "beats" "fixture abstract-run fails exactly beats.py's abstract run (soft)"
      assert_grep "nothing concrete in them" "$W/$f.report.json" "fixture abstract-run: the message names the run" ;;
    long-beat) assert_eq "$(failing_checks "$W/$f.report.json")" "beats" "fixture long-beat fails exactly the 4 s beat rule (soft)"
      assert_grep "b8 runs [0-9.]+ s" "$W/$f.report.json" "fixture long-beat: the message names the beat" ;;
  esac
done
assert_eq "$(json_get "$W/placeholder.report.json" hard.0.severity),$(json_get "$W/long-beat.report.json" soft.0.severity)" "hard,soft" "placeholders are hard, timing is soft"
assert_true "good: the report records detect.py PASS, the loop word, the stake identity words and beats.py's notes" python -c '
import json, sys; r = json.load(open(sys.argv[1], encoding="utf-8"))["checks"]
sys.exit(0 if r["detect"]["verdict"] == "PASS" and r["beats"]["loop_word"] == "identical" and r["stake"]["identity_ok"] and any("Loops" in n for n in r["beats"]["vendor_notes"]) and r["requirements"] == {"problem": True, "identity": True, "keyword": True} else 1)' "$W/good.report.json"
# humanize.py through the wrapper: a slop word is replaced, an em dash becomes a comma, rgba(0,0,0,.1) survives
python - "$SCRIPTS/good.json" "$W/answer-slop.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["beats"][4]["display"] = "I read the frontend-design skill " + chr(0x2014) + " it names tells and will elevate your pages."
d["beats"][4]["spoken"] = d["beats"][4]["display"]
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF
python "$SC" draft --answer "$W/answer-slop.json" --plan "$PLAN" --label a --tone insider --round 1 --source write --out "$W/slop.draft.json" >/dev/null
python "$SC" check --draft "$W/slop.draft.json" --plan "$PLAN" --out "$W/slop.report.json" --write >/dev/null
assert_eq "$(json_get "$W/slop.draft.json" beats.4.display)" "I read the frontend-design skill, it names tells and will improve your pages." "check --write: humanize.py replaced the stock word and the em dash in the draft"
assert_eq "$(json_get "$W/slop.draft.json" beats.2.display)" "Rounded cards again. Same shadow, rgba(0,0,0,.1)." "check --write: the exact value rgba(0,0,0,.1) survives humanize.py"
assert_true "check: the humanize report counts the lexical hit" python -c '
import json, sys; h = json.load(open(sys.argv[1], encoding="utf-8"))["checks"]["humanize"]; sys.exit(0 if h["lexical"] >= 1 and h["changed"] else 1)' "$W/slop.report.json"

# the cut: the fake fixtures, a cut that loses a value, the best attempt
python "$SC" draft --answer "$FAKE_M6/07-script.write.1.json" --plan "$PLAN" --label a --tone insider --round 1 --source write --out "$W/full-a.json" >/dev/null
cd_="$(python "$SC" cut-data --draft "$W/full-a.json" --plan "$PLAN")"
assert_true "cut-data: the listing, the targets and the tokens that must survive" python -c '
import json, sys; d = json.loads(sys.argv[1]); sys.exit(0 if d["words"] > 140 and d["floor"] == 81 and "#D97757" in d["must_keep"] and "TELLS" in d["must_keep"] and "b1 [hook]" in d["text"] else 1)' "$cd_"
res="$(python "$SC" cut-apply --draft "$W/full-a.json" --answer "$FAKE_M6/07-script.cut.1.json" --plan "$PLAN" --out "$W/cut-a-1.json" --attempt 1)"
assert_eq "$(jf "$res" ok)" "true" "cut-apply: the fixture cut passes (removed $(jf "$res" removed_pct)%)"
assert_true "cut-apply: 10 to 30 percent removed" python -c 'import json, sys; d = json.loads(sys.argv[1]); sys.exit(0 if 10 <= d["removed_pct"] <= 30 else 1)' "$res"
python - "$FAKE_M6/07-script.cut.1.json" "$W/cut-lost.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["beats"][5]["display"] = "One of them is Anthropic's own terracotta on a cream background."
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
EOF
res="$(python "$SC" cut-apply --draft "$W/full-a.json" --answer "$W/cut-lost.json" --plan "$PLAN" --out "$W/cut-a-2.json" --attempt 2)"
assert_eq "$(jf "$res" ok)" "false" "cut-apply: a cut that drops #D97757 fails"
assert_true "cut-apply: the error names the lost value" grep -q "lost these numbers.*#D97757" <<<"$res"
res="$(python "$SC" cut-best --draft "$W/full-a.json" --plan "$PLAN" --attempts "$W/cut-a-2.json" "$W/cut-a-1.json" --out "$W/cut-a.json")"
assert_eq "$(jf "$res" ok),$(jf "$res" chosen)" "true,attempt 1" "cut-best: the attempt that kept every value wins"
res="$(python "$SC" cut-best --draft "$W/full-a.json" --plan "$PLAN" --attempts "$W/cut-a-2.json" --out "$W/cut-none.json")"
assert_eq "$(jf "$res" ok),$(jf "$res" chosen)" "false,uncut" "cut-best: with only a lossy attempt the uncut draft is kept"

# the claims merge and the feedback text
python "$SC" check --draft "$W/cut-a.json" --plan "$PLAN" --out "$W/rep-a.json" --write >/dev/null
res="$(python "$SC" claims --report "$W/rep-a.json" --answer "$FAKE_M6/07-script.claims.json" --draft "$W/cut-a.json")"
assert_eq "$(jf "$res" ok),$(jf "$res" bad)" "true,0" "claims: every claim supported keeps the report ok"
res="$(python "$SC" claims --report "$W/rep-a.json" --answer "$FIXTURES/fake/m6-rewrite/07-script.claims.1.json" --draft "$W/cut-a.json" --out "$W/rep-a-bad.json")"
assert_eq "$(jf "$res" ok),$(jf "$res" hard)" "false,1" "claims: an overstated claim is one hard failure"
assert_eq "$(json_get "$W/rep-a-bad.json" hard.0.check),$(json_get "$W/rep-a-bad.json" hard.0.beat)" "facts,b11" "claims: the failure is check facts on the named beat"
fb="$(python "$SC" feedback --report "$W/rep-a-bad.json" --plan "$PLAN")"
assert_true "feedback: the rewrite prompt text carries the failure, its severity and the word budget" python -c '
import sys; t = sys.argv[1]; sys.exit(0 if "[must fix, facts]" in t and "81 to 130 words" in t else 1)' "$fb"

# the pick and compose
python "$SC" draft --answer "$FAKE_M6/07-script.write.2.json" --plan "$PLAN" --label b --tone warning --round 1 --source write --out "$W/full-b.json" >/dev/null
python "$SC" cut-apply --draft "$W/full-b.json" --answer "$FAKE_M6/07-script.cut.2.json" --plan "$PLAN" --out "$W/cut-b.json" --attempt 1 >/dev/null
python "$SC" check --draft "$W/cut-b.json" --plan "$PLAN" --out "$W/rep-b.json" --write >/dev/null
pd="$(python "$SC" pick-data --drafts "$W/cut-a.json" "$W/cut-b.json" --reports "$W/rep-a.json" "$W/rep-b.json" --seed test:pick --out "$W/pick-data.json")"
assert_true "pick-data: both drafts in a seeded order with their check summaries" python -c '
import json, sys; d = json.loads(sys.argv[1]); sys.exit(0 if sorted(d["order"]) == ["a", "b"] and "[hook]" in d["text_1"] and "detect.py" in d["checks_1"] else 1)' "$pd"
printf '{"winner": "2", "reason": "the second one", "notes": ""}' > "$SANDBOX/work/pick-2.json"
res="$(python "$SC" pick --data "$W/pick-data.json" --answer "$W/pick-2.json" --out "$W/pick.json")"
assert_eq "$(jf "$res" winner)" "$(json_get "$W/pick-data.json" order.1)" "pick: winner 2 maps to the draft shown second"
printf '{"winner": "both", "reason": "", "notes": ""}' > "$SANDBOX/work/pick-x.json"
res="$(python "$SC" pick --data "$W/pick-data.json" --answer "$W/pick-x.json" --out "$W/pick-x.out.json")"
assert_eq "$(jf "$res" lenient),$(jf "$res" winner)" "true,$(json_get "$W/pick-data.json" order.0)" "pick: an answer that names no draft takes the first one, leniently"
python "$SC" round-log --file "$W/rounds.json" --round 1 --label a --action "write, cut, check" --ok true >/dev/null
res="$(python "$SC" compose --draft "$W/cut-a.json" --report "$W/rep-a.json" --plan "$PLAN" --pick "$W/pick.json" --rounds 1 --rounds-log "$W/rounds.json" --draft-info "a=$W/cut-a.json" "b=$W/cut-b.json" --out "$W/script.json")"
assert_eq "$(jf "$res" ok)" "true" "compose: script.json written"
assert_true "compose: script.json validates against schema.json" python pipeline/bin/validate-json "$SCHEMA" "$W/script.json"
summary="$(script_ok "$W/script.json" "$HOOK_SPOKEN")"; rc=$?
assert_rc 0 $rc "compose: the rules of spec S7 hold on the file ($summary)"
assert_true "compose: both drafts, the pick, the cut and the checks are recorded" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(0 if set(d["drafts"]) == {"a", "b"} and d["pick"]["reason"] and d["cut"]["ok"] and d["checks"]["detail"]["claims"]["status"] == "checked" and d["hook2"]["spoken"] and d["rounds_log"] else 1)' "$W/script.json"
assert_true "schema: a card of 7 words is rejected" python -c '
import json, subprocess, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); d["beats"][2]["card"] = "one two three four five six seven"
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"))
sys.exit(0 if subprocess.run([sys.executable, "pipeline/bin/validate-json", sys.argv[3], sys.argv[2]], capture_output=True).returncode == 1 else 1)' "$W/script.json" "$W/script-badcard.json" "$SCHEMA"

# S8's one-line rewrite, applied
printf '{"spoken": "One command, the plugin install line on screen. Pick a scope.", "display": "One command: /plugin install frontend-design@claude-plugins-official. Pick a scope.", "notes": "named it"}' > "$SANDBOX/work/rl-ok.json"
res="$(python "$SC" rewrite-line-apply --script "$W/script.json" --beat b9 --answer "$W/rl-ok.json" --reason "WER 12%" --out "$W/script-rl.json")"
assert_eq "$(jf "$res" ok),$(jf "$res" rewrites)" "true,1" "rewrite-line-apply: the line is replaced and recorded"
assert_eq "$(json_get "$W/script-rl.json" rewrites.0.beat),$(json_get "$W/script-rl.json" rewrites.0.reason)" "b9,WER 12%" "rewrite-line-apply: the record names the beat and the reason"
assert_true "rewrite-line-apply: script-rl.json still validates" python pipeline/bin/validate-json "$SCHEMA" "$W/script-rl.json"
printf '{"spoken": "One command, which is slash plugin install frontend design at claude plugins official, and then you pick a scope and you are done with it.", "display": "x", "notes": ""}' > "$SANDBOX/work/rl-long.json"
res="$(python "$SC" rewrite-line-apply --script "$W/script.json" --beat b9 --answer "$W/rl-long.json" --out "$W/script-rl2.json")"
assert_eq "$(jf "$res" ok)" "false" "rewrite-line-apply: a longer line is refused"

# the fake serves fixtures by task
make_fake_fixtures "$SANDBOX/fixtures"
export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
fake_claude_reset
out1="$(printf '# Role: cut\n# Stage: 07-script\n# Task: cut\n\ncut it\n' | claude -p --output-format json --json-schema '{"type":"object"}' --model sonnet)"
out2="$(printf '# Role: cut\n# Stage: 07-script\n# Task: cut\n\ncut it again\n' | claude -p --output-format json --json-schema '{"type":"object"}' --model sonnet)"
out3="$(printf '# Role: script\n# Stage: 07-script\n\nno task line\n' | claude -p --output-format json --json-schema '{"type":"object"}' --model opus)"
assert_eq "$(jf "$(jf "$out1" structured_output)" notes)" "$(json_get "$FAKE_M6/07-script.cut.1.json" notes)" "fake: '# Task: cut' serves 07-script.cut.1.json"
assert_eq "$(jf "$(jf "$out2" structured_output)" notes)" "$(json_get "$FAKE_M6/07-script.cut.2.json" notes)" "fake: the second cut call serves 07-script.cut.2.json"
assert_eq "$(jf "$(jf "$out3" structured_output)" ok)" "true" "fake: without a task line only the stage files count (none here), so the plain ok answer comes back"
assert_eq "$(fake_field 1 task)" "cut" "fake: the log records the task"
unset FAKE_CLAUDE_FIXTURES
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. S7 through the runner with the fake claude, from the frozen M5 outputs (then the rewrite, block and soft paths)"
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
assert_grep "${ts_regex}START  idea 1/1 .* \(resumed at writing script, 5 stages done\)$" "$OUT" "START: the run seeded from the frozen outputs resumes at S7"
assert_grep "${ts_regex}INFO   S7: hook 1 h01 \"Why your Claude Code cards all look identical\.\"; default reel of 25 to 40 s \(tweaks.md\) at 195 wpm: 81 to 130 words after the cut; tones insider and warning \(brief\); solution external$" "$OUT" "S7: the plan line (hook 1, the length rule from tweaks.md, the tones from the brief, the solution type of M12)"
assert_grep "${ts_regex}INFO   S7: draft a \(insider\) written: 12 beats, 150 words before the cut$" "$OUT" "S7: draft a written"
assert_grep "${ts_regex}INFO   S7: draft a cut from 150 to 117 words \(22.0%, attempt 1\)$" "$OUT" "S7: draft a cut by 22 percent"
assert_grep "${ts_regex}INFO   S7: draft a \(insider\) round 1: 37.2 s, 117 words, detect 84.8, 9 claims checked: every check passes$" "$OUT" "S7: draft a passes every check"
assert_grep "${ts_regex}INFO   S7: draft b \(warning\) written: 12 beats, 152 words before the cut$" "$OUT" "S7: draft b written"
assert_grep "${ts_regex}INFO   S7: draft b \(warning\) round 1: .* every check passes$" "$OUT" "S7: draft b passes every check"
assert_grep "${ts_regex}INFO   S7: the judge picked draft [ab] \((insider|warning)\): Draft 1 reads like someone who opened the file" "$OUT" "S7: the pick line with the judge's reason"
assert_grep "${ts_regex}INFO   S7: script.json: draft [ab] \((insider|warning)\), 12 beats, [0-9.]+ s \([0-9]+ words at 195 wpm\), cut [0-9.]+%, detect [0-9.]+, 1 round; session D done$" "$OUT" "S7: the summary line"
assert_grep "${ts_regex}STEP   writing script done \([0-9hms]+\) -> generating voiceover$" "$OUT" "S7 done, the runner moves to S8"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the run continued to the (dummy) export"
assert_not_grep "${ts_regex}ERROR" "$OUT" "no ERROR line"
assert_not_grep "${ts_regex}BLOCK" "$OUT" "no BLOCK line"
assert_not_grep "${ts_regex}FLAG   needs review: soft script" "$OUT" "no script flag"
S="$RD/07-script"
assert_true "script.json validates against schema.json" python pipeline/bin/validate-json "$SCHEMA" "$S/script.json"
summary="$(script_ok "$S/script.json" "$HOOK_SPOKEN")"; rc=$?
assert_rc 0 $rc "script.json keeps the rules of spec S7 ($summary)"
picked="$(json_get "$S/script.json" picked)"
assert_eq "$(json_get "$S/script.json" pick.winner),$(json_get "$S/script.json" rounds)" "$picked,1" "script.json: the pick and one round"
assert_eq "$(json_get "$S/script.json" tone)" "$(json_get "$S/script.json" "drafts.$picked.tone")" "script.json: the tone is the picked draft's"
assert_true "script.json: two drafts with their cut, the pick's order and reason, hook 2's tracks, the claims checked" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8"))
ok = set(d["drafts"]) == {"a", "b"} and all(10 <= d["drafts"][k]["cut"]["removed_pct"] <= 30 for k in "ab") and sorted(d["pick"]["order"]) == ["a", "b"] and d["pick"]["reason"] and d["hook2"]["spoken"] and d["hook2"]["card"] and d["checks"]["detail"]["claims"]["n"] == 9 and d["checks"]["detail"]["detect"]["verdict"] == "PASS"
sys.exit(0 if ok else 1)' "$S/script.json"
assert_eq "$(json_get "$S/script.json" beats.0.display)|$(json_get "$S/script.json" beats.0.card)" "$HOOK_SPOKEN|IDENTICAL CARDS LOOK AI" "script.json: beat 1 is hook 1 with its on-screen line as card"
assert_eq "$(json_get "$S/script.json" ask.keyword),$(json_get "$S/script.json" ask.loop_word)" "TELLS,identical" "script.json: the keyword and the loop word"
for f in plan.json draft-a.r1.json draft-a.r1.cut.json draft-b.r1.cut.json checks-a-r1.json checks-b-r1.json pick-data.json pick.json rounds.json prompt-write-a.md prompt-write-b-short.md prompt-cut-a-r1.md prompt-claims-a-r1.md prompt-pick.md; do
  assert_file "$S/$f" "stage file $f"
done
assert_grep "^# Task: write$" "$S/prompt-write-a.md" "the write prompt carries the task line"
assert_grep "^## facts.md|^## Claims" "$S/prompt-claims-a-r1.md" "the claims prompt inlines facts.md"
assert_grep "rgba\(0,0,0,.1\)" "$S/prompt-cut-a-r1.md" "the cut prompt lists the values that must survive"
assert_grep "FlashFX" "$S/prompt-pick.md" "the pick prompt carries the voice excerpts"
assert_grep "Draft A was written in the insider tone" "$S/prompt-write-b.md" "the full prompt of draft B names draft A's tone (the fallback when session D is lost)"
# the fake's log: write a (new session D), cut a, claims a, write b (session D resumed), cut b, claims b, pick
assert_eq "$(fake_calls)" "7" "7 model calls: 2 drafts, 2 cuts, 2 claims checks, the pick"
assert_eq "$(fake_field 1 role),$(fake_field 2 role),$(fake_field 3 role),$(fake_field 4 role),$(fake_field 5 role),$(fake_field 6 role),$(fake_field 7 role)" "script,cut,checks,script,cut,checks,judge" "the roles in order"
assert_eq "$(fake_field 1 task),$(fake_field 2 task),$(fake_field 3 task),$(fake_field 4 task),$(fake_field 7 task)" "write,cut,claims,write,pick" "the tasks in order"
sidD="$(sid_of "$(ls "$S"/calls/*-write-a.json | head -n 1)")"
assert_eq "$(fake_field 1 resume)" "" "draft a starts session D"
assert_eq "$(fake_field 4 resume)" "$sidD" "draft b resumes session D"
assert_eq "$(fake_field 2 resume),$(fake_field 3 resume),$(fake_field 5 resume),$(fake_field 6 resume),$(fake_field 7 resume)" ",,,," "the cut, claims and pick calls are fresh sessions"
assert_eq "$(state_get "$RD" sessions.D)" "$sidD" "state.json keeps session D"
assert_eq "$(fake_field 1 model),$(fake_field 2 model),$(fake_field 3 model),$(fake_field 7 model)" "$(json_get "$REPO_DIR/config.json" models.script.model),$(json_get "$REPO_DIR/config.json" models.cut.model),$(json_get "$REPO_DIR/config.json" models.checks.model),$(json_get "$REPO_DIR/config.json" models.judge.model)" "the models from config (script, cut, checks, judge)"
assert_eq "$(fake_field 1 tools),$(fake_field 2 tools),$(fake_field 7 tools)" '[""],[""],[""]' "no tools on any call"
no_emdash_in "no em dash in the stage files" "$S/script.json" "$S/draft-a.r1.cut.json" "$S/draft-b.r1.cut.json" "$S/checks-a-r1.json" "$SANDBOX/logs/runner.log"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "ideas.txt: the idea is gone after the export"

# S8's one-line rewrite through the stage script (session D resumed)
fake_claude_reset
( cd "$SANDBOX" && NO_COLOR=1 bash "$SANDBOX/pipeline/stages/07-script/run.sh" "$RD" --rewrite-line b9 --reason "word error rate 12%" ) > "$SANDBOX/rl.out" 2>&1; rc=$?
assert_rc 0 $rc "rewrite-line: the stage script exits 0"
assert_grep "S7: line b9 rewritten in simpler words" "$SANDBOX/rl.out" "rewrite-line: the INFO line"
assert_eq "$(json_len "$S/script.json" rewrites),$(json_get "$S/script.json" rewrites.0.beat)" "1,b9" "rewrite-line: script.json records the rewrite"
assert_eq "$(json_get "$S/script.json" beats.8.spoken)" "One command, the plugin install line on screen. Pick a scope." "rewrite-line: the spoken track is the simpler line"
assert_eq "$(fake_calls),$(fake_field 1 role),$(fake_field 1 task),$(fake_field 1 resume)" "1,script,rewrite-line,$sidD" "rewrite-line: one script call that resumes session D"
assert_true "rewrite-line: script.json still validates" python pipeline/bin/validate-json "$SCHEMA" "$S/script.json"

# a rewrite round: both drafts fail the claims check in round 1 (an overstated claim), the pick is rewritten once
make_fake_fixtures "$SANDBOX/fixtures" "$FIXTURES/fake/m6-rewrite"
fake_claude_reset
RD2="$(seed_run)"
run_once "$SANDBOX/rewrite.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/rewrite.out"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "rewrite round: the runner exits 0"
assert_grep "${ts_regex}WARN   S7: draft a \(insider\) round 1: .* 1 hard and 0 soft failure \(first: b11: the claim 'the skill has over a million installs' says more than facts.md backs" "$OUT" "rewrite round: round 1 names the overstated claim"
assert_grep "${ts_regex}INFO   S7: draft [ab] \((insider|warning)\) round 2: .* every check passes$" "$OUT" "rewrite round: round 2 passes"
assert_grep "${ts_regex}INFO   S7: script.json: .* 2 rounds; session D done$" "$OUT" "rewrite round: the summary counts 2 rounds"
assert_grep "${ts_regex}DONE   exported #2 -> exports/2/" "$OUT" "rewrite round: the run continued to the export"
assert_not_grep "${ts_regex}(ERROR|BLOCK)" "$OUT" "rewrite round: no ERROR or BLOCK"
S2="$RD2/07-script"; P2="$(json_get "$S2/script.json" picked)"
assert_eq "$(json_get "$S2/script.json" rounds),$(json_get "$S2/script.json" checks.ok)" "2,true" "rewrite round: script.json says 2 rounds and ok"
assert_file "$S2/draft-$P2.r2.json" "rewrite round: the round 2 draft of the picked draft"
assert_file "$S2/checks-$P2-r2.json" "rewrite round: the round 2 report"
assert_eq "$(json_get "$S2/script.json" beats.10.display)" "Anthropic verified it. Over a million installs, as of November 2026." "rewrite round: the rewritten line is in script.json"
assert_eq "$(fake_calls)" "9" "rewrite round: 9 calls (7 plus the rewrite and its claims check)"
assert_eq "$(fake_field 8 role),$(fake_field 8 task),$(fake_field 9 role),$(fake_field 9 task)" "script,rewrite,checks,claims" "rewrite round: the rewrite in session D, then the claims check"
assert_eq "$(fake_field 8 resume)" "$(sid_of "$(ls "$S2"/calls/*-write-a.json | head -n 1)")" "rewrite round: the rewrite resumes session D"
assert_grep "^- \[must fix, facts\] b11: the claim" "$S2/prompt-rewrite-$P2-r2.md" "rewrite round: the rewrite prompt lists the failing check"
assert_grep "^# Task: rewrite$" "$S2/prompt-rewrite-$P2-r2.md" "rewrite round: the rewrite prompt carries its task line"
assert_eq "$(json_get "$S2/script.json" cut.removed_pct)" "$(json_get "$S2/draft-$P2.r1.cut.json" cut.removed_pct)" "rewrite round: script.json keeps round 1's cut statistics"
assert_eq "$(state_get "$RD2" rounds.script)" "2" "rewrite round: state.json rounds.script"
assert_true "rewrite round: the rounds log has round 1 for both drafts and round 2 for the pick" python -c '
import json, sys; log = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if [e["round"] for e in log] == [1, 1, 2] and log[2]["ok"] else 1)' "$S2/rounds.json"

# the block path: a claim nobody can back, the rewrite never fixes it, both drafts fail: the idea is blocked after 3 rounds
make_fake_fixtures "$SANDBOX/fixtures" "$FIXTURES/fake/m6-block"
fake_claude_reset
RD3="$(seed_run)"
run_once "$SANDBOX/block.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/block.out"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "block path: the runner exits 0 (the idea is blocked, the queue is empty)"
assert_grep "${ts_regex}BLOCK  idea \"Claude Code's frontend-design skill.*\" blocked at S7: script still failing after 3 rounds: b5: the claim 'the skill names every tell' is not backed by facts.md" "$OUT" "block path: the BLOCK line with the hard failure"
assert_not_grep "${ts_regex}(ERROR|DONE)" "$OUT" "block path: no ERROR and no export"
assert_grep "blocked at S7" "$SANDBOX/logs/blocked.txt" "block path: logs/blocked.txt"
assert_grep "| blocked: script still failing after 3 rounds" "$SANDBOX/logs/history.txt" "block path: the history line"
S3="$RD3/07-script"
assert_eq "$(json_get "$S3/result.json" stage)" "07-script" "block path: result.json"
assert_no_file "$S3/script.json" "block path: no script.json"
assert_eq "$(fake_calls)" "11" "block path: 11 calls (7, then two rewrite rounds with their claims checks)"
assert_eq "$(state_get "$RD3" status)" "blocked" "block path: state.json says blocked"

# the soft path: a beat over 4 s that no rewrite fixes: a FLAG, the export continues
make_fake_fixtures "$SANDBOX/fixtures" "$FIXTURES/fake/m6-soft"
fake_claude_reset
RD4="$(seed_run)"
run_once "$SANDBOX/soft.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/soft.out"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "soft path: the runner exits 0"
assert_grep "${ts_regex}FLAG   needs review: soft script check failed after 3 rounds: beats: b8 runs 6.2 s \(20 words\); no beat may run over 4 s" "$OUT" "soft path: the FLAG line names the long beat"
assert_grep "${ts_regex}DONE   exported #3 -> exports/3/" "$OUT" "soft path: the run continued to the export"
assert_not_grep "${ts_regex}(ERROR|BLOCK)" "$OUT" "soft path: no ERROR or BLOCK"
S4="$RD4/07-script"
assert_true "soft path: script.json validates, 3 rounds, checks not ok with a soft failure only, the flag recorded" python -c '
import json, subprocess, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
ok = d["rounds"] == 3 and d["checks"]["ok"] is False and d["checks"]["hard"] == [] and len(d["checks"]["soft"]) >= 1 and any("b8 runs" in f for f in d["flags"])
ok = ok and subprocess.run([sys.executable, "pipeline/bin/validate-json", sys.argv[2], sys.argv[1]], capture_output=True).returncode == 0
sys.exit(0 if ok else 1)' "$S4/script.json" "$SCHEMA"
assert_eq "$(fake_calls)" "11" "soft path: 11 calls (two rewrite rounds)"
unset FAKE_CLAUDE_FIXTURES
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. S7 on the frozen M5 outputs with the real models (several minutes)"
sandbox_init --with-pipeline
fake_claude_off
RD="$(seed_run)"
started="$EPOCHSECONDS"
run_once "$SANDBOX/real.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/real.out"
printf 'real run took %ss, kept at %s\n' "$((EPOCHSECONDS - started))" "$RD"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0"
assert_grep "${ts_regex}STEP   writing script done \([0-9hms]+\) -> generating voiceover$" "$OUT" "S7 done"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the run continued to the (dummy) export"
assert_not_grep "${ts_regex}ERROR" "$OUT" "no ERROR line"
assert_not_grep "${ts_regex}BLOCK" "$OUT" "no BLOCK line"
S="$RD/07-script"
assert_file "$S/script.json" "script.json written"
assert_true "script.json validates against schema.json" python pipeline/bin/validate-json "$SCHEMA" "$S/script.json"
summary="$(script_ok "$S/script.json" "$HOOK_SPOKEN")"; rc=$?
assert_rc 0 $rc "script.json passes every check: the structure, the hook line, one ask with the keyword, cards of 6 words or fewer, no placeholder, the cut 10 to 30 percent, the length in range, no em dash ($summary)"
python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8"))
for b in d["beats"]: print("    " + b["id"] + " [" + b["type"] + "] " + b["display"] + "  |  card: " + b["card"] + ("  |  " + ", ".join(b.get("facts", [])) if b.get("facts") else ""))
print("    hook 2 spoken: " + d["hook2"]["spoken"])
print("    pick: " + d["picked"] + " (" + d["tone"] + "), order " + ",".join(d["pick"]["order"]) + ": " + d["pick"]["reason"][:200])
c = d["checks"]["detail"]; print("    detect " + str(c["detect"]["overall"]) + " " + json.dumps({k: v["score"] for k, v in c["detect"]["checks"].items()}) + "; claims " + str(c["claims"]["n"]) + " checked, " + str(c["claims"]["unsupported"] + c["claims"]["overstated"]) + " bad; stake " + str(c["stake"]["seconds"]) + " s; loop " + c["beats"]["loop_word"])
for k in "ab": print("    draft " + k + ": " + d["drafts"][k]["tone"] + ", cut " + str(d["drafts"][k]["cut"]["before_words"]) + " -> " + str(d["drafts"][k]["cut"]["after_words"]) + " words (" + str(d["drafts"][k]["cut"]["removed_pct"]) + "%)")
for e in d["rounds_log"]: print("    round " + str(e["round"]) + " draft " + e["draft"] + ": " + e["action"] + ", ok " + str(e["ok"]) + (", " + e["note"][:100] if e["note"] else ""))
for f in d["flags"]: print("    flag: " + f)' "$S/script.json"
assert_true "script.json: two drafts in two different tones, the pick decision with a reason, the claims checked, detect.py PASS" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8"))
ok = set(d["drafts"]) == {"a", "b"} and d["drafts"]["a"]["tone"] != d["drafts"]["b"]["tone"] and d["pick"]["reason"] and d["pick"]["winner"] == d["picked"] and d["checks"]["detail"]["claims"]["status"] == "checked" and d["checks"]["detail"]["detect"]["verdict"] == "PASS" and 1 <= d["rounds"] <= 3
sys.exit(0 if ok else 1)' "$S/script.json"
assert_true "script.json: the spoken tracks hold no digits (numbers written out)" python -c '
import json, re, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); bad = [b["id"] for b in d["beats"] if re.search(r"\d", b["spoken"])]; print(bad); sys.exit(0 if not bad else 1)' "$S/script.json"
assert_grep "^resume: $" "$S/calls/001-write-a.meta" "draft a started session D"
sidD="$(sid_of "$S/calls/001-write-a.json")"
assert_grep "^resume: $sidD$" "$(ls "$S"/calls/*-write-b.meta | head -n 1)" "draft b resumed session D"
assert_grep "^resume: $" "$(ls "$S"/calls/*-pick.meta | head -n 1)" "the pick ran in a fresh session"
no_emdash_in "no em dash in the stage files" "$S/script.json" "$S/draft-a.r1.cut.json" "$S/draft-b.r1.cut.json" "$S/checks-a-r1.json" "$S/pick.json" "$SANDBOX/logs/runner.log"
if [ -n "${M6_FREEZE:-}" ] && [ "$rc" = 0 ] && [ -f "$S/script.json" ]; then
  rm -rf "$FROZEN/07-script"; mkdir -p "$FROZEN/07-script/calls"
  ( cd "$S" && find . -maxdepth 1 -type f \( -name '*.json' -o -name '*.md' \) ! -name 'prompt-*' ! -name 'error.json' ! -name 'result.json' -exec cp {} "$FROZEN/07-script/" \; )
  cp "$S"/calls/*.out.json "$FROZEN/07-script/calls/" 2>/dev/null || true
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
for dp, _, names in os.walk(os.path.join(sys.argv[1], "07-script")):
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
  printf 'frozen 07-script outputs added by M6_FREEZE=1 bash pipeline/tests/test-m6.sh on %s from %s\n' "$(date '+%Y-%m-%d %H:%M')" "$(basename "$RD")" >> "$FROZEN/README.txt"
  pass "frozen: 07-script copied to pipeline/tests/fixtures/runs/test-idea/"
fi
fi

test_summary
