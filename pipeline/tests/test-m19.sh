#!/usr/bin/env bash
# test-m19.sh: the acceptance test of M19 (Exports and channels side by side). No model call (the fake claude where a call is needed),
# no engine call.
#   bash pipeline/tests/test-m19.sh                       all sections (about 40 minutes: every run.sh start pays for the preflight)
#   M19_SECTIONS="1 4 5" bash pipeline/tests/test-m19.sh  only those sections
#
#   1. the export names and the numbering: dummy exports of a fixture channel are exports/<id>-1 and <id>-2 with <id>-N files, a second
#      channel's first export is <id2>-1 in the same exports/, after deleting exports/<id>-2 the next is <id>-3 (from history)
#   2. the export migration on the rehearsal fixture (after M18's moves): the dry run, the run, the undo, again, a kill halfway; then the real
#      folder (build/M19's records, check-manifest.py --after, no exports/N left)
#   3. the youtube-shorts exporter: platform.json and the schema, the selftest on the 6 fixture inputs and the planted faults, the stage's
#      run.sh with the fake model (one rewrite, NEEDS REVIEW after the second failure), the export step of a youtube-shorts channel
#   4. the heavy lock: dummy runners of two channels with heavy dummy stages never overlap a heavy step, one WAIT line per wait
#   5. limit sharing: a limit hit by channel A makes channel B wait for the same reset with no model call
#   6. quota: daily_quota 1 makes the second dummy idea wait with the IDLE line (fast clock), and it runs after midnight
#   7. new-channel: a new channel is listed incomplete by preflight, and runs in dummy mode once it is filled in
#   8. test-isolation.sh (both parts), the dummy fingerprint (build/M19/fingerprint/), runner-status and doctor, no em dash
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SECTIONS="${M19_SECTIONS:-1 2 3 4 5 6 7 8}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
T="$(mktemp -d)"
m19_cleanup() { rm -rf "$T" 2>/dev/null || { sleep 2; rm -rf "$T" 2>/dev/null; }; tests_cleanup; }
trap m19_cleanup EXIT
TM="$(mixed "$T")"
PT="$TESTS_DIR"
RM="$(mixed "$REPO_DIR")"
STATE_PY="$REPO_DIR/pipeline/lib/state.py"
EXPORT_PY="$REPO_DIR/pipeline/lib/export.py"
export NO_COLOR=1
ts_regex='^\[[0-9]{2}:[0-9]{2}\] '

