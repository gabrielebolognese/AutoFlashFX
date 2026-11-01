#!/usr/bin/env bash
# test-m7.sh: acceptance test for M7 (Voiceover: S8). Section 3 uses the real engine (Kokoro af_bella through the
# interpreter of library/voice/engine.txt, or the spec's defaults when that file is missing or names another engine)
# and the real faster-whisper; sections 1 and 2 use the fake workers in pipeline/tests/fakes (no engine, no model).
#   bash pipeline/tests/test-m7.sh                    everything (5 to 15 minutes, dominated by the real S8)
#   M7_SECTIONS="1 2" bash pipeline/tests/test-m7.sh  only those sections (no engine, no model, a few minutes)
#   M7_FREEZE=1 bash pipeline/tests/test-m7.sh        also copy the real 08-voiceover outputs (words.json,
#                                                    words_hook2.json, voiceover.json, vo.wav, vo_hook2.wav) into
#                                                    pipeline/tests/fixtures/runs/test-idea/; the wavs stay out of git
#                                                    (*.wav) and section 3 adds them whenever they are missing
#
# Covers (BUILD_SPEC.md section 12, M7, and PLAN.md M7):
#   1. units, no engine: engine.txt parsing (the full block, missing lines, a missing file, another engine, bad
#      numbers), the word error rate and its normalizer (split and joined words, digits and years, spelling
#      variants, possessives, inline phonemes), the automatic respelling rules, pronunciations.txt (a respelling,
#      inline phonemes, no double wrapping), the silence detector and the energy helper on a synthetic wav, the
#      preflight's voice check (an interpreter without kokoro stops the runner with the exact fix; the fakes pass)
#   2. S8 through the whole runner with the fake engine and the fake transcriber, from the frozen M6 outputs: the
#      happy path (vo.wav 48 kHz mono, words.json with the exact timeline: 0.05 s lead, 0.1 s gaps, the 1.0 s breath
#      after the hook, 0.2 s tail; no model call), the ladder (a line fixed by the respelling of an acronym, a line
#      fixed by S7's one-line rewrite, a slow line rewritten then flagged), the flag path (one misheard word under
#      8 percent after the rewrite), the block path (two misheard words above 8 percent), the engine crash (a code
#      error: ERROR, the review loop, a block with the fake reviewer), the engine hang (killed after the timeout),
#      the dummy stage's outputs against the schema
#   3. S8 on the frozen script with the real Kokoro and faster-whisper: vo.wav and vo_hook2.wav at 48 kHz mono,
#      -14 LUFS within 1 LU and true peak at most -1.5 dBTP, words.json valid with every beat covered and monotonic
#      timestamps, no pause of min_pause_s or longer except the hook breath, 5 spot-checked word timestamps against
#      the audio, every line's word error rate within 3 percent or the ladder visible in the log, the total length
#      against the estimate, the measured speed and pace printed (for DECISIONS.md), the preflight's import check
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
VO="$REPO_DIR/pipeline/lib/voiceover.py"
SECTIONS="${M7_SECTIONS:-1 2 3}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
FROZEN="$FIXTURES/runs/test-idea"
FAKES="$REPO_DIR/pipeline/tests/fakes"
SCHEMA="$REPO_DIR/pipeline/stages/08-voiceover/schema.json"
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '
LATER_DUMMIES="$(dummy_after 08-voiceover)"

vo() { python "$VO" "$@"; }
state_get() { python "$STATE_PY" get "$@"; }
run_once() {  # run_once <outfile> [env...]: the sandbox's own run.sh (REELS_REPO is the sandbox copy of the repo)
  local out="$1"; shift
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 3600 bash "$SANDBOX/run.sh" --once ) > "$out" 2>&1
}
fake_calls() { python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG" 2>/dev/null || echo 0; }
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
jf() { python -c 'import json, sys; d = json.loads(sys.argv[1]); v = d.get(sys.argv[2], ""); print(json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict, bool)) else v)' "$1" "$2"; }
seed_run() {  # a run in the sandbox with S1 to S7 done from the frozen outputs (04-angle stays skipped); prints the run dir
  local raw id created rd st
  raw="$(tr -d '\r' < "$FROZEN/idea.txt")"
  printf '{%s}\n' "$raw" > "$SANDBOX/ideas.txt"
  id="$(printf '%s' "$raw" | python pipeline/lib/ideas.py id)"
  created="$(printf '%s' "$raw" | python "$STATE_PY" new --runs "$SANDBOX_M/runs" --id "$id")"
  rd="$(jf "$created" run_dir)"
  for st in 01-research 02-expansion 03-gate 05-hooks 06-judge 07-script; do
    cp -r "$FROZEN/$st/." "$rd/$st/"
    python "$STATE_PY" stage-start "$rd" "$st" >/dev/null
    python "$STATE_PY" stage-done "$rd" "$st" --schemas "$REPO_DIR/pipeline/stages" >/dev/null \
      || printf 'seed_run: the frozen %s did not validate\n' "$st" >&2
  done
  printf '%s' "$rd"
}
fake_voice_on() {  # the fake engine and transcriber (the project's python runs them), with their state in the sandbox
  export REELS_TTS_PYTHON=python REELS_TTS_WORKER="$(mixed "$FAKES/kokoro_worker.py")"
  export REELS_WHISPER_PYTHON=python REELS_WHISPER_WORKER="$(mixed "$FAKES/whisper_worker.py")"
  export FAKE_WHISPER_STATE="$SANDBOX_M/fake-whisper-state" FAKE_TTS_LOG="$SANDBOX_M/fake-tts.log"
  rm -rf "$SANDBOX/fake-whisper-state"; : > "$SANDBOX/fake-tts.log"
}
fake_voice_off() { unset REELS_TTS_PYTHON REELS_TTS_WORKER REELS_WHISPER_PYTHON REELS_WHISPER_WORKER FAKE_WHISPER_STATE FAKE_TTS_LOG FAKE_WHISPER_GARBLE FAKE_TTS_SLOW FAKE_TTS_MODE FAKE_WHISPER_MODE; }
wav_info() {  # wav_info <file>: "rate channels width_bits seconds"
  python -c 'import sys, wave
with wave.open(sys.argv[1], "rb") as w: print(w.getframerate(), w.getnchannels(), w.getsampwidth() * 8, round(w.getnframes() / w.getframerate(), 3))' "$1"
}
timeline_ok() {  # timeline_ok <words.json> <n beats>: the exact layout (lead, gaps, breath, tail) and monotonic words inside their beats
  python - "$1" "$2" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); n = int(sys.argv[2]); bad = []
beats = d["beats"]; words = d["words"]
if len(beats) != n: bad.append(f"{len(beats)} beats, expected {n}")
if abs(beats[0]["start_ms"] - 50) > 2: bad.append(f"lead {beats[0]['start_ms']} ms, expected 50")
for a, b in zip(beats, beats[1:]):
    gap = b["start_ms"] - a["end_ms"]
    want = 1000 if a["type"] == "hook" else 100
    if abs(gap - want) > 2: bad.append(f"gap after {a['id']} is {gap} ms, expected {want}")
    if b["end_ms"] <= b["start_ms"]: bad.append(f"{b['id']} is empty")
tail = d["duration_ms"] - beats[-1]["end_ms"]
if abs(tail - 200) > 3: bad.append(f"tail {tail} ms, expected 200")
br = d.get("breath")
if not br or br["after"] != beats[0]["id"] or abs(br["start_ms"] - beats[0]["end_ms"]) > 2 or abs(br["end_ms"] - beats[1]["start_ms"]) > 2: bad.append(f"breath {br}")
by = {b["id"]: b for b in beats}
last = -1
for w in words:
    if w["beat"] not in by: bad.append(f"word {w['word']} in unknown beat {w['beat']}"); continue
    b = by[w["beat"]]
    if w["start_ms"] < last: bad.append(f"word {w['word']} starts at {w['start_ms']} before {last}")
    if w["end_ms"] < w["start_ms"]: bad.append(f"word {w['word']} ends before it starts")
    if w["start_ms"] < b["start_ms"] - 2 or w["end_ms"] > b["end_ms"] + 2: bad.append(f"word {w['word']} ({w['start_ms']}-{w['end_ms']}) outside {b['id']} ({b['start_ms']}-{b['end_ms']})")
    last = w["start_ms"]
covered = {w["beat"] for w in words}
missing = [b["id"] for b in beats if b["id"] not in covered]
if missing: bad.append(f"beats without words: {missing}")
print(f"{len(beats)} beats, {len(words)} words, {d['duration_ms']} ms, breath {br['seconds'] if br else None} s" + (f"; problems: {bad[:6]}" if bad else ""))
sys.exit(1 if bad else 0)
EOF
}
spoken_words() {  # spoken_words <script.json>: the number of spoken tokens with a letter or digit
  python -c 'import json, re, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); print(sum(len([t for t in b["spoken"].split() if re.search(r"[A-Za-z0-9]", t)]) for b in d["beats"]))' "$1"
}
write_engine_file() {  # write_engine_file <path> <python> [extra lines...]
  local path="$1" py="$2"; shift 2
  { printf 'engine = kokoro\npython = %s\nvoice = af_bella\nlang = a\nspeed = 1.0\nsilence_threshold_db = -40\nmin_pause_s = 0.3\nkeep_pause_s = 0.1\nbreath_after_hook_s = 1.0\n' "$py"; for l in "$@"; do printf '%s\n' "$l"; done; } > "$path"
}
SYS_PY="$(mixed "$(command -v python)")"

