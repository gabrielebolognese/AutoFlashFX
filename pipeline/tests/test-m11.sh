#!/usr/bin/env bash
# test-m11.sh: acceptance test for M11 (Sound effects pass S11 and the review loop S12, BUILD_SPEC.md section 12 and
# PLAN.md M11). Sections 1 to 3 call no model (the fake claude answers the qa editor and the visual director from
# fixtures, the fake whisper hears the words it is given); section 4 calls the real qa model once and the real
# faster-whisper.
#   bash pipeline/tests/test-m11.sh                       everything (30 to 45 minutes)
#   M11_SECTIONS="1 2 3" bash pipeline/tests/test-m11.sh  only those sections (no model)
#   M11_FREEZE=1 bash pipeline/tests/test-m11.sh          section 4 also copies the real 11-sfx and 12-review JSON outputs into
#                                                         pipeline/tests/fixtures/runs/test-idea/ (the inputs of M12)
#
# Sections:
#   1. units, no runner: S11 on the frozen build (cues.json validates; every mandatory cue present; the density, spacing,
#      first-word and ask rules hold; every planned sound within 33 ms of its event on the rendered stem and no extra sound;
#      every sound 8 dB under the local voice peak; the mix at -14 LUFS plus or minus 1 and at most -1.5 dBTP; one
#      sound-map.txt line per cue; the usage log; the hook 2 clip's sounds); the onset detector on a planted shift and a
#      planted extra sound; an [sfx] review note changes the next pass; the voice-only path; the mechanical, style and
#      audio checks on the clean draft (they pass, the branding is measured); the planted faults (a FlashFX logo in the
#      body of a non-FlashFX reel, a black lockup on ink, a stretched logo, a lockup under 300 px, a CTA without the DM
#      avatar, a chip in the right rail, a chip above the safe top: each caught by its kind); the routing rules; the
#      review notes a re-run pass gets; the dummies validate
#   2. S11 and S12 through the runner with the fake qa editor: the pass (lines, activities, review.json, filmstrips, the
#      prompt), then a planted [text] issue (the fake editor fails round 1 with [text] issues): 09b reopened, 09c, S10,
#      S11 and S12 run again, round 2 passes, the state and the log show it
#   3. the cap: an editor that always fails with an [sfx] issue: 5 rounds (3 main, 2 escalated: opus on an idea without
#      the [important] label, DECISIONS.md 334), then the export with the
#      NEEDS REVIEW flag and the notes; the sound pass changes with the feedback each round
#   4. the real editor and the real transcription on the frozen draft (1 model call)
#   5. no em dash in the files M11 wrote
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M11_SECTIONS:-1 2 3 4 5}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
VALIDATE="$REPO_DIR/pipeline/bin/validate-json"
FROZEN="$FIXTURES/runs/test-idea"
FAKES="$REPO_DIR/pipeline/tests/fakes"
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
LATER_DUMMIES="$(dummy_after 12-review)"
SFX_DIR_REAL="$(mixed "$REPO_DIR/channels/flashfx/styles/sfx")"
export REELS_SFX_DIR="$SFX_DIR_REAL" REELS_SFX_NO_BUILD=1
fake_whisper_on() { export REELS_WHISPER_PYTHON=python REELS_WHISPER_WORKER="$(mixed "$FAKES/whisper_worker.py")"; }
fake_whisper_off() { unset REELS_WHISPER_PYTHON REELS_WHISPER_WORKER; }

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
seed_run() {  # a run in the sandbox with S1 to S10 done from the frozen outputs, the projects rebuilt; prints the run dir
  local raw id created rd st
  raw="$(tr -d '\r' < "$FROZEN/idea.txt")"
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
run_once() {  # run_once <outfile> [env...]: the sandbox's own run.sh
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 5400 bash "$SANDBOX/run.sh" --once ) > "$out" 2>&1
}
run_stage() {  # run_stage <stage> <run_dir> <outfile> [env...]: one stage script alone, in the sandbox's copy of the pipeline
  local st="$1" rd="$2" out="$3"; shift 3
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 3600 bash "$SANDBOX/pipeline/stages/$st/run.sh" "$rd" ) > "$out" 2>&1
}
director_answers() {  # director_answers <dir>: the fake director's answers for a re-run pass are the frozen real director's
                      # answers (pipeline/tests/fixtures/runs/test-idea/<pass>/answer.json, the ones the frozen plans came from), so a
                      # fix round rebuilds the same composition; the M10 hand-made answers belong to the fake 9a plan
  local st
  for st in 09a-animations 09b-text 09c-transitions; do
    if [ -f "$FROZEN/$st/answer.json" ]; then cp "$FROZEN/$st/answer.json" "$1/$st.json"; else cp "$FIXTURES/fake/m10/$st.json" "$1/$st.json"; fi
  done
}
fake_calls() { python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG" 2>/dev/null || echo 0; }
no_emdash_in() {  # no_emdash_in <name> <file>...
  local name="$1"; shift
  if python -c 'import sys
bad = [p for p in sys.argv[1:] if open(p, "rb").read().find(bytes([0xE2, 0x80, 0x94])) >= 0]
print("\n".join(bad)); sys.exit(1 if bad else 0)' "$@" >/tmp/m11-emdash.txt; then pass "$name"; else fail "$name (em dash in: $(tr '\n' ' ' </tmp/m11-emdash.txt))"; fi
}
check_cues() {  # check_cues <run_dir> <label>: the S11 invariants on cues.json and the rendered files
  local rd="$1" lbl="$2" S="$1/11-sfx"
  assert_true "$lbl: cues.json validates against 11-sfx/schema.json" python "$VALIDATE" "$REPO_DIR/pipeline/stages/11-sfx/schema.json" "$S/cues.json"
  for f in sfx_stem.wav mix.wav draft_mixed.mp4 sound-map.txt; do assert_file "$S/$f" "$lbl: $f written"; done
  python - "$rd" "$(resolved_config)" "$SFX_DIR_REAL" <<'EOF' >/tmp/m11-cues.txt
import json, subprocess, sys
rd, cfg_path, sfx_dir = sys.argv[1:4]
cfg = json.load(open(cfg_path, encoding="utf-8-sig")); sx = cfg["sfx"]
c = json.load(open(rd + "/11-sfx/cues.json", encoding="utf-8-sig"))
ev = json.load(open(rd + "/10-build/events.json", encoding="utf-8-sig"))["events"]
words = json.load(open(rd + "/08-voiceover/words.json", encoding="utf-8-sig"))
m = json.load(open(sfx_dir + "/sfx-map.json", encoding="utf-8-sig"))
cues = c["cues"]; v = c["verification"]
by = {}
for x in cues: by.setdefault(x["cue_type"], []).append(x)
types = {e["type"] for e in ev}
want = {"hook_hit": True, "notification": "notification" in types, "success": "check" in types, "negative": "strike" in types, "typing": "typing" in types}
missing = [k for k, w in want.items() if w and k not in by]
print("mandatory", "ok" if not missing else "missing " + ",".join(missing))
print("transitions", "ok" if sum(1 for x in cues if x["group"] == "transition") >= 3 else "few")
times = sorted(x["ms"] for x in cues)
sp = min((b - a for a, b in zip(times, times[1:])), default=9999)
print("spacing", "ok" if sp >= sx["min_spacing_ms"] else f"{sp} ms")
hits = sorted(x["ms"] for x in cues if x["cue_type"] != "typing" and not x.get("series_of"))
worst = max((sum(1 for t in hits if s <= t <= s + 10000) for s in hits), default=0)
print("density", "ok" if worst <= sx["max_per_10s"] else f"{worst} in 10 s")
fw = words["words"][0]
bad = [x for x in cues if x["cue_type"] != "hook_hit" and fw["start_ms"] - sx["min_spacing_ms"] <= x["ms"] <= fw["end_ms"]]
print("first-word", "ok" if not bad else str([(x["cue_type"], x["ms"]) for x in bad]))
ask = next((b for b in words["beats"] if b["type"] == "ask"), None)
att = [x for x in cues if x["cue_type"] == "attention"]
print("attention", "ok" if all(x["ms"] >= 2000 and not (ask and x["ms"] >= ask["start_ms"]) for x in att) else "misplaced")
pools = m["pools"]
inpool = all(any(p["path"] == x["file"] for p in pools.get(x["cue_type"], [])) for x in cues)
print("files-in-pool", "ok" if inpool else "a file outside its pool")
rep = []
for k, lst in by.items():
    lst = sorted(lst, key=lambda x: x["ms"])
    for a, b in zip(lst, lst[1:]):
        if a["file"] == b["file"] and not b.get("series_of") and len(pools.get(k, [])) > 1: rep.append(k)
print("rotation", "ok" if not rep else "repeat in " + ",".join(rep))
acc = v["accuracy"]
print("sync", "ok" if acc["pass"] and acc["max_error_ms"] <= sx["sync_tolerance_ms"] and not acc["unplanned"] and acc["checked"] == len(cues) else f"max {acc['max_error_ms']} unplanned {len(acc['unplanned'])} checked {acc['checked']}/{len(cues)}")
vr = v["voice_rule"]
print("voice-rule", "ok" if vr["pass"] and (vr["min_margin_db"] is None or vr["min_margin_db"] >= -0.5) else f"margin {vr['min_margin_db']}")
ld = v["loudness"]
print("loudness", "ok" if ld["pass"] and abs(ld["lufs"] + 14) <= 1 and ld["true_peak_dbtp"] <= -1.45 else f"{ld['lufs']} LUFS {ld['true_peak_dbtp']} dBTP")
print("passes", v.get("passes"))
lines = [l for l in open(rd + "/11-sfx/sound-map.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
print("sound-map", "ok" if len(lines) == len(cues) else f"{len(lines)} lines for {len(cues)} cues")
anchor_ok = all((x["anchor"] == "peak") == (x["cue_type"] in ("transition_slow", "transition_fast", "attention", "hook_hit")) for x in cues)
print("anchors", "ok" if anchor_ok else "wrong anchor")
typ = [x for x in cues if x["cue_type"] == "typing"]
print("typing-trim", "ok" if all(abs((x["reel_start_ms"] + x["play_ms"]) - x["end_ms"]) <= 1 or x["play_ms"] < x["end_ms"] - x["reel_start_ms"] for x in typ) else "typing runs past its segment")
d = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,sample_rate:format=duration", "-of", "json", rd + "/11-sfx/draft_mixed.mp4"], capture_output=True, text=True).stdout or "{}")
a = next((s for s in d.get("streams", []) if s["codec_type"] == "audio"), None)
dur = float(d.get("format", {}).get("duration", 0))
print("mixed-draft", "ok" if a and a.get("codec_name") == "aac" and int(a.get("sample_rate", 0)) == 48000 and abs(dur - c["duration_ms"] / 1000) <= 0.3 else f"{a} {dur}")
h2 = c.get("hook2") or {}
print("hook2", "ok" if isinstance(h2, dict) and h2.get("cues") and any(x["cue_type"] == "hook_hit" for x in h2["cues"]) and h2["verification"]["pass"] else str(h2)[:120])
print("count", len(cues))
EOF
  sed 's/^/    /' /tmp/m11-cues.txt
  assert_grep "^mandatory ok" /tmp/m11-cues.txt "$lbl: every mandatory cue of the events present (hook_hit, notification, success, negative, typing)"
  assert_grep "^transitions ok" /tmp/m11-cues.txt "$lbl: whooshes on the scene changes"
  assert_grep "^spacing ok" /tmp/m11-cues.txt "$lbl: never two sounds within 250 ms"
  assert_grep "^density ok" /tmp/m11-cues.txt "$lbl: at most 4 hits in any 10 s"
  assert_grep "^first-word ok" /tmp/m11-cues.txt "$lbl: nothing on the hook's first word but hook_hit"
  assert_grep "^attention ok" /tmp/m11-cues.txt "$lbl: no attention whoosh in the first 2 s or during the ask"
  assert_grep "^files-in-pool ok" /tmp/m11-cues.txt "$lbl: every file comes from its cue type's pool"
  assert_grep "^rotation ok" /tmp/m11-cues.txt "$lbl: never the same file twice in a row for a cue type (a series excepted)"
  assert_grep "^sync ok" /tmp/m11-cues.txt "$lbl: every planned sound found within 33 ms of its event on the rendered stem, no unplanned sound"
  assert_grep "^voice-rule ok" /tmp/m11-cues.txt "$lbl: every sound at least 8 dB under the local voice peak"
  assert_grep "^loudness ok" /tmp/m11-cues.txt "$lbl: the mix at -14 LUFS plus or minus 1 and at most -1.5 dBTP"
  assert_grep "^sound-map ok" /tmp/m11-cues.txt "$lbl: sound-map.txt has one line per cue"
  assert_grep "^anchors ok" /tmp/m11-cues.txt "$lbl: whooshes placed by their peak, the rest by their onset"
  assert_grep "^typing-trim ok" /tmp/m11-cues.txt "$lbl: typing beds trimmed to their segment"
  assert_grep "^mixed-draft ok" /tmp/m11-cues.txt "$lbl: draft_mixed.mp4 carries AAC 48 kHz audio as long as the reel"
  assert_grep "^hook2 ok" /tmp/m11-cues.txt "$lbl: the hook 2 clip has its own verified hook_hit"
  assert_file "$S/sfx_stem_hook2.wav" "$lbl: the hook 2 stem written"
  assert_file "$S/mix_hook2.wav" "$lbl: the hook 2 mix written"
}
check_review_files() {  # check_review_files <run_dir> <label> <round>
  local rd="$1" lbl="$2" r="$3" R="$1/12-review"
  assert_true "$lbl: review.json validates against 12-review/schema.json" python "$VALIDATE" "$REPO_DIR/pipeline/stages/12-review/schema.json" "$R/review.json"
  for f in mechanical.json style.json audio.json "review-r$r.json" "edit-r$r.json" "prompt-r$r.md" notes.md filmstrips/hook.png filmstrips/transition-01.png digest/scenes.md digest/images.md; do
    assert_file "$R/$f" "$lbl: $f written"
  done
  assert_grep "sound-map.txt" "$R/prompt-r$r.md" "$lbl: the prompt carries the sound map beside the scenes"
  assert_grep "contact-sheet.png" "$R/prompt-r$r.md" "$lbl: the prompt points at the contact sheet"
  assert_grep "filmstrips.hook.png" "$R/prompt-r$r.md" "$lbl: the prompt points at the hook filmstrip"
  assert_grep "full_0" "$R/prompt-r$r.md" "$lbl: the prompt points at the look-reference stills"
  assert_eq "$(json_get "$R/review.json" round)" "$r" "$lbl: review.json is round $r"
}

# ------------------------------------------------------------------------------------------------ 1. units
if want 1; then
  section "1. units: the sound pass, the detector, the review notes, the voice-only path, the code checks, the planted faults, the routing"
  sandbox_init --with-review
  fake_whisper_on
  RD="$(seed_run)"
  assert_file "$RD/10-build/project/compositions/caption-word.html" "the run's project was rebuilt from the frozen plan (compositions in place)"
  assert_file "$RD/10-build/hook2/compositions/headline.html" "the hook 2 project was rebuilt too"
  assert_file "$RD/10-build/draft.mp4" "draft.mp4 present (frozen or rendered)"
  t0=$EPOCHSECONDS
  run_stage 11-sfx "$RD" "$SANDBOX/s11.out"; rc=$?
  printf '    (S11 took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "S11 runs on the frozen build"
  assert_grep "S11: [0-9]+ sounds placed \(.*\), [0-9]+ candidates dropped by the rules; seed [0-9]+; hook 2: [0-9]+ sounds" "$SANDBOX/s11.out" "S11: the summary line"
  assert_grep "S11: verified in [0-9]+ pass(es)?: every sound within [0-9.]+ ms of its event; closest to the voice [-0-9.]+ dB under the cap; mix [-0-9.]+ LUFS, [-0-9.]+ dBTP$" "$SANDBOX/s11.out" "S11: the verification line"
  # a stage run outside the runner prints its log to the captured output (the runner would route it into stage.log)
  assert_grep "^activity: adding sound effects \([0-9]+ sounds\)$" "$SANDBOX/s11.out" "activity \"adding sound effects (N sounds)\" was published"
  assert_grep "^activity: verifying sound sync and loudness$" "$SANDBOX/s11.out" "activity \"verifying sound sync and loudness\" was published"
  check_cues "$RD" "S11"
  N_SOUNDS="$(grep '^count' /tmp/m11-cues.txt | cut -d' ' -f2)"
  assert_true "S11 placed 10 to 25 sounds on the 41 s reel ($N_SOUNDS)" test "$N_SOUNDS" -ge 10 -a "$N_SOUNDS" -le 25
  USAGE="$SANDBOX/channels/flashfx/logs/sfx-usage.json"
  assert_file "$USAGE" "logs/sfx-usage.json written"
  assert_grep "\"run_id\": \"$(basename "$RD")\"" "$USAGE" "the usage log names this run"
  assert_grep '"transition_fast"' "$USAGE" "the usage log lists the files per cue type"
  SEED1="$(json_get "$RD/11-sfx/cues.json" seed)"

  # the detector: a planted shift and a planted extra sound on the rendered stem
  python - "$RD" <<'EOF' >/tmp/m11-detect.txt
import json, os, sys
sys.path.insert(0, os.path.join("pipeline", "lib", "sfx"))
import numpy as np
from audioio import read_audio, SR
import verify
rd = sys.argv[1]
c = json.load(open(rd + "/11-sfx/cues.json", encoding="utf-8-sig"))
stem, sr = read_audio(rd + "/11-sfx/sfx_stem.wav")
cues = c["cues"]
base = verify.accuracy(cues, stem, sr, 33, c["duration_ms"])
print("base", "ok" if base["pass"] else "fail")
# plant: claim a non-whoosh cue 80 ms earlier than it was rendered
shifted = json.loads(json.dumps(cues))
target = next(x for x in shifted if x["anchor"] == "onset")
target["ms"] -= 80; target["reel_start_ms"] -= 80
res = verify.accuracy(shifted, stem, sr, 33, c["duration_ms"])
r = next(x for x in res["results"] if x["id"] == target["id"])
print("shift", "ok" if (not r["ok"] and r["error_ms"] is not None and abs(r["error_ms"] - 80) <= 12) else str(r))
# plant: an extra click where nothing is planned
quiet = None
t = 1000
while t < c["duration_ms"] - 1000:
    a, b = int(t * sr / 1000), int((t + 400) * sr / 1000)
    # outside every planned span (a whoosh's span runs seconds past its peak; a stray sound inside one is covered by the plan)
    if np.abs(stem[a:b]).max() < 1e-4 and not any(x["reel_start_ms"] - 300 <= t + 300 and t - 100 <= x["reel_start_ms"] + x["play_ms"] + 100 for x in cues):
        quiet = t; break
    t += 250
stem2 = stem.copy()
n = int(0.25 * sr); i = int(quiet * sr / 1000)   # a 250 ms burst at -20 dBFS, decaying: well over the 30 ms a stray sound needs
stem2[i:i + n] += (0.1 * np.exp(-np.arange(n) / (0.08 * sr)) * np.sin(np.arange(n) * 2 * np.pi * 1800 / sr)).astype(np.float32)
res2 = verify.accuracy(cues, stem2, sr, 33, c["duration_ms"])
env2 = verify.envelope_db(stem2, sr, 5)
near = sorted((x["cue_type"], x["reel_start_ms"], round(x["reel_start_ms"] + x["play_ms"])) for x in cues if abs(x["reel_start_ms"] - quiet) < 4000)
print("extra-detail", "quiet", quiet, "env", [round(float(v), 1) for v in env2[int(quiet / 5) - 1: int(quiet / 5) + 6]], "spans near", near, "unplanned", res2["unplanned"][:3])
print("extra", "ok" if (not res2["pass"] and any(abs(u["start_ms"] - quiet) <= 60 for u in res2["unplanned"])) else str(res2["unplanned"])[:160])
EOF
  sed 's/^/    /' /tmp/m11-detect.txt
  assert_grep "^base ok" /tmp/m11-detect.txt "detector: the rendered stem verifies"
  assert_grep "^shift ok" /tmp/m11-detect.txt "detector: a sound 80 ms off its event is caught with the right error"
  assert_grep "^extra ok" /tmp/m11-detect.txt "detector: an unplanned click in a silent stretch is caught"

  # an [sfx] review note changes the next pass: fewer, softer, another seed
  mkdir -p "$RD/12-review"
  cat > "$RD/12-review/feedback.json" <<'JSON'
{"written_by": "12-review", "round": 1, "verdict": "fix", "scores": {"sound": 2}, "summary": "too busy",
 "issues": [{"tag": "sfx", "text": "The sounds are too many and too loud over the voice: a whoosh on every scene change crowds the stake beat.", "stage": "11-sfx", "source": "model"}],
 "by_stage": {"11-sfx": [{"tag": "sfx", "text": "The sounds are too many and too loud over the voice: a whoosh on every scene change crowds the stake beat.", "stage": "11-sfx"}]},
 "reopen": ["11-sfx", "12-review"]}
JSON
  python "$STATE_PY" set "$RD" "rounds.review=1" >/dev/null
  run_stage 11-sfx "$RD" "$SANDBOX/s11b.out"; rc=$?
  assert_rc 0 $rc "S11 runs again with the review's [sfx] note"
  assert_ne "$(json_get "$RD/11-sfx/cues.json" seed)" "$SEED1" "the note changes the seed (another rotation)"
  assert_grep "fewer sounds: at most 3 per 10 s, no attention whooshes, every sound 3 dB softer" "$RD/11-sfx/cues.json" "the note is applied: fewer and softer sounds"
  assert_grep "every sound 4 dB softer" "$RD/11-sfx/cues.json" "the note is applied: the loudness complaint lowers every sound"
  assert_eq "$(json_get "$RD/11-sfx/cues.json" settings.max_per_10s)" "3" "cues.json records the lowered density"
  assert_true "the second pass still verifies" test "$(json_get "$RD/11-sfx/cues.json" verification.pass)" = true
  N2="$(python -c 'import json, sys; print(len(json.load(open(sys.argv[1], encoding="utf-8-sig"))["cues"]))' "$RD/11-sfx/cues.json")"
  assert_true "the second pass places no more sounds than the first ($N2 against $N_SOUNDS)" test "$N2" -le "$N_SOUNDS"
  rm -f "$RD/12-review/feedback.json"; python "$STATE_PY" set "$RD" "rounds.review=0" >/dev/null

  # the voice-only path: no map
  EMPTY="$(mktemp -d)"
  run_stage 11-sfx "$RD" "$SANDBOX/s11c.out" REELS_SFX_DIR="$(mixed "$EMPTY")"; rc=$?
  assert_rc 0 $rc "S11 with no sfx map exits 0 (the voice alone)"
  assert_grep "${ts_regex}FLAG   needs review: no sound effects: the sfx map .* is missing; the reel has the voice alone" "$SANDBOX/s11c.out" "the FLAG line names the missing map"
  assert_eq "$(json_get "$RD/11-sfx/cues.json" voice_only)" "true" "cues.json says voice only"
  assert_true "the voice-only cues.json validates" python "$VALIDATE" "$REPO_DIR/pipeline/stages/11-sfx/schema.json" "$RD/11-sfx/cues.json"
  assert_file "$RD/11-sfx/draft_mixed.mp4" "the voice-only mixed draft exists"
  rm -rf "$EMPTY"
  # back to the normal pass for the review checks
  run_stage 11-sfx "$RD" "$SANDBOX/s11d.out"; rc=$?
  assert_rc 0 $rc "S11 runs once more for the review checks"

  # the review's code checks on the clean draft (no model)
  t0=$EPOCHSECONDS
  ( cd "$SANDBOX" && env NO_COLOR=1 python "$SANDBOX/pipeline/lib/review" mechanical --run-dir "$RD" ) >"$SANDBOX/mech.out" 2>&1; rc=$?
  printf '    (mechanical took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "the mechanical checks run on the clean draft"
  M="$RD/12-review/mechanical.json"
  assert_eq "$(json_get "$M" pass)" "true" "the mechanical checks pass on the clean draft ($(json_get "$M" issues | python -c 'import json, sys; print("; ".join(i["kind"] + ": " + i["text"][:60] for i in json.load(sys.stdin)[:3]))'))"
  assert_true "the checker measured 200 or more text boxes at 40 or more times" test "$(json_get "$M" counts.texts 0)" -ge 200 -a "$(json_get "$M" counts.times 0)" -ge 40
  assert_true "every emphasis hit landed within 80 ms of its word ($(json_get "$M" emphasis.ok)/$(json_get "$M" emphasis.checked))" test "$(json_get "$M" emphasis.ok 0)" = "$(json_get "$M" emphasis.checked 1)" -a "$(json_get "$M" emphasis.checked 0)" -ge 5
  assert_true "branding: the CTA's lockup measured 300 px or wider on a light surface" python -c 'import json, sys; b = json.load(open(sys.argv[1], encoding="utf-8-sig"))["branding"]["lockup"]; sys.exit(0 if b and b["box"]["w"] >= 300 and b.get("surface") == "light" and b.get("aspect_locked") else 1)' "$M"
  assert_true "branding: the DM avatar measured 112 px or wider with its bolt at 64 px or more" python -c 'import json, sys; b = json.load(open(sys.argv[1], encoding="utf-8-sig"))["branding"]["avatar"]; sys.exit(0 if b and min(b["box"]["w"], b["box"]["h"]) >= 112 and b.get("bolt_px", 0) >= 64 else 1)' "$M"
  assert_eq "$(json_get "$M" branding.outside_cta | python -c 'import json, sys; print(len(json.load(sys.stdin)))')" "0" "branding: no FlashFX logo outside the CTA (the solution is not FlashFX)"
  assert_true "the fonts seen are the style's five families only" python -c 'import json, sys; f = json.load(open(sys.argv[1], encoding="utf-8-sig"))["fonts_seen"]; sys.exit(0 if set(f) <= {"Inter Tight", "Instrument Serif", "Space Grotesk", "JetBrains Mono", "Caveat"} and len(f) >= 3 else 1)' "$M"
  ( cd "$SANDBOX" && env NO_COLOR=1 python "$SANDBOX/pipeline/lib/review" style --run-dir "$RD" ) >"$SANDBOX/style.out" 2>&1; rc=$?
  assert_rc 0 $rc "the style check runs"
  ST="$RD/12-review/style.json"
  assert_eq "$(json_get "$ST" pass)" "true" "the style check passes on the clean draft (cadence, palette $(json_get "$ST" palette.share_within_delta_e_pct) percent, accent max $(json_get "$ST" accent.max_frame_share_pct) percent, loudness)"
  assert_eq "$(json_get "$ST" cadence.checks.gap_median_s.ok)" "true" "cadence: the hero zone's median gap sits in the reference range"
  assert_true "palette: 90 percent or more of the non-image pixels within delta E 5 of a token color" python -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1], encoding="utf-8-sig"))["palette"]["share_within_delta_e_pct"] >= 90 else 1)' "$ST"
  assert_file "$RD/12-review/analysis/v01/summary.json" "tools/analyze_refs.py ran on the mixed draft"
  ( cd "$SANDBOX" && env NO_COLOR=1 python "$SANDBOX/pipeline/lib/review" audio --run-dir "$RD" ) >"$SANDBOX/audio.out" 2>&1; rc=$?
  assert_rc 0 $rc "the audio check runs (fake whisper)"
  AU="$RD/12-review/audio.json"
  assert_eq "$(json_get "$AU" pass)" "true" "the audio check passes (the sound verification, WER $(json_get "$AU" intelligible.wer_pct) percent)"
  assert_eq "$(json_get "$AU" sfx.pass)" "true" "the audio check reads S11's verification"

  # the planted faults, in a copy of the run: edited in the built project (what is on screen), not in the plan
  RD2="$SANDBOX_M/channels/flashfx/runs/planted"
  cp -r "$RD" "$RD2"; rm -rf "$RD2/12-review"
  python - "$RD2" <<'EOF'
