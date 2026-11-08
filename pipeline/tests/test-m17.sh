#!/usr/bin/env bash
# test-m17.sh: the acceptance test of M17 (Control check). No model call, no engine call, nothing written in the real folder but build/M17/
# when a section says so.
#   bash pipeline/tests/test-m17.sh                       all sections (about 5 minutes)
#   M17_SECTIONS="1 2" bash pipeline/tests/test-m17.sh    only those sections
#
#   1. the manifest rules on a fixture folder (m17-fixture.py): the lines, their methods and checks, the config keys
#   2. check-manifest.py: it passes on the fixture; each planted fault (a missing path, a collision, a new path outside channels/ and
#      exports/, a file nothing places, a file covered twice, an engine file covered, wrong numbers) fails; drift warns, --strict fails;
#      --after passes on a fixture that m17-simulate.py migrated and fails on planted faults
#   3. refindex.py on the fixture (kinds, rooted, certainty, the old paths in every form in the data) and determinism: make-manifest.py and
#      refindex.py each run twice on the fixture and on the real folder give identical files
#   4. the recorded artifacts of the real folder (inventory, manifest, refindex, risks, baseline), check-manifest.py on them, the baseline
#      machinery (fakeresults.py, run-fake.sh --list), the files M17 changed (git diff against MS_START_SHA), no em dash
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SECTIONS="${M17_SECTIONS:-1 2 3 4}"
want() { case " $SECTIONS " in *" $1 "*) return 0 ;; esac; return 1; }
T="$(mktemp -d)"
m17_cleanup() { rm -rf "$T" 2>/dev/null || { sleep 2; rm -rf "$T" 2>/dev/null; }; tests_cleanup; }
trap m17_cleanup EXIT
PT="$TESTS_DIR"
TM="$(mixed "$T")"

pycheck() {  # pycheck "name" args...: runs the python on stdin; passes when it prints a last line "ok"
  local name="$1"; shift
  local out; out="$(python - "$@" 2>&1)"
  if [ "$(printf '%s\n' "$out" | tail -n 1)" = "ok" ]; then pass "$name"; else fail "$name: $(printf '%s\n' "$out" | tail -n 4 | tr '\n' ' ')"; fi
}

new_fixture() {  # new_fixture <name>: a fresh fixture folder $T/<name>, with its inventory and manifest in $T/<name>-out
  local d="$T/$1"
  python "$PT/m17-fixture.py" "$(mixed "$d")" >/dev/null || return 1
  python "$PT/inventory.py" --root "$(mixed "$d")" --out "$TM/$1-out" >/dev/null || return 1
  python "$PT/make-manifest.py" --root "$(mixed "$d")" --out "$TM/$1-out/move-manifest.tsv" >/dev/null || return 1
}

if want 1; then
section "1. the manifest rules on a fixture folder"
assert_true "the fixture builds, with its inventory and manifest" new_fixture fx
FX="$TM/fx"; FO="$TM/fx-out"
cat > "$T/p1.py" <<'PY'
import sys, os
sys.path.insert(0, sys.argv[2])
import manifestlib as ml
rows = ml.read_tsv(sys.argv[1])[1]
by = {}
for r in rows:
    by.setdefault((r["old"], r["ms"], r["method"], r["scope"]), []).append(r)
def line(old, ms, method, scope="top"):
    got = by.get((old, ms, method, scope))
    assert got, "no %s line for %s (%s, %s)" % (method, old, ms, scope)
    return got[0]
assert line("ideas.txt", "M18", "git-mv")["new"] == "channels/flashfx/ideas.txt"
assert line("ideas.txt", "M18", "git-mv")["check"] == "sha256" and len(line("ideas.txt", "M18", "git-mv")["sha256"]) == 64
for d in ("library", "styles", "motion-lib", "golden"):
    r = line(d, "M18", "git-mv")
    assert r["new"] == "channels/flashfx/" + d and r["git"] == "mixed" and r["check"] == "count-and-bytes", d
r = line("runs", "M18", "fs-mv")
assert r["git"] == "ignored" and r["files"] == "8", r
for name in ("runner.log", "status.txt", "history.txt", ".activity", "build-sfx-map"):
    assert line("logs/" + name, "M18", "fs-mv")["new"] == "channels/flashfx/logs/" + name, name