# ----------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. units: engine.txt, the word error rate, respelling, pronunciations, silences, the preflight's voice check (no engine)"
sandbox_init
W="$SANDBOX/units"; mkdir -p "$W"; WM="$SANDBOX_M/units"
# engine.txt
write_engine_file "$W/engine-full.txt" "$SYS_PY" "speed = 1.1" >/dev/null   # the later speed line wins over the earlier one
res="$(REELS_ENGINE_FILE="$WM/engine-full.txt" vo engine)"
assert_eq "$(jf "$res" status)" "file" "engine: a full kokoro block is read from the file"
assert_eq "$(python -c 'import json,sys; e=json.loads(sys.argv[1])["engine"]; print(e["voice"], e["lang"], e["speed"], e["silence_threshold_db"], e["min_pause_s"], e["keep_pause_s"], e["breath_after_hook_s"])' "$res")" "af_bella a 1.1 -40.0 0.3 0.1 1.0" "engine: every setting comes from the file (numbers parsed, the last line of a key wins)"
assert_eq "$(python -c 'import json,sys; print(json.loads(sys.argv[1])["engine"]["python"])' "$res")" "$SYS_PY" "engine: the interpreter is the file's python line"
assert_eq "$(REELS_ENGINE_FILE="$WM/engine-full.txt" vo engine --brief)" "kokoro af_bella" "engine --brief: the banner text"
printf 'engine = kokoro\npython = %s\n' "$SYS_PY" > "$W/engine-short.txt"
res="$(REELS_ENGINE_FILE="$WM/engine-short.txt" vo engine)"
assert_eq "$(jf "$res" status)" "file+defaults" "engine: a file with only engine and python takes the defaults for the rest"
assert_true "engine: the note names the missing lines" grep -q "has no line for voice, lang, speed, silence_threshold_db, min_pause_s, keep_pause_s, breath_after_hook_s" <<<"$res"
assert_eq "$(python -c 'import json,sys; e=json.loads(sys.argv[1])["engine"]; print(e["voice"], e["speed"], e["breath_after_hook_s"])' "$res")" "af_bella 1.0 1.0" "engine: the spec's defaults fill them"
res="$(REELS_ENGINE_FILE="$WM/none.txt" vo engine)"
assert_eq "$(jf "$res" status)" "defaults" "engine: a missing file gives the defaults"
assert_true "engine: the missing file is noted with the defaults in use" grep -q "is missing: the kokoro defaults of BUILD_SPEC.md 2.5 are used" <<<"$res"
assert_eq "$(python -c 'import json,sys; e=json.loads(sys.argv[1])["engine"]; print(e["engine"], e["voice"])' "$res")" "kokoro af_bella" "engine: kokoro af_bella by default"
printf 'engine = turbo\npython = %s\nseed = 7\n' "$SYS_PY" > "$W/engine-turbo.txt"
res="$(REELS_ENGINE_FILE="$WM/engine-turbo.txt" vo engine)"
assert_eq "$(jf "$res" status)" "defaults-unsupported" "engine: another engine named means the kokoro defaults, never that engine"
assert_true "engine: the note says what to rewrite" grep -q "names engine 'turbo'; this pipeline voices every reel with kokoro af_bella" <<<"$res"
assert_ne "$(python -c 'import json,sys; print(json.loads(sys.argv[1])["engine"]["python"])' "$res")" "$SYS_PY" "engine: the other engine's interpreter is not used either (the default kokoro interpreter is)"
write_engine_file "$W/engine-bad.txt" "$SYS_PY" "keep_pause_s = 0.5" "speed = fast" >/dev/null
res="$(REELS_ENGINE_FILE="$WM/engine-bad.txt" vo engine)"
assert_eq "$(python -c 'import json,sys; print(len(json.loads(sys.argv[1])["problems"]))' "$res")" "2" "engine: a keep longer than min_pause and a non-numeric speed are problems"
# the word error rate
w() { vo wer --ref "$1" --hyp "$2"; }
assert_eq "$(jf "$(w 'Why your Claude Code cards all look identical.' 'Why your Claude code cards all look identical?')" wer_pct)" "0.0" "wer: case and punctuation do not count"
assert_eq "$(jf "$(w 'a b c d e f g h i j' 'a b c d e f g h i k')" wer_pct)" "10.0" "wer: one substitution in ten words is 10 percent"
assert_eq "$(jf "$(w 'a b c d e f g h i j' 'a b c d e f g h i')" wer_pct)" "10.0" "wer: one deletion in ten words is 10 percent"
assert_eq "$(jf "$(w 'a b c d e' 'a b c d e extra')" wer_pct)" "20.0" "wer: one insertion in five words is 20 percent"
assert_eq "$(jf "$(w 'Type slash plugin install frontend design at claude plugins official. Pick a scope.' 'Type slash plug -in install frontend design at Claude plug -ins official. Pick a scope.')" wer_pct)" "0.0" "wer: plugin heard as plug -in is the same word"
assert_eq "$(jf "$(w 'flash F X does it in four to six steps as of November twenty twenty six' 'Flash FX does it in 4 to 6 steps as of November 2026')" wer_pct)" "0.0" "wer: spelled letters, digits and a year read as the line says it"
assert_eq "$(jf "$(w 'One million one hundred thirty four thousand installs' '1,134,000 installs')" wer_pct)" "0.0" "wer: a long number in digits"
assert_eq "$(jf "$(w "Anthropic's skill file names it: rounded cards, one radius, same grey shadow." "Anthropic skill file names it, rounded cards, one radius, same gray shadow.")" wer_pct)" "0.0" "wer: a possessive heard without its s and a British spelling are not errors"
assert_eq "$(jf "$(w '[Claude](/klɔd/) plans it' 'Claude plans it')" wer_pct)" "0.0" "wer: inline phonemes compare as the word"
res="$(w 'Why your Claude Code cards all look identical.' 'Why your cloud code cards all look identical?')"
assert_eq "$(jf "$res" wer_pct)" "12.5" "wer: a misheard word in eight is 12.5 percent"
assert_eq "$(jf "$res" misheard)" '["Claude"]' "wer: the misheard word is named"
assert_eq "$(jf "$res" heard)" '["claude -> cloud"]' "wer: and what was heard instead"
# respelling
assert_eq "$(vo respell FlashFX)" "Flash F X" "respell: camelCase split and the acronym spelled out"
assert_eq "$(vo respell API)" "A P I" "respell: an acronym letter by letter"
assert_eq "$(vo respell GPT4)" "G P T four" "respell: letters and a digit"
assert_eq "$(vo respell add-idea.sh)" "add idea dot sh" "respell: a file name"
assert_eq "$(vo respell frontend-design@claude-plugins-official)" "frontend design at claude plugins official" "respell: an at-sign and dashes"
assert_eq "$(vo respell Claude)" "" "respell: a plain word has no rule (the rewrite is next)"
assert_eq "$(vo respell identical)" "" "respell: a plain lowercase word has no rule"
# pronunciations.txt
printf '# comment\nFlashFX = flash F X\nClaude = /kl%sd/\n\nbad line without equals\n' "$(printf '\xc9\x94')" > "$W/pron.txt"
res="$(vo pronounce --text "Claude Code and FlashFX's cards. FlashFX again, claude too." --file "$WM/pron.txt")"
assert_eq "$(jf "$res" text)" "[Claude](/klɔd/) Code and flash F X's cards. flash F X again, [claude](/klɔd/) too." "pronounce: a respelling and inline phonemes, whole words, any case"
assert_eq "$(jf "$res" applied)" '["FlashFX -> flash F X", "Claude -> /klɔd/"]' "pronounce: the applied entries are listed"
res2="$(vo pronounce --text "$(jf "$res" text)" --file "$WM/pron.txt")"
assert_eq "$(jf "$res2" text)" "$(jf "$res" text)" "pronounce: applying the file again changes nothing (no double wrapping)"
res="$(vo pronounce --text "the API and the api" --respell "API=A P I")"
assert_eq "$(jf "$res" text)" "the A P I and the api" "pronounce: a reel's own respelling is exact-case and whole-word"
# silences and energy on a synthetic wav: 0.05 s lead, 0.4 s tone, 0.5 s pause, 0.3 s tone, 1.0 s pause, 0.2 s tone, 0.2 s tail
python - "$WM/synth.wav" <<'EOF'
import math, struct, sys, wave
sr = 48000
def tone(s): return [int(9000 * math.sin(2 * math.pi * 220 * i / sr)) for i in range(int(sr * s))]
def gap(s): return [0] * int(sr * s)
pcm = gap(0.05) + tone(0.4) + gap(0.5) + tone(0.3) + gap(1.0) + tone(0.2) + gap(0.2)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(struct.pack("<%dh" % len(pcm), *pcm))
EOF
res="$(vo silences --wav "$WM/synth.wav" --min-s 0.1)"
assert_eq "$(python -c 'import json,sys; d=json.loads(sys.argv[1]); print([r["seconds"] for r in d["runs"]], d["longest_s"])' "$res")" "[0.5, 1.0, 0.2] 1.0" "silences: the three pauses of 0.1 s or longer, the lead under 0.1 s left out"
assert_eq "$(vo energy --wav "$WM/synth.wav" --from-ms 100 --to-ms 400 | cut -d. -f1)" "-14" "energy: the tone's level (a 9000 of 32768 sine is -14 dBFS RMS)"
assert_true "energy: silence is far below -40 dB" python -c 'import sys; sys.exit(0 if float(sys.argv[1]) < -60 else 1)' "$(vo energy --wav "$WM/synth.wav" --from-ms 500 --to-ms 900)"
# the preflight's voice check
mkdir -p "$SANDBOX/library/voice"
write_engine_file "$SANDBOX/library/voice/engine.txt" "$SYS_PY" >/dev/null   # the project's python has no kokoro
( cd "$SANDBOX" && NO_COLOR=1 bash "$REPO_DIR/pipeline/bin/preflight" ) > "$SANDBOX/preflight-bad.out" 2>&1; rc=$?
assert_rc 3 $rc "preflight: an engine.txt whose interpreter cannot import kokoro is a systemic stop (exit 3)"
assert_grep "cannot import kokoro" "$SANDBOX/logs/STOPPED.md" "preflight: STOPPED.md names the import failure"
assert_grep "write library/voice/engine.txt as in BUILD_SPEC.md 2.5" "$SANDBOX/logs/STOPPED.md" "preflight: STOPPED.md gives the exact fix"
printf 'engine = kokoro\npython = C:/nowhere/python.exe\n' > "$SANDBOX/library/voice/engine.txt"
( cd "$SANDBOX" && NO_COLOR=1 bash "$REPO_DIR/pipeline/bin/preflight" ) > "$SANDBOX/preflight-missing.out" 2>&1; rc=$?
assert_rc 3 $rc "preflight: an interpreter that does not exist is a systemic stop"
assert_grep "C:/nowhere/python.exe does not exist" "$SANDBOX/logs/STOPPED.md" "preflight: the missing interpreter is named"
fake_voice_on
( cd "$SANDBOX" && NO_COLOR=1 bash "$REPO_DIR/pipeline/bin/preflight" ) > "$SANDBOX/preflight-fake.out" 2>&1; rc=$?
assert_rc 0 $rc "preflight: with the fake workers the import checks are skipped and the preflight passes"
assert_grep "${ts_regex}WARN   preflight: REELS_TTS_WORKER is set" "$SANDBOX/preflight-fake.out" "preflight: and says a fake engine is in use"
fake_voice_off
rm -f "$SANDBOX/library/voice/engine.txt"
( cd "$SANDBOX" && NO_COLOR=1 REELS_TTS_WORKER=x REELS_WHISPER_WORKER=x bash "$REPO_DIR/pipeline/bin/preflight" ) > "$SANDBOX/preflight-none.out" 2>&1; rc=$?
assert_grep "${ts_regex}WARN   preflight: library/voice/engine.txt is missing: the kokoro defaults" "$SANDBOX/preflight-none.out" "preflight: a missing engine.txt is a warning that names the defaults"
fi

