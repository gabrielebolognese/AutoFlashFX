"""One-off patch of the M10 build batch for pipeline/tests/test-m10.sh: the kicker-mark grep, the builder repair-loop
check with a planted broken component, and the freeze step that keeps the hand-made fake answers and saves the drafts.
Kept under build/M10/ as a record; safe to run twice."""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
P = os.path.join(REPO, "pipeline", "tests", "test-m10.sh")
s = open(P, encoding="utf-8").read()


def patch(old, new, label):
    global s
    if new in s:
        print(label + ": already patched")
        return
    if old not in s:
        print(label + ": old text not found", file=sys.stderr)
        sys.exit(1)
    s = s.replace(old, new)
    print(label + ": patched")


patch('''      assert_grep "^s1-headline-1 ok brand/mark/mark-gradient.png\\|^s1-headline-1 ok mark/mark-gradient.png" /tmp/m10-logos.txt "branding (flashfx): the hook's kicker mark is the FlashFX bolt image"''',
      '''      assert_grep "^s1-headline-1 ok mark/mark-gradient.png" /tmp/m10-logos.txt "branding (flashfx): the hook's kicker mark is the FlashFX bolt image"''',
      "kicker grep")

patch('''      probe_draft "$RD/10-build/draft.mp4" "$VOICE_MS" >/tmp/m10-probe2.txt
      assert_grep "^size ok" /tmp/m10-probe2.txt "branding (flashfx): the draft rendered at 540x960"
    fi
  done
  sandbox_cleanup
  fake_claude_off
fi''',
      '''      probe_draft "$RD/10-build/draft.mp4" "$VOICE_MS" >/tmp/m10-probe2.txt
      assert_grep "^size ok" /tmp/m10-probe2.txt "branding (flashfx): the draft rendered at 540x960"
    fi
  done

  # ---- the builder's repair loop: a component that throws at mount makes the check fail; the (fake) builder cannot fix
  # it, so the stage asks it config visual.build_fix_rounds times and then fails as a code error
  fake_claude_reset
  RD="$(seed_run)"
  run_stage 09a-animations "$RD" "$SANDBOX/9a-repair.out" && run_stage 09b-text "$RD" "$SANDBOX/9b-repair.out" && run_stage 09c-transitions "$RD" "$SANDBOX/9c-repair.out"; rc=$?
  assert_rc 0 $rc "repair loop: the three plan passes run"
  python - "$SANDBOX/motion-lib/compositions/dark-chip.html" <<'EOF2'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
marker = "(function () {\\n      var v = PC.vars("
planted = "(function () {\\n      throw new Error(\\"planted by the test: a broken component\\");\\n      var v = PC.vars("
s = s.replace(marker, planted, 1)
open(p, "w", encoding="utf-8", newline="\\n").write(s)
print("planted" if "planted by the test" in s else "NOT planted")
EOF2
  n_before="$(fake_calls)"
  run_stage 10-build "$RD" "$SANDBOX/10-repair.out"; rc=$?
  assert_rc 1 $rc "repair loop: the build stage fails as a code error when the check still fails after the repairs"
  assert_grep "S10: hyperframes check found [0-9]+ errors \\(runtime: console_error: .*planted by the test" "$RD/10-build/stage.log" "repair loop: the check named the planted error"
  assert_grep "asking the builder model to repair the project \\(round 1/2\\)" "$RD/10-build/stage.log" "repair loop: the builder was asked a first time (round 1/2)"
  assert_grep "asking the builder model to repair the project \\(round 2/2\\)" "$RD/10-build/stage.log" "repair loop: the builder was asked a second time (round 2/2)"
  assert_grep "hyperframes check still reports errors after 2 builder repairs" "$RD/10-build/stage.log" "repair loop: the stage's last line names the cap"
  assert_eq "$(( $(fake_calls) - n_before ))" "2" "repair loop: exactly two builder calls (config visual.build_fix_rounds)"
  assert_file "$RD/10-build/prompt-repair-r1.md" "repair loop: the repair prompt was written"
  assert_grep "planted by the test" "$RD/10-build/prompt-repair-r1.md" "repair loop: the repair prompt quotes the check's errors"
  assert_grep "^# Role: builder" "$RD/10-build/prompt-repair-r1.md" "repair loop: the prompt is the builder's"
  assert_eq "$(python "$STATE_PY" get "$RD" rounds.build 0)" "2" "repair loop: state.json counts the two build rounds"
  assert_no_file "$RD/10-build/draft.mp4" "repair loop: no draft was rendered from a failing project"
  sandbox_cleanup
  fake_claude_off
fi''',
      "repair loop")

