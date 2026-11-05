"""Round 21: test-m12 section 1 read the user's profile. Two of its assertions assumed the state of library/profile at
M12's time (a voice.md draft with no usable proof line, an account.md without a Content strategy section); the user
filled both on 2026-11-07 (commits 589c4f4 and 50218ae, before M14), so the M12 fake rerun failed on them although
solution.py is unchanged. The test now writes its own placeholder drafts for those two checks; nothing in the tests
reads the curated library/ content any more (the voice profile stays the user's)."""


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert old in s, (path, old[:80])
        assert s.count(old) == 1, (path, "not unique", old[:80])
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched", path)


patch("pipeline/tests/test-m12.sh", [
    ('''assert_eq "$(python pipeline/lib/solution.py proof --voice library/profile/voice.md | grep -c .)" "0" "solution.py proof: the repo's draft voice.md has no usable proof line"''',
     '''# the drafts build-voice-profile writes before the user fills them (placeholders only, no Content strategy section);
# the test never reads library/profile itself: the user's filled profile is theirs (DECISIONS.md 305)
printf '# voice\\n\\n## Proof I can use\\n\\n- [FILL IN: a real number]\\n- [FILL IN: a client result]\\n\\n## The ask\\n\\n- [FILL IN]\\n' > "$W/voice-draft.md"
printf '# account\\n\\n## Who follows\\n\\n- [FILL IN]\\n\\n## Deliverables\\n\\n- [FILL IN]\\n' > "$W/account-draft.md"
assert_eq "$(python pipeline/lib/solution.py proof --voice "$W/voice-draft.md" | grep -c .)" "0" "solution.py proof: a placeholder draft voice.md has no usable proof line"'''),
    ('''prompt_text="$(python pipeline/lib/solution.py prompt --run-dir "$RD" --voice library/profile/voice.md --account library/profile/account.md --history "$SANDBOX_M/logs/history.txt" --deliverables library/profile/deliverables.txt)"''',
     '''prompt_text="$(python pipeline/lib/solution.py prompt --run-dir "$RD" --voice "$W/voice-draft.md" --account "$W/account-draft.md" --history "$SANDBOX_M/logs/history.txt" --deliverables library/profile/deliverables.txt)"'''),
])

DECISION = '''305. **The tests never read the curated profile.** test-m12 section 1 checked `solution.py proof` and `prompt` against
    library/profile/voice.md and account.md as they were at M12's time (a draft with no usable proof line, no Content
    strategy section); the user filled both on the morning of 2026-11-07 (commits 589c4f4 and 50218ae), so the M12
    fake rerun of M14 failed those two checks with solution.py unchanged. The test now writes its own placeholder
    drafts for them (the shape build-voice-profile writes before the user fills it). The rule: a test may read
    library/ files it treats as opaque inputs (deliverables.txt, the sound pack), never assert on the user's curated
    text.
'''

patch("DECISIONS.md", [
    ('''    hold levels and the room per scene with the real lives.
''', '''    hold levels and the room per scene with the real lives.
''' + DECISION),
])

patch("build/M14/report.md", [
    ('''  304; test-m14 section 3 checks the DM card at the CTA's y and at y 700).''',
     '''  304; test-m14 section 3 checks the DM card at the CTA's y and at y 700).
- test-m12 section 1 asserted on the user's profile as it was at M12's time (no usable proof line, no Content
  strategy section); the user filled library/profile/voice.md and account.md on the morning of 2026-11-07, so two of
  its checks failed in the rerun with solution.py unchanged. The test now writes its own placeholder drafts for them
  (DECISIONS.md 305).'''),
    ('''  M11 (mechanical.py: the 3D scale, the transients, and common.py's landed sample time). Their fake-only tests were
  run again (below).''',
     '''  M11 (mechanical.py: the 3D scale, the transients, the short-lived elements; common.py's sample times), M12 (its
  test only: two checks that read the user's profile now use placeholder drafts). Their fake-only tests were run again
  (below).'''),
])
print("round 21 done")