# ----------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. S8 through the runner with the fake engine and transcriber, from the frozen M6 outputs"
sandbox_init --with-pipeline
fake_claude_on
mkdir -p "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m7/"*.json "$SANDBOX/fixtures/"
export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
fake_voice_on
RD="$(seed_run)"
fast_mode
run_once "$SANDBOX/happy.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/happy.out"; S="$RD/08-voiceover"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "happy path: the runner exits 0"
assert_grep "${ts_regex}START  idea 1/1 .* \(resumed at generating voiceover, 6 stages done\)$" "$OUT" "START: the run seeded from the frozen outputs resumes at S8"
assert_grep "${ts_regex}INFO   S8: kokoro af_bella \(the defaults, no engine.txt\), speed 1: 11 beats plus hook 2, 118 spoken words at [0-9]+ wpm; pauses of 0.3 s or more cut to 0.1 s below -40 dB, 1 s breath after the hook$" "$OUT" "S8: the setup line (engine, voice, where the config came from, the lines, the tightening values)"
assert_grep "${ts_regex}INFO   S8: first pass: every line transcribes back within 3% word error rate \(worst 0.0%\)$" "$OUT" "S8: every line passes the word error rate check"
assert_grep "${ts_regex}INFO   S8: generated 12 lines in [0-9]+ s \(.*x real time for [0-9.]+ s of raw voice, model load [0-9]+ s\), aligned in [0-9]+ s; pace [0-9]+ wpm after tightening \([0-9]+ on speech alone\)$" "$OUT" "S8: the speed and pace line"
assert_grep "${ts_regex}INFO   S8: vo.wav [0-9.]+ s at -1[345]\.[0-9]+ LUFS, true peak -[0-9.]+ dBTP \([0-9] passes\); words.json 118 words, 11 beats; vo_hook2.wav [0-9.]+ s$" "$OUT" "S8: the outputs line (loudness on target, 118 words, hook 2)"
assert_grep "${ts_regex}STEP   generating voiceover done \([0-9hms]+\) -> planning animations$" "$OUT" "S8 done, the runner moves to S9a"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the run continued to the (dummy) export"
assert_not_grep "${ts_regex}(ERROR|BLOCK|FLAG)" "$OUT" "no ERROR, BLOCK or FLAG line"
assert_eq "$(fake_calls)" "0" "no model call on the happy path"
assert_file "$S/vo.wav" "vo.wav written"
assert_eq "$(wav_info "$S/vo.wav" | cut -d' ' -f1-3)" "48000 1 16" "vo.wav is 48 kHz mono 16-bit"
assert_file "$S/vo_hook2.wav" "vo_hook2.wav written"
assert_eq "$(wav_info "$S/vo_hook2.wav" | cut -d' ' -f1-3)" "48000 1 16" "vo_hook2.wav is 48 kHz mono 16-bit"
assert_true "words.json validates against schema.json" python pipeline/bin/validate-json "$SCHEMA" "$S/words.json"
assert_true "words_hook2.json validates against schema.json" python pipeline/bin/validate-json "$SCHEMA" "$S/words_hook2.json"
summary="$(timeline_ok "$S/words.json" 11)"; rc=$?
assert_rc 0 $rc "words.json: 11 beats with the exact layout (0.05 s lead, 0.1 s gaps, the 1.0 s breath after the hook, 0.2 s tail), monotonic words inside their beats, every beat covered ($summary)"
assert_eq "$(json_get "$S/words.json" words | python -c 'import json,sys; print(len(json.load(sys.stdin)))')" "$(spoken_words "$RD/07-script/script.json")" "words.json has one entry per spoken word of the script"
assert_eq "$(json_get "$S/words_hook2.json" beats.0.id)" "hook2" "words_hook2.json: the beat is hook2"
assert_eq "$(json_get "$S/words.json" engine) $(json_get "$S/words.json" voice) $(json_get "$S/words.json" sample_rate)" "kokoro af_bella 48000" "words.json: engine, voice, sample rate"
assert_true "words.json: the lead and the breath are silence in vo.wav" python -c '
import json, sys
sys.path.insert(0, "pipeline/lib"); import voiceover as v
d = json.load(open(sys.argv[1], encoding="utf-8")); br = d["breath"]
ok = v.window_db(sys.argv[2], 0, 45) < -60 and v.window_db(sys.argv[2], br["start_ms"] + 20, br["end_ms"] - 20) < -60 and v.window_db(sys.argv[2], d["beats"][0]["start_ms"] + 20, d["beats"][0]["end_ms"] - 20) > -30
sys.exit(0 if ok else 1)' "$S/words.json" "$S/vo.wav"
assert_eq "$(json_get "$S/voiceover.json" verdict.status) $(json_get "$S/voiceover.json" timing.calls)" "ok 2" "voiceover.json: verdict ok, one generation call and one transcription call"
for a in "generating voiceover (beat 3/12)" "tightening silences" "aligning words" "normalizing loudness"; do
  assert_grep "^activity: $(printf '%s' "$a" | sed 's/[()]/\\&/g')$" "$S/stage.log" "activity \"$a\" was published"