treesum() { python - "$1" <<'PYEOF'
import hashlib, os, sys
root = sys.argv[1]
h = hashlib.sha256()
n = 0
for dp, dn, fn in os.walk(root):
    dn[:] = sorted(d for d in dn if d not in (".git", "build"))
    for f in sorted(fn):
        p = os.path.join(dp, f)
        h.update(os.path.relpath(p, root).replace(chr(92), "/").encode()); h.update(open(p, "rb").read()); n += 1
print(n, h.hexdigest()[:20])
PYEOF
}
tree() {  # tree <dir>: relative paths, a trailing slash on folders, sorted, the run stamp replaced
  (cd "$1" 2>/dev/null && find . -mindepth 1 | sed 's#^\./##' | while IFS= read -r p; do if [ -d "$p" ]; then echo "$p/"; else echo "$p"; fi; done) \
    | sed -E 's/20[0-9]{2}-[0-9]{2}-[0-9]{2}_[0-9]{4}/<ts>/g' | LC_ALL=C sort
}
add_channel() {  # add_channel <id> [enabled] [platform]: a channel in the sandbox, a copy of channels/flashfx with its own id and an empty queue
  local id="$1" en="${2:-true}" plat="${3:-instagram-reels}"
  cp -r "$SANDBOX/channels/flashfx" "$SANDBOX/channels/$id"
  rm -rf "$SANDBOX/channels/$id/.cache" "$SANDBOX/channels/$id/runs" "$SANDBOX/channels/$id/logs" "$SANDBOX/channels/$id/.locks"
  mkdir -p "$SANDBOX/channels/$id/logs"; : > "$SANDBOX/channels/$id/ideas.txt"
  python - "$SANDBOX_M/channels/$id/channel.json" "$id" "$en" "$plat" <<'PYEOF'
import json, sys
p, cid, en, plat = sys.argv[1:5]
d = json.load(open(p, encoding="utf-8"))
d["id"] = cid; d["name"] = cid.capitalize(); d["enabled"] = (en == "true"); d["brand"] = {"display_name": cid.capitalize()}; d["platform"] = plat
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
}
set_channel_json() {  # set_channel_json <id> <python statement on d>
  python - "$SANDBOX_M/channels/$1/channel.json" "$2" <<'PYEOF'
import json, sys
p, stmt = sys.argv[1:3]
d = json.load(open(p, encoding="utf-8"))
exec(stmt)
open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=2) + "\n")
PYEOF
}
run_ch() {  # run_ch <channel> <outfile> [env...]: the real run.sh against $SANDBOX for one channel, --once
  local ch="$1" out="$2"; shift 2
  ( cd "$SANDBOX" && env NO_COLOR=1 "$@" timeout 1500 bash "$REPO_DIR/run.sh" --channel "$ch" --once ) > "$out" 2>&1
}
jget() { python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8-sig"))
for k in sys.argv[2].split("."):
    d = d.get(k) if isinstance(d, dict) else None
print(json.dumps(d) if isinstance(d, (list, dict, bool)) else ("" if d is None else d))' "$1" "$2"; }
wait_for() {  # wait_for <regex> <file> <seconds>
  local i=0
  while [ "$i" -lt "$(( $3 * 5 ))" ]; do grep -q -E -- "$1" "$2" 2>/dev/null && return 0; sleep 0.2; i=$((i + 1)); done
  return 1
}
HIST_A() { printf '%s' "$SANDBOX_M/channels/$1/logs/history.txt"; }

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 1; then
section "1. the export names and the numbering"
sandbox_init
fast_mode
# units: the number comes from this channel's folders and history lines
EX="$SANDBOX_M/exports"; H="$T/h.txt"
nn() { python "$EXPORT_PY" next-number --exports "$EX" --channel "$1" --history "$H"; }
assert_eq "$(nn flashfx)" "1" "numbering: the first export of a channel is 1"
mkdir -p "$SANDBOX/exports/flashfx-3" "$SANDBOX/exports/flashfx-7" "$SANDBOX/exports/other-12" "$SANDBOX/exports/9" "$SANDBOX/exports/notes"
assert_eq "$(nn flashfx)" "8" "numbering: this channel's highest folder plus 1; another channel's folders, a plain number and other names do not count"
assert_eq "$(nn other)" "13" "numbering: the other channel counts its own folders"
printf '2026-11-01 10:00 | idea a | external | exported flashfx-9\n2026-11-01 11:00 | idea b | - | dropped: x\n2026-11-01 12:00 | idea c | method | exported other-20\n' > "$H"
assert_eq "$(nn flashfx)" "10" "numbering: the history line 'exported flashfx-9' counts after its folder was deleted"
assert_eq "$(nn other)" "21" "numbering: the other channel's history counts for it only"
rm -rf "$SANDBOX/exports"
: > "$H"

add_channel second
printf '{Idea one for the first channel: gh in 60 seconds}\n{Idea two for the first channel: uv in one tool}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
printf '{Idea for the second channel: just in one line}\n' > "$SANDBOX/channels/second/ideas.txt"
run_ch flashfx "$T/s1a.out" REELS_DUMMY=all REELS_DUMMY_SECONDS=0.2; rc=$?
assert_rc 0 "$rc" "two dummy ideas of flashfx: the runner exits 0"
assert_grep "${ts_regex}DONE   exported flashfx-1 -> exports/flashfx-1/ \([0-9]+(s| min), 0 issues fixed\)$" "$T/s1a.out" "DONE line for flashfx-1"
assert_grep "${ts_regex}DONE   exported flashfx-2 -> exports/flashfx-2/ \([0-9]+(s| min), 0 issues fixed\)$" "$T/s1a.out" "DONE line for flashfx-2"
for n in 1 2; do
  assert_file "$SANDBOX/exports/flashfx-$n/flashfx-$n.mp4" "exports/flashfx-$n/flashfx-$n.mp4"
  assert_file "$SANDBOX/exports/flashfx-$n/flashfx-${n}captions.txt" "exports/flashfx-$n/flashfx-${n}captions.txt"
  assert_file "$SANDBOX/exports/flashfx-$n/flashfx-${n}hook2.mp4" "exports/flashfx-$n/flashfx-${n}hook2.mp4"
  assert_grep "^flashfx-$n\.mp4 uses: \"" "$SANDBOX/exports/flashfx-$n/flashfx-${n}captions.txt" "captions $n: the HOOKS line carries the new name"
  assert_grep "^flashfx-${n}hook2\.mp4 uses: \"" "$SANDBOX/exports/flashfx-$n/flashfx-${n}captions.txt" "captions $n: the hook 2 line carries the new name"
done
assert_grep "^channels/flashfx/runs/[0-9_]+-" "$SANDBOX/exports/flashfx-1/flashfx-1captions.txt" "captions: the RUN path is channels/<id>/runs/<run>"
assert_eq "$(ls "$SANDBOX/exports" | paste -sd,)" "flashfx-1,flashfx-2" "exports/ holds exactly flashfx-1 and flashfx-2"
assert_grep '\| exported flashfx-1$' "$(HIST_A flashfx)" "history: exported flashfx-1"
assert_grep '\| exported flashfx-2$' "$(HIST_A flashfx)" "history: exported flashfx-2"
run_ch second "$T/s1b.out" REELS_DUMMY=all REELS_DUMMY_SECONDS=0.2; rc=$?
assert_rc 0 "$rc" "the second channel's runner exits 0"
assert_file "$SANDBOX/exports/second-1/second-1.mp4" "a second channel's first export is second-1 in the same exports/"
assert_file "$SANDBOX/exports/second-1/second-1captions.txt" "and its captions file is second-1captions.txt"
assert_eq "$(ls "$SANDBOX/exports" | paste -sd,)" "flashfx-1,flashfx-2,second-1" "exports/ holds both channels"
assert_not_grep 'flashfx' "$SANDBOX/exports/second-1/second-1captions.txt" "the second channel's captions file names no other channel"
assert_grep '\| exported second-1$' "$(HIST_A second)" "the second channel's history line"
assert_not_grep 'exported second' "$(HIST_A flashfx)" "the histories do not mix"
# after deleting a posted folder the number is not reused: it comes from history
rm -rf "$SANDBOX/exports/flashfx-2"
assert_eq "$(python "$EXPORT_PY" next-number --exports "$EX" --channel flashfx)" "3" "after deleting exports/flashfx-2 the next number is 3 (from the channel's history)"
printf '{Idea three for the first channel: bun in a minute}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
run_ch flashfx "$T/s1c.out" REELS_DUMMY=all REELS_DUMMY_SECONDS=0.2; rc=$?
assert_rc 0 "$rc" "the third idea: the runner exits 0"
assert_file "$SANDBOX/exports/flashfx-3/flashfx-3.mp4" "the next export is flashfx-3, not flashfx-2 again"
assert_no_file "$SANDBOX/exports/flashfx-2" "flashfx-2 stays deleted"
assert_eq "$(find "$SANDBOX/.locks" "$SANDBOX/channels/flashfx/.locks" "$SANDBOX/channels/second/.locks" -mindepth 1 2>/dev/null | wc -l | tr -d ' ')" "0" "no lock is left behind"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 2; then
section "2. the export migration: rehearsal fixture, undo, again; the real folder"
MC="$REPO_DIR/pipeline/bin/migrate-channels"
new_fx() {  # new_fx <name>: the rehearsal fixture with the new .gitignore, M18 executed and committed (the state M19 starts from)
  local d="$T/$1"
  python "$PT/m17-fixture.py" "$(mixed "$d")" >/dev/null || return 1
  cp "$REPO_DIR/.gitignore" "$d/.gitignore"
  printf '%s\n' 'library/voice/*' '!library/voice/README.txt' 'library/.hooks.index.json' 'styles/*/refs/' 'styles/*/analysis/' 'styles/sfx/**/*.wav' \
    'motion-lib/.harness/' 'golden/*/golden.mp4' >> "$d/.gitignore"
  git -C "$d" add -A && git -C "$d" commit -q -m "new gitignore" || return 1
  bash "$MC" --ms M18 --root "$(mixed "$d")" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/$1-m18.out" 2>&1 || return 1
  git -C "$d" add -A && git -C "$d" commit -q -m "M18 moves" || return 1
}
assert_true "the rehearsal fixture builds and M18 runs on it" new_fx fx
FX="$TM/fx"
ls "$FX/exports" | paste -sd, > "$T/fx-exports-before.txt"
assert_grep '^1,2,notes.txt$' "$T/fx-exports-before.txt" "the fixture has exports/1, exports/2 and a note"
sum0="$(treesum "$FX")"
bash "$MC" --dry-run --ms M19 --root "$FX" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/m19dry.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the dry run exits 0"
assert_grep '^DRY RUN: nothing changed' "$T/m19dry.out" "the dry run says nothing changed"
assert_grep 'STEP rename-in-place exports/1 -> exports/flashfx-1' "$T/m19dry.out" "the dry run lists the rename of exports/1"
assert_grep 'STEP rewrite  channels/flashfx/logs/history.txt' "$T/m19dry.out" "the dry run lists the history rewrite"
assert_eq "$(treesum "$FX")" "$sum0" "the dry run changed nothing in the tree (checksums)"
rm -rf "$FX/build/M19"
bash "$MC" --ms M19 --root "$FX" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/m19run1.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the run exits 0"
assert_grep '^migrate M19: verified' "$T/m19run1.out" "the run ends verified"
assert_grep $'\tverified\t' "$FX/build/M19/migration-log.tsv" "the migration log ends verified"
assert_file "$FX/build/M19/undo-migration.sh" "the undo script is written"
for n in 1 2; do
  assert_file "$FX/exports/flashfx-$n/flashfx-$n.mp4" "exports/flashfx-$n/flashfx-$n.mp4"
  assert_file "$FX/exports/flashfx-$n/flashfx-${n}captions.txt" "exports/flashfx-$n/flashfx-${n}captions.txt"
  assert_file "$FX/exports/flashfx-$n/flashfx-${n}hook2.mp4" "exports/flashfx-$n/flashfx-${n}hook2.mp4"
  assert_file "$FX/exports/flashfx-$n/project/p.json" "project/ of export $n keeps its name"
  assert_no_file "$FX/exports/$n" "exports/$n is gone"
  assert_grep "^flashfx-$n\.mp4 uses:" "$FX/exports/flashfx-$n/flashfx-${n}captions.txt" "captions $n: the HOOKS line follows"
  assert_grep "^flashfx-${n}hook2\.mp4 uses:" "$FX/exports/flashfx-$n/flashfx-${n}captions.txt" "captions $n: the hook 2 line follows"
done
assert_file "$FX/exports/notes.txt" "exports/notes.txt (not an export folder) stays"
assert_grep '\| exported flashfx-1$' "$FX/channels/flashfx/logs/history.txt" "history: exported 1 became exported flashfx-1"
assert_grep '\| exported flashfx-2$' "$FX/channels/flashfx/logs/history.txt" "history: exported 2 became exported flashfx-2"
assert_not_grep '\| exported [0-9]+$' "$FX/channels/flashfx/logs/history.txt" "history: no old export line is left"
assert_eq "$(python "$EXPORT_PY" next-number --exports "$FX/exports" --channel flashfx --history "$FX/channels/flashfx/logs/history.txt")" "3" "the next export after the migration is flashfx-3"
python "$PT/check-manifest.py" --after --root "$FX" --manifest "$FX/build/M19/move-manifest.tsv" > "$T/m19after.out" 2>&1; rc=$?
assert_rc 0 "$rc" "check-manifest.py --after passes on the migrated fixture ($(tail -n 1 "$T/m19after.out" | cut -c1-80))"
assert_eq "$(git -C "$FX" status --porcelain | grep -v 'build/' | grep -v '^R' | wc -l | tr -d ' ')" "0" "git status shows only renames (the exports are not tracked; the history is ignored)"
# the undo
bash "$MC" --undo --ms M19 --root "$FX" > "$T/m19undo.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the undo exits 0"
assert_eq "$(treesum "$FX")" "$sum0" "the undo brings back an identical tree (checksums)"
assert_file "$FX/exports/1/1captions.txt" "exports/1/1captions.txt is back"
# and again
rm -rf "$FX/build/M19"
bash "$MC" --ms M19 --root "$FX" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/m19run2.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the run after the undo exits 0"
assert_grep '^migrate M19: verified' "$T/m19run2.out" "and ends verified again"
bash "$MC" --ms M19 --root "$FX" > "$T/m19run3.out" 2>&1; rc=$?
assert_rc 0 "$rc" "a third start only verifies"
assert_grep 'this migration was verified before' "$T/m19run3.out" "and says so"
bash "$MC" --undo --ms M19 --root "$FX" >/dev/null 2>&1
assert_eq "$(treesum "$FX")" "$sum0" "after the second undo the tree is identical again"
# a run killed halfway is undone by the next start
rm -rf "$FX/build/M19"
MIGRATE_KILL_AFTER=1 bash "$MC" --ms M19 --root "$FX" --plan "$REPO_DIR/build/M17/move-manifest.tsv" > "$T/m19kill.out" 2>&1
assert_grep 'ending the process after 1 move' "$T/m19kill.out" "the planted kill ends the run after 1 move"
assert_true "the folder is half moved (exports/flashfx-1 exists, exports/2 too)" bash -c "[ -d '$FX/exports/flashfx-1' ] && [ -d '$FX/exports/2' ]"
bash "$MC" --ms M19 --root "$FX" > "$T/m19restart.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the next start exits 0"
assert_grep 'without its final .verified. line: undoing it first' "$T/m19restart.out" "the next start undoes the killed attempt first"
assert_grep '^migrate M19: verified' "$T/m19restart.out" "then migrates and verifies"
# the real folder
B="$REPO_DIR/build/M19"
assert_no_file "$REPO_DIR/exports/1" "the real folder has no exports/N folder left"
assert_eq "$(ls "$REPO_DIR/exports" 2>/dev/null | grep -c -E '^[0-9]+$')" "0" "no plain-number export folder in the real exports/"
assert_file "$B/move-manifest.tsv" "build/M19/move-manifest.tsv exists (the real run's executed manifest)"
assert_file "$B/manifest-diff.md" "build/M19/manifest-diff.md exists"
assert_file "$B/real-migration.txt" "build/M19/real-migration.txt: the output of the migration on the real folder"
assert_grep 'nothing to do|verified' "$B/real-migration.txt" "the real run found no M19 line (the folder has no export yet) or verified them"
python "$PT/check-manifest.py" --after --root "$RM" --manifest "$REPO_DIR/build/M18/move-manifest.tsv" > "$T/gate.out" 2>&1
assert_eq "$(grep '^FAIL' "$T/gate.out" | grep -v -E 'checksum of channels/flashfx/logs/(runner.log|status.txt) changed|bytes, the manifest says' | wc -l | tr -d ' ')" "0" "the gate of 14.13: check-manifest.py --after on M18's manifest (only the growth of the logs and the gallery differs)"
bash "$REPO_DIR/pipeline/bin/preflight" --channel flashfx > "$T/pf.out" 2>&1; rc=$?
assert_rc 0 "$rc" "preflight --channel flashfx passes"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 3; then
section "3. the youtube-shorts exporter and the platform interface"
for p in instagram-reels youtube-shorts; do
  python "$REPO_DIR/pipeline/lib/platform_lib.py" check "$p" > "$T/pl.out" 2>&1; rc=$?
  assert_rc 0 "$rc" "platform.json of $p validates against pipeline/schemas/platform.schema.json"
done
bad="$T/badplat"; mkdir -p "$bad/pipeline/platforms/zz"; printf '{"id": "zz", "name": "ZZ"}\n' > "$bad/pipeline/platforms/zz/platform.json"
mkdir -p "$bad/pipeline/schemas"; cp "$REPO_DIR/pipeline/schemas/platform.schema.json" "$bad/pipeline/schemas/"
REELS_REPO="$TM/badplat" python "$REPO_DIR/pipeline/lib/platform_lib.py" check zz > "$T/pl2.out" 2>&1; rc=$?
assert_rc 1 "$rc" "a platform.json without its required keys fails the check"
python "$PT/m19-ytshorts.py" selftest > "$T/yt-self.out" 2>&1; rc=$?
assert_rc 0 "$rc" "the exporter's selftest (6 fixture inputs, the planted faults, the caption_max rule): $(tail -n 1 "$T/yt-self.out")"
assert_not_grep '^FAIL' "$T/yt-self.out" "the selftest has no FAIL line"
for f in "an 1100-character description" "5 hashtags" "400-character" "without a list" "earlier description"; do
  assert_grep "PASS.*$f|PASS.*$(printf '%s' "$f" | sed 's/ .*//')" "$T/yt-self.out" "the selftest covers: $f"
done

# the stage's run.sh with the fake model on a serial part
sandbox_init
fast_mode
add_channel shorts true youtube-shorts
set_channel_json shorts 'd["export"] = {"caption_max": 100, "description_max": 1000, "hashtags": 4, "required_hashtags": ["#shorts", "#businessstory"], "pinned_comment": True}'
FXD="$T/ytfix"; mkdir -p "$FXD"; python "$PT/m19-ytshorts.py" fixtures "$FXD" > /dev/null
fake_claude_on
yt_run() {  # yt_run <fixture name> <fixture-1.json> [fixture-2.json]: a run folder with input.json, the stage with the fake model; prints the run dir
  local name="$1" f1="$2" f2="${3:-}" rd created
  created="$(printf '{%s}' "$name" | python "$STATE_PY" new --runs "$SANDBOX_M/channels/shorts/runs" --id "yt-$name-$RANDOM" | python -c 'import json, sys; print(json.load(sys.stdin)["run_dir"])')"
  rd="$created"; mkdir -p "$rd/export" "$rd/13-render"
  python - "$FXD/$name.json" "$rd/export/input.json" "$(basename "$rd")" <<'PYEOF'
import json, os, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); d["run_id"] = sys.argv[3]
if os.environ.get("YT_FILE_EARLIER"):
    d["earlier_descriptions"] = []   # the stage then reads the channel's own logs/descriptions.jsonl
json.dump(d, open(sys.argv[2], "w", encoding="utf-8", newline="\n"), indent=2)
PYEOF
  printf 'dummy mp4\n' > "$rd/13-render/final.mp4"
  rm -rf "$T/fx-answers"; mkdir -p "$T/fx-answers"
  cp "$f1" "$T/fx-answers/14-export.1.json"; cp "${f2:-$f1}" "$T/fx-answers/14-export.2.json"
  fake_claude_reset
  ( cd "$SANDBOX" && env REELS_CHANNEL=shorts FAKE_CLAUDE_FIXTURES="$TM/fx-answers" FAKE_CLAUDE_MODE=auto bash "$REPO_DIR/pipeline/platforms/youtube-shorts/run.sh" "$rd" ) > "$rd/yt.out" 2>&1
  printf '%s' "$?" > "$rd/yt.rc"
  printf '%s' "$rd"
}
plant() {  # plant <good answer file> <kind> <out>: a bad answer made from a good one
  python - "$1" "$2" "$3" <<'PYEOF'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8")); kind = sys.argv[2]
d = a["description"]
if kind == "long":
    a["description"] = d.rsplit("\n", 1)[0] + "\n" + ("Filler words that go on and on without a point. " * 24) + "\n#shorts #a #b #c"
elif kind == "tags":
    a["description"] = d.rsplit("\n", 1)[0] + "\n#shorts #businessstory #1990s #storytime #extra"
elif kind == "paragraph":
    a["description"] = a["description"].split("\n")[0] + "\n" + ("This part keeps going in one long unbroken paragraph with no list at all, " * 6) + "\n\n#shorts #businessstory #1990s #storytime"
elif kind == "nolist":
    a["description"] = "\n".join(x for x in d.split("\n") if not x.startswith("- "))
json.dump(a, open(sys.argv[3], "w", encoding="utf-8", newline="\n"))
PYEOF
}
GOOD="$FXD/answer-ok-serial-part1.json"
assert_file "$GOOD" "the fixture answer of the Part 1 input exists"
rd="$(yt_run serial-part1 "$GOOD")"
assert_rc 0 "$(cat "$rd/yt.rc")" "run.sh with a good answer exits 0"
assert_file "$rd/14-export/export.json" "14-export/export.json is written"
assert_eq "$(jget "$rd/14-export/export.json" needs_review)" "[]" "a good first answer: no NEEDS REVIEW"
assert_eq "$(python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG")" "1" "a good first answer: exactly one model call"
assert_file "$SANDBOX/channels/shorts/logs/descriptions.jsonl" "the description is stored in the channel's logs/descriptions.jsonl"
for kind in long tags paragraph nolist; do
  plant "$GOOD" "$kind" "$T/bad-$kind.json"
  rd="$(yt_run serial-part1 "$T/bad-$kind.json" "$GOOD")"
  assert_rc 0 "$(cat "$rd/yt.rc")" "a planted '$kind' fault then a good answer: run.sh exits 0"
  assert_eq "$(python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG")" "2" "'$kind': the bad answer got exactly one rewrite (2 calls)"
  assert_eq "$(jget "$rd/14-export/export.json" needs_review)" "[]" "'$kind': the rewrite passed, no NEEDS REVIEW"
