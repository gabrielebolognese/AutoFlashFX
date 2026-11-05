"""Round 22: test-m13's voice-profile block starts from the profile drafts as they were when the test was written
(pipeline/tests/fixtures/profile/voice.md and account.md, the files before the user's fill of 2026-11-07, taken from
git 589c4f4^), not from the user's filled profile: seven of its checks edited placeholders that no longer exist and
expected sections the user has since written themselves. Same cause as round 21 (decision 305)."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/tests/test-m13.sh", [
    ('''# build-voice-profile --force on a copy of the profile keeps the hand-written parts
sandbox_init
P="$SANDBOX/library/profile"
python - "$P" <<'EOF\'''',
     '''# build-voice-profile --force on a copy of the profile keeps the hand-written parts. The copy is the drafts as they
# were when this block was written (pipeline/tests/fixtures/profile/, placeholders and all): the user's filled profile
# stays out of the tests (DECISIONS.md 305)
sandbox_init
P="$SANDBOX/library/profile"
cp "$REPO_DIR/pipeline/tests/fixtures/profile/voice.md" "$P/voice.md"
cp "$REPO_DIR/pipeline/tests/fixtures/profile/account.md" "$P/account.md"
python - "$P" <<'EOF\''''),
])

patch("DECISIONS.md", [
    ('''    sandbox (the shape build-voice-profile writes before the user fills it). The rule: a test may read library/ files
    it treats as opaque inputs (deliverables.txt, the sound pack), never assert on the user's curated text.''',
     '''    sandbox (the shape build-voice-profile writes before the user fills it), and test-m13's voice-profile block
    (seven checks that edit the drafts' placeholders and rebuild them with --force) starts from the drafts as they
    were when it was written, kept as pipeline/tests/fixtures/profile/voice.md and account.md. The rule: a test may
    read library/ files it treats as opaque inputs (deliverables.txt, the sound pack), never assert on the user's
    curated text.'''),
])

patch("build/M14/report.md", [
    ('''  and account.md on the morning of 2026-11-07, so three of its checks failed in the rerun with solution.py and gate.py
  unchanged. The test now writes its own placeholder drafts for them (DECISIONS.md 305).''',
     '''  and account.md on the morning of 2026-11-07, so three of its checks failed in the rerun with solution.py and gate.py
  unchanged, and seven checks of test-m13's voice-profile block (which edit the drafts' placeholders and rebuild them)
  failed the same way. test-m12 now writes its own placeholder drafts; test-m13 starts from the drafts as they were
  when it was written, kept as pipeline/tests/fixtures/profile/ (DECISIONS.md 305).'''),
    ('''  M11 (mechanical.py: the 3D scale, the transients, the short-lived elements; common.py's sample times), M12 (its
  test only: three checks that read the user's profile now use placeholder drafts). Their fake-only tests were run
  again (below).''',
     '''  M11 (mechanical.py: the 3D scale, the transients, the short-lived elements; common.py's sample times), M12 and M13
  (their tests only: the checks that read the user's profile now use drafts of their own). Their fake-only tests were
  run again (below).'''),
])
print("round 22 done")