import html, json, re, sys
rd = sys.argv[1]
p = rd + "/10-build/project/index.html"
s = open(p, encoding="utf-8").read()
def edit_host(s, host_id, fn):
    m = re.search(r'(<div id="' + re.escape(host_id) + r'" class="clip".*?data-variable-values=\')(.*?)(\'></div>)', s, re.S)
    assert m, host_id
    props = json.loads(html.unescape(m.group(2)))
    fn(props)
    raw = json.dumps(props, ensure_ascii=False).replace("&", "&amp;").replace("'", "&#39;")
    return s[:m.start(2)] + raw + s[m.end(2):]
# 1. a FlashFX logo in the body of a non-FlashFX reel (the s4 card's image)
s = edit_host(s, "s4-card-1", lambda p: p.update({"image": "assets/brand/mark/mark-gradient.png", "image_h": 400}))
# 2. a black lockup on ink: the s3 window card turned dark with the black lockup as its image
s = edit_host(s, "s3-window-card-1", lambda p: p.update({"kind": "dark", "image": "assets/brand/lockup/lockup-black.png", "image_fit": "contain"}))
# 4. a lockup under 300 px (the component's clamp is removed below)
s = edit_host(s, "s11-end-card-1", lambda p: p.update({"lockup_w": 200}))
# 5. a CTA without the DM avatar
s = edit_host(s, "s11-dm-card-2", lambda p: p.update({"avatar": ""}))
# 6. a chip in the right rail of the lower half, 7. a chip above the safe top
s = edit_host(s, "s6-dark-chip-2", lambda p: p.update({"x": 820, "y": 1000}))
s = edit_host(s, "s9-light-chip-2", lambda p: p.update({"x": 120, "y": 120}))
open(p, "w", encoding="utf-8", newline="\n").write(s)
# 3. a stretched logo and the lockup clamp: the end card draws the lockup 200 wide and 60 tall, object-fit fill
c = rd + "/10-build/project/compositions/end-card.html"
t = open(c, encoding="utf-8").read()
t2 = t.replace('lockupImg.style.width = Math.max(300, v.lockup_w) + "px";', 'lockupImg.style.width = v.lockup_w + "px"; lockupImg.style.objectFit = "fill";')
t2 = t2.replace('lockupImg.style.height = "auto";', 'lockupImg.style.height = "60px";')
assert t2 != t
open(c, "w", encoding="utf-8", newline="\n").write(t2)
EOF
  mkdir -p "$RD2/10-build/project/assets/brand/mark" "$RD2/10-build/project/assets/brand/lockup"
  cp "$REPO_DIR/channels/flashfx/library/brand/mark/mark-gradient.png" "$RD2/10-build/project/assets/brand/mark/"
  cp "$REPO_DIR/channels/flashfx/library/brand/lockup/lockup-black.png" "$RD2/10-build/project/assets/brand/lockup/"
  t0=$EPOCHSECONDS
  ( cd "$SANDBOX" && env NO_COLOR=1 python "$SANDBOX/pipeline/lib/review" mechanical --run-dir "$RD2" ) >"$SANDBOX/mech2.out" 2>&1; rc=$?
  printf '    (mechanical on the planted copy took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "the mechanical checks run on the planted copy"
  M2="$RD2/12-review/mechanical.json"
  assert_eq "$(json_get "$M2" pass)" "false" "the planted copy fails"
  kinds="$(python -c 'import json, sys; print(" ".join(sorted({i["kind"] + ":" + str(i.get("instance")) for i in json.load(open(sys.argv[1], encoding="utf-8-sig"))["issues"]})))' "$M2")"
  printf '    kinds: %s\n' "$kinds"
  assert_true "planted: a FlashFX logo in the body of a non-FlashFX reel is caught (brand_outside on s4-card-1)" grep -q "brand_outside:s4-card-1" <<<"$kinds"
  assert_true "planted: a black lockup on ink is caught (brand_variant on the dark window card)" grep -q "brand_variant:s3-window-card-1" <<<"$kinds"
  assert_true "planted: the black lockup on ink also fails the readable contrast (brand_contrast)" grep -q "brand_contrast:s3-window-card-1" <<<"$kinds"
  assert_true "planted: a stretched logo is caught (brand_stretched on the end card)" grep -q "brand_stretched:s11-end-card-1" <<<"$kinds"
  assert_true "planted: a lockup under 300 px is caught (brand_small on the end card)" grep -q "brand_small:s11-end-card-1" <<<"$kinds"
  assert_true "planted: a CTA without the DM avatar is caught (brand_cta)" grep -q "brand_cta:" <<<"$kinds"
  assert_true "planted: a chip in the right rail of the lower half is caught (right_rail)" grep -q "right_rail:s6-dark-chip-2" <<<"$kinds"
  assert_true "planted: a chip above the safe top is caught (zone)" grep -q "zone:s9-light-chip-2" <<<"$kinds"
  assert_true "every planted issue carries a routing tag" python -c 'import json, sys; sys.exit(0 if all(i["tag"] in ("voice", "animation", "text", "transition", "sfx") for i in json.load(open(sys.argv[1], encoding="utf-8-sig"))["issues"]) else 1)' "$M2"

  # the routing rules (route.decide on synthetic reports)
  python - "$RD" <<'EOF' >/tmp/m11-route.txt