line("logs/limits.log", "M18", "stays")
line("voicetests", "M18", "stays")
line("exports/notes.txt", "M19", "stays")
for n in ("1", "2"):
    assert line("exports/" + n, "M19", "rename-in-place")["new"] == "exports/flashfx-" + n
    for suf in (".mp4", "captions.txt", "hook2.mp4"):
        r = line("exports/%s/%s%s" % (n, n, suf), "M19", "rename-in-place", "inner")
        assert r["new"] == "exports/flashfx-%s/flashfx-%s%s" % (n, n, suf), r
    line("exports/%s/%scaptions.txt" % (n, n), "M18", "rewrite", "inner")
    line("exports/%s/%scaptions.txt" % (n, n), "M19", "rewrite", "inner")
assert line("runs/2026-11-01_1000_done-idea", "M18", "rewrite", "inner")["files"] == "1", "the raw model output calls/001.out.json must not count"
assert line("runs/2026-11-02_1100_open-idea", "M18", "rewrite", "inner")["files"] == "2"
assert line("logs/history.txt", "M19", "rewrite", "inner")["check"] == "export-names"
assert ("logs/history.txt", "M18", "rewrite", "inner") not in by, "the history has no old path: no M18 rewrite"
# nothing of the engine is listed
for r in rows:
    assert r["old"].split("/")[0] not in ("pipeline", "tools", "build", "node_modules", "config.json", "run.sh"), r
# order: every M18 line before every M19 line
ms = [r["ms"] for r in rows]
assert ms == sorted(ms), "M18 lines come first"
assert [int(r["seq"]) for r in rows] == list(range(1, len(rows) + 1))
print("ok")
PY
pycheck_file() { local name="$1" script="$2"; shift 2; local out; out="$(python "$script" "$@" 2>&1)"; if [ "$(printf '%s\n' "$out" | tail -n 1)" = "ok" ]; then pass "$name"; else fail "$name: $(printf '%s\n' "$out" | tail -n 4 | tr '\n' ' ')"; fi; }
pycheck_file "the fixture's lines: moves, stays, rewrites, renames, checksums, order" "$TM/p1.py" "$FO/move-manifest.tsv" "$(mixed "$PT")"
cat > "$T/p1b.py" <<'PY'
import sys
sys.path.insert(0, sys.argv[2])
import manifestlib as ml
rows = ml.read_tsv(sys.argv[1])[1]
d = {r["key"]: r for r in rows}
want = {"voice.wpm": ("channel", "M18"), "lengths.default_s": ("channel", "M18"), "style": ("channel", "M18"), "sfx.max_per_10s": ("channel", "M18"),
        "paths.logs": ("channel", "M18"), "paths.ideas": ("channel", "M18"), "paths.exports": ("engine", "-"), "paths.vendor": ("engine", "-"),
        "review.fixer_paths": ("engine", "-"), "review.protected_paths": ("engine", "-"), "review.reviewer_tools": ("engine", "-"),
        "review.energy_check": ("format", "M20"), "script.hook_max_s": ("format", "M20"), "visual.energy_rules": ("format", "M20"),
        "research.max_assets": ("format", "M20"), "hooks.shortlist": ("format", "M20"), "tts.device": ("engine", "-"),
        "models.research": ("engine", "-"), "caps.angle_rounds": ("engine", "-"), "runner.timezone": ("engine", "-"), "render.fps": ("engine", "-")}
for k, (dest, ms) in want.items():
    assert k in d, "missing key " + k
    assert (d[k]["destination"], d[k]["moves_in"]) == (dest, ms), (k, d[k]["destination"], d[k]["moves_in"])
import json
cfg = json.load(open(sys.argv[3], encoding="utf-8-sig"))
assert set(r["key"].split(".")[0] for r in rows) == set(cfg), "every top-level key of config.json has a row"
assert all(r["destination"] in ("engine", "format", "channel") for r in rows)
print("ok")
PY
pycheck_file "config-keys.tsv: every key has a destination (channel, format, engine), the four review safety keys are engine" "$TM/p1b.py" "$FO/config-keys.tsv" "$(mixed "$PT")" "$FX/config.json"
assert_true "the fixture manifest passes check-manifest" python "$PT/check-manifest.py" --root "$FX" --manifest "$FO/move-manifest.tsv"
fi