done
no_emdash_in "no em dash in the stage files" "$S/words.json" "$S/words_hook2.json" "$S/voiceover.json" "$S/stage.log" "$SANDBOX/logs/runner.log"
# the dummy stage's outputs against the schema
python "$STATE_PY" stage-start "$RD" 08-voiceover >/dev/null 2>&1 || true
( cd "$SANDBOX" && REELS_DUMMY_SECONDS=0 bash "$REPO_DIR/pipeline/stages/08-voiceover/dummy.sh" "$RD" ) >/dev/null 2>&1
assert_true "dummy.sh: its words.json validates against the schema" python pipeline/bin/validate-json "$SCHEMA" "$S/words.json"
assert_true "dummy.sh: its words_hook2.json validates against the schema" python pipeline/bin/validate-json "$SCHEMA" "$S/words_hook2.json"

# ---- the ladder: an acronym fixed by respelling, a word fixed by S7's rewrite, a slow line rewritten then flagged
sandbox_init --with-pipeline
fake_claude_reset; export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"; mkdir -p "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m7/"*.json "$SANDBOX/fixtures/"
fake_voice_on
RD="$(seed_run)"
run_once "$SANDBOX/ladder.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_WHISPER_GARBLE="b5:AI:*;b9:scope:1" FAKE_TTS_SLOW="b7=1.4"; rc=$?
OUT="$SANDBOX/ladder.out"; S="$RD/08-voiceover"
grep -E "$ts_regex(STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "ladder: the runner exits 0"
assert_grep "${ts_regex}WARN   S8: first pass: 2 of 12 lines misheard: b5 WER 9.1%: ai -> xx; b9 WER 7.7%: scope -> xx$" "$OUT" "ladder: the first pass names the misheard lines and words"
assert_grep "${ts_regex}WARN   S8: line b5 misheard \(WER 9.1%: ai -> xx\), fixing the pronunciation: AI -> A I$" "$OUT" "ladder step 1: the acronym is respelled"
assert_grep "${ts_regex}INFO   S8: line b5 ok after the pronunciation fix \(WER 0.0%\)$" "$OUT" "ladder step 1: the respelled line passes"
assert_grep "${ts_regex}WARN   S8: line b9 still misheard \(WER 7.7%: scope -> xx\) after the pronunciation step, rewriting it through S7$" "$OUT" "ladder step 2: a plain word has no respelling, the line goes to S7"
assert_grep "${ts_regex}INFO   S8: line b9 rewritten by S7 in simpler words: \"Type the plugin install command for frontend design in Claude Code. Pick a scope.\"$" "$OUT" "ladder step 2: S7 rewrote the line (the fake's answer) and S8 says so"
assert_grep "^  S7: .*INFO   S7: line b9 rewritten in simpler words: " "$RD/08-voiceover/stage.log" "ladder step 2: S7's own log lines land in the stage log with the S7 prefix"
assert_grep "${ts_regex}INFO   S8: line b9 ok after the rewrite \(WER 0.0%\)$" "$OUT" "ladder step 2: the rewritten line passes"
assert_grep "${ts_regex}WARN   S8: line b7 runs [2-9][0-9]% over its estimate \([0-9.]+ s against [0-9.]+ s at [0-9]+ wpm\), rewriting it through S7$" "$OUT" "overrun: a slow line is sent to S7"
assert_grep "${ts_regex}FLAG   needs review: voice: line b7 runs [0-9]+% over its estimate \([0-9.]+ s against [0-9.]+ s at [0-9]+ wpm\) after a rewrite$" "$OUT" "overrun: still slow after the rewrite, so a NEEDS REVIEW flag"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "ladder: the run continued to the export"
assert_not_grep "${ts_regex}(ERROR|BLOCK)" "$OUT" "ladder: no ERROR or BLOCK"
assert_eq "$(fake_calls)" "2" "ladder: two model calls, S7's rewrites of b9 and b7"
assert_eq "$(json_get "$S/voiceover.json" verdict.status)" "flag" "ladder: the verdict is flag"
assert_true "ladder: the respelling is recorded in voiceover.json" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); b5 = next(l for l in d["lines"] if l["id"] == "b5")
sys.exit(0 if b5["respellings"] == {"AI": "A I"} and b5["respelled"] and b5["status"] == "ok" else 1)' "$S/voiceover.json"
assert_eq "$(json_get "$RD/07-script/script.json" rewrites | python -c 'import json,sys; r=json.load(sys.stdin); print(",".join(e["beat"] for e in r))')" "b9,b7" "ladder: script.json records both rewrites"
assert_grep "^activity: fixing pronunciation \(line b5\)$" "$S/stage.log" "ladder: the activity text while fixing a pronunciation"
assert_grep "^activity: rewriting line b9$" "$S/stage.log" "ladder: the activity text while rewriting"
assert_true "ladder: words.json keeps the script's word AI timed from the respelled A I" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); ws = [w for w in d["words"] if w["beat"] == "b5"]
sys.exit(0 if any(w["word"].rstrip(".,") == "AI" for w in ws) and not any(w["word"] in ("A", "I") for w in ws) else 1)' "$S/words.json"
summary="$(timeline_ok "$S/words.json" 11)"; rc=$?
assert_rc 0 $rc "ladder: words.json still has the exact layout after the regenerations ($summary)"