import os, sys
sys.path.insert(0, os.path.join("pipeline", "lib"))
from review import common as rc, route
ctx = rc.Ctx(sys.argv[1])
ok = {"pass": True, "issues": []}
good = {"scores": {k: 4 for k in route.SCORE_KEYS}, "branding_natural": True, "issues": [], "summary": "fine"}
r = route.decide(ctx, 1, ok, ok, ok, good)
print("pass", "ok" if r["pass"] and r["verdict"] == "pass" and not r["routing"]["reopen"] else r["verdict"])
low = dict(good, scores=dict(good["scores"], hierarchy=3), issues=[{"tag": "text", "text": "the s4 chip doubles the title", "scene": "s4"}])
r = route.decide(ctx, 1, ok, ok, ok, low)
print("text", "ok" if (not r["pass"] and r["verdict"] == "fix" and r["routing"]["owners"] == ["09b-text"] and r["routing"]["reopen"] == ["09b-text", "09c-transitions", "10-build", "11-sfx", "12-review"] and r["routing"]["activity"] == "fixing [text] issues (round 2, sonnet)") else str(r["routing"]))
mech_bad = {"pass": False, "issues": [{"tag": "animation", "kind": "right_rail", "text": "a chip in the rail"}]}
r = route.decide(ctx, 1, mech_bad, ok, ok, good)
print("code-fail", "ok" if (not r["pass"] and r["verdict"] == "fix" and r["routing"]["owners"] == ["09a-animations"] and r["routing"]["reopen"][0] == "09a-animations" and "09b-text" in r["routing"]["reopen"]) else str(r["routing"]))
voice = dict(good, scores=dict(good["scores"], sync=3), issues=[{"tag": "voice", "text": "the read feels flat in the stake"}])
r = route.decide(ctx, 1, ok, ok, ok, voice)
print("voice-flag", "ok" if (r["verdict"] == "flag" and not r["routing"]["reopen"] and r["flags"]) else r["verdict"])
voice2 = dict(voice, issues=[{"tag": "voice", "text": "the word \"Anthropic's\" is said wrong"}])
r = route.decide(ctx, 1, ok, ok, ok, voice2)
print("voice-word", "ok" if (r["verdict"] == "fix" and r["routing"]["owners"] == ["08-voiceover"] and r["routing"]["reopen"][0] == "08-voiceover" and "10-build" in r["routing"]["reopen"]) else str(r["routing"]))
r = route.decide(ctx, 4, ok, ok, ok, low)
print("escalated", "ok" if r["routing"]["activity"] == "fixing [text] issues (round 5, opus)" and r["routing"]["next_model"][0] == "opus" else r["routing"]["activity"])
r = route.decide(ctx, 5, ok, ok, ok, low)
print("cap", "ok" if (r["verdict"] == "cap" and not r["routing"]["reopen"] and r["flags"] and "still failing after 5 rounds" in r["flags"][0]) else str(r["verdict"]) + str(r["flags"])[:80])
ad = dict(good, scores=dict(good["scores"], look=3), branding_natural=False, branding_note="the lockup is huge")
r = route.decide(ctx, 1, ok, ok, ok, ad)
print("ad", "ok" if any(i.get("kind") == "branding_feel" and i["tag"] == "animation" for i in r["issues"]) and r["routing"]["owners"] == ["09a-animations"] else str(r["issues"])[:120])
fb = route.feedback_record(route.decide(ctx, 1, ok, ok, ok, low))
notes_b = route.stage_notes(fb, "09b-text"); notes_c = route.stage_notes(fb, "09c-transitions"); notes_a = route.stage_notes(fb, "09a-animations")
print("notes", "ok" if ("the s4 chip doubles the title" in notes_b and "Notes from the edit review (round 1)" in notes_b and "No issue was routed to this pass" in notes_c and notes_a == "") else repr((notes_b[:60], notes_c[:60], notes_a[:60])))
EOF
  sed 's/^/    /' /tmp/m11-route.txt
  assert_grep "^pass ok" /tmp/m11-route.txt "routing: every check passed and every score 4 or more is a pass"
  assert_grep "^text ok" /tmp/m11-route.txt "routing: a [text] issue reopens 09b-text, 09c, S10, S11 and S12 with the activity \"fixing [text] issues (round 2, sonnet)\""
  assert_grep "^code-fail ok" /tmp/m11-route.txt "routing: a failing code check routes by its tag even when the editor's scores pass"
  assert_grep "^voice-flag ok" /tmp/m11-route.txt "routing: a [voice] issue naming no word becomes a flag, not a loop"
  assert_grep "^voice-word ok" /tmp/m11-route.txt "routing: a [voice] issue naming a word in quotes reopens S8 and everything after it"
  assert_grep "^escalated ok" /tmp/m11-route.txt "routing: after the main rounds the fix escalates (opus: the test idea has no [important] label)"
  assert_grep "^cap ok" /tmp/m11-route.txt "routing: the fifth failed round exports with the NEEDS REVIEW notes"
  assert_grep "^ad ok" /tmp/m11-route.txt "routing: branding that feels like an ad is an [animation] issue"
  assert_grep "^notes ok" /tmp/m11-route.txt "routing: the re-run pass gets its notes, a later pass a context note, an untouched pass nothing"
  # the dummies
  for st in 11-sfx 12-review; do
    out="$(python "$STATE_PY" stages | cut -f1,4 | awk -F'\t' -v s="$st" '$1 == s {print $2}')"
    rm -rf "$SANDBOX/channels/flashfx/runs/dummy-$st"; mkdir -p "$SANDBOX/channels/flashfx/runs/dummy-$st/$st"
    printf '{"run_id":"d","idea":{"id":"i","text":"t","raw":"t"},"status":"running","stages":{},"flags":[],"rounds":{}}\n' > "$SANDBOX/channels/flashfx/runs/dummy-$st/state.json"
    ( cd "$SANDBOX" && REELS_DUMMY_SECONDS=0 bash "$SANDBOX/pipeline/stages/$st/dummy.sh" "$SANDBOX_M/channels/flashfx/runs/dummy-$st" ) >/dev/null 2>&1
    assert_true "the $st dummy's $out validates against the M11 schema" python "$VALIDATE" "$REPO_DIR/pipeline/stages/$st/schema.json" "$SANDBOX/channels/flashfx/runs/dummy-$st/$st/$out"
  done
  fake_whisper_off
  sandbox_cleanup