if want 2; then
section "2. check-manifest.py: the checks and planted faults"
new_fixture fb >/dev/null; FB="$TM/fb"; BO="$TM/fb-out"
cat > "$T/mut.py" <<'PY'
# mut.py <in.tsv> <out.tsv> <mutation> : plants one fault in a copy of the manifest
import sys
sys.path.insert(0, sys.argv[4])
import manifestlib as ml
header, rows = ml.read_tsv(sys.argv[1])
mut = sys.argv[3]
def renum(rs):
    for i, r in enumerate(rs, 1):
        r["seq"] = str(i)
    return rs
if mut == "missing-old":
    rows.append(dict(rows[0], seq="0", old="library/does-not-exist.txt", new="channels/flashfx/library/does-not-exist.txt", scope="inner", method="fs-mv"))
elif mut == "collision":
    r = [x for x in rows if x["old"] == "library"][0]
    rows.append(dict(r, old="golden/test-idea/plan.json", new=r["new"], scope="top", method="fs-mv", files="1", bytes="3"))
elif mut == "outside":
    for r in rows:
        if r["old"] == "ideas.txt":
            r["new"] = "elsewhere/ideas.txt"
elif mut == "double":
    rows.append(dict([x for x in rows if x["old"] == "library"][0], old="library/hooks.txt", new="channels/flashfx/other/hooks.txt", files="1", bytes="14", method="fs-mv", check="sha256"))
elif mut == "engine":
    rows.append(dict(rows[0], old="tools", new="channels/flashfx/tools", scope="top", method="git-mv", files="1", bytes="1"))
elif mut == "bytes":
    for r in rows:
        if r["old"] == "styles":
            r["bytes"] = str(int(r["bytes"]) + 1)
elif mut == "dropped":
    rows = [r for r in rows if r["old"] != "golden"]
elif mut == "stay-moves":
    for r in rows:
        if r["old"] == "voicetests":
            r["new"] = "channels/flashfx/voicetests"
elif mut == "bad-method":
    rows[0]["method"] = "copy"
elif mut == "inner-orphan":
    rows.append(dict(rows[0], old="stray-dir/x", new="channels/flashfx/stray-dir/x", scope="inner", method="fs-mv"))
else:
    raise SystemExit("unknown mutation " + mut)
ml.write_tsv(sys.argv[2], ml.MANIFEST_COLUMNS, renum(rows) if mut != "missing-old" else renum(rows))
PY
for m in missing-old collision outside double engine bytes dropped stay-moves bad-method; do
  python "$T/mut.py" "$BO/move-manifest.tsv" "$TM/mut-$m.tsv" "$m" "$(mixed "$PT")" 2>"$T/mut.err" || { fail "planting $m: $(cat "$T/mut.err")"; continue; }
  out="$(python "$PT/check-manifest.py" --root "$FB" --manifest "$TM/mut-$m.tsv" --inventory "$BO/inventory.tsv" 2>&1)"; rc=$?
  assert_rc 1 $rc "planted fault '$m' fails check-manifest"
  case "$m" in
    missing-old) assert_grep "does not exist" <(printf '%s\n' "$out") "  ... it names the missing path" ;;
    collision) assert_grep "also the new path|new path .* is inside new path|moved twice" <(printf '%s\n' "$out") "  ... it names the collision" ;;
    outside) assert_grep "not inside channels/<id>/ or exports/" <(printf '%s\n' "$out") "  ... it says the new path is outside" ;;
    double) assert_grep "covered by 2 lines|is inside library" <(printf '%s\n' "$out") "  ... it says the file is covered twice" ;;
    engine) assert_grep "engine file .* is covered" <(printf '%s\n' "$out") "  ... it says an engine file is covered" ;;
    bytes) assert_grep "the manifest says .* bytes" <(printf '%s\n' "$out") "  ... it names the numbers that differ" ;;
    dropped) assert_grep "nothing places golden/" <(printf '%s\n' "$out") "  ... it says nothing places the golden files" ;;
    stay-moves) assert_grep "a stay must keep its path" <(printf '%s\n' "$out") "  ... a stay that moves is refused" ;;
    bad-method) assert_grep "method 'copy' is unknown" <(printf '%s\n' "$out") "  ... an unknown method is refused" ;;
  esac
