#!/usr/bin/env python
"""M12: the earlier tests' assertions that the solution field in history lines, the gate's H and the keyword rule
touch (test-m2, test-m3, test-m4). Kept as a record of the patch; run once from the repo root."""
from __future__ import annotations

import sys


def patch(path: str, pairs: list[tuple[str, str]]) -> None:
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        n = s.count(old)
        if n < 1:
            sys.exit(f"{path}: not found: {old!r}")
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print(path, "patched", len(pairs))


# test-m2: the history line gained the solution field (the dummy S2 writes an external solution, M12) and the
# captions file gained the SOLUTION section
patch("pipeline/tests/test-m2.sh", [
    (r'\| $IDEA_A \| exported 1$" "$SANDBOX/logs/history.txt" "history: date | idea | exported 1"',
     r'\| $IDEA_A \| external \| exported 1$" "$SANDBOX/logs/history.txt" "history: date | idea | solution | exported 1"'),
    (r'\| $IDEA_B \| exported 2$" "$SANDBOX/logs/history.txt"', r'\| $IDEA_B \| external \| exported 2$" "$SANDBOX/logs/history.txt"'),
    (r'\| $IDEA_A \| dropped: facts do not hold \(dummy 03-gate\)$"', r'\| $IDEA_A \| external \| dropped: facts do not hold \(dummy 03-gate\)$"'),
    (r'\| $IDEA_B \| blocked: environment problem: fake reviewer: exit 1"', r'\| $IDEA_B \| external \| blocked: environment problem: fake reviewer: exit 1"'),
    (r'\| $IDEA_C \| exported 1$" "$SANDBOX/logs/history.txt" "history: exported line"', r'\| $IDEA_C \| external \| exported 1$" "$SANDBOX/logs/history.txt" "history: exported line"'),
    ("grep -E '^(CAPTION|HASHTAGS|COMMENT KEYWORD|HOOKS|NEEDS REVIEW|FACTS AND SOURCES|RUN)$' | paste -sd,)\"",
     "grep -E '^(CAPTION|HASHTAGS|COMMENT KEYWORD|SOLUTION|HOOKS|NEEDS REVIEW|FACTS AND SOURCES|RUN)$' | paste -sd,)\""),
    ('  "CAPTION,HASHTAGS,COMMENT KEYWORD,HOOKS,NEEDS REVIEW,FACTS AND SOURCES,RUN" "captions: the sections of spec section 8, in order"',
     '  "CAPTION,HASHTAGS,COMMENT KEYWORD,SOLUTION,HOOKS,NEEDS REVIEW,FACTS AND SOURCES,RUN" "captions: the sections of spec section 8, in order"'),
])

# test-m3: the blocked line carries the solution field (the dummy S2 ran before the block at S10)
patch("pipeline/tests/test-m3.sh", [
    (r'assert_grep "\| $IDEA_A \| blocked: environment problem: " "$SANDBOX/logs/history.txt" "history: the blocked line"',
     r'assert_grep "\| $IDEA_A \| (-|external) \| blocked: environment problem: " "$SANDBOX/logs/history.txt" "history: the blocked line (with the solution field, M12)"'),
])