done
# a copy of an earlier description: the channel's descriptions.jsonl now holds the Part 1 description
rd="$(YT_FILE_EARLIER=1 yt_run serial-part1 "$GOOD" "$GOOD")"
assert_rc 0 "$(cat "$rd/yt.rc")" "the same description again: run.sh exits 0"
assert_true "a copy of an earlier description fails its check and goes out with NEEDS REVIEW after the rewrite also fails" python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if d["needs_review"] else 1)' "$rd/14-export/export.json"
assert_eq "$(python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG")" "2" "the copy got one rewrite, then NEEDS REVIEW (2 calls)"
# two bad answers: NEEDS REVIEW, and no title is longer than caption_max
plant "$GOOD" long "$T/bad-long.json"
rd="$(yt_run serial-mid "$T/bad-long.json" "$T/bad-long.json")"
assert_true "two failing answers: the export carries NEEDS REVIEW lines" python -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if d["needs_review"] and all(x.startswith("youtube-shorts exporter") or True for x in d["needs_review"]) else 1)' "$rd/14-export/export.json"
assert_true "no title is longer than caption_max (100)" python -c 'import json, sys
sys.exit(0 if all(len(json.load(open(p, encoding="utf-8"))["title"]) <= 100 for p in sys.argv[1:]) else 1)' "$rd/14-export/export.json"
fake_claude_off

