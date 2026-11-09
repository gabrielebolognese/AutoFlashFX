#!/usr/bin/env bash
# test-isolation.sh: channels never touch each other (BUILD_SPEC.md 14.5). No model call, no engine call.
#   bash pipeline/tests/test-isolation.sh                    part 1 (the only part that exists in M18)
#   ISOLATION_PARTS="1" bash pipeline/tests/test-isolation.sh
#
#   part 1 (static, M18): no literal path to library/, styles/, motion-lib/, golden/, ideas.txt, runs/, logs/ or exports/ in pipeline/, run.sh
#          or tools/ outside paths.sh and paths.py (pipeline/tests/isolation_scan.py; the exceptions are one by one in
#          pipeline/tests/isolation-allowlist.txt, each with its reason); paths.sh and paths.py give the same answers for every variable; the
#          path module refuses (exit 3 and an ERROR line) a path inside another channel's folder and another channel's export folder, in
#          bash and in Python; REELS_PATH_TRACE logs every path chpath resolves
#   part 2 (the canary test: two fixture channels, every prompt recorded) arrives with M19.
set -u
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
PARTS="${ISOLATION_PARTS:-1}"
want() { case " $PARTS " in *" $1 "*) return 0 ;; esac; return 1; }
T="$(mktemp -d)"
iso_cleanup() { rm -rf "$T" 2>/dev/null || { sleep 2; rm -rf "$T" 2>/dev/null; }; tests_cleanup; }
trap iso_cleanup EXIT
TM="$(mixed "$T")"

if want 1; then
section "part 1. the static check and the path module"
out="$(python "$REPO_DIR/pipeline/tests/isolation_scan.py" 2>&1)"; rc=$?
assert_rc 0 "$rc" "isolation_scan.py: no literal path to channel data outside the paths module ($(printf '%s' "$out" | tail -n 1))"
assert_true "every allowlist entry has a reason and is used" bash -c "python '$REPO_DIR/pipeline/tests/isolation_scan.py' --list | grep -q -v 'unused entry'"

# a planted violation is found
mkdir -p "$T/plant/pipeline/lib" "$T/plant/pipeline/tests"
printf '#!/usr/bin/env bash\nHOOKS="$REELS_ROOT/library/hooks.txt"\n' > "$T/plant/pipeline/lib/x.sh"
printf 'import os\np = os.path.join(root, "styles")\nq = "runs/" + rid\n' > "$T/plant/pipeline/lib/y.py"
printf '' > "$T/plant/pipeline/tests/isolation-allowlist.txt"
out="$(python "$REPO_DIR/pipeline/tests/isolation_scan.py" --root "$TM/plant" 2>&1)"; rc=$?
assert_rc 1 "$rc" "a planted literal path fails the scan"
assert_true "the scan names the shell file and the Python file" bash -c "printf '%s' '$out' | grep -q 'x.sh:2' && printf '%s' '$out' | grep -q 'y.py:2' && printf '%s' '$out' | grep -q 'y.py:3'"
printf 'pipeline/lib/x.sh | REELS_ROOT/library | a planted exception with a reason\n' > "$T/plant/pipeline/tests/isolation-allowlist.txt"
out="$(python "$REPO_DIR/pipeline/tests/isolation_scan.py" --root "$TM/plant" 2>&1)"
assert_true "an allowlist entry lets exactly its line through" bash -c "! printf '%s' '$out' | grep -q 'x.sh' && printf '%s' '$out' | grep -q 'y.py:2'"
printf 'pipeline/lib/x.sh | REELS_ROOT/library |\n' > "$T/plant/pipeline/tests/isolation-allowlist.txt"
assert_false "an allowlist entry without a reason is refused" python "$REPO_DIR/pipeline/tests/isolation_scan.py" --root "$TM/plant"

# paths.sh and paths.py agree
mkdir -p "$T/root/channels/alpha" "$T/root/channels/beta"
for id in alpha beta; do printf '{"id": "%s", "name": "%s", "platform": "instagram-reels", "format": "problem-solution-reel"}\n' "$id" "$id" > "$T/root/channels/$id/channel.json"; done
cmp_paths() {  # cmp_paths <channel or empty>
  local sh py
  sh="$(env -u REELS_CHANNEL ${1:+REELS_CHANNEL="$1"} REELS_ROOT="$TM/root" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; reels_paths_dump')"
  py="$(env -u REELS_CHANNEL ${1:+REELS_CHANNEL="$1"} REELS_ROOT="$TM/root" python "$REPO_DIR/pipeline/lib/paths.py" dump)"
  [ "$sh" = "$py" ] && [ -n "$sh" ]
}
assert_true "paths.sh and paths.py give the same answers with a channel" cmp_paths alpha
assert_true "paths.sh and paths.py give the same answers without a channel" cmp_paths ""
assert_true "paths.sh puts the channel's files inside channels/alpha" bash -c "env REELS_CHANNEL=alpha REELS_ROOT='$TM/root' bash -c 'source \"$REPO_DIR/pipeline/lib/common.sh\"; [ \"\$REELS_IDEAS\" = \"$TM/root/channels/alpha/ideas.txt\" ] && [ \"\$REELS_LOGS\" = \"$TM/root/channels/alpha/logs\" ] && [ \"\$REELS_LOCKS\" = \"$TM/root/channels/alpha/.locks\" ]'"