fi

# ------------------------------------------------------------------------------------------------ 2. the runner with the fake editor
if want 2; then
  section "2. S11 and S12 through the runner with the fake editor: a pass, then a planted [text] issue routed to 9b"
  sandbox_init --with-review
  fake_claude_on
  fake_whisper_on
  mkdir -p "$SANDBOX/fixtures"; director_answers "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m11/12-review.json" "$SANDBOX/fixtures/"
  export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
  RD="$(seed_run)"
  fast_mode
  t0=$EPOCHSECONDS
  run_once "$SANDBOX/pass.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_CLAUDE_REVIEW=no; rc=$?
  OUT="$SANDBOX/pass.out"
  grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
  printf '    (the pass took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "pass: the runner exits 0"
  assert_grep "${ts_regex}START  idea 1/1 .* \(resumed at adding sound effects, 11 stages done\)$" "$OUT" "pass: the run seeded from the frozen build resumes at S11"
  assert_grep "${ts_regex}INFO   S11: [0-9]+ sounds placed" "$OUT" "pass: S11's summary line"
  assert_grep "${ts_regex}STEP   adding sound effects done \([0-9hms]+\) -> reviewing: mechanical checks$" "$OUT" "pass: S11 done, the runner moves to S12"
  assert_grep "${ts_regex}INFO   S12: review round 1/5 of the draft$" "$OUT" "pass: S12 announces round 1 of 5"
  assert_grep "${ts_regex}INFO   S12: code checks: mechanical ok, style ok, audio ok \(voice WER [0-9.]+%\)$" "$OUT" "pass: the three code checks pass"
  assert_grep "${ts_regex}INFO   S12: review round 1 passed \(scores stop 4, hierarchy 4, look 4, variety 4, sync 5, sound 4, generic 4, requirements 4, energy 5\)$" "$OUT" "pass: the round passes with the editor's scores"
  assert_grep "${ts_regex}STEP   reviewing: mechanical checks done \([0-9hms]+\) -> rendering final video$" "$OUT" "pass: S12 done, the runner moves to S13"
  assert_grep "${ts_regex}DONE   exported flashfx-1 -> exports/flashfx-1/" "$OUT" "pass: the run continued to the (dummy) export"
  assert_not_grep "${ts_regex}(ERROR|BLOCK)" "$OUT" "pass: no ERROR or BLOCK line"
  assert_eq "$(fake_calls)" "1" "pass: one model call, the editor's"
  for a in "reviewing: mechanical checks" "reviewing: style check" "reviewing: audio check" "reviewing: edit review \(round 1/5\)"; do assert_grep "^activity: $a$" "$RD/12-review/stage.log" "activity \"$a\" was published by S12"; done
  check_cues "$RD" "pass"
  check_review_files "$RD" "pass" 1
  assert_eq "$(json_get "$RD/12-review/review.json" pass)" "true" "pass: review.json pass true"
  assert_eq "$(json_get "$RD/12-review/review.json" verdict)" "pass" "pass: the verdict is pass"
  assert_eq "$(json_get "$RD/12-review/review.json" edit_review.scores.sync)" "5" "pass: the editor's scores are recorded"
  assert_eq "$(python "$STATE_PY" get "$RD" rounds.review 0)" "0" "pass: no failed round counted"
  assert_grep "^# Role: qa" "$RD/12-review/prompt-r1.md" "pass: the prompt is the editor's"
  assert_grep "Scores \(1 to 5" "$RD/12-review/notes.md" "pass: notes.md written in prose"
  no_emdash_in "pass: no em dash in the stage files" "$RD/11-sfx/cues.json" "$RD/11-sfx/sound-map.txt" "$RD/12-review/review.json" "$RD/12-review/prompt-r1.md" "$RD/12-review/notes.md" "$SANDBOX/channels/flashfx/logs/runner.log"

  # ---- the planted [text] issue: the editor fails round 1 with two [text] issues, passes round 2
  fake_claude_reset
  rm -f "$SANDBOX/fixtures/12-review.json"; cp "$FIXTURES/fake/m11-text/"*.json "$SANDBOX/fixtures/"
  RD="$(seed_run)"
  t0=$EPOCHSECONDS
  run_once "$SANDBOX/text.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_CLAUDE_REVIEW=no; rc=$?
  OUT="$SANDBOX/text.out"
  grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
  printf '    (the text loop took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "text loop: the runner exits 0"
  assert_grep "${ts_regex}WARN   S12: review round 1 failed \(2 issues; scores stop 4, hierarchy 3, .*\): back to 09b-text, then every step after it runs again$" "$OUT" "text loop: round 1 fails and names 09b-text"
  assert_grep "${ts_regex}STEP   reviewing: mechanical checks done \([0-9hms]+\) -> planning text$" "$OUT" "text loop: S12 hands over to S9b"
  assert_grep "${ts_regex}INFO   S9: planning text for .*: asking the visual director \(sonnet, fine tuning after review round 1\) with the edit review's notes$" "$OUT" "text loop: the text pass runs again with the review's notes (sonnet fine tunes)"
  assert_grep "${ts_regex}STEP   planning text done \([0-9hms]+\) -> planning transitions$" "$OUT" "text loop: then the transitions pass"
  assert_grep "${ts_regex}STEP   planning transitions done \([0-9hms]+\) -> building visuals$" "$OUT" "text loop: then the build"
  assert_grep "${ts_regex}STEP   building visuals done \([0-9hms]+\) -> adding sound effects$" "$OUT" "text loop: then the sounds"
  assert_grep "${ts_regex}INFO   S12: review round 2/5 of the draft$" "$OUT" "text loop: round 2"
  assert_grep "${ts_regex}INFO   S12: review round 2 passed" "$OUT" "text loop: round 2 passes"
  assert_grep "${ts_regex}DONE   exported flashfx-[0-9]+ -> exports/flashfx-[0-9]+/ \([0-9]+ min, 1 issue fixed\)" "$OUT" "text loop: the run continued to the (dummy) export, with the review counted as one issue fixed"
  assert_not_grep "${ts_regex}(ERROR|BLOCK)" "$OUT" "text loop: no ERROR or BLOCK line"
  assert_eq "$(fake_calls)" "4" "text loop: four model calls: the editor twice, the director for 9b and 9c"
  assert_grep "^activity: fixing \[text\] issues \(round 2, sonnet\)$" "$RD/12-review/stage.log" "text loop: the activity \"fixing [text] issues (round 2, sonnet)\" was published"
  for st in 09b-text 09c-transitions 10-build 11-sfx 12-review; do
    assert_eq "$(python "$STATE_PY" get "$RD" "stages.$st.reopened" 0)" "1" "text loop: state.json counts one reopen of $st"
  done
  assert_eq "$(python "$STATE_PY" get "$RD" "stages.09a-animations.reopened" 0)" "0" "text loop: 09a-animations was not reopened"
  assert_eq "$(python "$STATE_PY" get "$RD" rounds.review 0)" "1" "text loop: rounds.review counts the failed round"
  assert_eq "$(python "$STATE_PY" get "$RD" issues.fixed 0)" "1" "text loop: the failed review counts as an issue fixed"
  assert_eq "$(python "$STATE_PY" get "$RD" issues.open 0)" "0" "text loop: no issue left open"
  assert_eq "$(json_get "$RD/12-review/review-r1.json" verdict)" "fix" "text loop: review-r1.json says fix"
  assert_eq "$(json_get "$RD/12-review/review-r2.json" verdict)" "pass" "text loop: review-r2.json says pass"
  assert_eq "$(json_get "$RD/12-review/review.json" round)" "2" "text loop: review.json is round 2"
  assert_grep "distributional convergence" "$RD/12-review/feedback.json" "text loop: feedback.json carries the editor's issue"
  assert_grep "Notes from the edit review \(round 1\)" "$RD/09b-text/prompt.md" "text loop: the text pass's prompt carries the review's notes"
  assert_grep "distributional convergence" "$RD/09b-text/prompt.md" "text loop: the notes quote the issue"
  assert_grep "No issue was routed to this pass" "$RD/09c-transitions/prompt.md" "text loop: the transitions pass gets the context note"
  assert_true "text loop: the second draft was rendered again (draft.mp4 newer than review-r1.json)" test "$RD/10-build/draft.mp4" -nt "$RD/12-review/review-r1.json"
  assert_true "text loop: cues.json is from the second sound pass (round 1 recorded)" test "$(json_get "$RD/11-sfx/cues.json" round)" = "1"
  check_review_files "$RD" "text loop" 2
  fake_whisper_off
  sandbox_cleanup
  fake_claude_off