patch('''  if [ "$FAIL_N" -eq 0 ] && [ -n "${M10_FREEZE:-}" ]; then
    for st in 09a-animations 09b-text 09c-transitions; do
      mkdir -p "$FROZEN/$st"; cp "$RD/$st/plan.json" "$FROZEN/$st/plan.json"
      last="$(ls "$RD/$st"/calls/*.out.json | tail -n 1)"; cp "$last" "$FIXTURES/fake/m10/$st.json"
    done
    cp "$RD/09c-transitions/merged.json" "$FROZEN/09c-transitions/merged.json"
    mkdir -p "$FROZEN/10-build/project" "$FROZEN/10-build/hook2"
    for f in events.json plan.json build.json check.json; do cp "$RD/10-build/$f" "$FROZEN/10-build/$f"; done
    cp "$RD/10-build/project/index.html" "$RD/10-build/project/instances.json" "$FROZEN/10-build/project/"
    cp "$RD/10-build/hook2/index.html" "$RD/10-build/hook2/plan.json" "$FROZEN/10-build/hook2/"
    cp "$RD/10-build/contact-sheet.png" "$FROZEN/10-build/contact-sheet.png"
    pass "frozen: the real plans, events.json, the project's index.html and instances.json copied to pipeline/tests/fixtures/runs/test-idea/; the director's answers to pipeline/tests/fixtures/fake/m10/ (M10_FREEZE)"
  fi''',
      '''  if [ "$FAIL_N" -eq 0 ] && [ -n "${M10_FREEZE:-}" ]; then
    # the real outputs become the frozen inputs of M11; the fake director keeps its hand-made answers (the golden design)
    for st in 09a-animations 09b-text 09c-transitions; do
      mkdir -p "$FROZEN/$st"; cp "$RD/$st/plan.json" "$FROZEN/$st/plan.json"
      last="$(ls "$RD/$st"/calls/*.out.json | tail -n 1)"; cp "$last" "$FROZEN/$st/answer.json"
    done
    cp "$RD/09c-transitions/merged.json" "$FROZEN/09c-transitions/merged.json"
    mkdir -p "$FROZEN/10-build/project" "$FROZEN/10-build/hook2"
    for f in events.json plan.json build.json check.json draft.mp4 hook2.mp4 contact-sheet.png; do cp "$RD/10-build/$f" "$FROZEN/10-build/$f"; done
    cp "$RD/10-build/project/index.html" "$RD/10-build/project/instances.json" "$FROZEN/10-build/project/"
    cp "$RD/10-build/hook2/index.html" "$RD/10-build/hook2/plan.json" "$FROZEN/10-build/hook2/"
    pass "frozen: the real plans (with the director's answers), merged.json, events.json, plan.json, build.json, check.json, the contact sheet, the project's index.html and instances.json, the hook 2 files and the two drafts (ignored by git) copied to pipeline/tests/fixtures/runs/test-idea/ (M10_FREEZE)"
  fi''',
      "freeze")

patch('''#   M10_FREEZE=1 bash pipeline/tests/test-m10.sh          section 3 also copies the real plans, events.json and project files into
#                                                         pipeline/tests/fixtures/runs/test-idea/ and the director's answers into
#                                                         pipeline/tests/fixtures/fake/m10/ (the fake's answers from then on)''',
      '''#   M10_FREEZE=1 bash pipeline/tests/test-m10.sh          section 3 also copies the real plans (with the director's answers), events.json,
#                                                         the project files and the drafts into pipeline/tests/fixtures/runs/test-idea/
#                                                         (the inputs of M11; the fake director keeps its hand-made answers)''',
      "header freeze")

patch('''#      brand.json with a use_on matching its surface; in the built flashfx project every logo is an image with its aspect
#      ratio locked (measured in the harness)''',
      '''#      brand.json with a use_on matching its surface; in the built flashfx project every logo is an image with its aspect
#      ratio locked (measured in the harness). Then the builder's repair loop with a planted broken component: the check
#      fails, the (fake) builder is asked visual.build_fix_rounds times, the stage fails as a code error''',
      "header repair")

open(P, "w", encoding="utf-8", newline="\n").write(s)
print("done")