# ---- the flag path: one misheard word under 8 percent after the rewrite
sandbox_init --with-pipeline
fake_claude_reset; export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"; mkdir -p "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m7/"*.json "$SANDBOX/fixtures/"
fake_voice_on
RD="$(seed_run)"
run_once "$SANDBOX/flag.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_WHISPER_GARBLE="b9:scope:*"; rc=$?
OUT="$SANDBOX/flag.out"
grep -E "$ts_regex(DONE|ERROR|BLOCK|FLAG|WARN)" "$OUT" | sed 's/^/    /'
assert_rc 0 $rc "flag path: the runner exits 0"
assert_grep "${ts_regex}FLAG   needs review: voice: line b9 is misheard by faster-whisper \(WER 7.1%: scope -> xx\) after no respelling rule, rewritten by S7: .*; listen to vo.wav$" "$OUT" "flag path: 7.1 percent after the rewrite is a NEEDS REVIEW flag that tells the whole story"
assert_grep "${ts_regex}DONE   exported #1" "$OUT" "flag path: the export continues"
assert_not_grep "${ts_regex}BLOCK" "$OUT" "flag path: no BLOCK"
assert_eq "$(fake_calls)" "1" "flag path: one model call (the rewrite)"

# ---- the block path: two misheard words, above 8 percent after the rewrite
sandbox_init --with-pipeline
fake_claude_reset; export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"; mkdir -p "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m7/"*.json "$SANDBOX/fixtures/"
fake_voice_on
RD="$(seed_run)"
run_once "$SANDBOX/block.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_WHISPER_GARBLE="b9:n=2:*"; rc=$?
OUT="$SANDBOX/block.out"
grep -E "$ts_regex(DONE|ERROR|BLOCK|FLAG|WARN)" "$OUT" | sed 's/^/    /'
assert_rc 0 $rc "block path: the runner exits 0 (the idea is blocked, the loop goes on)"
assert_grep "${ts_regex}BLOCK  idea \"Claude Code's frontend-design skill.*\" blocked at S8: voice: line b9 cannot be said clearly by af_bella \(WER 14.3%: .*\) after no respelling rule, rewritten by S7: .*\. Moved to logs/blocked.txt$" "$OUT" "block path: the BLOCK line names the line, the rate and the steps tried"
assert_grep "blocked at S8" "$SANDBOX/logs/blocked.txt" "block path: logs/blocked.txt"
assert_not_grep "${ts_regex}DONE" "$OUT" "block path: nothing exported"
assert_eq "$(python pipeline/lib/ideas.py count --file "$SANDBOX_M/ideas.txt")" "0" "block path: the idea left ideas.txt"
assert_eq "$(fake_calls)" "1" "block path: one model call (the rewrite), never another voice or engine"
assert_true "block path: the trail shows only kokoro af_bella in every attempt" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8"))
ok = d["engine"]["engine"] == "kokoro" and d["engine"]["voice"] == "af_bella" and all(a["wav"].endswith(".wav") for l in d["lines"] for a in l["attempts"]) and d["verdict"]["status"] == "block"
sys.exit(0 if ok else 1)' "$RD/08-voiceover/voiceover.json"

