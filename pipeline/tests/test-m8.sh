#!/usr/bin/env bash
# test-m8.sh: acceptance test for M8 (Sound effects memory map, BUILD_SPEC.md 2.6 and section 12). No real model
# call: section 1 builds a synthetic pack (ffmpeg lavfi) in the sandbox with the fake claude answering the one
# indexer call from fixtures; section 2 checks the repo's own map of styles/sfx/ (built once with the real indexer
# model and committed) and that a rebuild of an unchanged pack is a no-op without a model call.
#   bash pipeline/tests/test-m8.sh                    everything (2 to 4 minutes)
#   M8_SECTIONS="1" bash pipeline/tests/test-m8.sh    only that section
#
# Covers:
#   1. synthetic pack: every file measured (every field), the whoosh speed classes (fast, slow), the clipped, silent
#      and undecodable files excluded with a reason, the normalized 48 kHz cache copies at -12 dBFS, the pools
#      (clicks, pops, typing, the model-classified tone), the previews with their listing, overrides.txt created;
#      the model path (one batched call plus the retry for a skipped id, the low-confidence file waiting); the
#      no-op rebuild (no re-measure, no model call); ban kept through two rebuilds; pin first (also approving a
#      waiting file); an unknown override line; a new file measured alone, a removed file pruned; --check; the
#      failed model call (exit 1) and --no-model
#   2. the repo's map: every audio file under styles/sfx/ in the map or excluded with a reason, every field, every
#      cue type with a pool of at least 3 or named in build/HUMAN_TODO.md, no pool over 8, previews present, a
#      rebuild of the unchanged pack makes no model call and leaves the map as it is, no em dash
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$REPO_DIR"
SECTIONS="${M8_SECTIONS:-1 2}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
BUILD="$REPO_DIR/pipeline/bin/build-sfx-map"
SFX_LIB="$REPO_DIR/pipeline/lib/sfx"
MAP_SCHEMA="$SFX_LIB/map.schema.json"
VALIDATE="$REPO_DIR/pipeline/bin/validate-json"
CUES="transition_slow transition_fast attention hero_enter ui_click stamp number success typing negative hook_hit notification"
MEASURED_FIELDS="duration_s peak_dbfs true_peak_dbtp lufs floor_p5_db onset_s peak_s attack_s tail_s end_s effective_s pad_start_s pad_end_s centroid_hz clipped_samples clip_runs gain_db channels sample_rate cache tags"

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
fake_calls() { python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG"; }
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
file_field() {  # file_field <map> <path> <key> -> the field of that file's entry
  python -c 'import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig"))
for f in m["files"]:
    if f["path"] == sys.argv[2]:
        v = f.get(sys.argv[3])
        print("true" if v is True else "false" if v is False else "" if v is None else (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)); break
else:
    print("(no such file)")' "$1" "$2" "$3"
}
in_pool() {  # in_pool <map> <cue> <path> -> 0 when the path is in that pool
  python -c 'import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig"))
sys.exit(0 if any(e["path"] == sys.argv[3] for e in m["pools"].get(sys.argv[2], [])) else 1)' "$1" "$2" "$3"
}
pool_first() { json_get "$1" "pools.$2.0.path"; }
pool_size() { json_len "$1" "pools.$2"; }
excluded_reason() {  # excluded_reason <map> <path>
  python -c 'import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig"))
print(next((e["reason"] for e in m["excluded"] if e["path"] == sys.argv[2]), ""))' "$1" "$2"
}
fields_present() {  # fields_present <map>: every mapped (not excluded) file has every measured field; prints the problems
  python - "$1" "$MEASURED_FIELDS" <<'EOF'
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig")); fields = sys.argv[2].split()
bad = []
for f in m["files"]:
    if f.get("excluded") or f.get("decode_error"):
        continue
    missing = [k for k in fields if f.get(k) is None]
    if missing:
        bad.append(f"{f['path']}: {', '.join(missing)}")
print("; ".join(bad) if bad else "ok")
sys.exit(1 if bad else 0)
EOF
}
map_paths_match() {  # map_paths_match <map> <pack dir>: the audio files on disk are exactly the map's files, each mapped or excluded with a reason
  python - "$1" "$2" "$SFX_LIB" <<'EOF'
import json, sys
sys.path.insert(0, sys.argv[3])
from common import list_audio_files
m = json.load(open(sys.argv[1], encoding="utf-8-sig"))
disk = {e["path"] for e in list_audio_files(sys.argv[2])}
inmap = {f["path"] for f in m["files"]}
excluded = {e["path"]: e["reason"] for e in m["excluded"]}
problems = []
if disk != inmap:
    problems.append(f"on disk but not in the map: {sorted(disk - inmap)}; in the map but not on disk: {sorted(inmap - disk)}")
for f in m["files"]:
    if f.get("excluded"):
        if not excluded.get(f["path"]):
            problems.append(f"{f['path']} excluded without a listed reason")
    elif f["path"] in excluded:
        problems.append(f"{f['path']} listed as excluded but not marked")
print("; ".join(problems) if problems else f"ok: {len(disk)} files, {len(excluded)} excluded")
sys.exit(1 if problems else 0)
EOF
}
sha_of() { python -c 'import hashlib, sys; print(hashlib.sha1(open(sys.argv[1], "rb").read()).hexdigest())' "$1"; }
wav_info() {  # wav_info <wav> -> "channels rate seconds peak_dbfs"
  python -c 'import wave, sys, numpy as np
w = wave.open(sys.argv[1]); n = w.getnframes(); ch = w.getnchannels(); sr = w.getframerate()
x = np.frombuffer(w.readframes(n), dtype="<i2").astype(float) / 32768.0
pk = 20 * np.log10(max(1e-9, float(np.abs(x).max()))) if n else -120.0
print(ch, sr, round(n / sr, 3), round(pk, 2))' "$1"
}
fid() { python -c 'import sys; sys.path.insert(0, sys.argv[1]); from common import file_id; print(file_id(sys.argv[2]))' "$SFX_LIB" "$1"; }

gen() {  # gen <lavfi graph> <out.wav>: a synthetic sound, 48 kHz mono 16-bit
  ffmpeg -v error -nostdin -y -f lavfi -i "$1" -ar 48000 -ac 1 -c:a pcm_s16le "$2" || { echo "ffmpeg could not generate $2" >&2; return 1; }
}
make_pack() {  # make_pack <dir>: 13 synthetic audio files plus one that is not audio
  local P="$1"
  mkdir -p "$P/clicks" "$P/whoosh" "$P/misc"
  gen "anoisesrc=d=0.03:c=white:a=0.6:r=48000:seed=1,afade=t=out:st=0.005:d=0.025,apad=pad_dur=0.3" "$P/clicks/click-a.wav"
  gen "anoisesrc=d=0.04:c=white:a=0.5:r=48000:seed=2,afade=t=out:st=0.005:d=0.035,apad=pad_dur=0.3" "$P/clicks/click-b.wav"
  gen "anoisesrc=d=0.05:c=white:a=0.4:r=48000:seed=3,afade=t=out:st=0.005:d=0.045,apad=pad_dur=0.3" "$P/clicks/click-c.wav"
  gen "anoisesrc=d=0.06:c=white:a=0.3:r=48000:seed=4,afade=t=out:st=0.01:d=0.05,apad=pad_dur=0.3" "$P/clicks/mouse-click-d.wav"
  gen "anoisesrc=d=0.3:c=pink:a=0.7:r=48000:seed=5,afade=t=in:d=0.05,afade=t=out:st=0.1:d=0.2,apad=pad_dur=0.2" "$P/whoosh/fast-whoosh.wav"
  gen "anoisesrc=d=1.6:c=pink:a=0.7:r=48000:seed=6,afade=t=in:d=0.7,afade=t=out:st=0.9:d=0.7,apad=pad_dur=0.2" "$P/whoosh/slow-whoosh.wav"
  gen "sine=f=200:d=0.4:r=48000,volume=30dB" "$P/clipped-pop.wav"
  gen "anullsrc=r=48000:cl=mono:d=1" "$P/silent.wav"
  gen "sine=f=1200:d=1.2:r=48000,afade=t=out:st=0.05:d=1.1:curve=exp" "$P/ding-bell.wav"
  gen "sine=f=70:d=0.5:r=48000,afade=t=out:st=0.02:d=0.45:curve=exp" "$P/boom-hit.wav"
  gen "anoisesrc=d=2:c=white:a=0.5:r=48000:seed=7,tremolo=f=8:d=1" "$P/keyboard-typing.wav"
  gen "sine=f=1000:d=0.4:r=48000,afade=t=out:st=0.05:d=0.35" "$P/misc/mystery-tone.wav"
  gen "sine=f=500:d=0.6:r=48000,afade=t=out:st=0.1:d=0.5" "$P/misc/odd-thing.wav"
  printf 'this is not audio\n' > "$P/broken.mp3"
}
make_fixtures() {  # make_fixtures <dir>: the fake indexer's answers, call 1 skips one id, call 2 answers it with low confidence
  local d="$1"
  mkdir -p "$d"
  printf '{"files": [{"id": "%s", "cue_types": ["success"], "tags": ["tone", "clean ding"], "confidence": 0.9, "note": "a clean tone, a ding"}]}\n' \
    "$(fid misc/mystery-tone.wav)" > "$d/build-sfx-map.1.json"
  printf '{"files": [{"id": "%s", "cue_types": ["number"], "tags": ["tone"], "confidence": 0.3, "note": "guessing from a generic name"}]}\n' \
    "$(fid misc/odd-thing.wav)" > "$d/build-sfx-map.2.json"
}

# ---------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. a synthetic pack in the sandbox: measurements, classes, exclusions, cache, pools, previews, overrides, rebuilds (fake indexer)"
sandbox_init
PACK="$SANDBOX/pack"; PACK_M="$SANDBOX_M/pack"; MAP="$PACK/sfx-map.json"
make_pack "$PACK"
assert_eq "$(ls "$PACK"/*.wav "$PACK"/*/*.wav | wc -l | tr -d ' ')" "13" "13 synthetic wav files generated with ffmpeg"
fake_claude_on
make_fixtures "$SANDBOX/fixtures-sfx"
export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures-sfx"

bash "$BUILD" --check --dir "$PACK_M" >"$SANDBOX/check0.out" 2>&1; rc=$?
assert_rc 1 $rc "--check exits 1 before any map exists"
assert_grep "needs a rebuild: no map yet" "$SANDBOX/check0.out" "--check says why"

out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
printf '%s\n' "$out" > "$SANDBOX/build1.out"
assert_rc 0 $rc "build-sfx-map exits 0 on the synthetic pack ($(printf '%s' "$out" | grep -c .) lines of output)"
assert_grep "measuring 14 of 14 audio files" "$SANDBOX/build1.out" "every file is measured on the first build"
assert_eq "$(fake_calls)" "2" "one batched indexer call, then one more for the id the first answer skipped"
assert_eq "$(fake_field 1 role)" "indexer" "the call's role is indexer"
assert_eq "$(fake_field 1 model)" "haiku" "the indexer model from config"
assert_eq "$(fake_field 1 tools)" '[""]' "no tools"
assert_eq "$(fake_field 1 schema)" "true" "a JSON schema is passed"
assert_file "$MAP" "sfx-map.json written next to the pack"
assert_file "$PACK/SFX-MAP.md" "SFX-MAP.md written"
assert_file "$PACK/overrides.txt" "overrides.txt created with its header"
assert_grep "^#   ban: <path>" "$PACK/overrides.txt" "the header explains ban:"
assert_grep "^#   pin: <cue type>: <path>" "$PACK/overrides.txt" "the header explains pin:"
assert_grep "the id the first answer skipped|classifying 1 unclear sound file\(s\).*call 2" "$SANDBOX/build1.out" "the second call is announced"
python "$VALIDATE" "$MAP_SCHEMA" "$MAP" >/dev/null 2>&1; assert_rc 0 $? "sfx-map.json validates against pipeline/lib/sfx/map.schema.json"
assert_eq "$(json_get "$MAP" counts.files)" "14" "14 audio files in the map (13 wav plus the broken mp3)"
res="$(map_paths_match "$MAP" "$PACK_M")"; assert_rc 0 $? "every audio file is in the map or excluded with a reason ($res)"
res="$(fields_present "$MAP")"; assert_rc 0 $? "every measured field is present for every mapped file ($res)"
ls "$SANDBOX"/logs/build-sfx-map/calls/*classify*.json >/dev/null 2>&1 && pass "the call files live under logs/build-sfx-map/calls/" || fail "no call files under logs/build-sfx-map/calls/"
assert_grep "^- id [0-9a-f]{10}: folder \"misc\", file \"mystery-tone.wav\"; duration" "$SANDBOX/logs/build-sfx-map/prompt-classify.md" "the prompt lists the unclear file with its folder, name and measurements"
assert_eq "$(grep -c '^- id ' "$SANDBOX/logs/build-sfx-map/prompt-classify.md")" "2" "only the 2 unclear files went to the model"

# classes and exclusions
assert_eq "$(file_field "$MAP" whoosh/fast-whoosh.wav whoosh_speed)" "fast" "a 0.3 s noise swoosh is a fast whoosh"
assert_eq "$(file_field "$MAP" whoosh/slow-whoosh.wav whoosh_speed)" "slow" "a 1.6 s swell is a slow whoosh"
assert_eq "$(file_field "$MAP" clicks/click-a.wav category)" "click" "click-a is a click by rule"
assert_eq "$(file_field "$MAP" ding-bell.wav category)" "success" "ding-bell is a success sound by rule"
assert_eq "$(file_field "$MAP" boom-hit.wav category)" "impact" "boom-hit is an impact by rule"
assert_eq "$(file_field "$MAP" keyboard-typing.wav category)" "typing" "keyboard-typing is typing by rule"
assert_true "clipped-pop.wav is excluded as clipped" grep -q "^clipped" <<<"$(excluded_reason "$MAP" clipped-pop.wav)"
assert_true "silent.wav is excluded as silent" grep -q "^silent" <<<"$(excluded_reason "$MAP" silent.wav)"
assert_true "broken.mp3 is excluded as undecodable" grep -q "^cannot be decoded" <<<"$(excluded_reason "$MAP" broken.mp3)"
assert_eq "$(json_get "$MAP" counts.excluded)" "3" "3 files excluded"
assert_eq "$(file_field "$MAP" misc/mystery-tone.wav source)" "model" "mystery-tone was classified by the model"
assert_eq "$(file_field "$MAP" misc/mystery-tone.wav confidence)" "0.9" "with the model's confidence"
assert_eq "$(file_field "$MAP" misc/odd-thing.wav waiting)" "true" "odd-thing (confidence 0.3) waits for approval"
assert_eq "$(json_len "$MAP" waiting)" "1" "one file in the waiting list"
assert_eq "$(file_field "$MAP" misc/odd-thing.wav pooled)" "[]" "a waiting file is in no pool"
assert_grep "mystery-tone.wav" "$PACK/SFX-MAP.md" "SFX-MAP.md names the model-classified file"
assert_grep "^- clipped-pop.wav: clipped" "$PACK/SFX-MAP.md" "SFX-MAP.md lists the clipped file with its reason"
assert_grep "^- misc/odd-thing.wav: maybe number \(confidence 0.30" "$PACK/SFX-MAP.md" "SFX-MAP.md lists the waiting file with the model's guess"

# pools
assert_true "fast-whoosh is in the transition_fast pool" in_pool "$MAP" transition_fast whoosh/fast-whoosh.wav
assert_true "fast-whoosh is in the attention pool" in_pool "$MAP" attention whoosh/fast-whoosh.wav
assert_true "slow-whoosh is in the transition_slow pool" in_pool "$MAP" transition_slow whoosh/slow-whoosh.wav
assert_false "slow-whoosh is not in the transition_fast pool" in_pool "$MAP" transition_fast whoosh/slow-whoosh.wav
assert_eq "$(pool_size "$MAP" ui_click)" "4" "the ui_click pool holds the 4 clicks"
assert_true "ding-bell is in the success pool" in_pool "$MAP" success ding-bell.wav
assert_true "mystery-tone is in the success pool (the model's answer)" in_pool "$MAP" success misc/mystery-tone.wav
assert_true "boom-hit is in the stamp pool" in_pool "$MAP" stamp boom-hit.wav
assert_true "boom-hit is in the hook_hit pool" in_pool "$MAP" hook_hit boom-hit.wav
assert_true "keyboard-typing is in the typing pool" in_pool "$MAP" typing keyboard-typing.wav
assert_false "the clipped file is in no pool" in_pool "$MAP" hero_enter clipped-pop.wav
ok=1; for c in $CUES; do n="$(pool_size "$MAP" "$c")"; [ "$n" -le 8 ] || ok=0; done
[ "$ok" = 1 ] && pass "no pool exceeds 8 sounds" || fail "a pool exceeds 8 sounds"
assert_true "short pools are named (the synthetic pack is small)" grep -q "ui_click\|negative" <<<"$(json_get "$MAP" short_pools)"
[ "$(json_get "$MAP" pools.ui_click.0.fit)" != "" ] && pass "pool entries carry a fit" || fail "pool entries carry no fit"

# the cache copies and the gain
cache="$(file_field "$MAP" clicks/click-a.wav cache)"
assert_file "$PACK/$cache" "the normalized cache copy exists ($cache)"
read -r ch sr secs pk <<<"$(wav_info "$PACK/$cache")"
assert_eq "$ch $sr" "1 48000" "the cache copy is 48 kHz with the file's channel count"
python -c 'import sys; sys.exit(0 if abs(float(sys.argv[1]) + 12.0) <= 0.5 else 1)' "$pk"; assert_rc 0 $? "the cache copy peaks at -12 dBFS (measured $pk)"
peak="$(file_field "$MAP" clicks/click-a.wav peak_dbfs)"; gain="$(file_field "$MAP" clicks/click-a.wav gain_db)"
python -c 'import sys; sys.exit(0 if abs(float(sys.argv[1]) + float(sys.argv[2]) + 12.0) < 0.05 else 1)' "$peak" "$gain"; assert_rc 0 $? "gain_db = -12 - peak_dbfs ($gain = -12 - ($peak))"
assert_eq "$(ls "$PACK/.cache"/*.wav | wc -l | tr -d ' ')" "13" "13 cache copies (none for the undecodable file)"
assert_eq "$(file_field "$MAP" broken.mp3 cache)" "" "the undecodable file has no cache copy"
no_emdash_in "no em dash in the map, SFX-MAP.md and overrides.txt" "$MAP" "$PACK/SFX-MAP.md" "$PACK/overrides.txt"

# previews
for c in ui_click transition_fast success; do
  assert_file "$PACK/previews/$c.wav" "previews/$c.wav exists"
  assert_file "$PACK/previews/$c.txt" "previews/$c.txt exists"
done
assert_no_file "$PACK/previews/negative.wav" "no preview for an empty pool (negative)"
read -r ch sr secs pk <<<"$(wav_info "$PACK/previews/ui_click.wav")"
python -c 'import sys; sys.exit(0 if 3.0 <= float(sys.argv[1]) <= 4.5 else 1)' "$secs"; assert_rc 0 $? "the ui_click preview is 4 trimmed clicks 1 s apart (about 3.2 s, got $secs s)"
assert_eq "$(grep -c '^[0-9]*\. at ' "$PACK/previews/ui_click.txt")" "4" "the ui_click listing has 4 lines"
assert_eq "$(sed -n '3p' "$PACK/previews/ui_click.txt" | sed -E 's/^1\. at +0\.00 s  ([^ ]+) .*/\1/')" "$(pool_first "$MAP" ui_click)" "the listing's first sound is the pool's first"
assert_grep "^2\. at +1\.[0-9]+ s" "$PACK/previews/ui_click.txt" "the second sound starts about 1 s after the first ends"

# the no-op rebuild: nothing re-measured, no model call
fake_claude_reset; export FAKE_CLAUDE_MODE=error
sha1_before="$(sha_of "$MAP")"
start=$(date +%s)
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 0 $rc "a rebuild of an unchanged pack exits 0"
assert_true "and says it is up to date" grep -q "sfx map up to date (14 audio files, no change in pack/, no model call)" <<<"$out"
assert_eq "$(fake_calls)" "0" "and makes no model call"
assert_eq "$(sha_of "$MAP")" "$sha1_before" "and leaves sfx-map.json byte for byte as it was"
[ $(( $(date +%s) - start )) -le 15 ] && pass "and is fast" || fail "the no-op rebuild took $(( $(date +%s) - start )) s"
bash "$BUILD" --check --dir "$PACK_M" >/dev/null 2>&1; assert_rc 0 $? "--check exits 0 on a current map"

# ban: dropped from the pool, kept through another rebuild
printf 'ban: clicks/click-a.wav\n' >> "$PACK/overrides.txt"
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 0 $rc "a rebuild after a ban exits 0"
assert_true "the overrides change is the reason" grep -q "overrides.txt changed" <<<"$out"
assert_true "nothing is re-measured" grep -q "nothing to measure: 14 files unchanged" <<<"$out"
assert_eq "$(fake_calls)" "0" "no model call for an overrides change (cached answers)"
assert_false "the banned click left the ui_click pool" in_pool "$MAP" ui_click clicks/click-a.wav
assert_eq "$(pool_size "$MAP" ui_click)" "3" "the ui_click pool has 3 clicks now"
assert_eq "$(file_field "$MAP" clicks/click-a.wav banned)" "true" "the file is marked banned"
assert_eq "$(json_get "$MAP" overrides.bans.0.matched)" "true" "the ban matched a file"
assert_grep "^- ban: clicks/click-a.wav$" "$PACK/SFX-MAP.md" "SFX-MAP.md lists the ban"
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
assert_true "another rebuild is a no-op" grep -q "up to date" <<<"$out"
assert_false "and the ban holds" in_pool "$MAP" ui_click clicks/click-a.wav
touch "$PACK/clicks/click-b.wav"   # a touched file (new date) is measured again and the ban still holds
out="$(bash "$BUILD" --force --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 0 $rc "a forced rebuild exits 0"
assert_true "a forced rebuild measures every file again" grep -q "measuring 14 of 14" <<<"$out"
assert_eq "$(fake_calls)" "0" "and still makes no model call (the answers are cached)"
assert_false "the ban holds through a forced rebuild" in_pool "$MAP" ui_click clicks/click-a.wav
assert_eq "$(file_field "$MAP" misc/mystery-tone.wav source)" "model" "the model's classification survives a forced rebuild"

# pin: first in the pool; a pin approves a waiting file
printf 'pin: ui_click: clicks/mouse-click-d.wav\npin: number: misc/odd-thing.wav\nfrobnicate: something\n' >> "$PACK/overrides.txt"
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 0 $rc "a rebuild after pins exits 0"
assert_eq "$(pool_first "$MAP" ui_click)" "clicks/mouse-click-d.wav" "the pinned click is first in the ui_click pool"
assert_eq "$(json_get "$MAP" pools.ui_click.0.pinned)" "true" "and marked pinned"
assert_eq "$(pool_first "$MAP" number)" "misc/odd-thing.wav" "the pinned waiting file is first in the number pool"
assert_eq "$(file_field "$MAP" misc/odd-thing.wav waiting)" "false" "and no longer waits"
assert_eq "$(json_len "$MAP" waiting)" "0" "the waiting list is empty"
assert_true "the unknown line is reported" grep -q "WARN: 1 line(s) of overrides.txt not understood" <<<"$out"
assert_grep "not understood: \`frobnicate: something\`" "$PACK/SFX-MAP.md" "SFX-MAP.md shows the unknown line"
assert_grep "^1\. at +0\.00 s  clicks/mouse-click-d.wav .*pinned" "$PACK/previews/ui_click.txt" "the preview listing starts with the pinned sound"
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"
assert_true "pins hold through another rebuild (no-op)" grep -q "up to date" <<<"$out"
assert_eq "$(pool_first "$MAP" ui_click)" "clicks/mouse-click-d.wav" "the pin is still first"

# a changed folder: one new file measured alone, a removed file pruned
gen "anoisesrc=d=0.02:c=white:a=0.5:r=48000:seed=9,afade=t=out:st=0.004:d=0.016,apad=pad_dur=0.2" "$PACK/clicks/click-e.wav"
bash "$BUILD" --check --dir "$PACK_M" >"$SANDBOX/check2.out" 2>&1; rc=$?
assert_rc 1 $rc "--check exits 1 after a file was added"
assert_grep "folder changed \(1 new, 0 changed, 0 removed\)" "$SANDBOX/check2.out" "--check names the change"
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 0 $rc "a rebuild after a new file exits 0"
assert_true "only the new file is measured" grep -q "measuring 1 of 15 audio files" <<<"$out"
assert_eq "$(json_get "$MAP" counts.files)" "15" "15 files in the map"
assert_true "the new click joined the ui_click pool" in_pool "$MAP" ui_click clicks/click-e.wav
assert_eq "$(fake_calls)" "0" "a clear new file needs no model call"
old_cache="$(file_field "$MAP" clicks/click-c.wav cache)"
rm "$PACK/clicks/click-c.wav"
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 0 $rc "a rebuild after a removed file exits 0"
assert_eq "$(json_get "$MAP" counts.files)" "14" "the removed file left the map"
assert_eq "$(file_field "$MAP" clicks/click-c.wav id)" "(no such file)" "no entry for the removed file"
assert_no_file "$PACK/$old_cache" "its cache copy was pruned"

# the model path failing, and --no-model
gen "sine=f=900:d=0.3:r=48000,afade=t=out:st=0.05:d=0.25" "$PACK/misc/thing-two.wav"
fake_claude_reset; export FAKE_CLAUDE_MODE=error
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 1 $rc "a failed indexer call exits 1 (a code error for the calling stage)"
assert_true "and says so" grep -q "the indexer call failed" <<<"$out"
assert_eq "$(fake_calls)" "1" "one call was attempted"
out="$(bash "$BUILD" --no-model --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 0 $rc "--no-model builds without the model"
assert_true "and warns about the unclassified file" grep -q "WARN: 1 unclear file(s) left unclassified (--no-model)" <<<"$out"
assert_eq "$(json_get "$MAP" counts.unclassified)" "1" "one file not classified yet"
assert_eq "$(file_field "$MAP" misc/thing-two.wav unclassified)" "true" "it is the new unclear file"
assert_grep "^- misc/thing-two.wav$" "$PACK/SFX-MAP.md" "SFX-MAP.md lists it under not classified yet"
bash "$BUILD" --check --dir "$PACK_M" >"$SANDBOX/check3.out" 2>&1; rc=$?
assert_rc 1 $rc "--check exits 1 while a file waits for the model"
assert_grep "still wait for the indexer model" "$SANDBOX/check3.out" "--check says so"
out="$(bash "$BUILD" --no-model --dir "$PACK_M" 2>&1)"
assert_true "--no-model again is a no-op" grep -q "up to date" <<<"$out"
rm -f "$SANDBOX/fixtures-sfx/build-sfx-map.1.json" "$SANDBOX/fixtures-sfx/build-sfx-map.2.json"   # the fake serves <stage>.<n>.json first
printf '{"files": [{"id": "%s", "cue_types": ["ui_click"], "tags": ["tone"], "confidence": 0.8, "note": "a short tone"}]}\n' "$(fid misc/thing-two.wav)" > "$SANDBOX/fixtures-sfx/build-sfx-map.json"
fake_claude_reset; unset FAKE_CLAUDE_MODE
out="$(bash "$BUILD" --dir "$PACK_M" 2>&1)"; rc=$?
assert_rc 0 $rc "the next run with the model exits 0"
assert_eq "$(fake_calls)" "1" "and asks only about the pending file"
assert_eq "$(json_get "$MAP" counts.unclassified)" "0" "nothing left unclassified"
assert_true "the pending file joined its pool" in_pool "$MAP" ui_click misc/thing-two.wav
fake_claude_off
unset FAKE_CLAUDE_FIXTURES
fi

# ---------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. the repo's map of styles/sfx/ (built with the real indexer model, committed): coverage, pools, previews, no-op rebuild"
sandbox_init
REAL_PACK="$REPO_DIR/styles/sfx"; REAL_PACK_M="$(mixed "$REAL_PACK")"; REAL_MAP="$REAL_PACK/sfx-map.json"
n_audio="$(python -c 'import sys; sys.path.insert(0, sys.argv[1]); from common import list_audio_files; print(len(list_audio_files(sys.argv[2])))' "$SFX_LIB" "$REAL_PACK_M")"
if [ "$n_audio" = 0 ]; then
  printf 'NOTE: styles/sfx/ holds no audio files on this machine (the pack is not in git); section 2 checks only the committed map\n'
fi
assert_file "$REAL_MAP" "styles/sfx/sfx-map.json exists (committed)"
assert_file "$REAL_PACK/SFX-MAP.md" "styles/sfx/SFX-MAP.md exists"
assert_file "$REAL_PACK/overrides.txt" "styles/sfx/overrides.txt exists"
python "$VALIDATE" "$MAP_SCHEMA" "$REAL_MAP" >/dev/null 2>&1; assert_rc 0 $? "the map validates against map.schema.json"
if [ "$n_audio" != 0 ]; then
  res="$(map_paths_match "$REAL_MAP" "$REAL_PACK_M")"; assert_rc 0 $? "every audio file under styles/sfx/ is in the map or excluded with a reason ($res)"
  assert_eq "$(json_get "$REAL_MAP" counts.files)" "$n_audio" "counts.files matches the folder ($n_audio)"
fi
res="$(fields_present "$REAL_MAP")"; assert_rc 0 $? "every measured field is present for every mapped file ($res)"
n_ex="$(json_len "$REAL_MAP" excluded)"
python -c 'import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig"))
sys.exit(0 if all(e.get("reason") for e in m["excluded"]) else 1)' "$REAL_MAP"; assert_rc 0 $? "every excluded file has a reason ($n_ex excluded)"
ok=1; over=""
for c in $CUES; do n="$(pool_size "$REAL_MAP" "$c")"; [ "$n" -le 8 ] || { ok=0; over="$over $c:$n"; }; done
[ "$ok" = 1 ] && pass "no pool exceeds 8 sounds" || fail "pools over 8:$over"
ok=1; short=""; todo="$REPO_DIR/build/HUMAN_TODO.md"
for c in $CUES; do
  n="$(pool_size "$REAL_MAP" "$c")"
  if [ "$n" -lt 3 ]; then
    if grep -q -E "M8:.*\b$c\b" "$todo" 2>/dev/null; then short="$short $c:$n(HUMAN_TODO)"; else ok=0; short="$short $c:$n(NOT in HUMAN_TODO)"; fi
  fi
done
[ "$ok" = 1 ] && pass "every cue type has a pool of at least 3 sounds, or build/HUMAN_TODO.md names it as short (${short:- none short})" \
  || fail "short pools not named in build/HUMAN_TODO.md:$short"
assert_eq "$(json_get "$REAL_MAP" short_pools)" "$(python -c 'import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig"))
print(json.dumps([c for c in sys.argv[2].split() if len(m["pools"].get(c, [])) < 3]))' "$REAL_MAP" "$CUES")" "short_pools in the map matches the pools"
assert_true "the map was classified with the indexer model (model answers present)" python -c 'import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8-sig")); sys.exit(0 if m["counts"].get("by_model", 0) > 0 and m.get("model") else 1)' "$REAL_MAP"
no_emdash_in "no em dash in the map, SFX-MAP.md and overrides.txt" "$REAL_MAP" "$REAL_PACK/SFX-MAP.md" "$REAL_PACK/overrides.txt"
assert_grep "^## Thresholds" "$REAL_PACK/SFX-MAP.md" "SFX-MAP.md records the thresholds"
assert_grep "^## Excluded files" "$REAL_PACK/SFX-MAP.md" "SFX-MAP.md lists the excluded files"
if [ "$n_audio" != 0 ]; then
  # a rebuild of the unchanged pack: no model call (the fake would fail it), the map untouched, previews present
  fake_claude_on; export FAKE_CLAUDE_MODE=error
  sha1_before="$(sha_of "$REAL_MAP")"
  out="$(bash "$BUILD" 2>&1)"; rc=$?
  assert_rc 0 $rc "bash pipeline/bin/build-sfx-map on the unchanged styles/sfx/ exits 0 ($(printf '%s' "$out" | tail -n 1 | cut -c1-100))"
  assert_eq "$(fake_calls)" "0" "and makes no model call"
  assert_eq "$(sha_of "$REAL_MAP")" "$sha1_before" "and leaves the committed map as it is"
  bash "$BUILD" --check >/dev/null 2>&1; assert_rc 0 $? "--check exits 0: the committed map is current"
  fake_claude_off
  for c in $CUES; do
    n="$(pool_size "$REAL_MAP" "$c")"
    [ "$n" -gt 0 ] || continue
    if [ -f "$REAL_PACK/previews/$c.wav" ] && [ -f "$REAL_PACK/previews/$c.txt" ]; then
      [ "$(grep -c '^[0-9]*\. at ' "$REAL_PACK/previews/$c.txt")" = "$n" ] && pass "previews/$c.wav and .txt exist, $n sounds listed" || fail "previews/$c.txt lists a different count than the pool ($n)"
    else
      fail "previews/$c.wav or .txt missing"
    fi
  done
  no_emdash_in "no em dash in the preview listings" "$REAL_PACK"/previews/*.txt
fi
fi

test_summary