fi

# ------------------------------------------------------------------------------------------------ 3. the cap
if want 3; then
  section "3. the cap: an editor that always fails with an [sfx] issue: 5 rounds, then the export with NEEDS REVIEW"
  sandbox_init --with-review
  fake_claude_on
  fake_whisper_on
  mkdir -p "$SANDBOX/fixtures"; director_answers "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m11-sfx/12-review.json" "$SANDBOX/fixtures/"
  export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
  RD="$(seed_run)"
  fast_mode
  t0=$EPOCHSECONDS
  run_once "$SANDBOX/cap.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_CLAUDE_REVIEW=no; rc=$?
  OUT="$SANDBOX/cap.out"
  grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN)" "$OUT" | sed 's/^/    /'
  printf '    (the cap loop took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "cap: the runner exits 0"
  for r in 1 2 3 4; do assert_grep "${ts_regex}WARN   S12: review round $r failed \(1 issues; scores .*sound 2.*\): back to 11-sfx, then every step after it runs again$" "$OUT" "cap: round $r fails and goes back to S11"; done
  assert_grep "${ts_regex}WARN   S12: review round 5 failed and the 5 rounds are used up: exporting with NEEDS REVIEW" "$OUT" "cap: round 5 ends the loop"
  assert_grep "${ts_regex}FLAG   needs review: edit review: still failing after 5 rounds \(3 main, 2 escalated on opus\); exported as it is. Scores: .*Open issues: \[sfx\]" "$OUT" "cap: the NEEDS REVIEW flag carries the scores and the notes"
  assert_grep "${ts_regex}DONE   exported flashfx-1 -> exports/flashfx-1/" "$OUT" "cap: the run still exports (the dummy export)"
  assert_not_grep "${ts_regex}(ERROR|BLOCK)" "$OUT" "cap: no ERROR or BLOCK line"
  assert_eq "$(fake_calls)" "5" "cap: five editor calls, one per round"
  for pair in "2, sonnet" "3, sonnet" "4, opus" "5, opus"; do assert_grep "^activity: fixing \[sfx\] issues \(round $pair\)$" "$RD/12-review/stage.log" "cap: the activity \"fixing [sfx] issues (round $pair)\" was published"; done
  assert_eq "$(python "$STATE_PY" get "$RD" rounds.review 0)" "5" "cap: rounds.review is 5"
  assert_eq "$(python "$STATE_PY" get "$RD" stages.11-sfx.reopened 0)" "4" "cap: S11 ran five times (reopened four times)"
  assert_eq "$(python "$STATE_PY" get "$RD" stages.12-review.reopened 0)" "4" "cap: S12 ran five times"
  assert_eq "$(python "$STATE_PY" get "$RD" stages.10-build.reopened 0)" "0" "cap: the build never ran again (an [sfx] issue stops at S11)"
  assert_eq "$(json_get "$RD/12-review/review.json" verdict)" "cap" "cap: the last review.json says cap"
  assert_eq "$(json_get "$RD/12-review/review.json" cap.reached)" "true" "cap: review.json records the cap"
  assert_grep "fewer sounds: at most 3 per 10 s" "$RD/11-sfx/cues.json" "cap: the sound pass applied the editor's note"
  assert_grep "the previous result stands" "$RD/12-review/stage.log" "cap: the unchanged composition's checks came from the cache in the later rounds"
  assert_grep "12-review: edit review: still failing after 5 rounds" "$RD/14-export/export.json" "cap: the export's NEEDS REVIEW block carries the review notes"
  for r in 1 2 3 4 5; do assert_file "$RD/12-review/review-r$r.json" "cap: review-r$r.json kept"; done
  fake_whisper_off
  sandbox_cleanup
  fake_claude_off