# ---- the engine crash: a code error, the review loop, a block (fake reviewer: not auto-applicable)
sandbox_init --with-pipeline
fake_claude_reset; unset FAKE_CLAUDE_FIXTURES
fake_voice_on
RD="$(seed_run)"
run_once "$SANDBOX/crash.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_TTS_MODE=crash FAKE_CLAUDE_REVIEW=no REELS_SLEEP_SCALE=0; rc=$?
OUT="$SANDBOX/crash.out"
grep -E "$ts_regex(STEP|DONE|ERROR|BLOCK|FLAG|WARN|FIXED|ESCAL)" "$OUT" | sed 's/^/    /'
assert_grep "${ts_regex}ERROR  S8 generating voiceover: exit 1: 08-voiceover: the voice engine failed \(kokoro_worker.py exit 1, call 1\); see the kokoro: lines above$" "$OUT" "crash: an engine crash is a code error with the worker's exit code"
assert_grep "${ts_regex}BLOCK  idea .* blocked at S8: " "$OUT" "crash: the review path ends in a block (the fake reviewer cannot fix it), never in another engine"
assert_grep "fake kokoro crash" "$RD/08-voiceover/stage.log" "crash: the worker's traceback is in the stage log"
assert_not_grep "${ts_regex}DONE" "$OUT" "crash: nothing exported"

# ---- the engine hang: killed after timeouts.tts_seconds
sandbox_init --with-pipeline
fake_claude_reset; unset FAKE_CLAUDE_FIXTURES
fake_voice_on
python - "$SANDBOX_M/config.json" <<'EOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p, encoding="utf-8")); d["timeouts"]["tts_seconds"] = 4
json.dump(d, open(p, "w", encoding="utf-8", newline="\n"), indent=2)
EOF
RD="$(seed_run)"
run_once "$SANDBOX/hang.out" REELS_DUMMY="$LATER_DUMMIES" FAKE_TTS_MODE=hang FAKE_CLAUDE_REVIEW=no REELS_SLEEP_SCALE=0; rc=$?
OUT="$SANDBOX/hang.out"
grep -E "$ts_regex(STEP|DONE|ERROR|BLOCK|RETRY|WARN)" "$OUT" | sed 's/^/    /'
assert_grep "the voice engine hung: kokoro_worker.py did not finish in 4 s \(killed\)" "$RD/08-voiceover/stage.log" "hang: the worker is killed after the timeout"
assert_grep "${ts_regex}(ERROR  S8 generating voiceover: exit 1: 08-voiceover: the voice engine hung|RETRY  temporary error)" "$OUT" "hang: the runner classifies the failure (a code error, or a timeout retry first)"
assert_grep "${ts_regex}BLOCK  idea .* blocked at S8: " "$OUT" "hang: the idea ends blocked, never voiced with anything else"
fake_voice_off
fake_claude_off
fi