# the refusals, in bash and in Python
RM="$(mixed "$REPO_DIR")"
shrun() { env REELS_CHANNEL=alpha REELS_ROOT="$TM/root" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; '"$1" 2>&1; }
pyrun() { env REELS_CHANNEL=alpha REELS_ROOT="$TM/root" python -c "import sys; sys.path.insert(0, '$RM/pipeline/lib'); import paths; $1" 2>&1; echo "rc=$?"; }
grep2() {  # grep2 "pattern" "pattern2" name: both patterns in $T/o.txt
  if grep -q -E -- "$1" "$T/o.txt" && grep -q -E -- "$2" "$T/o.txt"; then pass "$3"; else fail "$3 ($(tr '\n' ' ' < "$T/o.txt" | cut -c1-200))"; fi
}
shrun 'chpath library/hooks.txt' > "$T/o.txt"
assert_eq "$(cat "$T/o.txt")" "$TM/root/channels/alpha/library/hooks.txt" "chpath: a path of the channel's own folder resolves"
shrun 'reels_path_refuse "$REELS_CHANNELS_DIR/beta/library/hooks.txt"; echo "rc=$?"' > "$T/o.txt"
grep2 'ERROR paths' 'rc=3' "bash: a path inside channels/beta is refused for channel alpha (exit 3, an ERROR line)"
shrun 'chpath ../beta/library; echo "rc=$?"' > "$T/o.txt"
grep2 'leaves the channel folder' 'rc=3' "bash: chpath refuses a relative path that leaves the channel folder"
shrun 'reels_path_refuse "$REELS_EXPORTS/beta-3/beta-3.mp4"; echo "rc=$?"' > "$T/o.txt"
grep2 'export folder' 'rc=3' "bash: another channel's export folder is refused"
shrun 'reels_path_refuse "$REELS_EXPORTS/alpha-3/alpha-3.mp4"; echo "rc=$?"' > "$T/o.txt"
grep2 'rc=0' 'rc=0' "bash: the channel's own export folder is allowed"
pyrun 'print(paths.ch("library/hooks.txt"))' > "$T/o.txt"
grep2 'channels/alpha/library/hooks.txt' 'rc=0' "python: paths.ch resolves inside the channel"
pyrun 'paths.check(paths.channels_dir() + "/beta/styles/x")' > "$T/o.txt"
grep2 'ERROR paths' 'rc=3' "python: a path inside channels/beta is refused for alpha (exit 3, an ERROR line)"
pyrun 'paths.ch("../beta/library")' > "$T/o.txt"
grep2 'leaves the channel folder' 'rc=3' "python: a relative path that leaves the channel folder is refused"
pyrun 'paths.check(paths.exports() + "/beta-1/beta-1.mp4")' > "$T/o.txt"
grep2 'export folder' 'rc=3' "python: another channel's export folder is refused"
env -u REELS_CHANNEL REELS_ROOT="$TM/root" python -c "import sys; sys.path.insert(0, '$RM/pipeline/lib'); import paths; paths.require_channel()" > "$T/o.txt" 2>&1; echo "rc=$?" >> "$T/o.txt"
grep2 'rc=2' 'alpha' "python: with two channels and none chosen the module exits 2 and lists them"
grep2 'beta' 'rc=2' "python: the list names the second channel too"
# the trace
env REELS_CHANNEL=alpha REELS_ROOT="$TM/root" REELS_PATH_TRACE=1 REELS_PATH_TRACE_FILE="$TM/trace.txt" bash -c 'source "'"$REPO_DIR"'/pipeline/lib/common.sh"; chpath library/a >/dev/null; chpath runs >/dev/null'
env REELS_CHANNEL=alpha REELS_ROOT="$TM/root" REELS_PATH_TRACE=1 REELS_PATH_TRACE_FILE="$TM/trace.txt" python -c "import sys; sys.path.insert(0, '$RM/pipeline/lib'); import paths; paths.ch('styles')"
assert_eq "$(grep -c "/channels/alpha/" "$T/trace.txt")" "3" "REELS_PATH_TRACE logs every path the module resolves (bash and Python)"
fi

test_summary