# the export step of a youtube-shorts channel: <id>-N.mp4 and <id>-Ncaptions.txt, no hook 2 clip
GOODEX="$T/ex-good"; mkdir -p "$GOODEX"
rd="$(yt_run serial-final "$FXD/answer-ok-serial-final.json")"
printf '{x}\n' > /dev/null
( cd "$SANDBOX" && env REELS_CHANNEL=shorts REELS_ROOT="$SANDBOX_M" python "$EXPORT_PY" run --run-dir "$(mixed "$rd")" --exports "$SANDBOX_M/exports" --root "$SANDBOX_M/channels/shorts" > "$T/yt-export.json" 2> "$T/yt-export.err" ); rc=$?
assert_rc 0 "$rc" "export.py run on a youtube-shorts run exits 0 ($(head -c 200 "$T/yt-export.err"))"
assert_file "$SANDBOX/exports/shorts-1/shorts-1.mp4" "exports/shorts-1/shorts-1.mp4"
assert_file "$SANDBOX/exports/shorts-1/shorts-1captions.txt" "exports/shorts-1/shorts-1captions.txt"
assert_no_file "$SANDBOX/exports/shorts-1/shorts-1hook2.mp4" "no hook 2 clip for youtube-shorts"
assert_eq "$(grep -E '^(STORY|TITLE|DESCRIPTION|PINNED COMMENT|UPLOAD STEPS|HOOKS|NEEDS REVIEW|FACTS AND SOURCES|RUN)$' "$SANDBOX/exports/shorts-1/shorts-1captions.txt" | paste -sd,)" "STORY,TITLE,DESCRIPTION,PINNED COMMENT,UPLOAD STEPS,HOOKS,FACTS AND SOURCES,RUN" "the captions file has the youtube-shorts sections of spec section 8 in order"
assert_grep '^shorts-1\.mp4 uses: "' "$SANDBOX/exports/shorts-1/shorts-1captions.txt" "the HOOKS line carries the export name"
assert_grep '^channels/shorts/runs/' "$SANDBOX/exports/shorts-1/shorts-1captions.txt" "the RUN section is channels/<id>/runs/<run>"
assert_not_grep 'CAPTION|HASHTAGS|COMMENT KEYWORD' "$SANDBOX/exports/shorts-1/shorts-1captions.txt" "no instagram section in it"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 4; then
section "4. the heavy lock: two channels' dummy runners never overlap a heavy step"
sandbox_init
fast_mode
add_channel second
printf '{Heavy idea for flashfx: one}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
printf '{Heavy idea for second: two}\n' > "$SANDBOX/channels/second/ideas.txt"
TRACE="$TM/heavy-trace.txt"; : > "$TRACE"
export REELS_HEAVY_TRACE="$TRACE" REELS_HEAVY_POLL=0.2
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_DUMMY_HEAVY=08-voiceover,10-build,13-render REELS_DUMMY_SECONDS=1.5 timeout 1500 bash "$REPO_DIR/run.sh" --channel flashfx --once ) > "$T/hv-a.out" 2>&1 &
pa=$!
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_DUMMY_HEAVY=08-voiceover,10-build,13-render REELS_DUMMY_SECONDS=1.5 timeout 1500 bash "$REPO_DIR/run.sh" --channel second --once ) > "$T/hv-b.out" 2>&1 &
pb=$!
wait "$pa"; rca=$?; wait "$pb"; rcb=$?
unset REELS_HEAVY_TRACE REELS_HEAVY_POLL
assert_rc 0 "$rca" "the flashfx runner exits 0"
assert_rc 0 "$rcb" "the second channel's runner exits 0"
assert_eq "$(grep -c ' start ' "$TRACE")" "6" "six heavy steps ran (three per channel)"
python - "$TRACE" > "$T/overlap.txt" <<'PYEOF'
import sys
ev = []
for line in open(sys.argv[1], encoding="utf-8"):
    p = line.split()
    if len(p) >= 4:
        ev.append((float(p[0]), p[1], p[2], " ".join(p[3:])))