# ----------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. S8 on the frozen script with the real Kokoro and faster-whisper (a few minutes)"
fails_before_3="$FAIL_N"
sandbox_init --with-pipeline
fake_claude_off; fake_voice_off
mkdir -p "$SANDBOX/library/voice"
if [ -f "$REPO_DIR/library/voice/engine.txt" ]; then cp "$REPO_DIR/library/voice/engine.txt" "$SANDBOX/library/voice/"; fi
eng="$(vo --root "$SANDBOX_M" engine)"
printf '    engine config: %s (%s)\n' "$(jf "$eng" status)" "$(python -c 'import json,sys; e=json.loads(sys.argv[1])["engine"]; print(e["engine"], e["voice"], "via", e["python"])' "$eng")"
( cd "$SANDBOX" && NO_COLOR=1 bash "$REPO_DIR/pipeline/bin/preflight" ) > "$SANDBOX/preflight.out" 2>&1; rc=$?
assert_rc 0 $rc "preflight: the voice interpreter imports kokoro and a whisper interpreter exists (the real import test)"
assert_grep "${ts_regex}READY  preflight ok" "$SANDBOX/preflight.out" "preflight: READY"
RD="$(seed_run)"
started="$EPOCHSECONDS"
run_once "$SANDBOX/real.out" REELS_DUMMY="$LATER_DUMMIES"; rc=$?
OUT="$SANDBOX/real.out"; S="$RD/08-voiceover"
printf 'real run took %ss, kept at %s\n' "$((EPOCHSECONDS - started))" "$RD"
grep -E "$ts_regex(START|STEP|DONE|ERROR|BLOCK|FLAG|WARN|INFO)" "$OUT" | grep -v "root:" | sed 's/^/    /'
assert_rc 0 $rc "the runner exits 0"
assert_grep "${ts_regex}STEP   generating voiceover done \([0-9hms]+\) -> planning animations$" "$OUT" "S8 done"
assert_grep "${ts_regex}DONE   exported #1 -> exports/1/" "$OUT" "the run continued to the (dummy) export"
assert_not_grep "${ts_regex}ERROR" "$OUT" "no ERROR line"
assert_not_grep "${ts_regex}BLOCK" "$OUT" "no BLOCK line"
assert_file "$S/vo.wav" "vo.wav written"
assert_file "$S/vo_hook2.wav" "vo_hook2.wav written"
assert_eq "$(wav_info "$S/vo.wav" | cut -d' ' -f1-3)" "48000 1 16" "vo.wav is 48 kHz mono 16-bit"
assert_eq "$(wav_info "$S/vo_hook2.wav" | cut -d' ' -f1-3)" "48000 1 16" "vo_hook2.wav is 48 kHz mono 16-bit"
assert_true "words.json validates against schema.json" python pipeline/bin/validate-json "$SCHEMA" "$S/words.json"
assert_true "words_hook2.json validates against schema.json" python pipeline/bin/validate-json "$SCHEMA" "$S/words_hook2.json"
summary="$(timeline_ok "$S/words.json" 11)"; rc=$?
assert_rc 0 $rc "words.json: every beat covered, monotonic timestamps inside the beats, the exact layout ($summary)"
assert_eq "$(json_get "$S/words.json" words | python -c 'import json,sys; print(len(json.load(sys.stdin)))')" "$(spoken_words "$RD/07-script/script.json")" "words.json has one entry per spoken word (after any rewrite)"
# loudness
for f in vo vo_hook2; do
  m="$(vo measure --wav "$S/$f.wav")"
  assert_true "$f.wav: $(jf "$m" lufs) LUFS (target -14, within 1 LU) and true peak $(jf "$m" true_peak_dbtp) dBTP (at most -1.5)" python -c '
import json, sys; d = json.loads(sys.argv[1]); sys.exit(0 if d["lufs"] is not None and abs(d["lufs"] + 14) <= 1.0 and d["true_peak_dbtp"] <= -1.45 else 1)' "$m"
done
# silences: nothing of min_pause_s or longer except the breath; the tail is 0.2 s
sil="$(vo silences --wav "$S/vo.wav" --min-s 0.3)"
assert_true "no pause of 0.3 s or longer remains except the hook breath ($(python -c 'import json,sys; d=json.loads(sys.argv[1]); print([(r["start_s"], r["seconds"]) for r in d["runs"]])' "$sil"))" python -c '
import json, sys
sil = json.loads(sys.argv[1]); d = json.load(open(sys.argv[2], encoding="utf-8")); br = d["breath"]
runs = sil["runs"]
inside = [r for r in runs if r["start_s"] * 1000 >= br["start_ms"] - 60 and r["end_s"] * 1000 <= br["end_ms"] + 60]
sys.exit(0 if len(runs) >= 1 and len(inside) == len(runs) and 0.9 <= max(r["seconds"] for r in inside) <= 1.12 else 1)' "$sil" "$S/words.json"
longer="$(python -c 'import json,sys; d=json.loads(sys.argv[1]); br=json.load(open(sys.argv[2], encoding="utf-8"))["breath"]; print(sum(1 for r in d["runs"] if not (r["start_s"]*1000 >= br["start_ms"]-60 and r["end_s"]*1000 <= br["end_ms"]+60)))' "$(vo silences --wav "$S/vo.wav" --min-s 0.15)" "$S/words.json")"
printf '    pauses between 0.15 and 0.3 s outside the breath (natural short pauses the tightener keeps): %s\n' "$longer"
# 5 spot-checked word timestamps against the audio: the first word of 5 beats starts where the beat's audio starts,
# the word's window holds speech and the gap before the beat is silent
spot="$(python - "$S/words.json" "$S/vo.wav" <<'EOF'
import json, sys
sys.path.insert(0, "pipeline/lib"); import voiceover as v
d = json.load(open(sys.argv[1], encoding="utf-8")); wav = sys.argv[2]
beats = {b["id"]: b for b in d["beats"]}; words = d["words"]
picks = ["b1", "b3", "b6", "b9", "b11"]; bad = []; lines = []
for bid in picks:
    first = next(w for w in words if w["beat"] == bid); b = beats[bid]
    diff = first["start_ms"] - b["start_ms"]
    speech = v.window_db(wav, first["start_ms"], max(first["end_ms"], first["start_ms"] + 120))
    before = v.window_db(wav, b["start_ms"] - 90, b["start_ms"] - 10) if b["start_ms"] >= 100 else -99.0
    lines.append(f"{bid} {first['word']!r} starts {first['start_ms']} ms (beat {b['start_ms']} ms, diff {diff:+d}), level {speech:.0f} dB, gap before {before:.0f} dB")
    if abs(diff) > 150 or speech < -35 or before > -40: bad.append(bid)
print("\n".join("    " + l for l in lines))
sys.exit(1 if bad else 0)
EOF
)"; rc=$?
printf '%s\n' "$spot"
assert_rc 0 $rc "5 spot-checked word timestamps line up with the audio (first words within 150 ms of their beat's start, speech in the window, silence before it)"
# word error rate per line, or the ladder visible in the log
python - "$S/voiceover.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for l in d["lines"]:
    print(f"    {l['id']:6} {l['words']:2} words  est {l['estimate_s']:.2f} s  got {l['duration_s']:.2f} s  WER {l['wer_pct']}%  {l['status']:5}  heard: {l.get('heard_text', '')[:80]}" + (f"  steps: {l['steps']}" if l["steps"] else ""))