done
# a file nothing places: a new top-level folder after the inventory
mkdir -p "$FB/stray" && echo x > "$FB/stray/x.txt"
python "$PT/check-manifest.py" --root "$FB" --manifest "$BO/move-manifest.tsv" --inventory "$BO/inventory.tsv" > "$T/c1.out" 2>&1; rc=$?
assert_rc 0 $rc "a file that appeared after the inventory is a drift warning, not an error"
assert_grep "WARN DRIFT stray/x.txt is new since the inventory" "$T/c1.out" "  ... the warning names it"
python "$PT/check-manifest.py" --strict --root "$FB" --manifest "$BO/move-manifest.tsv" --inventory "$BO/inventory.tsv" > "$T/c2.out" 2>&1; rc=$?
assert_rc 1 $rc "--strict makes the drift an error"
python "$PT/check-manifest.py" --live --root "$FB" --manifest "$BO/move-manifest.tsv" > "$T/c3.out" 2>&1; rc=$?
assert_rc 1 $rc "--live: a file that no line places and that is not engine fails the coverage check"
assert_grep "nothing places stray/x.txt" "$T/c3.out" "  ... it names the file nothing places"
rm -rf "$FB/stray"
echo "more" >> "$FB/library/hooks.txt"
python "$PT/check-manifest.py" --root "$FB" --manifest "$BO/move-manifest.tsv" --inventory "$BO/inventory.tsv" > "$T/c4.out" 2>&1; rc=$?
assert_rc 0 $rc "a changed file is a drift warning"
assert_grep "WARN DRIFT line [0-9]+ \(library\)" "$T/c4.out" "  ... the warning names the folder and its numbers"