ev.sort()
busy = None
bad = 0
for t, kind, ch, label in ev:
    if kind == "start":
        if busy is not None:
            bad += 1
        busy = (ch, label)
    elif kind == "end":
        busy = None
print("overlaps %d" % bad)
PYEOF
assert_grep '^overlaps 0$' "$T/overlap.txt" "no two heavy steps overlap (timestamps in the trace)"
waits_a="$(grep -c -E "${ts_regex}WAIT   heavy: " "$T/hv-a.out")"; waits_b="$(grep -c -E "${ts_regex}WAIT   heavy: " "$T/hv-b.out")"
assert_true "a runner that had to wait printed WAIT lines ($waits_a and $waits_b): at least one wait happened" test $((waits_a + waits_b)) -ge 1
assert_eq "$(grep -c "WAIT   heavy: " "$SANDBOX/channels/flashfx/logs/runner.log" | tr -d ' ')" "$waits_a" "the WAIT lines are in the channel's runner.log too"
cat "$T/hv-a.out" "$T/hv-b.out" > "$T/hv-ab.out"
assert_grep "${ts_regex}WAIT   heavy: (flashfx|second) dummy [0-9a-z-]+ holds it since [0-9]{2}:[0-9]{2}$" "$T/hv-ab.out" "a WAIT line names the holder, its step and the time"
assert_eq "$(ls "$SANDBOX/.locks" 2>/dev/null | wc -l | tr -d ' ')" "0" "no lock is left behind at the root"
# a stale lock (its holder is gone) is broken at once
mkdir -p "$SANDBOX/.locks/heavy.lock"; printf '999999 %s ghost render S13\n' "$(date +%s)" > "$SANDBOX/.locks/heavy.lock/holder"
out="$(REELS_ROOT="$SANDBOX_M" REELS_CHANNEL=flashfx REELS_HEAVY_POLL=0.2 bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; source "$REELS_PIPELINE/lib/log.sh"; source "$REELS_PIPELINE/lib/config.sh"; source "$REELS_PIPELINE/lib/state.sh"; source "$REELS_PIPELINE/lib/heavy.sh"; heavy_run render "S13 render" -- echo ran' 2>&1)"
assert_eq "$(printf '%s' "$out" | tail -n 1)" "ran" "a lock whose holder is gone does not block"
assert_not_grep 'WAIT' <(printf '%s' "$out") "and printed no WAIT line"
# the editor lock is the same mechanism under its own name
mkdir -p "$SANDBOX/.locks/editor.lock"; printf '999999 %s ghost editor x\n' "$(date +%s)" > "$SANDBOX/.locks/editor.lock/holder"
out="$(REELS_ROOT="$SANDBOX_M" REELS_CHANNEL=flashfx REELS_HEAVY_POLL=0.2 bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; source "$REELS_PIPELINE/lib/log.sh"; source "$REELS_PIPELINE/lib/config.sh"; source "$REELS_PIPELINE/lib/state.sh"; source "$REELS_PIPELINE/lib/heavy.sh"; editor_run "advance the editor copy" -- echo edited' 2>&1)"
assert_eq "$(printf '%s' "$out" | tail -n 1)" "edited" "editor_run: the editor lock works like the heavy lock"
assert_no_file "$SANDBOX/.locks/editor.lock" "and is released"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 5; then
section "5. limit sharing: a limit hit by one channel makes the other wait for the same reset, with no model call"
sandbox_init
fake_claude_on
add_channel second
mkdir -p "$SANDBOX/channels/flashfx/runs/r1/01-research" "$SANDBOX/channels/second/runs/r1/01-research"
printf 'hello\n' > "$T/p.md"
drive() {  # drive <channel> <outfile>: one ai() call of that channel through the fake claude
  ( cd "$SANDBOX" && env REELS_CHANNEL="$1" REELS_ROOT="$SANDBOX_M" REELS_LIMIT_MARGIN=12 bash "$REPO_DIR/pipeline/tests/ai-driver.sh" research "$SANDBOX_M/channels/$1/runs/r1/01-research" "$TM/p.md" --no-protect ) > "$2" 2>&1
}
# A hits a limit (the fake says it resets right now: epoch+0), waits for reset + 3 s margin and retries
export FAKE_CLAUDE_MODE="limit:epoch+0"
t0="$(date +%s)"
drive flashfx "$T/lim-a.out" &
pa=$!
i=0; while [ ! -f "$SANDBOX/.locks/limit.json" ] && [ "$i" -lt 100 ]; do sleep 0.1; i=$((i + 1)); done
assert_file "$SANDBOX/.locks/limit.json" "channel A's limit wrote .locks/limit.json"
assert_true "limit.json names channel A and a target in the future" python -c 'import json, sys, time
d = json.load(open(sys.argv[1], encoding="utf-8")); sys.exit(0 if d["channel"] == "flashfx" and d["target"] > time.time() - 1 else 1)' "$SANDBOX/.locks/limit.json"
target="$(python -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["target"])' "$SANDBOX/.locks/limit.json")"
calls_before="$(python -c 'import sys; print(sum(1 for l in open(sys.argv[1], encoding="utf-8") if l.strip()))' "$FAKE_CLAUDE_LOG")"
export FAKE_CLAUDE_MODE="ok:from B"
drive second "$T/lim-b.out"; rcb=$?
wait "$pa"; rca=$?
t1="$(date +%s)"
assert_rc 0 "$rcb" "channel B's call goes through after the wait"
assert_true "B waited for the same reset: it ended no earlier than A's target ($target)" test "$t1" -ge "$target"
assert_grep 'limit hit by flashfx, waiting for the same reset' "$T/lim-b.out" "B printed a LIMIT line naming A"
assert_true "B's call came at or after A's target" python -c 'import json, sys
calls = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
sys.exit(0 if calls[-1]["at"] >= int(sys.argv[2]) - 1 else 1)' "$FAKE_CLAUDE_LOG" "$target"
assert_grep "\| second \| shared .* limit \| hit by flashfx \|" "$SANDBOX/logs/limits.log" "the shared logs/limits.log has B's wait with its channel id"
assert_grep "\| flashfx \| .*limit \| reset " "$SANDBOX/logs/limits.log" "and A's own wait with its channel id"
assert_grep "shared .*limit wait: .* hit by flashfx" "$SANDBOX/logs/engine.log" "logs/engine.log has the shared wait"
python - "$FAKE_CLAUDE_LOG" "$calls_before" > "$T/calls.txt" <<'PYEOF'
import json, sys
calls = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
before = int(sys.argv[2])
print("calls_before=%d total=%d" % (before, len(calls)))
PYEOF
assert_true "B made no model call while the limit was on (the log has A's limit call, then A's retry and B's one call)" bash -c "grep -q 'calls_before=1 total=3' '$T/calls.txt'"
assert_no_file "$SANDBOX/.locks/limit.json" "the limit file is removed once the wait is over"
unset FAKE_CLAUDE_MODE
fake_claude_off
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 6; then
section "6. quota: daily_quota 1 makes the second idea wait with the IDLE line"
sandbox_init
fast_mode
set_channel_json flashfx 'd["daily_quota"] = 1; d["timezone"] = "Europe/Rome"'
printf '{Quota idea one: first}\n{Quota idea two: second}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
NOW="$TM/now.txt"
python -c 'import time; print(int(time.time()))' > "$NOW"
python - "$SANDBOX_M/channels/flashfx/channel.json" <<'PYEOF' > /dev/null
PYEOF
( cd "$SANDBOX" && env NO_COLOR=1 REELS_DUMMY=all REELS_DUMMY_SECONDS=0.2 REELS_NOW_FILE="$NOW" timeout 1500 bash "$REPO_DIR/run.sh" --channel flashfx ) > "$T/q.out" 2>&1 &
pq=$!
wait_for "${ts_regex}IDLE   quota 1/1 today, next idea after 00:00" "$T/q.out" 900; rc=$?
assert_rc 0 "$rc" "the IDLE line says: quota 1/1 today, next idea after 00:00"
assert_grep "${ts_regex}DONE   exported flashfx-1 " "$T/q.out" "the first idea exported"
sleep 3
assert_not_grep "exported flashfx-2" "$T/q.out" "the second idea did not start while the quota was reached"
assert_eq "$(python "$REPO_DIR/pipeline/lib/ideas.py" count --file "$SANDBOX_M/channels/flashfx/ideas.txt")" "1" "the second idea is still queued"
assert_eq "$(ls "$SANDBOX/exports" | paste -sd,)" "flashfx-1" "only flashfx-1 is in exports/"
bash "$REPO_DIR/pipeline/bin/runner-status" --channel flashfx 2>&1 | grep -q 'today: 1 of 1 exports (daily quota), reached' && pass "runner-status shows today's exports against the quota" || fail "runner-status shows today's exports against the quota"
# midnight: the fast clock moves a day on
python -c 'import time; print(int(time.time()) + 90000)' > "$NOW"
wait_for "${ts_regex}DONE   exported flashfx-2 " "$T/q.out" 900; rc=$?
assert_rc 0 "$rc" "after midnight (fast clock) the second idea runs and exports as flashfx-2"
kill "$pq" 2>/dev/null; sleep 1; kill -9 "$pq" 2>/dev/null; wait "$pq" 2>/dev/null
# --once with the quota reached: the line, the summary, exit 0, the idea stays
sandbox_init
fast_mode
set_channel_json flashfx 'd["daily_quota"] = 1'
printf '2026-11-01 10:00 | earlier | - | exported flashfx-1\n' | sed "s/^2026-11-01 10:00/$(date '+%Y-%m-%d %H:%M')/" > "$SANDBOX/channels/flashfx/logs/history.txt"
printf '{Waits for tomorrow}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
run_ch flashfx "$T/q2.out" REELS_DUMMY=all REELS_DUMMY_SECONDS=0.2; rc=$?
assert_rc 0 "$rc" "--once with the quota reached exits 0"
assert_grep "${ts_regex}IDLE   quota 1/1 today, next idea after 00:00" "$T/q2.out" "and prints the quota line"
assert_not_grep 'START  idea' "$T/q2.out" "and starts no idea"
python "$REPO_DIR/pipeline/lib/logcheck.py" story "$SANDBOX/channels/flashfx/logs/runner.log" > "$T/lc.out" 2>&1; rc=$?
assert_rc 0 "$rc" "logcheck.py understands the quota IDLE line and the summary ($(tail -n 1 "$T/lc.out" | cut -c1-100))"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 7; then
section "7. new-channel"
sandbox_init
fast_mode
# the sandbox carries pipeline/platforms and pipeline/formats only when the repo's own are used: new-channel runs from the repo against the sandbox root
env REELS_ROOT="$SANDBOX_M" bash "$REPO_DIR/pipeline/bin/new-channel" demo --format problem-solution-reel --platform youtube-shorts --name "Demo Channel" > "$T/nc.out" 2>&1; rc=$?
assert_rc 0 "$rc" "new-channel creates the channel"
assert_file "$SANDBOX/channels/demo/channel.json" "channels/demo/channel.json"
assert_eq "$(jget "$SANDBOX/channels/demo/channel.json" enabled)" "false" "the channel starts disabled"
assert_eq "$(jget "$SANDBOX/channels/demo/channel.json" platform)" "youtube-shorts" "its platform is youtube-shorts"
assert_eq "$(jget "$SANDBOX/channels/demo/channel.json" export.caption_max)" "150" "the platform's defaults are in channel.json export"
assert_file "$SANDBOX/channels/demo/ideas.txt" "an empty ideas.txt"
assert_grep 'channels/demo/library/profile/voice.md' "$T/nc.out" "it prints what to fill in"
assert_grep 'preflight --channel demo' "$T/nc.out" "and the command that checks it"
env REELS_ROOT="$SANDBOX_M" bash "$REPO_DIR/pipeline/bin/new-channel" demo --format problem-solution-reel --platform youtube-shorts > "$T/nc2.out" 2>&1; rc=$?
assert_rc 2 "$rc" "a second new-channel with the same id exits 2"
env REELS_ROOT="$SANDBOX_M" bash "$REPO_DIR/pipeline/bin/new-channel" Bad-Id --format problem-solution-reel --platform youtube-shorts > "$T/nc3.out" 2>&1; rc=$?
assert_rc 2 "$rc" "a malformed id exits 2"
env REELS_ROOT="$SANDBOX_M" bash "$REPO_DIR/pipeline/bin/new-channel" other --format nosuchformat --platform youtube-shorts > "$T/nc4.out" 2>&1; rc=$?
assert_rc 2 "$rc" "an unknown format exits 2 (engine work)"
assert_no_file "$SANDBOX/channels/other" "and creates nothing"
env REELS_ROOT="$SANDBOX_M" bash "$REPO_DIR/pipeline/bin/new-channel" other --format problem-solution-reel --platform nosuchplatform > "$T/nc5.out" 2>&1; rc=$?
assert_rc 2 "$rc" "an unknown platform exits 2 (engine work)"
# preflight lists it as incomplete
env REELS_ROOT="$SANDBOX_M" bash "$REPO_DIR/pipeline/bin/preflight" --channel demo > "$T/pf-demo.out" 2>&1; rc=$?
assert_true "preflight --channel demo fails: the channel is incomplete (exit $rc)" test "$rc" -ne 0
assert_file "$SANDBOX/channels/demo/logs/STOPPED.md" "preflight wrote the channel's logs/STOPPED.md"
assert_grep 'still says \[FILL IN\]' "$SANDBOX/channels/demo/logs/STOPPED.md" "STOPPED.md lists the files that still say [FILL IN]"
assert_grep 'tokens.json|catalog.json|brand' "$SANDBOX/channels/demo/logs/STOPPED.md" "and the files that are missing"
assert_no_file "$SANDBOX/channels/flashfx/logs/STOPPED.md" "no other channel is stopped"
# fill it in: the fixture files (the sandbox's flashfx files stand in for the owner's own)
rm -f "$SANDBOX/channels/demo/logs/STOPPED.md"
D="$SANDBOX/channels/demo"; F="$SANDBOX/channels/flashfx"
cp "$F/library/hooks.txt" "$D/library/hooks.txt"
cp "$F"/library/profile/* "$D/library/profile/" 2>/dev/null
sed -i 's/\[FILL IN\]/filled in by the test/g' "$D"/library/profile/*.md "$D"/library/profile/*.txt 2>/dev/null
rm -rf "$D/library/brand"; cp -r "$F/library/brand" "$D/library/brand"
cp "$F"/styles/paper-cards/* "$D/styles/paper-cards/" 2>/dev/null; cp "$F/styles/sfx/sfx-map.json" "$D/styles/sfx/sfx-map.json" 2>/dev/null || { mkdir -p "$D/styles/sfx"; cp "$F/styles/sfx/sfx-map.json" "$D/styles/sfx/"; }
cp "$F/motion-lib/catalog.json" "$D/motion-lib/catalog.json"; mkdir -p "$D/motion-lib/candidates"; : > "$D/motion-lib/candidates/.gitkeep"
sed -i 's/\[FILL IN\]/filled in by the test/g' "$D"/library/voice/README.txt 2>/dev/null
env REELS_ROOT="$SANDBOX_M" bash "$REPO_DIR/pipeline/bin/preflight" --channel demo > "$T/pf-demo2.out" 2>&1; rc=$?
assert_rc 0 "$rc" "preflight --channel demo passes once the files are filled in ($(tail -n 1 "$T/pf-demo2.out" | cut -c1-110))"
set_channel_json demo 'd["platform"] = "instagram-reels"; d["enabled"] = True'
printf '{An idea for the new channel: it runs}\n' > "$D/ideas.txt"
run_ch demo "$T/nc-run.out" REELS_DUMMY=all REELS_DUMMY_SECONDS=0.2; rc=$?
assert_rc 0 "$rc" "the filled-in channel runs in dummy mode"
assert_grep "${ts_regex}DONE   exported demo-1 -> exports/demo-1/" "$T/nc-run.out" "and exports demo-1"
assert_file "$SANDBOX/exports/demo-1/demo-1.mp4" "exports/demo-1/demo-1.mp4"
fi

# ---------------------------------------------------------------------------------------------------------------------------------------
if want 8; then
section "8. test-isolation (both parts), the dummy fingerprint, runner-status and doctor, no em dash"
ISOLATION_PARTS="1 2" bash "$REPO_DIR/pipeline/tests/test-isolation.sh" > "$T/iso.out" 2>&1; rc=$?
assert_rc 0 "$rc" "test-isolation.sh, both parts, passes ($(tail -n 1 "$T/iso.out"))"
sandbox_init
fast_mode
printf '{Claude Code'"'"'s frontend-design skill: it makes websites built with AI stop looking AI-generated. Show what it does and how to install it.}\n' > "$SANDBOX/channels/flashfx/ideas.txt"
run_ch flashfx "$T/fp.out" REELS_DUMMY=all; rc=$?
assert_rc 0 "$rc" "REELS_DUMMY=all bash run.sh --channel flashfx --once exits 0"
tree "$SANDBOX/channels/flashfx/runs" > "$T/fp-run.txt"
tree "$SANDBOX/exports" > "$T/fp-exports.txt"
FP="$REPO_DIR/build/M19/fingerprint"
if [ -n "${M19_RECORD:-}" ]; then
  mkdir -p "$FP"; cp "$T/fp-run.txt" "$FP/fingerprint-run.txt"; cp "$T/fp-exports.txt" "$FP/fingerprint-exports.txt"; pass "the dummy fingerprint is recorded in build/M19/fingerprint/ (M19_RECORD)"
fi
if cmp -s "$T/fp-run.txt" "$FP/fingerprint-run.txt"; then pass "the run folder tree equals build/M19/fingerprint/ ($(grep -c . "$T/fp-run.txt") entries)"
else fail "the run folder tree differs from build/M19/fingerprint/: $(diff "$T/fp-run.txt" "$FP/fingerprint-run.txt" | head -n 6 | tr '\n' ' ')"; fi
if cmp -s "$T/fp-exports.txt" "$FP/fingerprint-exports.txt"; then pass "the exports tree equals build/M19/fingerprint/ (flashfx-1/ with flashfx-1.mp4, flashfx-1captions.txt, flashfx-1hook2.mp4)"
else fail "the exports tree differs from build/M19/fingerprint/: $(diff "$T/fp-exports.txt" "$FP/fingerprint-exports.txt" | head -n 6 | tr '\n' ' ')"; fi
sed -E 's/flashfx-([0-9]+)/\1/g' "$T/fp-exports.txt" > "$T/fp-exports-old.txt"
if cmp -s "$T/fp-exports-old.txt" "$REPO_DIR/build/M17/baseline/fingerprint-exports.txt"; then pass "with the names normalized the exports tree is M17's baseline"
else fail "normalized, the exports tree differs from M17's baseline"; fi
add_channel second
env -u REELS_CHANNEL bash "$REPO_DIR/pipeline/bin/runner-status" > "$T/rs.txt" 2>&1; rc=$?
assert_rc 0 "$rc" "runner-status without arguments exits 0"
assert_grep '^== channel second ==$' "$T/rs.txt" "runner-status: one block per channel"
assert_grep '^today: [0-9]+ ' "$T/rs.txt" "runner-status: today's exports (against the quota)"
env -u REELS_CHANNEL bash "$REPO_DIR/pipeline/bin/doctor" --quick > "$T/doc.txt" 2>&1; rc=$?
assert_grep '== shared locks and logs' "$T/doc.txt" "doctor: the shared locks and logs"
assert_grep 'heavy lock: free' "$T/doc.txt" "doctor: the heavy lock"
assert_grep 'platform youtube-shorts: valid' "$T/doc.txt" "doctor: the platforms"
assert_grep '== channel second: runner' "$T/doc.txt" "doctor: every channel"
python - "$REPO_DIR" > "$T/emdash.txt" <<'PYEOF'
import os, sys
root = sys.argv[1]
files = ["pipeline/lib/export.py", "pipeline/lib/export.sh", "pipeline/lib/heavy.sh", "pipeline/lib/limits.sh", "pipeline/lib/quota.py", "pipeline/lib/platform_lib.py",
         "pipeline/lib/newchannel.py", "pipeline/bin/new-channel", "pipeline/schemas/platform.schema.json", "pipeline/tests/test-m19.sh", "pipeline/tests/m19-ytshorts.py"]
for dp, dn, fn in os.walk(os.path.join(root, "pipeline", "platforms")):
    files += [os.path.relpath(os.path.join(dp, f), root).replace(chr(92), "/") for f in fn if f.endswith((".py", ".json", ".md", ".sh"))]
for dp, dn, fn in os.walk(os.path.join(root, "pipeline", "formats")):
    files += [os.path.relpath(os.path.join(dp, f), root).replace(chr(92), "/") for f in fn]
bad = [f for f in files if os.path.isfile(os.path.join(root, f)) and b"\xe2\x80\x94" in open(os.path.join(root, f), "rb").read()]
print("\n".join(bad))
PYEOF
assert_eq "$(grep -c . "$T/emdash.txt")" "0" "no em dash in the files M19 added"
fi

test_summary