t = d["timing"]; p = d["pace"]
print(f"    speed: {t['speed_x_realtime']}x real time ({t['tts_synth_s']} s of synthesis for {t['audio_raw_s']} s of raw voice; import+load {t['tts_load_s']} s; whole TTS {t['tts_wall_s']} s); alignment {t['align_wall_s']} s ({d['whisper_model']}); loudness {t['loudness_s']} s; total {t['total_s']} s")
print(f"    pace after tightening: {p['wpm']} wpm with the 0.1 s gaps ({p['wpm_speech_only']} on speech alone): {p['words']} words in {p['speech_s']} s of speech; config voice.wpm is {d['thresholds']['wpm']}")
print(f"    loudness: vo {d['loudness']['vo']['lufs']} LUFS / {d['loudness']['vo']['true_peak_dbtp']} dBTP in {d['loudness']['vo']['passes']} passes (gain {d['loudness']['vo']['gain_db']} dB)")
EOF
assert_true "every line's word error rate is 3 percent or under, or its ladder (pronunciation fix, rewrite, flag) is in the log" python -c '
import json, re, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); log = open(sys.argv[2], encoding="utf-8", errors="replace").read()
bad = [l["id"] for l in d["lines"] if (l["wer_pct"] is None or l["wer_pct"] > 3) and not (l["steps"] and re.search(r"line " + l["id"] + r" (misheard|still misheard)", log))]
sys.exit(0 if not bad and d["verdict"]["status"] in ("ok", "flag") else 1)' "$S/voiceover.json" "$S/stage.log"
assert_true "the measured speed and pace are recorded (speed under 1x real time, pace between 120 and 240 wpm)" python -c '
import json, sys; d = json.load(open(sys.argv[1], encoding="utf-8")); t = d["timing"]; p = d["pace"]
sys.exit(0 if 0 < t["speed_x_realtime"] < 1.0 and 120 <= p["wpm"] <= 240 and d["engine"]["voice"] == "af_bella" else 1)' "$S/voiceover.json"
# the total length against the estimate at the configured pace
python - "$S/words.json" "$RD/07-script/script.json" "$REPO_DIR/config.json" <<'EOF'
import json, re, sys
w = json.load(open(sys.argv[1], encoding="utf-8")); s = json.load(open(sys.argv[2], encoding="utf-8")); c = json.load(open(sys.argv[3], encoding="utf-8"))
words = sum(len([t for t in b["spoken"].split() if re.search(r"[A-Za-z0-9]", t)]) for b in s["beats"])
wpm = c["voice"]["wpm"]; est = words / wpm * 60 + 1.0 + 0.1 * (len(s["beats"]) - 1) + 0.25
got = w["duration_ms"] / 1000
print(f"    total {got:.1f} s against {est:.1f} s expected at {wpm} wpm ({(got - est) / est * 100:+.0f}%); the script's own estimate was {s['estimated_seconds']} s at {s['wpm']} wpm")
sys.exit(0 if abs(got - est) / est <= 0.15 or w.get("flags") else 1)
EOF
assert_rc 0 $? "the total length is within 15 percent of the estimate at the configured pace (or the run carries a flag)"
no_emdash_in "no em dash in the stage files" "$S/words.json" "$S/words_hook2.json" "$S/voiceover.json" "$S/stage.log" "$SANDBOX/logs/runner.log"
# The frozen 08-voiceover fixtures (PLAN.md M7; M9 and M10 render the golden reel against them) are the five outputs
# of one run: words.json, words_hook2.json, voiceover.json, vo.wav and vo_hook2.wav. The wavs are ignored by git
# (*.wav), so a fresh clone has only the JSON: when the section 3 run passed, the wavs are added whenever they are
# missing (alone when the run's words.json and words_hook2.json equal the frozen ones, else all five files together,
# so the audio and the timestamps always come from the same run); M7_FREEZE=1 refreshes all five.
FROZEN_VO="$FROZEN/08-voiceover"
same_json() { python -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1], encoding="utf-8")) == json.load(open(sys.argv[2], encoding="utf-8")) else 1)' "$1" "$2" 2>/dev/null; }
if [ "$FAIL_N" -eq "$fails_before_3" ] && [ -f "$S/words.json" ] && [ -f "$S/words_hook2.json" ] && [ -f "$S/voiceover.json" ] && [ -f "$S/vo.wav" ] && [ -f "$S/vo_hook2.wav" ]; then
  freeze=""
  if [ -n "${M7_FREEZE:-}" ]; then freeze=all
  elif [ ! -f "$FROZEN_VO/vo.wav" ] || [ ! -f "$FROZEN_VO/vo_hook2.wav" ]; then
    if same_json "$FROZEN_VO/words.json" "$S/words.json" && same_json "$FROZEN_VO/words_hook2.json" "$S/words_hook2.json"; then freeze=wavs; else freeze=all; fi
  fi
  case "$freeze" in
    all)
      rm -rf "$FROZEN_VO"; mkdir -p "$FROZEN_VO"
      cp "$S/words.json" "$S/words_hook2.json" "$S/voiceover.json" "$S/vo.wav" "$S/vo_hook2.wav" "$FROZEN_VO/"
      printf 'frozen 08-voiceover outputs added by %sbash pipeline/tests/test-m7.sh on %s from %s (vo.wav and vo_hook2.wav are kept out of git by *.wav; test-m7 section 3 regenerates them when they are missing)\n' "${M7_FREEZE:+M7_FREEZE=1 }" "$(date '+%Y-%m-%d %H:%M')" "$(basename "$RD")" >> "$FROZEN/README.txt"
      pass "frozen: the five 08-voiceover outputs (JSON and wavs) copied to pipeline/tests/fixtures/runs/test-idea/${M7_FREEZE:+ (M7_FREEZE)}"
      [ -n "${M7_FREEZE:-}" ] || printf '    NOTE: the frozen wavs were missing and this run%ss words.json differs from the frozen one, so the JSON fixtures were refreshed too: commit pipeline/tests/fixtures/runs/test-idea/08-voiceover/ (git status shows the change)\n' "'" ;;
    wavs)
      cp "$S/vo.wav" "$S/vo_hook2.wav" "$FROZEN_VO/"
      pass "frozen: vo.wav and vo_hook2.wav added to pipeline/tests/fixtures/runs/test-idea/08-voiceover/ (this run's words.json equals the frozen one)" ;;
  esac
fi
# whatever happened above, the fixture must be usable by M9 and M10: both wavs present and as long as their words.json says
frozen_check="$(python - "$FROZEN_VO" <<'EOF_FROZEN'
import json, os, sys, wave
d = sys.argv[1]; bad = []; out = []
for wav, js in (("vo.wav", "words.json"), ("vo_hook2.wav", "words_hook2.json")):
    wp, jp = os.path.join(d, wav), os.path.join(d, js)
    if not os.path.isfile(wp): bad.append(f"{wav} missing"); continue
    if not os.path.isfile(jp): bad.append(f"{js} missing"); continue
    with wave.open(wp, "rb") as w: ms = round(w.getnframes() * 1000 / w.getframerate())
    want = json.load(open(jp, encoding="utf-8"))["duration_ms"]
    out.append(f"{wav} {ms} ms, {js} says {want} ms")
    if abs(ms - want) > 10: bad.append(f"{wav} is {ms} ms but {js} says {want} ms")
print("; ".join(out + bad))
sys.exit(1 if bad else 0)
EOF_FROZEN
)"; rc=$?
assert_rc 0 $rc "the frozen fixtures hold vo.wav and vo_hook2.wav as long as their words.json says, within 10 ms ($frozen_check; rerun with M7_FREEZE=1 to refresh all five)"
fi

test_summary