# --after on a fixture the simulator migrated
new_fixture fc >/dev/null; FC="$TM/fc"; CO="$TM/fc-out"
# M18 commits the new .gitignore (14.3: the rules of the moved folders, written for channels/*/) before the first move: the same here
cat > "$FC/.gitignore" <<'GI'
node_modules/
__pycache__/
*.pyc
/exports/
/logs/
/.locks/
voicetests/
channels/*/runs/
channels/*/logs/
channels/*/.locks/
channels/*/library/voice/*
!channels/*/library/voice/README.txt
channels/*/library/.hooks.index.json
channels/*/styles/*/refs/
channels/*/styles/*/analysis/
channels/*/styles/sfx/**/*.wav
channels/*/styles/sfx/**/*.mp3
channels/*/motion-lib/.harness/
channels/*/golden/*/golden.mp4
*.mp4
*.wav
GI
git -C "$FC" add .gitignore && git -C "$FC" commit -q -m "new gitignore"
python "$PT/m17-simulate.py" "$FC" "$CO/move-manifest.tsv" --only M18 > /dev/null 2>&1
python "$PT/check-manifest.py" --after --root "$FC" --manifest "$CO/move-manifest.tsv" > "$T/a0.out" 2>&1; rc=$?
assert_rc 1 $rc "--after after M18 only fails: the M19 lines are not done"
assert_grep "line [0-9]+: new path exports/flashfx-1 is missing" "$T/a0.out" "  ... it names the export folder"
python "$PT/m17-simulate.py" "$FC" "$CO/move-manifest.tsv" --only M19 > /dev/null 2>&1
python "$PT/check-manifest.py" --after --root "$FC" --manifest "$CO/move-manifest.tsv" > "$T/a1.out" 2>&1; rc=$?
assert_rc 0 $rc "--after passes after M18 and M19"
assert_eq "$(git -C "$FC" status --porcelain | grep -v '^R ' | wc -l | tr -d ' ')" "0" "the simulated migration shows only renames in git status"
assert_true "channels/flashfx/library/voice/reference.wav (ignored) is still ignored after the move" bash -c "git -C '$FC' check-ignore -q channels/flashfx/library/voice/reference.wav"
assert_true "the captions file names the new export and the new run path" bash -c "grep -q 'flashfx-1.mp4 uses' '$FC/exports/flashfx-1/flashfx-1captions.txt' && grep -q '^channels/flashfx/runs/' '$FC/exports/flashfx-1/flashfx-1captions.txt'"
assert_true "the history says exported flashfx-2" grep -q "| exported flashfx-2" "$FC/channels/flashfx/logs/history.txt"
assert_true "the raw model output keeps its old path" grep -q '"runs/2026-11-01_1000_done-idea"' "$FC/channels/flashfx/runs/2026-11-01_1000_done-idea/01-research/calls/001.out.json"
# planted faults after the migration
mkdir "$FC/library"
python "$PT/check-manifest.py" --after --root "$FC" --manifest "$CO/move-manifest.tsv" > "$T/a2.out" 2>&1; rc=$?
assert_rc 1 $rc "--after fails when a moved folder exists again at its old path"
assert_grep "old top-level folder library still exists|still at its old path" "$T/a2.out" "  ... it names the folder"
rmdir "$FC/library"
rm "$FC/channels/flashfx/styles/paper-cards/refs/a.mp4"
python "$PT/check-manifest.py" --after --root "$FC" --manifest "$CO/move-manifest.tsv" > "$T/a3.out" 2>&1; rc=$?
assert_rc 1 $rc "--after fails when a file went missing in a moved folder (the count differs)"
echo "x" > "$FC/channels/flashfx/styles/paper-cards/refs/a.mp4"
printf 'see runs/2026-11-02_1100_open-idea\n' >> "$FC/channels/flashfx/runs/2026-11-02_1100_open-idea/01-research/research.json"
python "$PT/check-manifest.py" --after --root "$FC" --manifest "$CO/move-manifest.tsv" > "$T/a4.out" 2>&1; rc=$?
assert_rc 1 $rc "--after fails when a rewritten file keeps an old path"
assert_grep "still names an old path" "$T/a4.out" "  ... it names the file"
fi

if want 3; then
section "3. refindex.py on the fixture, and determinism"
new_fixture fd >/dev/null; FD="$TM/fd"
python "$PT/refindex.py" --root "$FD" --out "$TM/fd-ref1" > "$T/r1.out" 2>&1; rc=$?
assert_rc 0 $rc "refindex.py runs on the fixture"
cat > "$T/p3.py" <<'PY'
import sys
sys.path.insert(0, sys.argv[3])
import manifestlib as ml
rows = ml.read_tsv(sys.argv[1])[1]
def find(file, subject, match_part, line=None):
    got = [r for r in rows if r["file"] == file and r["subject"] == subject and match_part in r["match"] and (line is None or r["line"] == str(line))]
    assert got, "no %s row for %s in %s" % (subject, match_part, file)
    return got[0]
r = find("pipeline/lib/x.sh", "path", "library/hooks.txt", 3)
assert (r["kind"], r["rooted"], r["change"]) == ("code", "yes", "paths module call (chpath, paths.ch)"), r
r = find("pipeline/lib/x.sh", "path", "library/hooks.txt", 2)
assert r["kind"] == "comment", r
r = find("pipeline/lib/x.sh", "config-key", "voice.wpm")
assert (r["certainty"], r["kind"]) == ("exact", "code")
r = find("pipeline/lib/x.sh", "export-name", "captions.txt")
assert r["kind"] == "code" and r["change"] == "export name (M19)", r
r = find("pipeline/lib/x.sh", "export-name", "exports/$n")
r = find("pipeline/lib/x.sh", "config-read", "REELS_CONFIG")
r = find("pipeline/lib/x.sh", "path", "logs/history.txt", 7)
assert r["rooted"] == "yes"
r = find("pipeline/lib/x.sh", "path", "runs/a", 8)
assert r["rooted"] == "no" and r["change"].startswith("none"), r
r = find("pipeline/lib/y.py", "path", "styles/paper-cards/tokens.json", 1)
assert r["kind"] == "comment", "a docstring line is a comment"
r = find("pipeline/lib/y.py", "config-key", "cfg[", 4) if False else [x for x in rows if x["file"] == "pipeline/lib/y.py" and x["subject"] == "config-key" and x["line"] == "4"][0]
assert r["certainty"] == "candidate" and r["match"].startswith("["), r
assert [x for x in rows if x["file"] == "pipeline/lib/y.py" and x["subject"] == "config-key" and x["line"] == "5"], "cfg.get(\"voice\") is a candidate"
r = find("pipeline/lib/y.py", "path", "library/profile/voice.md", 6)
assert r["kind"] == "code"
find("pipeline/lib/y.py", "export-name", "hook2.mp4")
find("pipeline/lib/y.py", "config-read", "config.json")
r = find("pipeline/stages/01-x/prompt.md", "path", "library/profile/voice.md")
assert (r["kind"], r["change"]) == ("prompt", "channel path in docs"), r
r = find("pipeline/tests/t.sh", "path", "logs/history.txt")
assert (r["kind"], r["change"]) == ("test", "channel path in a test (test edit)"), r
r = find("pipeline/tests/fixtures/f.json", "path", "runs/test/state.json")
assert r["kind"] == "fixture", r
r = find("CLAUDE.md", "path", "library/hooks.txt")
assert r["kind"] == "doc"
find("CLAUDE.md", "export-name", "exports/N")
find("CLAUDE.md", "export-name", "Ncaptions.txt")
find("CLAUDE.md", "export-name", "Nhook2.mp4")
r = find("styles/sfx/sfx-map.json", "path", "styles/sfx/pop.wav")
assert r["certainty"] == "absolute" and r["kind"] == "data", r
r = find(".gitignore", "path", "runs/")
assert r["kind"] == "config" and r["change"] == "new .gitignore (14.3)"
assert not [x for x in rows if x["file"].startswith("build/") or x["file"] == "BUILD_SPEC.md"], "build/ is left out"
assert all(len(x["context"]) <= 110 for x in rows)
# sorted
keys = [(r["file"], int(r["line"]), int(r["col"])) for r in rows]
assert keys == sorted(keys), "sorted by file, line, column"
# the data counts
drows = ml.read_tsv(sys.argv[2])[1]
forms = set((r["bucket"], r["form"]) for r in drows if r["bucket"] == "runs")
for form in ("relative", "mixed", "posix-drive", "backslash", "json-backslash"):
    assert ("runs", form) in forms, "the runs data has an old path in the form " + form
raw = [r for r in drows if "raw model output" in r["bucket"]]
assert raw and raw[0]["git"] == "ignored", "the raw model output is counted apart"
assert any(r["bucket"] == "styles" and r["git"] == "tracked" and r["form"] == "mixed" for r in drows), "the tracked sound map holds the absolute path"
assert any(r["bucket"] == "motion-lib" and r["git"] == "ignored" and r["form"] == "mixed" for r in drows), "the ignored harness page holds it too"
assert any(r["bucket"] == "exports" for r in drows), "the captions files hold the RUN path"
assert all(r["example"] for r in drows)
print("ok")
PY
pycheck_file "refindex rows: kinds, rooted, certainty, changes, exclusions, the old paths in every form" "$T/p3.py" "$TM/fd-ref1/refindex.tsv" "$TM/fd-ref1/refindex-data.tsv" "$(mixed "$PT")"
python "$PT/refindex.py" --root "$FD" --out "$TM/fd-ref2" > /dev/null 2>&1
assert_true "refindex.tsv is identical on a second run (fixture)" cmp -s "$T/fd-ref1/refindex.tsv" "$T/fd-ref2/refindex.tsv"
assert_true "refindex-data.tsv is identical on a second run (fixture)" cmp -s "$T/fd-ref1/refindex-data.tsv" "$T/fd-ref2/refindex-data.tsv"
python "$PT/make-manifest.py" --root "$FD" --out "$TM/fd-m1.tsv" --keys-out "$TM/fd-k1.tsv" > /dev/null 2>&1
python "$PT/make-manifest.py" --root "$FD" --out "$TM/fd-m2.tsv" --keys-out "$TM/fd-k2.tsv" > /dev/null 2>&1
assert_true "make-manifest.py gives an identical manifest on a second run (fixture)" cmp -s "$T/fd-m1.tsv" "$T/fd-m2.tsv"
assert_true "...and an identical config-keys.tsv" cmp -s "$T/fd-k1.tsv" "$T/fd-k2.tsv"
assert_true "no em dash in refindex output (a source line with one is cleaned)" python -c "
import sys
d = open(sys.argv[1], 'rb').read()
sys.exit(1 if bytes([0xE2, 0x80, 0x94]) in d else 0)" "$TM/fd-ref1/refindex.tsv"

# the real folder, twice
python "$PT/make-manifest.py" --out "$TM/real-m1.tsv" --keys-out "$TM/real-k1.tsv" > /dev/null 2>&1
python "$PT/make-manifest.py" --out "$TM/real-m2.tsv" --keys-out "$TM/real-k2.tsv" > /dev/null 2>&1
assert_true "make-manifest.py: identical files on two runs (real folder)" cmp -s "$T/real-m1.tsv" "$T/real-m2.tsv"
assert_true "make-manifest.py: identical config-keys.tsv on two runs (real folder)" cmp -s "$T/real-k1.tsv" "$T/real-k2.tsv"
python "$PT/refindex.py" --out "$TM/real-r1" > /dev/null 2>&1
python "$PT/refindex.py" --out "$TM/real-r2" > /dev/null 2>&1
assert_true "refindex.py: identical refindex.tsv on two runs (real folder)" cmp -s "$T/real-r1/refindex.tsv" "$T/real-r2/refindex.tsv"
assert_true "refindex.py: identical refindex-data.tsv on two runs (real folder)" cmp -s "$T/real-r1/refindex-data.tsv" "$T/real-r2/refindex-data.tsv"
assert_true "the fresh manifest of the real folder passes check-manifest (against a fresh inventory)" bash -c "python '$PT/inventory.py' --out '$TM/real-inv' >/dev/null && python '$PT/check-manifest.py' --manifest '$TM/real-m1.tsv' --inventory '$TM/real-inv/inventory.tsv'"
fi

if want 4; then
section "4. the recorded artifacts, the baseline machinery, the files M17 changed"
B="$REPO_DIR/build/M17"
for f in inventory.md inventory.tsv refindex.tsv refindex-data.tsv move-manifest.tsv config-keys.tsv risks.md riskiest-moves.md report.md; do
  assert_file "$B/$f" "build/M17/$f exists"
done
if [ -f "$B/move-manifest.tsv" ]; then
  assert_true "check-manifest.py passes on the recorded manifest and inventory" python "$PT/check-manifest.py" --manifest "$B/move-manifest.tsv" --inventory "$B/inventory.tsv"
fi
assert_true "inventory.tsv has the columns of the spec" bash -c "head -n 1 '$B/inventory.tsv' | grep -q -P '^path\tkind\tsize\tfiles\tgit\ttop\$'"
assert_true "risks.md marks every item BLOCKER or NOTE" bash -c "! grep -v -E '^(- \*\*(BLOCKER|NOTE) |#|\$|Written by|None)' '$B/risks.md' | grep -q ."
# the baseline
cat > "$T/p4.py" <<'PY'
import sys, subprocess, os
sys.path.insert(0, sys.argv[2])
import manifestlib as ml
base = sys.argv[1]
listed = [l.split("\t")[0] for l in subprocess.run(["bash", sys.argv[3], "--list"], capture_output=True, text=True).stdout.splitlines() if l.strip()]
rows = ml.read_tsv(os.path.join(base, "results.tsv"))[1]
got = {r["test"]: r for r in rows}
missing = [t for t in listed if t not in got and t not in ("test-m17", "test-models")]
assert not missing, "no recorded result for " + ", ".join(missing)
for r in rows:
    assert r["status"] in ("pass", "fail", "error", "timeout"), r
    assert os.path.exists(os.path.join(sys.argv[4], r["log"])) or r["test"] == "test-m17", "no log for " + r["test"]
for f in ("preflight.txt", "doctor-quick.txt", "fingerprint-run.txt", "fingerprint-exports.txt", "fingerprint-state.txt", "dummy-run.txt", "summary.txt", "failures.tsv"):
    assert os.path.exists(os.path.join(base, f)), "baseline/" + f + " is missing"
assert "exit code 0" in open(os.path.join(base, "dummy-run.txt"), encoding="utf-8").read(), "the baseline's dummy run did not end with exit code 0"
assert len([l for l in open(os.path.join(base, "fingerprint-run.txt"), encoding="utf-8") if l.strip()]) > 20
print("ok")
PY
if [ -f "$B/baseline/results.tsv" ]; then
  pycheck_file "build/M17/baseline records every fake-only test, preflight, doctor --quick and the dummy fingerprint" "$TM/p4.py" "$(mixed "$B/baseline")" "$(mixed "$PT")" "$(mixed "$PT/run-fake.sh")" "$(mixed "$REPO_DIR")"
else
  fail "build/M17/baseline/results.tsv is missing: run bash pipeline/tests/run-fake.sh"
fi
# fakeresults: parse and compare
mkdir -p "$T/fr/a" "$T/fr/b"
printf 'PASS  one\nFAIL  two broke\n\ntest-x.sh: 5 passed, 1 failed\n' > "$T/fr/log1.txt"
python "$PT/fakeresults.py" parse "$TM/fr/log1.txt" test-x "1 2" 1 12 > "$T/fr/row.txt"
assert_eq "$(head -n 1 "$T/fr/row.txt" | cut -f1-7)" "$(printf 'test-x\t1 2\tfail\t5\t1\t1\t12')" "fakeresults parse: a failing test is recorded with its numbers"
assert_eq "$(tail -n 1 "$T/fr/row.txt")" "$(printf 'FAILLINE\ttwo broke')" "fakeresults parse: the failing check is recorded"
printf 'test-x.sh: 9 passed, 0 failed\n' > "$T/fr/log2.txt"
python "$PT/fakeresults.py" parse "$TM/fr/log2.txt" test-y all 0 3 > "$T/fr/row2.txt"
assert_eq "$(head -n 1 "$T/fr/row2.txt" | cut -f3)" "pass" "fakeresults parse: a passing test"
python "$PT/fakeresults.py" parse "$TM/fr/log2.txt" test-y all 124 3 > "$T/fr/row3.txt"
assert_eq "$(head -n 1 "$T/fr/row3.txt" | cut -f3)" "timeout" "fakeresults parse: exit 124 is a timeout"
hdr="$(printf 'test\tsections\tstatus\tpassed\tfailed\texit\tseconds\tlog')"
printf '%s\ntest-a\tall\tpass\t3\t0\t0\t1\tl\ntest-b\tall\tfail\t3\t1\t1\t1\tl\n' "$hdr" > "$T/fr/a/results.tsv"; printf 'test-b\told failure\n' > "$T/fr/a/failures.tsv"
printf '%s\ntest-a\tall\tpass\t3\t0\t0\t9\tl\ntest-b\tall\tpass\t4\t0\t0\t9\tl\n' "$hdr" > "$T/fr/b/results.tsv"; : > "$T/fr/b/failures.tsv"
python "$PT/fakeresults.py" compare "$TM/fr/a" "$TM/fr/b" > "$T/fr/cmp1.txt" 2>&1; rc=$?
assert_rc 0 $rc "compare: a known failure that now passes is fine (and a longer duration is not compared)"
assert_grep "FIXED   test-b" "$T/fr/cmp1.txt" "  ... it says test-b is fixed"
printf '%s\ntest-a\tall\tfail\t2\t1\t1\t1\tl\ntest-b\tall\tfail\t3\t1\t1\t1\tl\n' "$hdr" > "$T/fr/b/results.tsv"; printf 'test-a\tnew breakage\ntest-b\told failure\n' > "$T/fr/b/failures.tsv"
python "$PT/fakeresults.py" compare "$TM/fr/a" "$TM/fr/b" > "$T/fr/cmp2.txt" 2>&1; rc=$?
assert_rc 1 $rc "compare: a test that passed in the baseline and fails now is a problem"
assert_grep "PROBLEM test-a: passed in the baseline, now fail" "$T/fr/cmp2.txt" "  ... it names the test"
assert_grep "PROBLEM test-a: new failing check: new breakage" "$T/fr/cmp2.txt" "  ... and the new failing check"
assert_not_grep "PROBLEM test-b" "$T/fr/cmp2.txt" "  ... the known failure of test-b is not a problem"
assert_true "run-fake.sh --list names every fake-only test file" bash -c "bash '$PT/run-fake.sh' --list | cut -f1 | tr '\n' ' ' | grep -q 'test-no-emdash test-limits test-m1 test-m2 test-m3 test-m4 test-m5 test-m6 test-m7 test-m8 test-m9 test-m10 test-m11 test-m12 test-m13 test-m14 test-m15 test-m16'"

# the files M17 changed: only build/, pipeline/tests/ and the build's memory files
START="$(grep '^MS_START_SHA=' "$REPO_DIR/build/state.env" 2>/dev/null | cut -d= -f2)"
if [ -n "$START" ] && git -C "$REPO_DIR" cat-file -e "$START^{commit}" 2>/dev/null; then
  bad="$({ git -C "$REPO_DIR" log --format='%H %s' "$START..HEAD" | grep -v -E ' (autofix\(|chore: snapshot runner-written)' | cut -d' ' -f1 | while read -r c; do git -C "$REPO_DIR" diff-tree --no-commit-id --name-only -r "$c"; done
           git -C "$REPO_DIR" diff --name-only HEAD; git -C "$REPO_DIR" ls-files --others --exclude-standard; } | sort -u \
          | grep -v -E '^(build/|pipeline/tests/|CLAUDE\.md$|PLAN\.md$|DECISIONS\.md$|library/\.hooks\.stats\.json$|library/hooks\.suggested\.txt$|motion-lib/gallery/frame-match\.(json|md)$)' || true)"
  assert_eq "$bad" "" "git diff START..HEAD (and the working tree) lists only build/, pipeline/tests/, CLAUDE.md, PLAN.md, DECISIONS.md and the two runner-written files"
else
  pass "no MS_START_SHA in build/state.env (not a build run): the file list is not checked"
fi
assert_true "no em dash in any file" python "$PT/no_emdash.py"
fi
test_summary