fi

# ------------------------------------------------------------------------------------------------ 4. the real editor
if want 4; then
  section "4. the real editor and the real transcription on the frozen draft (1 model call)"
  sandbox_init --with-review
  RD="$(seed_run)"
  t0=$EPOCHSECONDS
  run_stage 11-sfx "$RD" "$SANDBOX/real-s11.out"; rc=$?
  assert_rc 0 $rc "real: S11 runs"
  run_stage 12-review "$RD" "$SANDBOX/real-s12.out"; rc=$?
  grep -E "$ts_regex" "$SANDBOX/real-s12.out" | sed 's/^/    /'
  printf '    (S11 plus S12 took %s s)\n' "$((EPOCHSECONDS - t0))"
  assert_rc 0 $rc "real: S12 runs (whatever its verdict)"
  check_review_files "$RD" "real" 1
  R="$RD/12-review/review.json"
  assert_eq "$(json_get "$R" edit_review.answered)" "true" "real: the editor answered"
  assert_true "real: eight scores between 1 and 5" python -c 'import json, sys; s = json.load(open(sys.argv[1], encoding="utf-8-sig"))["edit_review"]["scores"]; sys.exit(0 if len(s) == 8 and all(1 <= int(v) <= 5 for v in s.values()) else 1)' "$R"
  assert_true "real: every issue carries a tag" python -c 'import json, sys; sys.exit(0 if all(i["tag"] in ("voice", "animation", "text", "transition", "sfx") for i in json.load(open(sys.argv[1], encoding="utf-8-sig"))["issues"]) else 1)' "$R"
  assert_eq "$(json_get "$R" mechanical.pass)" "true" "real: the mechanical checks pass on the frozen draft (the branding checks included)"
  assert_eq "$(json_get "$R" style.pass)" "true" "real: the style check passes"
  assert_true "real: the voice is intelligible in the mix with the real faster-whisper (WER $(json_get "$R" audio.wer_pct) percent)" python -c 'import json, sys; sys.exit(0 if float(json.load(open(sys.argv[1], encoding="utf-8-sig"))["audio"]["wer_pct"]) < 5 else 1)' "$R"
  printf '    editor: verdict %s, scores %s\n    summary: %s\n' "$(json_get "$R" verdict)" "$(json_get "$R" edit_review.scores)" "$(json_get "$R" edit_review.summary | cut -c1-300)"
  python -c 'import json, sys