# test-m4: the gate's score text gained H (M12), the history line the solution field, and the fake expansion's
# keyword follows its external solution (LINK; a method keeps the model's keyword)
patch("pipeline/tests/test-m4.sh", [
    (r'assert_grep "^Comment keyword: SKILL\. Deliverable \(NEW, to create\): " "$RD/02-expansion/expansion.md" "expansion.md: a keyword not in deliverables.txt is NEW"',
     r'assert_grep "^Comment keyword: LINK\. Deliverable \(existing\): the link to .*\(https://github.com/anthropics/skills\)$" "$RD/02-expansion/expansion.md" "expansion.md: an external solution takes the keyword LINK with its link (M12)"' "\n"
     r'assert_grep "^Solution decision: external \(the frontend-design skill \(anthropics/skills\), https://github.com/anthropics/skills\): " "$RD/02-expansion/expansion.md" "expansion.md: the solution decision line (M12)"' "\n"
     r'assert_eq "$(json_get "$RD/02-expansion/solution.json" type)/$(json_get "$RD/02-expansion/solution.json" keyword)" "external/LINK" "solution.json: the type and the keyword (M12)"'),
    ('good = dict(base); good["keyword"] = "guide"; good["deliverable_status"] = "new"',
     'good = dict(base); good["keyword"] = "guide"; good["deliverable_status"] = "new"\n'
     'good["solution_decision"] = {"type": "method", "name": "copy the skill folder by hand", "url": "", "reason": "fixture: a method keeps the keyword the model chose (M12)"}'),
    ('"scores_text": "P3 S1 C3 F ok", "failing_text": "S1"', '"scores_text": "P3 S1 C3 F ok H ok", "failing_text": "S1"'),
    ('"reason": "still failing after 2 angle rounds (P3 S1 C3 F ok): ', '"reason": "still failing after 2 angle rounds (P3 S1 C3 F ok H ok): '),
    ('"reason": "facts don.t hold (P2 S2 C2 F fail): ', '"reason": "facts don.t hold (P2 S2 C2 F fail H ok): '),
    ('"scores_text": "P3 S3 C3 F fail", "failing_text": "F wording"', '"scores_text": "P3 S3 C3 F fail H ok", "failing_text": "F wording"'),
    ('"reason": "still failing after 2 angle rounds (P3 S3 C3 F fail): Fixture gate: ', '"reason": "still failing after 2 angle rounds (P3 S3 C3 F fail H ok): Fixture gate: '),
    ('"decision": "drop", "scores_text": "P3 S3 C3 F fail", .*core claim is false.*"F_kind": "core"', '"decision": "drop", "scores_text": "P3 S3 C3 F fail H ok", .*core claim is false.*"F_kind": "core"'),
    ('"decision": "drop", "scores_text": "P3 S3 C3 F fail", .*core claim is unverified.*"F_kind": "core"', '"decision": "drop", "scores_text": "P3 S3 C3 F fail H ok", .*core claim is unverified.*"F_kind": "core"'),
    ('"reason": "facts don.t hold (P3 S3 C3 F fail): ', '"reason": "facts don.t hold (P3 S3 C3 F fail H ok): '),
    ('"scores_text": "P3 S1 C3 F fail", "failing_text": "S1 F wording"', '"scores_text": "P3 S1 C3 F fail H ok", "failing_text": "S1 F wording"'),
    ('"decision": "drop", "scores_text": "P3 S3 C3 F fail", .*core claim is false\' <<<', '"decision": "drop", "scores_text": "P3 S3 C3 F fail H ok", .*core claim is false\' <<<'),
    ('"decision": "drop", "scores_text": "P3 S3 C3 F fail"\' <<<', '"decision": "drop", "scores_text": "P3 S3 C3 F fail H ok"\' <<<'),
    ('"decision": "pass", "scores_text": "P3 S3 C3 F ok"\' <<<', '"decision": "pass", "scores_text": "P3 S3 C3 F ok H ok"\' <<<'),
    ('no angle keeps the core topic (P3 S1 C3 F ok)\' <<<', 'no angle keeps the core topic (P3 S1 C3 F ok H ok)\' <<<'),
    (r'dropped: still failing after 2 angle rounds \(P3 S1 C3 F ok\): Fixture gate: the share driver is too weak to be forwarded on its own\.\. Removed from ideas.txt$" "$OUT" "DROP line with the scores and the reason"',
     r'dropped: still failing after 2 angle rounds \(P3 S1 C3 F ok H ok\): Fixture gate: the share driver is too weak to be forwarded on its own\.\. Removed from ideas.txt$" "$OUT" "DROP line with the scores and the reason"'),
    (r'\| $TEST_IDEA \| dropped: still failing after 2 angle rounds \(P3 S1 C3 F ok\): " "$SANDBOX/logs/history.txt"',
     r'\| $TEST_IDEA \| external \| dropped: still failing after 2 angle rounds \(P3 S1 C3 F ok H ok\): " "$SANDBOX/logs/history.txt"'),
    (r'GATE   passed \(P3 S3 C3 F ok\) after 1 angle round$" "$OUT" "pass on round 2: the GATE line names the angle round"',
     r'GATE   passed \(P3 S3 C3 F ok H ok\) after 1 angle round$" "$OUT" "pass on round 2: the GATE line names the angle round"'),
    (r'''dropped: facts don't hold \(P3 S3 C3 F fail\): the idea's core claim is false \(the ffmpeg 8 documentation lists no such option\)"''',
     r'''dropped: facts don't hold \(P3 S3 C3 F fail H ok\): the idea's core claim is false \(the ffmpeg 8 documentation lists no such option\)"'''),
    (r'''assert_grep "dropped: facts don't hold \(P3 S3 C3 F fail\)" "$SANDBOX/logs/history.txt"''', r'''assert_grep "dropped: facts don't hold \(P3 S3 C3 F fail H ok\)" "$SANDBOX/logs/history.txt"'''),
    (r'dropped: no angle keeps the core topic \(P3 S1 C3 F ok\): .*suggestion written', r'dropped: no angle keeps the core topic \(P3 S1 C3 F ok H ok\): .*suggestion written'),
    (r'GATE   passed \(P3 S3 C3 F ok\) after 1 angle round$" "$OUT" "wording repair: the gate passes on round 2"',
     r'GATE   passed \(P3 S3 C3 F ok H ok\) after 1 angle round$" "$OUT" "wording repair: the gate passes on round 2"'),
    (r'"^Scores: P3 S3 C3 F fail\. Failing: F \(wording\)\.$"', r'"^Scores: P3 S3 C3 F fail H ok\. Failing: F \(wording\)\.$"'),
    (r'"gate round 1: P3 S3 C3 F fail \(wording\), decision angle"', r'"gate round 1: P3 S3 C3 F fail \(wording\) H ok, decision angle"'),
    (r'GATE   passed \(P[2-3] S[2-3] C[2-3] F ok\)" "$OUT" "GATE passed (directly or after an angle round)"',
     r'GATE   passed \(P[2-3] S[2-3] C[2-3] F ok H ok\)" "$OUT" "GATE passed (directly or after an angle round)"'),
    (r'''dropped: facts don't hold \(P[0-3] S[0-3] C[0-3] F fail\): " "$OUT"''', r'''dropped: facts don't hold \(P[0-3] S[0-3] C[0-3] F fail H (ok|fail)\): " "$OUT"'''),
    (r'\| dropped: .*\(P[0-3] S[0-3] C[0-3] F (ok|fail)\): " "$SANDBOX/logs/history.txt"',
     r'\| (-|flashfx|external|method) \| dropped: .*\(P[0-3] S[0-3] C[0-3] F (ok|fail) H (ok|fail)\): " "$SANDBOX/logs/history.txt"'),
])
print("done")
