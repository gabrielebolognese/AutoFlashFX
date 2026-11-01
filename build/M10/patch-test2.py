"""One-off patch of the M10 build batch for pipeline/tests/test-m10.sh: the repair-loop block becomes its own
sub-section (2r, also run by section 2) and its assertions read the stage's captured output (a stage run directly
prints its terminal lines to stdout, not to stage.log). Kept under build/M10/ as a record; safe to run twice."""
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


patch('''
  # ---- the builder's repair loop: a component that throws at mount makes the check fail; the (fake) builder cannot fix
  # it, so the stage asks it config visual.build_fix_rounds times and then fails as a code error
  fake_claude_reset
  RD="$(seed_run)"''',
      '''  sandbox_cleanup
  fake_claude_off
fi

# ------------------------------------------------------------------------------------------------ 2r. the builder's repair loop
if want 2 || want 2r; then
  section "2r. the builder's repair loop: a planted broken component, the (fake) builder asked twice, then a code error"
  # a component that throws at mount makes the check fail; the (fake) builder cannot fix it, so the stage asks it
  # config visual.build_fix_rounds times and then fails as a code error
  sandbox_init --with-visual
  fake_claude_on
  mkdir -p "$SANDBOX/fixtures"; cp "$FIXTURES/fake/m10/"*.json "$SANDBOX/fixtures/"
  export FAKE_CLAUDE_FIXTURES="$SANDBOX_M/fixtures"
  RD="$(seed_run)"''',
      "section 2r")

patch('''  assert_grep "S10: hyperframes check found [0-9]+ errors \\(runtime: console_error: .*planted by the test" "$RD/10-build/stage.log" "repair loop: the check named the planted error"
  assert_grep "asking the builder model to repair the project \\(round 1/2\\)" "$RD/10-build/stage.log" "repair loop: the builder was asked a first time (round 1/2)"
  assert_grep "asking the builder model to repair the project \\(round 2/2\\)" "$RD/10-build/stage.log" "repair loop: the builder was asked a second time (round 2/2)"
  assert_grep "hyperframes check still reports errors after 2 builder repairs" "$RD/10-build/stage.log" "repair loop: the stage's last line names the cap"''',
      '''  # a stage run directly prints its terminal lines to stdout (the runner would route them through fd 3): they are in the captured output
  assert_grep "S10: hyperframes check found [0-9]+ errors \\(runtime: console_error: .*planted by the test" "$SANDBOX/10-repair.out" "repair loop: the check named the planted error"
  assert_grep "asking the builder model to repair the project \\(round 1/2\\)" "$SANDBOX/10-repair.out" "repair loop: the builder was asked a first time (round 1/2)"
  assert_grep "asking the builder model to repair the project \\(round 2/2\\)" "$SANDBOX/10-repair.out" "repair loop: the builder was asked a second time (round 2/2)"
  assert_grep "hyperframes check still reports errors after 2 builder repairs" "$SANDBOX/10-repair.out" "repair loop: the stage's last line names the cap"''',
      "repair asserts")

patch('''#   M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh    only those sections (no model; about 10 minutes)''',
      '''#   M10_SECTIONS="1 2" bash pipeline/tests/test-m10.sh    only those sections (no model; about 15 minutes); "2r" is the repair loop alone''',
      "header sections")

open(P, "w", encoding="utf-8", newline="\n").write(s)
print("done")