for i in json.load(open(sys.argv[1], encoding="utf-8-sig"))["issues"]: print("    issue [%s] %s" % (i["tag"], i["text"][:160]))' "$R"
  if [ "$FAIL_N" -eq 0 ] && [ -n "${M11_FREEZE:-}" ]; then
    mkdir -p "$FROZEN/11-sfx" "$FROZEN/12-review"
    cp "$RD/11-sfx/cues.json" "$RD/11-sfx/sound-map.txt" "$FROZEN/11-sfx/"
    [ -f "$RD/11-sfx/sound-map-hook2.txt" ] && cp "$RD/11-sfx/sound-map-hook2.txt" "$FROZEN/11-sfx/"
    for f in review.json mechanical.json style.json audio.json edit-r1.json notes.md; do cp "$RD/12-review/$f" "$FROZEN/12-review/" 2>/dev/null || true; done
    pass "frozen: the real 11-sfx (cues.json, sound-map.txt) and 12-review (review.json, the check reports, the editor's answer, notes.md) outputs copied to pipeline/tests/fixtures/runs/test-idea/ (M11_FREEZE; the wav and mp4 files stay out of git)"
  fi
  sandbox_cleanup
fi

# ------------------------------------------------------------------------------------------------ 5. em dashes
if want 5; then
  section "5. no em dash in the files M11 wrote"
  files=(pipeline/bin/mix-sfx pipeline/tests/test-m11.sh pipeline/tests/materialize-project.py build/M11/patch-1.py build/M11/patch-2.py)
  for f in pipeline/lib/sfx/*.py pipeline/lib/review/*.py pipeline/stages/11-sfx/* pipeline/stages/12-review/* pipeline/tests/fixtures/fake/m11/*.json pipeline/tests/fixtures/fake/m11-text/*.json pipeline/tests/fixtures/fake/m11-sfx/*.json; do
    [ -f "$f" ] && files+=("$f")
  done
  no_emdash_in "no em dash in the M11 files" "${files[@]}"
fi

test_summary
