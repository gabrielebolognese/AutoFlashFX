#!/usr/bin/env bash
# make-test-copy.sh: a throwaway copy of the repo to run the tests in, so a test that writes into the folder (the
# frame-match reports, build/M<n>/ scratch files) never touches the real one (M17).
#
#   bash pipeline/tests/make-test-copy.sh <dest-dir>
#
# Copies everything except .git, node_modules (a junction to the real one), build/ (only its tracked files, the tests read
# a few frozen ones) and the Python caches; then runs git init and one commit there, so the tests that need a git repo
# (test-no-emdash, the fixer's commits) work. The copy has its own history and cannot reach the real repo.
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${1:-}"
if [ -z "$DEST" ]; then echo "usage: make-test-copy.sh <dest-dir>" >&2; exit 2; fi
mkdir -p "$DEST" || exit 1
DEST="$(cd "$DEST" && pwd)"
if [ "$DEST" = "$SRC" ]; then echo "make-test-copy: the destination is the repo itself" >&2; exit 2; fi
if [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then echo "make-test-copy: $DEST is not empty" >&2; exit 2; fi

cd "$SRC" || exit 1
tar -c --exclude=./.git --exclude=./node_modules --exclude=./build --exclude=__pycache__ --exclude=./.harness . | tar -x -C "$DEST" || exit 1
mkdir -p "$DEST/build"
git ls-files -z build | tar --null -c -T - | tar -x -C "$DEST" || exit 1

# node_modules: a directory junction to the real one (Windows); a symlink elsewhere
if [ -d "$SRC/node_modules" ]; then
  if command -v cygpath >/dev/null 2>&1; then
    cmd //c "mklink /J $(cygpath -w "$DEST/node_modules") $(cygpath -w "$SRC/node_modules")" >/dev/null 2>&1 || { echo "make-test-copy: the node_modules junction failed" >&2; exit 1; }
  else
    ln -s "$SRC/node_modules" "$DEST/node_modules" || exit 1
  fi
fi

cd "$DEST" || exit 1
git init -q . || exit 1
git config user.email "tests@example.invalid"
git config user.name "test copy"
git config core.autocrlf false
mkdir -p .git/info && echo node_modules >> .git/info/exclude   # a junction is not a directory to the "node_modules/" rule
git add -A >/dev/null 2>&1
git commit -q -m "test copy" >/dev/null 2>&1
echo "$DEST"
